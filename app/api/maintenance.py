from __future__ import annotations

import io
import os
import sqlite3
import zipfile
from datetime import date, timedelta, timezone

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
        item["month_based"] = inst.task.schedule_type in ("annual_repeat", "annual_window")
        item["month"] = inst.due_date.month
        item["due_year"] = inst.due_date.year
        items.append(item)

    # Dringend: echter Rückstand (überfällig) und datumsgenaue Aufgaben, die
    # heute fällig sind. Monatsbasierte Aufgaben gehören in den Monats-Fokus.
    urgent = sorted(
        (
            i for i in items
            if i["status"] == "overdue"
            or (i["status"] == "due" and not i["month_based"])
        ),
        key=lambda i: (i["priority_rank"], i["due_date"]),
    )

    month_start = today.replace(day=1)
    month_end = date(today.year, today.month, _last_day_of_month(today.year, today.month))
    in_month = [
        i
        for i in items
        if i["month"] == today.month
        and i["due_year"] == today.year
        and (
            i["status"] == "upcoming"
            or (i["status"] == "due" and i["month_based"])
        )
        and i["instance_id"] not in {x["instance_id"] for x in urgent}
    ]
    in_month.sort(key=lambda i: (i["priority_rank"], i["due_date"]))
    month_focus = [i for i in in_month if i["priority"] in ("high", "normal")]
    month_rest = [i for i in in_month if i["priority"] == "low"]

    month_ids = {i["instance_id"] for i in in_month}
    urgent_ids = {i["instance_id"] for i in urgent}
    later = sorted(
        (
            i
            for i in items
            if i["status"] == "upcoming"
            and i["instance_id"] not in month_ids
            and i["instance_id"] not in urgent_ids
            and date.fromisoformat(i["due_date"]) <= today + timedelta(days=30)
        ),
        key=lambda i: (i["priority_rank"], i["due_date"]),
    )
    return {
        "urgent": urgent,
        "month_focus": month_focus,
        "month_rest": month_rest,
        "later": later,
        "overdue_total": len(urgent),
    }


@router.get("/sections")
def get_sections(db: Session = Depends(get_db)):
    return dashboard_sections(db, date.today())


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


def _to_local_iso(dt):
    """Naive UTC-Zeitstempel (Datenbank) in die konfigurierte Lokalzeit
    konvertieren und als ISO-String mit Offset zurückgeben."""
    if dt is None:
        return None
    try:
        from zoneinfo import ZoneInfo

        local = dt.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(config.TIMEZONE))
    except Exception:
        return dt.isoformat()
    return local.isoformat()


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


def _month_due_for_task(task: Task, month: int, year: int) -> date | None:
    from ..services.recurrence import parse_repeat_months

    if task.schedule_type == "annual_repeat":
        if month not in parse_repeat_months(task.repeat_months):
            return None
        day = min(max(int(task.repeat_day or 1), 1), _last_day_of_month(year, month))
        return date(year, month, day)
    if task.schedule_type == "annual_window":
        start, _ = recurrence.window_bounds(task, year)
        if start.month == month:
            return start
        return None
    return None


@router.post("/complete-month/{month}")
def complete_month(month: int, db: Session = Depends(get_db)):
    if not 1 <= month <= 12:
        raise HTTPException(status_code=422, detail="Monat muss zwischen 1 und 12 liegen.")
    year = date.today().year
    existing = {
        (i.task_id, i.due_date): i
        for i in _instances_in_month(db, month, ("open", "done", "skipped"))
    }
    completed = 0
    tasks = db.query(Task).filter(Task.active.is_(True)).all()
    for task in tasks:
        due = _month_due_for_task(task, month, year)
        if due is None:
            continue
        inst = existing.get((task.id, due))
        if inst is None:
            inst = TaskInstance(task_id=task.id, due_date=due, year=year, status="done")
            db.add(inst)
            db.flush()
            db.add(TaskCompletion(task_id=task.id, instance_id=inst.id))
            completed += 1
        elif inst.status != "done":
            inst.status = "done"
            db.add(TaskCompletion(task_id=task.id, instance_id=inst.id))
            _schedule_next_interval(db, task, due)
            completed += 1
    db.commit()
    return {"ok": True, "completed": completed}


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


@router.post("/skip-all-overdue")
def skip_all_overdue(db: Session = Depends(get_db)):
    """Rettungsanker nach Erstinstallation/Migration: alle überfälligen offenen
    Fälligkeiten als übersprungen markieren (ohne Verlaufseinträge)."""
    today = date.today()
    rows = (
        db.query(TaskInstance)
        .join(Task)
        .filter(Task.active.is_(True), TaskInstance.status == "open")
        .all()
    )
    skipped = 0
    for inst in rows:
        if recurrence.status_for(inst.task, inst, today) == "overdue":
            inst.status = "skipped"
            skipped += 1
    if skipped:
        db.commit()
    return {"ok": True, "skipped": skipped}


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
                "completed_at": _to_local_iso(c.completed_at),
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


MONTH_NAMES = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]
PRIORITY_FILTERS = ("all", "high", "normal", "low", "tip")


def jahresplan_payload(db: Session, view: str, month: int | None, priority: str, today: date | None = None) -> dict:
    """Jahresplan-Daten für die SPA: Aufgaben je Monat (monatsbasiert) plus
    laufende/einmalige Aufgaben, mit Status je Monat und Summen."""
    from ..services.recurrence import parse_repeat_months, window_bounds

    today = today or date.today()
    scheduler.ensure_all_instances(db)
    year = today.year
    view = "year" if view == "year" else "month"
    if month is None or not 1 <= month <= 12:
        month = today.month
    if priority not in PRIORITY_FILTERS:
        priority = "all"

    tasks = db.query(Task).filter(Task.active.is_(True)).all()
    year_start, year_end = date(year, 1, 1), date(year, 12, 31)
    instances = (
        db.query(TaskInstance)
        .join(Task)
        .filter(Task.active.is_(True), TaskInstance.due_date >= year_start, TaskInstance.due_date <= year_end)
        .all()
    )
    open_by_task_month: dict[tuple[int, int], int] = {}
    done_by_task_month: dict[tuple[int, int], int] = {}
    overdue_by_task: dict[int, int] = {}
    for inst in instances:
        key = (inst.task_id, inst.due_date.month)
        if inst.status == "open":
            open_by_task_month[key] = inst.id
            if inst.due_date < today:
                overdue_by_task[inst.task_id] = overdue_by_task.get(inst.task_id, 0) + 1
        elif inst.status == "done":
            done_by_task_month[key] = done_by_task_month.get(key, 0) + 1

    def month_of_window(task: Task, m: int) -> bool:
        start, end = window_bounds(task, year)
        cursor = start
        while cursor <= end:
            if cursor.month == m:
                return True
            cursor += timedelta(days=1)
        return False

    def matches_priority(task: Task) -> bool:
        prio = task.priority if task.priority in ("high", "normal", "low") else "normal"
        if priority == "tip":
            return task.source == "tip"
        if priority == "all":
            return True
        return prio == priority

    def serialize_item(task: Task, m: int | None) -> dict:
        key = (task.id, m) if m else (task.id, today.month)
        open_id = open_by_task_month.get(key)
        done_cnt = done_by_task_month.get(key, 0)
        status = "done" if (done_cnt and not open_id) else ("open" if open_id else "planned")
        prio = task.priority if task.priority in ("high", "normal", "low") else "normal"
        item = {
            "task_id": task.id,
            "title": task.title,
            "description": task.description,
            "area": task.area.slug if task.area else None,
            "area_name": task.area.name if task.area else None,
            "category_name": task.category.name if task.category else None,
            "priority": prio,
            "is_tip": task.source == "tip",
            "open_id": open_id,
            "done": done_cnt,
            "overdue": overdue_by_task.get(task.id, 0),
            "schedule_text": recurrence.human_schedule(task),
            "status": status,
            "estimated_minutes": task.estimated_minutes,
            "window_end": None,
        }
        if task.schedule_type == "annual_window":
            item["window_end"] = window_bounds(task, year)[1].isoformat()
        return item

    months_out: list[dict] = []
    month_range = range(1, 13) if view == "year" else [month]
    for m in month_range:
        items = []
        for task in tasks:
            if task.schedule_type == "annual_repeat":
                if m not in parse_repeat_months(task.repeat_months):
                    continue
            elif task.schedule_type == "annual_window":
                if not month_of_window(task, m):
                    continue
            elif task.schedule_type == "one_time" and task.due_date:
                if task.due_date.month != m:
                    continue
            else:
                continue
            if not matches_priority(task):
                continue
            items.append(serialize_item(task, m))
        items.sort(key=lambda i: ({"high": 0, "normal": 1, "low": 2}.get(i["priority"], 3), i["title"]))
        months_out.append({"month": m, "name": MONTH_NAMES[m - 1], "items": items})

    running = []
    for task in tasks:
        if task.schedule_type not in ("interval_days", "one_time"):
            continue
        if not matches_priority(task):
            continue
        running.append(serialize_item(task, None))
    running.sort(key=lambda i: i["title"])

    all_items = [i for mrow in months_out for i in mrow["items"]] + running
    total = len(all_items)
    done_total = sum(1 for i in all_items if i["status"] == "done")
    return {
        "view": view,
        "month": month,
        "priority": priority,
        "year": year,
        "months": months_out,
        "running": running,
        "total": total,
        "done_total": done_total,
        "open_total": total - done_total,
        "today": today.isoformat(),
    }


@router.get("/jahresplan")
def get_jahresplan(
    view: str = "month",
    month: int | None = None,
    priority: str = "all",
    db: Session = Depends(get_db),
):
    return jahresplan_payload(db, view, month, priority)


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
