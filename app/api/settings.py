from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import config, crypto
from ..db import get_db
from ..models import Property, PushSubscription
from ..services import notifications

router = APIRouter(prefix="/api/settings", tags=["settings"])

SMTP_SECURITIES = ("starttls", "ssl", "none")


def get_property(db: Session) -> Property:
    prop = db.query(Property).first()
    if prop is None:
        prop = Property(name="Mein Grundstück")
        db.add(prop)
        db.commit()
    return prop


def settings_public(db: Session) -> dict:
    prop = get_property(db)
    smtp = notifications.get_smtp_config(db)
    password_set = bool(notifications.get_setting(db, "smtp_password"))
    vapid_pub = notifications.get_setting(db, "vapid_public")
    return {
        "property": {"name": prop.name, "address": prop.address},
        "smtp": {
            "host": smtp["host"],
            "port": smtp["port"],
            "security": smtp["security"],
            "user": smtp["user"],
            "from": smtp["from"],
            "password_set": password_set,
        },
        "notify_email": smtp["to"],
        "channels": {
            "email": notifications.channel_enabled(db, "email"),
            "push": notifications.channel_enabled(db, "push"),
        },
        "push_enabled_env": config.PUSH_ENABLED,
        "vapid_public_key": vapid_pub if config.PUSH_ENABLED else None,
        "app_url": config.APP_URL,
        "backup_dir": str(config.BACKUP_DIR),
    }


class SettingsPayload(BaseModel):
    property_name: str | None = None
    property_address: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_security: str | None = None
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_clear_password: bool = False
    smtp_from: str | None = None
    notify_email: str | None = None
    notify_days_ahead: int | None = None
    email_enabled: bool | None = None
    push_enabled: bool | None = None


@router.get("")
def get_settings(db: Session = Depends(get_db)):
    return settings_public(db)


@router.put("")
def update_settings(payload: SettingsPayload, db: Session = Depends(get_db)):
    prop = get_property(db)
    if payload.property_name is not None and payload.property_name.strip():
        prop.name = payload.property_name.strip()
    if payload.property_address is not None:
        prop.address = payload.property_address.strip() or None

    if payload.smtp_security is not None and payload.smtp_security not in SMTP_SECURITIES:
        raise HTTPException(
            status_code=422,
            detail=f"smtp_security muss einer dieser Werte sein: {', '.join(SMTP_SECURITIES)}",
        )
    if payload.smtp_port is not None and not 1 <= payload.smtp_port <= 65535:
        raise HTTPException(status_code=422, detail="smtp_port muss zwischen 1 und 65535 liegen.")
    if payload.notify_days_ahead is not None and not 0 <= payload.notify_days_ahead <= 60:
        raise HTTPException(
            status_code=422, detail="notify_days_ahead muss zwischen 0 und 60 liegen."
        )

    str_fields = {
        "smtp_host": payload.smtp_host,
        "smtp_user": payload.smtp_user,
        "smtp_from": payload.smtp_from,
        "notify_email": payload.notify_email,
    }
    for key, value in str_fields.items():
        if value is not None:
            notifications.set_setting(db, key, value.strip())
    if payload.smtp_host is not None and payload.smtp_host.strip() == "":
        notifications.set_setting(db, "smtp_host", "")
    if payload.smtp_security is not None:
        notifications.set_setting(db, "smtp_security", payload.smtp_security)
    if payload.smtp_port is not None:
        notifications.set_setting(db, "smtp_port", str(payload.smtp_port))
    if payload.notify_days_ahead is not None:
        notifications.set_setting(db, "notify_days_ahead", str(payload.notify_days_ahead))
    if payload.smtp_clear_password:
        notifications.set_setting(db, "smtp_password", "")
    elif payload.smtp_password:
        notifications.set_setting(db, "smtp_password", crypto.encrypt(payload.smtp_password))
    if payload.email_enabled is not None:
        notifications.set_channel(db, "email", payload.email_enabled)
    if payload.push_enabled is not None:
        notifications.set_channel(db, "push", payload.push_enabled)
    db.commit()
    return settings_public(db)


def crypto_encrypt(value: str) -> str:
    from .. import crypto

    return crypto.encrypt(value)


class TestEmailPayload(BaseModel):
    recipient: str | None = None


@router.post("/test-email")
def test_email(payload: TestEmailPayload | None = None, db: Session = Depends(get_db)):
    cfg = notifications.get_smtp_config(db)
    if payload and payload.recipient:
        cfg["to"] = payload.recipient
    if not notifications.smtp_configured(cfg):
        raise HTTPException(
            status_code=400,
            detail="E-Mail ist nicht vollständig konfiguriert (Host und Empfänger erforderlich).",
        )
    try:
        notifications.send_email(
            cfg,
            "Hausmeister: Test-Nachricht",
            f"Diese Test-Nachricht wurde erfolgreich über {cfg['host']} versendet.",
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Versand fehlgeschlagen: {exc}")
    return {"ok": True, "detail": f"Test-E-Mail an {cfg['to']} versendet."}


class PushSubscribePayload(BaseModel):
    endpoint: str
    keys: dict
    user_agent: str | None = None


@router.get("/push/vapid-key")
def push_vapid_key(db: Session = Depends(get_db)):
    if not config.PUSH_ENABLED:
        raise HTTPException(status_code=404, detail="Web Push ist deaktiviert.")
    keys = notifications.get_vapid_keys(db)
    if not keys:
        raise HTTPException(status_code=500, detail="VAPID-Schlüssel konnten nicht erzeugt werden.")
    return {"public_key": keys[1]}


@router.post("/push/subscribe")
def push_subscribe(payload: PushSubscribePayload, db: Session = Depends(get_db)):
    if not config.PUSH_ENABLED:
        raise HTTPException(status_code=404, detail="Web Push ist deaktiviert.")
    if not payload.endpoint.startswith("https://"):
        raise HTTPException(status_code=422, detail="Push-Endpoint muss HTTPS verwenden.")
    if not payload.keys.get("p256dh") or not payload.keys.get("auth"):
        raise HTTPException(status_code=422, detail="Push-Keys unvollständig (p256dh, auth).")
    sub = (
        db.query(PushSubscription)
        .filter(PushSubscription.endpoint == payload.endpoint)
        .one_or_none()
    )
    if sub is None:
        sub = PushSubscription(endpoint=payload.endpoint[:500])
        db.add(sub)
    sub.p256dh = payload.keys["p256dh"]
    sub.auth = payload.keys["auth"]
    sub.user_agent = (payload.user_agent or "")[:300] or None
    db.commit()
    return {"ok": True}


class PushUnsubscribePayload(BaseModel):
    endpoint: str


@router.post("/push/unsubscribe")
def push_unsubscribe(payload: PushUnsubscribePayload, db: Session = Depends(get_db)):
    sub = (
        db.query(PushSubscription)
        .filter(PushSubscription.endpoint == payload.endpoint)
        .one_or_none()
    )
    if sub:
        db.delete(sub)
        db.commit()
    return {"ok": True}


@router.post("/push/test")
def push_test(db: Session = Depends(get_db)):
    if not config.PUSH_ENABLED:
        raise HTTPException(status_code=404, detail="Web Push ist deaktiviert.")
    sent = notifications.send_web_push(
        db,
        {"title": "Hausmeister", "body": "Test-Push erfolgreich.", "url": "/"},
    )
    return {"ok": True, "sent": sent}
