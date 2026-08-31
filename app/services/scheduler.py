"""Täglicher Wartungslauf: Instanzen erzeugen, Backup ziehen, Zusammenfassung senden."""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from .. import config
from . import notifications, recurrence


def ensure_instances_for_task(db, task, today: date | None = None, horizon_days: int | None = None) -> int:
    from ..models import TaskCompletion, TaskInstance

    today = today or date.today()
    horizon_days = horizon_days or config.INSTANCE_HORIZON_DAYS
    horizon = today + timedelta(days=horizon_days)
    existing = {
        i.due_date: i
        for i in db.query(TaskInstance).filter(TaskInstance.task_id == task.id).all()
    }
    created = 0

    if task.schedule_type == "interval_days":
        if any(i.status == "open" for i in existing.values()):
            return 0
        last = (
            db.query(TaskCompletion)
            .filter(TaskCompletion.task_id == task.id)
            .order_by(TaskCompletion.completed_at.desc())
            .first()
        )
        if last is not None:
            due = last.completed_at.date() + timedelta(days=max(int(task.interval_days or 1), 1))
        else:
            occ = recurrence.occurrences(task, today, horizon)
            if not occ:
                return 0
            due = occ[0]
        if due not in existing:
            db.add(TaskInstance(task_id=task.id, due_date=due, year=due.year))
            db.commit()
            created += 1
        return created

    # Aufwärmschutz: Fälligkeiten werden erst ab dem aktuellen Monat erzeugt,
    # damit eine frische Installation nicht mit dem Jahres-Rückstand überrollt wird.
    # Rückwirkend abgehakt werden kann jederzeit über die Monatsaktionen im Jahresplan.
    lookback = today.replace(day=1)
    for due in recurrence.occurrences(task, lookback, horizon):
        if due not in existing:
            db.add(TaskInstance(task_id=task.id, due_date=due, year=due.year))
            created += 1
    if task.schedule_type == "annual_window":
        # läuft das Jahresfenster gerade, wird die Fälligkeit des laufenden
        # Fensters auch dann angelegt, wenn der Fensterbeginn vor dem Monatsstart liegt
        for year in (today.year - 1, today.year):
            start, end = recurrence.window_bounds(task, year)
            if start < lookback <= end and start not in existing:
                db.add(TaskInstance(task_id=task.id, due_date=start, year=year))
                created += 1
    if created:
        db.commit()
    return created


def ensure_all_instances(db, today: date | None = None) -> int:
    from ..models import Task

    total = 0
    for task in db.query(Task).filter(Task.active.is_(True)).all():
        total += ensure_instances_for_task(db, task, today)
    return total


def backup_db(backup_dir: Path | None = None, keep: int | None = None) -> Path:
    config.ensure_dirs()
    target_dir = Path(backup_dir or config.BACKUP_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = target_dir / f"hausmeister-{stamp}.sqlite3"
    src = sqlite3.connect(str(config.DB_PATH))
    dst = sqlite3.connect(str(target))
    with dst:
        src.backup(dst)
    dst.close()
    src.close()
    keep = keep or config.DEFAULT_BACKUP_KEEP
    backups = sorted(target_dir.glob("hausmeister-*.sqlite3"))
    for old in backups[:-keep] if keep > 0 else []:
        old.unlink(missing_ok=True)
    return target


def run_daily(db, today: date | None = None) -> dict:
    today = today or date.today()
    created = ensure_all_instances(db, today)
    backup_path = backup_db()
    summary = notifications.send_daily_summary(db, today)
    pushed = 0
    if config.PUSH_ENABLED and notifications.channel_enabled(db, "push"):
        items = notifications.due_summary_items(db, today)
        if items:
            pushed = notifications.send_web_push(
                db,
                {
                    "title": "Hausmeister: fällige Wartungen",
                    "body": f"{len(items)} Aufgabe(n) fällig oder überfällig.",
                    "url": "/",
                },
            )
    return {
        "date": today.isoformat(),
        "instances_created": created,
        "backup": str(backup_path),
        "email_summary": summary,
        "push_sent": pushed,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="hausmeister-scheduler",
        description="Täglicher Wartungslauf für Hausmeister (systemd-Timer).",
    )
    parser.add_argument("--run-daily", action="store_true", help="Täglichen Lauf ausführen")
    args = parser.parse_args(argv)
    if not args.run_daily:
        parser.error("--run-daily ist erforderlich")

    config.ensure_dirs()
    from ..db import init

    init()
    from ..db import SessionLocal

    db = SessionLocal()
    try:
        result = run_daily(db)
    finally:
        db.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
