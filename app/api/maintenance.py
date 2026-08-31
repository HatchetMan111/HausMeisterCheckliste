from __future__ import annotations

import io
import os
import sqlite3
import zipfile
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db, reinitialize
from ..models import Task, TaskCompletion, TaskInstance
from ..services import recurrence, scheduler

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


def serialize_instance(inst: TaskInstance, status: str) -> dict:
    task = inst.task
    window_end = None
    if task.schedule_type == "annual_window":
        _, window_end_dt = recurrence.window_bounds(task, inst.year)
        window_end = window_end_dt.isoformat()
    return {
        "instance_id": inst.id,
        "task_id": task.id,
        "slug": task.slug,
        "title": task.title,
        "description": task.description,
        "area": task.area.slug if task.area else None,
        "area_name": task.area.name if task.area else None,
        "category": task.category.slug if task.category else None,
        "category_name": task.category.name if task.category else None,
        "priority": task.priority,
        "schedule_type": task.schedule_type,
        "due_date": inst.due_date.isoformat(),
        "window_end": window_end,
        "status": status,
        "estimated_minutes": task.estimated_minutes,
    }


def dashboard_buckets(db: Session, today: date) -> dict:
    buckets: dict[str, list] = {"overdue": [], "today": [], "week": [], "upcoming": []}
    rows = (
        db.query(TaskInstance)
        .join(Task)
        .filter(Task.active.is_(True), TaskInstance.status == "open")
        .all()
    )
    for inst in rows:
        status = recurrence.status_for(inst.task, inst, today)
        if status in ("done", "skipped"):
            continue
        if status == "overdue":
            bucket = "overdue"
        elif status == "due":
            bucket = "today"
        elif inst.due_date <= today + timedelta(days=7):
            bucket = "week"
        elif inst.due_date <= today + timedelta(days=30):
            bucket = "upcoming"
        else:
            continue
        buckets[bucket].append(serialize_instance(inst, status))
    for bucket in buckets.values():
        bucket.sort(key=lambda item: item["due_date"])
    return buckets


class CompletePayload(BaseModel):
    note: str | None = None
    completed_by: str | None = None


def _get_open_instance(db: Session, instance_id: int) -> TaskInstance:
    inst = db.query(TaskInstance).filter(TaskInstance.id == instance_id).one_or_none()
    if inst is None:
        raise HTTPException(status_code=404, detail="Fälligkeit nicht gefunden.")
    return inst


def _schedule_next_interval(db: Session, task: Task, from_date: date) -> None:
    if task.schedule_type != "interval_days":
        return
    interval = max(int(task.interval_days or 1), 1)
    next_due = from_date + timedelta(days=interval)
    exists = (
        db.query(TaskInstance)
        .filter(TaskInstance.task_id == task.id, TaskInstance.due_date == next_due)
        .one_or_none()
    )
    if exists is None:
        db.add(TaskInstance(task_id=task.id, due_date=next_due, year=next_due.year))


@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    return dashboard_buckets(db, date.today())


def dashboard_sections(db: Session, today: date) -> dict:
    """Dashboard-Reihenfolge: dringend -> Monat im Fokus -> Rest."""
    rows = (
        db.query(TaskInstance)
        .join(Task)
        .filter(Task.active.is_(True), TaskInstance.status == "open")
        .all()
    )
    items = []
    for inst in rows:
        st = recurrence.status_for(inst.task, inst, today)
        if st in ("done", "skipped"):
            continue
        item = serialize_instance(inst, st)
        prio = item.get("priority") if item.get("priority") in ("high", "normal", "low") else "normal"
        item["priority"] = prio
        item["priority_rank"] = {"high": 0, "normal": 1, "low": 2}[prio]
        item["due_str"] = inst.due_date.strftime("%d.%m.")
        items.append(item)

    urgent = sorted(
        (i for i in items if i["status"] in ("overdue", "due")),
        key=lambda i: (i["priority_rank"], i["due_date"]),
    )

    month_start = today.replace(day=1)
    month_end = date(today.year, today.month, _last_day_of_month(today.year, today.month))
    in_month = [
        i
        for i in items
        if i["status"] == "upcoming" and month_start <= date.fromisoformat(i["due_date"]) <= month_end
    ]
    in_month.sort(key=lambda i: (i["priority_rank"], i["due_date"]))
    month_focus = [i for i in in_month if i["priority"] in ("high", "normal")]
    month_rest = [i for i in in_month if i["priority"] == "low"]

    month_ids = {i["instance_id"] for i in in_month}
    later = sorted(
        (
            i
            for i in items
            if i["status"] == "upcoming"
            and i["instance_id"] not in month_ids
            and date.fromisoformat(i["due_date"]) <= today + timedelta(days=30)
        ),
        key=lambda i: (i["priority_rank"], i["due_date"]),
    )
    return {"urgent": urgent, "month_focus": month_focus, "month_rest": month_rest, "later": later}


@router.get("/instances")
def list_instances(
    from_date: date | None = None,
    to_date: date | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(TaskInstance).join(Task).filter(Task.active.is_(True))
    today = date.today()
    if from_date:
        query = query.filter(TaskInstance.due_date >= from_date)
    if to_date:
        query = query.filter(TaskInstance.due_date <= to_date)
    instances = query.order_by(TaskInstance.due_date).all()
    out = []
    for inst in instances:
        st = recurrence.status_for(inst.task, inst, today)
        if status and st != status and inst.status != status:
            continue
        out.append(serialize_instance(inst, st))
    return {"instances": out}


@router.post("/instances/{instance_id}/complete")
def complete_instance(instance_id: int, payload: CompletePayload | None = None, db: Session = Depends(get_db)):
    inst = _get_open_instance(db, instance_id)
    if inst.status == "done":
        raise HTTPException(status_code=409, detail="Aufgabe ist bereits erledigt.")
    inst.status = "done"
    db.add(
        TaskCompletion(
            task_id=inst.task_id,
            instance_id=inst.id,
            note=payload.note if payload else None,
            completed_by=payload.completed_by if payload else None,
        )
    )
    _schedule_next_interval(db, inst.task, inst.due_date)
    db.commit()
    return {"ok": True, "instance_id": inst.id, "status": "done"}


@router.post("/instances/{instance_id}/skip")
def skip_instance(instance_id: int, db: Session = Depends(get_db)):
    inst = _get_open_instance(db, instance_id)
    if inst.status == "done":
        raise HTTPException(status_code=409, detail="Aufgabe ist bereits erledigt.")
    inst.status = "skipped"
    _schedule_next_interval(db, inst.task, inst.due_date)
    db.commit()
    return {"ok": True, "instance_id": inst.id, "status": "skipped"}


def _last_day_of_month(year: int, month: int) -> int:
    import calendar

    return calendar.monthrange(year, month)[1]


def _instances_in_month(db: Session, month: int, statuses: tuple[str, ...]) -> list[TaskInstance]:
    if not 1 <= month <= 12:
        raise HTTPException(status_code=422, detail="Monat muss zwischen 1 und 12 liegen.")
    year = date.today().year
    first = date(year, month, 1)
    last = date(year, month, _last_day_of_month(year, month))
    return (
        db.query(TaskInstance)
        .join(Task)
        .filter(
            Task.active.is_(True),
            TaskInstance.status.in_(statuses),
            TaskInstance.due_date >= first,
            TaskInstance.due_date <= last,
        )
        .all()
    )


@router.post("/complete-month/{month}")
def complete_month(month: int, db: Session = Depends(get_db)):
    instances = _instances_in_month(db, month, ("open",))
    for inst in instances:
        inst.status = "done"
        db.add(TaskCompletion(task_id=inst.task_id, instance_id=inst.id))
        _schedule_next_interval(db, inst.task, inst.due_date)
    if instances:
        db.commit()
    return {"ok": True, "completed": len(instances)}


@router.post("/reopen-month/{month}")
def reopen_month(month: int, db: Session = Depends(get_db)):
    instances = _instances_in_month(db, month, ("done", "skipped"))
    reopened = 0
    for inst in instances:
        inst.status = "open"
        db.query(TaskCompletion).filter(TaskCompletion.instance_id == inst.id).delete()
        reopened += 1
    if reopened:
        db.commit()
    return {"ok": True, "reopened": reopened}


@router.get("/history")
def history(limit: int = 100, db: Session = Depends(get_db)):
    rows = (
        db.query(TaskCompletion)
        .order_by(TaskCompletion.completed_at.desc())
        .limit(min(max(limit, 1), 500))
        .all()
    )
    return {
        "completions": [
            {
                "id": c.id,
                "task_id": c.task_id,
                "task_title": c.task.title if c.task else None,
                "completed_at": c.completed_at.isoformat() if c.completed_at else None,
                "completed_by": c.completed_by,
                "note": c.note,
            }
            for c in rows
        ]
    }


@router.post("/ensure-instances")
def ensure_instances(db: Session = Depends(get_db)):
    created = scheduler.ensure_all_instances(db)
    return {"ok": True, "instances_created": created}


def export_backup_zip() -> bytes:
    config.ensure_dirs()
    buf = io.BytesIO()
    tmp = config.DATA_DIR / f".export-{os.getpid()}.sqlite3"
    try:
        src = sqlite3.connect(str(config.DB_PATH))
        dst = sqlite3.connect(str(tmp))
        with dst:
            src.backup(dst)
        dst.close()
        src.close()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(tmp, "hausmeister.sqlite3")
            if config.TEMPLATES_DIR.exists():
                for f in sorted(config.TEMPLATES_DIR.iterdir()):
                    if f.is_file():
                        zf.write(f, f"templates/{f.name}")
            zf.writestr(
                "WIEDERHERSTELLUNG.txt",
                "Hausmeister-Backup\n\n"
                "Inhalt:\n"
                "  hausmeister.sqlite3  Datenbank\n"
                "  templates/           Aufgabenvorlagen (JSON/CSV)\n\n"
                "Wiederherstellen: Über die Web-UI (Einstellungen → Backup importieren)\n"
                "oder update.sh / Installer erneut ausführen und das Archiv einspielen.\n\n"
                "Hinweis: Der geheime Schlüssel (.secret_key) ist nicht im Backup enthalten.\n"
                "Ohne denselben Schlüssel muss das SMTP-Passwort nach dem Import neu\n"
                "eingetragen werden.\n",
            )
    finally:
        tmp.unlink(missing_ok=True)
    return buf.getvalue()


def import_backup_zip(data: bytes) -> dict:
    config.ensure_dirs()
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Keine gültige ZIP-Datei.")
    names = zf.namelist()
    if "hausmeister.sqlite3" not in names:
        raise HTTPException(
            status_code=400,
            detail="ZIP enthält keine hausmeister.sqlite3 – Import abgebrochen.",
        )
    payload = zf.read("hausmeister.sqlite3")
    if not payload.startswith(b"SQLite format 3\x00"):
        raise HTTPException(status_code=400, detail="Datenbankdatei ist keine SQLite-Datei.")

    templates_restored = 0
    for name in names:
        if name.startswith("templates/") and not name.endswith("/"):
            target = config.TEMPLATES_DIR / os.path.basename(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(name))
            templates_restored += 1

    tmp_db = config.DB_PATH.with_suffix(".sqlite3.import")
    tmp_db.write_bytes(payload)
    from ..db import engine

    if engine is not None:
        engine.dispose()
    for suffix in ("-wal", "-shm"):
        config.DB_PATH.with_name(config.DB_PATH.name + suffix).unlink(missing_ok=True)
    os.replace(tmp_db, config.DB_PATH)
    reinitialize()
    return {
        "ok": True,
        "templates_restored": templates_restored,
        "hint": "Alle Dienste nutzen die Datenbank ab sofort unverändert weiter.",
    }


@router.get("/backup/export")
def backup_export():
    data = export_backup_zip()
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=hausmeister-backup.zip"},
    )


@router.post("/backup/import")
async def backup_import(file: UploadFile):
    data = await file.read()
    return import_backup_zip(data)
