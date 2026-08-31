from __future__ import annotations

import base64
import json
import smtplib
from datetime import date
from email.message import EmailMessage

from sqlalchemy.orm import Session

from .. import config, crypto
from ..models import NotificationSetting, PushSubscription, Setting


def get_setting(db: Session, key: str, default: str | None = None) -> str | None:
    row = db.query(Setting).filter(Setting.key == key).one_or_none()
    return row.value if row and row.value is not None else default


def set_setting(db: Session, key: str, value: str | None) -> None:
    row = db.query(Setting).filter(Setting.key == key).one_or_none()
    if row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value
    db.commit()


def channel_enabled(db: Session, channel: str) -> bool:
    row = (
        db.query(NotificationSetting)
        .filter(NotificationSetting.channel == channel)
        .one_or_none()
    )
    return bool(row and row.enabled)


def set_channel(db: Session, channel: str, enabled: bool) -> None:
    row = (
        db.query(NotificationSetting)
        .filter(NotificationSetting.channel == channel)
        .one_or_none()
    )
    if row is None:
        db.add(NotificationSetting(channel=channel, enabled=enabled))
    else:
        row.enabled = enabled
    db.commit()


def get_smtp_config(db: Session) -> dict:
    return {
        "host": get_setting(db, "smtp_host") or "",
        "port": int(get_setting(db, "smtp_port") or "587"),
        "security": get_setting(db, "smtp_security") or "starttls",
        "user": get_setting(db, "smtp_user") or "",
        "password": crypto.decrypt(get_setting(db, "smtp_password") or ""),
        "from": get_setting(db, "smtp_from") or "",
        "to": get_setting(db, "notify_email") or "",
    }


def smtp_configured(cfg: dict) -> bool:
    return bool(cfg["host"] and cfg["to"] and cfg["port"])


def send_email(cfg: dict, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["from"] or cfg["user"]
    msg["To"] = cfg["to"]
    msg.set_content(body)
    if cfg["security"] == "ssl":
        with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=20) as smtp:
            if cfg["user"]:
                smtp.login(cfg["user"], cfg["password"])
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=20) as smtp:
            if cfg["security"] == "starttls":
                smtp.starttls()
            if cfg["user"]:
                smtp.login(cfg["user"], cfg["password"])
            smtp.send_message(msg)


def due_summary_items(db: Session, today: date) -> list[dict]:
    from ..models import Task, TaskInstance
    from . import recurrence

    items: list[dict] = []
    rows = (
        db.query(TaskInstance)
        .join(Task)
        .filter(Task.active.is_(True), TaskInstance.status == "open")
        .all()
    )
    for inst in rows:
        status = recurrence.status_for(inst.task, inst, today)
        if status in ("overdue", "due"):
            items.append(
                {
                    "title": inst.task.title,
                    "status": status,
                    "due_date": inst.due_date,
                }
            )
    return items


def send_daily_summary(db: Session, today: date) -> dict:
    items = due_summary_items(db, today)
    if not items:
        return {"sent": False, "reason": "nichts fällig oder überfällig"}
    if not channel_enabled(db, "email"):
        return {"sent": False, "reason": "E-Mail-Benachrichtigung deaktiviert"}
    cfg = get_smtp_config(db)
    if not smtp_configured(cfg):
        return {"sent": False, "reason": "E-Mail nicht konfiguriert"}
    lines = [
        f"Wartungsübersicht für {today.isoformat()}",
        "",
    ]
    for item in sorted(items, key=lambda x: x["due_date"]):
        label = "überfällig" if item["status"] == "overdue" else "fällig"
        lines.append(f"- {item['title']} ({label}, fällig am {item['due_date'].isoformat()})")
    lines.append("")
    lines.append(f"Öffnen: {config.APP_URL}")
    try:
        send_email(cfg, "Hausmeister: fällige Wartungen", "\n".join(lines))
    except Exception as exc:
        return {"sent": False, "reason": f"Versand fehlgeschlagen: {exc}"}
    return {"sent": True, "count": len(items)}


def get_vapid_keys(db: Session) -> tuple[str, str] | None:
    priv = get_setting(db, "vapid_private")
    pub = get_setting(db, "vapid_public")
    if priv and pub:
        return priv, pub
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            PublicFormat,
        )

        key = ec.generate_private_key(ec.SECP256R1())
        priv_b64 = base64.urlsafe_b64encode(
            key.private_numbers().private_value.to_bytes(32, "big")
        ).rstrip(b"=").decode("ascii")
        pub_b64 = base64.urlsafe_b64encode(
            key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
        ).rstrip(b"=").decode("ascii")
    except Exception:
        return None
    set_setting(db, "vapid_private", priv_b64)
    set_setting(db, "vapid_public", pub_b64)
    return priv_b64, pub_b64


def send_web_push(db: Session, payload: dict) -> int:
    try:
        from pywebpush import webpush
    except Exception:
        return 0
    keys = get_vapid_keys(db)
    if not keys:
        return 0
    claims = {
        "sub": f"mailto:{get_setting(db, 'smtp_from') or 'wartung@hausmeister.local'}"
    }
    sent = 0
    for sub in db.query(PushSubscription).all():
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=json.dumps(payload, ensure_ascii=False),
                vapid_private_key=keys[0],
                vapid_claims=claims,
            )
            sent += 1
        except Exception:
            db.delete(sub)
            db.commit()
    return sent
