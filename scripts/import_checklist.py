"""Import von Aufgabenbibliotheken (JSON oder CSV) mit Matching über den stabilen slug."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import AREAS, init, seed_base_data  # noqa: E402
from app.models import Area, Category, Task  # noqa: E402
from app.services import scheduler  # noqa: E402

CSV_FIELDS = [
    "slug",
    "title",
    "description",
    "area",
    "category",
    "priority",
    "schedule_type",
    "interval_days",
    "window_start_month",
    "window_end_month",
    "repeat_months",
    "repeat_day",
    "due_date",
    "start_date",
    "estimated_minutes",
    "source",
]


def load_entries(path: Path) -> tuple[dict, list[dict]]:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            data = {"tasks": data}
        return data, list(data.get("tasks", []))
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            missing = [f for f in ("slug", "title") if f not in (reader.fieldnames or [])]
            if missing:
                raise SystemExit(f"CSV fehlt Spalte(n): {', '.join(missing)} (erforderlich: slug, title)")
            entries = []
            for row in reader:
                row = {k: (v or "").strip() for k, v in row.items()}
                row["repeat_months"] = row.get("repeat_months", "")
                entries.append(row)
            return {"source": "csv-import"}, entries
    raise SystemExit(f"Nicht unterstützter Dateityp: {path} (JSON oder CSV erwartet)")


def _int_or_none(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _date_or_none(value):
    from datetime import date as date_cls

    if value in (None, ""):
        return None
    if isinstance(value, date_cls):
        return value
    try:
        return date_cls.fromisoformat(str(value))
    except ValueError:
        return None


def _parse_months(value) -> list[int] | None:
    if value in (None, ""):
        return None
    if isinstance(value, list):
        return [int(m) for m in value]
    months = []
    for part in str(value).replace(",", ";").split(";"):
        part = part.strip()
        if part.isdigit():
            months.append(int(part))
    return months or None


def _ensure_schema() -> None:
    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parent.parent
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "app" / "migrations"))
    command.upgrade(cfg, "head")


def run_import(path: Path, deactivate_missing: bool = False) -> dict:
    init()
    _ensure_schema()
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        seed_base_data(db)
        data, entries = load_entries(path)
        source = data.get("source") or "import"
        default_source = source if source != "csv-import" else "user"
        if default_source == "placeholder" and "placeholder" not in str(data.get("source", "")):
            default_source = source

        area_map = {a.slug: a for a in db.query(Area).all()}
        for area_entry in data.get("areas", []):
            slug = area_entry.get("slug")
            if slug and slug not in area_map:
                area = Area(slug=slug, name=area_entry.get("name", slug))
                db.add(area)
                db.flush()
                area_map[slug] = area

        cat_map = {c.slug: c for c in db.query(Category).all()}
        for cat_entry in data.get("categories", []):
            slug = cat_entry.get("slug")
            if slug and slug not in cat_map:
                area = area_map.get(cat_entry.get("area") or "")
                cat = Category(slug=slug, name=cat_entry.get("name", slug), area_id=area.id if area else None)
                db.add(cat)
                db.flush()
                cat_map[slug] = cat

        created = 0
        updated = 0
        seen_slugs: set[str] = set()
        for entry in entries:
            slug = str(entry.get("slug") or "").strip()
            title = str(entry.get("title") or "").strip()
            if not slug or not title:
                raise SystemExit(f"Eintrag ohne slug oder title uebersprungen: {entry}")
            seen_slugs.add(slug)
            task = db.query(Task).filter(Task.slug == slug).one_or_none()
            if task is None:
                task = Task(slug=slug, source=str(entry.get("source") or default_source))
                db.add(task)
                created += 1
            else:
                updated += 1
                if entry.get("source"):
                    task.source = str(entry["source"])

            area_slug = entry.get("area") or None
            area = area_map.get(area_slug) if area_slug else (task.area if task.id else None)
            if entry.get("category"):
                area_for_cat = area_map.get(entry.get("area") or "")
                cat = cat_map.get(entry["category"])
                if cat is None:
                    cat = Category(
                        slug=entry["category"],
                        name=entry["category"].replace("-", " ").title(),
                        area_id=area_for_cat.id if area_for_cat else None,
                    )
                    db.add(cat)
                    db.flush()
                    cat_map[cat.slug] = cat
                task.category_id = cat.id
                if area_for_cat:
                    task.area_id = area_for_cat.id
            elif area:
                task.area_id = area.id

            task.title = title
            task.description = entry.get("description") or None
            task.priority = entry.get("priority") if entry.get("priority") in ("high", "normal", "low") else "normal"
            st = entry.get("schedule_type") or task.schedule_type or "one_time"
            task.schedule_type = st
            task.interval_days = _int_or_none(entry.get("interval_days"))
            task.window_start_month = _int_or_none(entry.get("window_start_month"))
            task.window_end_month = _int_or_none(entry.get("window_end_month"))
            task.repeat_months = _parse_months(entry.get("repeat_months"))
            task.repeat_day = _int_or_none(entry.get("repeat_day")) or 1
            task.due_date = _date_or_none(entry.get("due_date"))
            task.start_date = _date_or_none(entry.get("start_date"))
            task.estimated_minutes = _int_or_none(entry.get("estimated_minutes"))
            if entry.get("source"):
                task.source = str(entry["source"])

        deactivated = 0
        if deactivate_missing:
            for task in db.query(Task).filter(Task.active.is_(True)).all():
                if task.slug not in seen_slugs:
                    task.active = False
                    deactivated += 1

        db.commit()

        from app.models import Task as TaskModel

        for task in db.query(TaskModel).filter(TaskModel.active.is_(True)).all():
            scheduler.ensure_instances_for_task(db, task)

        return {"created": created, "updated": updated, "deactivated": deactivated, "total": len(seen_slugs)}
    finally:
        db.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="import_checklist",
        description="Aufgabenbibliothek (JSON/CSV) nach Hausmeister importieren. Matching ueber slug.",
    )
    parser.add_argument("file", type=Path, help="JSON- oder CSV-Datei")
    parser.add_argument(
        "--deactivate-missing",
        action="store_true",
        help="Aufgaben deaktivieren, die nicht in der Import-Datei enthalten sind",
    )
    args = parser.parse_args(argv)
    if not args.file.exists():
        parser.error(f"Datei nicht gefunden: {args.file}")
    result = run_import(args.file, deactivate_missing=args.deactivate_missing)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
