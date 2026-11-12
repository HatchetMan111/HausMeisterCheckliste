from __future__ import annotations

import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Area, Category, Task
from ..services import recurrence, scheduler

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "aufgabe"


def unique_slug(db: Session, base: str, exclude_id: int | None = None) -> str:
    slug = slugify(base)
    n = 2
    query = db.query(Task).filter(Task.slug == slug)
    if exclude_id:
        query = query.filter(Task.id != exclude_id)
    while query.first() is not None:
        slug = f"{slugify(base)}-{n}"
        n += 1
        query = db.query(Task).filter(Task.slug == slug)
        if exclude_id:
            query = query.filter(Task.id != exclude_id)
    return slug


def escape_like(q: str) -> str:
    """% und _ in Suchbegriffen maskieren, damit sie nicht als Wildcards wirken."""
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class TaskPayload(BaseModel):
    title: str
    slug: str | None = None
    description: str | None = None
    area: str | None = None
    category: str | None = None
    priority: str = "normal"
    schedule_type: str = "one_time"
    interval_days: int | None = None
    window_start_month: int | None = None
    window_end_month: int | None = None
    repeat_months: list[int] | None = None
    repeat_day: int = 1
    due_date: date | None = None
    start_date: date | None = None
    estimated_minutes: int | None = None
    active: bool = True


def resolve_area(db: Session, slug: str | None) -> Area | None:
    if not slug:
        return None
    area = db.query(Area).filter(Area.slug == slug).one_or_none()
    if area is None:
        raise HTTPException(status_code=422, detail=f"Unbekannter Bereich: {slug}")
    return area


def resolve_category(db: Session, slug: str | None, area: Area | None) -> Category | None:
    if not slug:
        return None
    cat = db.query(Category).filter(Category.slug == slug).one_or_none()
    if cat is None:
        if area is None:
            raise HTTPException(
                status_code=422, detail=f"Kategorie '{slug}' ohne gültigen Bereich."
            )
        cat = Category(slug=slugify(slug), name=slug.replace("-", " ").title(), area_id=area.id)
        db.add(cat)
        db.flush()
    return cat


def apply_payload(db: Session, task: Task, payload: TaskPayload) -> None:
    data = payload.model_dump()
    data["schedule_type"] = data.get("schedule_type") or "one_time"
    errors = recurrence.validate_schedule(data)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    if payload.priority not in ("high", "normal", "low"):
        raise HTTPException(status_code=422, detail="priority muss high, normal oder low sein.")

    area = resolve_area(db, payload.area)
    category = resolve_category(db, payload.category, area)

    task.title = payload.title.strip()
    task.description = payload.description
    task.area_id = area.id if area else None
    task.category_id = category.id if category else None
    task.priority = payload.priority
    task.schedule_type = payload.schedule_type
    task.interval_days = payload.interval_days
    task.window_start_month = payload.window_start_month
    task.window_end_month = payload.window_end_month
    task.repeat_months = payload.repeat_months
    task.repeat_day = payload.repeat_day or 1
    task.due_date = payload.due_date
    task.start_date = payload.start_date
    task.estimated_minutes = payload.estimated_minutes
    task.active = payload.active


def serialize_task(task: Task) -> dict:
    open_inst = next((i for i in task.instances if i.status == "open"), None)
    return {
        "id": task.id,
        "slug": task.slug,
        "title": task.title,
        "description": task.description,
        "area": task.area.slug if task.area else None,
        "area_name": task.area.name if task.area else None,
        "category": task.category.slug if task.category else None,
        "category_name": task.category.name if task.category else None,
        "priority": task.priority,
        "schedule_type": task.schedule_type,
        "interval_days": task.interval_days,
        "window_start_month": task.window_start_month,
        "window_end_month": task.window_end_month,
        "repeat_months": task.repeat_months,
        "repeat_day": task.repeat_day,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "start_date": task.start_date.isoformat() if task.start_date else None,
        "estimated_minutes": task.estimated_minutes,
        "active": task.active,
        "source": task.source,
        "next_due": open_inst.due_date.isoformat() if open_inst else None,
        "schedule_text": recurrence.human_schedule(task),
    }


@router.get("")
def list_tasks(
    area: str | None = None,
    category: str | None = None,
    active: bool | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Task)
    if area:
        query = query.join(Task.area).filter(Area.slug == area)
    if category:
        query = query.join(Task.category).filter(Category.slug == category)
    if active is not None:
        query = query.filter(Task.active.is_(active))
    if q:
        query = query.filter(Task.title.ilike(f"%{escape_like(q)}%", escape="\\"))
    tasks = query.order_by(Task.active.desc(), Task.title).all()
    return {"tasks": [serialize_task(t) for t in tasks]}


@router.post("", status_code=201)
def create_task(payload: TaskPayload, db: Session = Depends(get_db)):
    if not payload.title.strip():
        raise HTTPException(status_code=422, detail="Titel ist erforderlich.")
    task = Task(
        slug=payload.slug.strip() if payload.slug else unique_slug(db, payload.title),
        source="user",
    )
    if payload.slug:
        existing = db.query(Task).filter(Task.slug == task.slug).one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail=f"Slug existiert bereits: {task.slug}")
    apply_payload(db, task, payload)
    db.add(task)
    db.commit()
    scheduler.ensure_instances_for_task(db, task)
    db.refresh(task)
    return serialize_task(task)


@router.get("/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden.")
    return serialize_task(task)


@router.put("/{task_id}")
def update_task(task_id: int, payload: TaskPayload, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden.")
    apply_payload(db, task, payload)
    db.commit()
    scheduler.ensure_instances_for_task(db, task)
    db.refresh(task)
    return serialize_task(task)


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden.")
    db.delete(task)
    db.commit()


@router.post("/{task_id}/toggle")
def toggle_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden.")
    task.active = not task.active
    db.commit()
    if task.active:
        scheduler.ensure_instances_for_task(db, task)
    return serialize_task(task)
