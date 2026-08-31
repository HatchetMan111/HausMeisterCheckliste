from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

_TEST_DIR = tempfile.mkdtemp(prefix="hausmeister-test-")
_DATA_DIR = Path(_TEST_DIR) / "data"
os.environ["HAUSMEISTER_DATA_DIR"] = str(_DATA_DIR)
os.environ["HAUSMEISTER_DB_PATH"] = str(_DATA_DIR / "test.sqlite3")
os.environ["HAUSMEISTER_BACKUP_DIR"] = str(_DATA_DIR / "backups")
os.environ["HAUSMEISTER_PUSH_ENABLED"] = "0"


@pytest.fixture(scope="session")
def app_env():
    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parent.parent
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "app" / "migrations"))
    command.upgrade(cfg, "head")

    from app.main import app

    return app


@pytest.fixture()
def client(app_env):
    from fastapi.testclient import TestClient

    with TestClient(app_env) as c:
        yield c


@pytest.fixture()
def db(app_env):
    from app.db import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
