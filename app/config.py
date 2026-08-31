from __future__ import annotations

import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
APP_NAME = "Hausmeister"
VERSION = "0.2.1"

DATA_DIR = Path(os.environ.get("HAUSMEISTER_DATA_DIR", BASE_DIR / "data"))
DB_PATH = Path(os.environ.get("HAUSMEISTER_DB_PATH", DATA_DIR / "hausmeister.sqlite3"))
BACKUP_DIR = Path(os.environ.get("HAUSMEISTER_BACKUP_DIR", DATA_DIR / "backups"))
TEMPLATES_DIR = Path(os.environ.get("HAUSMEISTER_TEMPLATES_DIR", BASE_DIR / "data" / "templates"))
SECRET_KEY_FILE = Path(
    os.environ.get("HAUSMEISTER_SECRET_KEY_FILE", DATA_DIR / ".secret_key")
)

PUSH_ENABLED = os.environ.get("HAUSMEISTER_PUSH_ENABLED", "0") == "1"
APP_URL = os.environ.get("HAUSMEISTER_APP_URL", "https://hausmeister.local")

DEFAULT_BACKUP_KEEP = int(os.environ.get("HAUSMEISTER_BACKUP_KEEP", "14"))
INSTANCE_HORIZON_DAYS = int(os.environ.get("HAUSMEISTER_HORIZON_DAYS", "400"))

_secret_key_cache: bytes | None = None


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    SECRET_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)


def get_secret_key() -> bytes:
    global _secret_key_cache
    if _secret_key_cache:
        return _secret_key_cache
    ensure_dirs()
    if SECRET_KEY_FILE.exists():
        raw = SECRET_KEY_FILE.read_text(encoding="utf-8").strip()
        if raw:
            _secret_key_cache = raw.encode("utf-8")
            return _secret_key_cache
    raw = secrets.token_urlsafe(48)
    SECRET_KEY_FILE.write_text(raw + "\n", encoding="utf-8")
    try:
        os.chmod(SECRET_KEY_FILE, 0o600)
    except OSError:
        pass
    _secret_key_cache = raw.encode("utf-8")
    return _secret_key_cache
