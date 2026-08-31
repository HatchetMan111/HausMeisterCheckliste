from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from . import config


class Base(DeclarativeBase):
    pass


engine = None
SessionLocal = None


def _create_engine():
    eng = create_engine(
        f"sqlite:///{config.DB_PATH}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(eng, "connect")
    def _set_pragma(dbapi_conn, _record):  # pragma: no cover
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return eng


def init() -> None:
    global engine, SessionLocal
    config.ensure_dirs()
    engine = _create_engine()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def reinitialize() -> None:
    global engine, SessionLocal
    if engine is not None:
        engine.dispose()
    init()


def get_db():
    if SessionLocal is None:
        init()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def utcnow() -> datetime:
    return datetime.utcnow()


AREAS: list[tuple[str, str]] = [
    ("haus", "Haus"),
    ("hof", "Hof"),
    ("technik", "Technik"),
    ("garten", "Garten"),
    ("sicherheit", "Sicherheit"),
]


def seed_base_data(db) -> None:
    from .models import Area, Property

    if db.query(Property).count() == 0:
        db.add(Property(name="Mein Grundstück"))
    existing = {a.slug for a in db.query(Area).all()}
    for sort_order, (slug, name) in enumerate(AREAS):
        if slug not in existing:
            db.add(Area(slug=slug, name=name, sort_order=sort_order))
    db.commit()
