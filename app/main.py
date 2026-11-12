from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .api import defects, maintenance, meta, settings as settings_api
from .api import tasks as tasks_api
from .db import get_db, init, seed_base_data  # noqa: F401 (get_db für Router-Defaults)

STATIC_DIR = Path(__file__).resolve().parent / "static"
ROOT_CA_PATH = config.DATA_DIR / "certs" / "root-ca.crt"
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
INDEX_FILE = FRONTEND_DIST / "index.html"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init()
    from .db import SessionLocal

    db = SessionLocal()
    try:
        seed_base_data(db)
    finally:
        db.close()
    yield


app = FastAPI(title=config.APP_NAME, version=config.VERSION, lifespan=lifespan)
app.include_router(tasks_api.router)
app.include_router(maintenance.router)
app.include_router(settings_api.router)
app.include_router(defects.router)
app.include_router(meta.router)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
if (FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


@app.get("/health")
def health():
    return {"status": "ok", "app": config.APP_NAME, "version": config.VERSION}


@app.get("/certs/root-ca.crt")
def root_ca():
    if not ROOT_CA_PATH.exists():
        raise HTTPException(status_code=404, detail="Zertifikat noch nicht verfügbar.")
    return FileResponse(
        ROOT_CA_PATH,
        media_type="application/x-x509-ca-cert",
        headers={"Content-Disposition": "inline; filename=hausmeister-root-ca.crt"},
    )


if FRONTEND_DIST.is_dir():

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        # Unbekannte API-Pfade bleiben JSON-404s, kein Shell-Fallback.
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Nicht gefunden.")
        if full_path:
            candidate = (FRONTEND_DIST / full_path).resolve()
            if candidate.is_file() and str(candidate).startswith(str(FRONTEND_DIST.resolve())):
                return FileResponse(candidate)
        if not INDEX_FILE.exists():
            raise HTTPException(status_code=404, detail="Frontend nicht gebaut.")
        # no-cache: Der Shell-Index referenziert gehashte Assets und muss immer frisch sein.
        return FileResponse(INDEX_FILE, headers={"Cache-Control": "no-cache"})
