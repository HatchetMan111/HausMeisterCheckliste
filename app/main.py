from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import config
from .api import defects, maintenance, settings as settings_api
from .api import tasks as tasks_api
from .api.maintenance import dashboard_buckets, export_backup_zip, import_backup_zip
from .db import get_db, init, seed_base_data
from .models import Area, Category, Task, TaskCompletion, TaskInstance
from .services import recurrence, scheduler
from .services.recurrence import parse_repeat_months, window_bounds

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
STATIC_DIR = Path(__file__).resolve().parent / "static"
ROOT_CA_PATH = config.DATA_DIR / "certs" / "root-ca.crt"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init()
    from .db import SessionLocal

    db = SessionLocal()
    try:
        seed_base_data(db)
    finally:
        db.close()
    yield


app = FastAPI(title=config.APP_NAME, version=config.VERSION, lifespan=lifespan)
app.include_router(tasks_api.router)
app.include_router(maintenance.router)
app.include_router(settings_api.router)
app.include_router(defects.router)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
def health():
    return {"status": "ok", "app": config.APP_NAME, "version": config.VERSION}


@app.get("/certs/root-ca.crt")
def root_ca():
    if not ROOT_CA_PATH.exists():
        raise HTTPException(status_code=404, detail="Zertifikat noch nicht verfügbar.")
    return FileResponse(
        ROOT_CA_PATH,
        media_type="application/x-x509-ca-cert",
        headers={"Content-Disposition": "inline; filename=hausmeister-root-ca.crt"},
    )


def _flash(request: Request) -> str | None:
    return request.query_params.get("msg")


@app.get("/", response_class=HTMLResponse)
def dashboard_page(request: Request, db: Session = Depends(get_db)):
    from .api.maintenance import dashboard_sections

    today = date.today()
    sections = dashboard_sections(db, today)
    weekdays = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "sections": sections,
            "month_name": MONTH_NAMES[today.month - 1],
            "today_long": f"{weekdays[today.weekday()]}, {today.day}. {MONTH_NAMES[today.month - 1]} {today.year}",
            "msg": _flash(request),
            "page": "dashboard",
        },
    )


def _task_view(task: Task) -> dict:
    data = tasks_api.serialize_task(task)
    data["schedule_text"] = recurrence.human_schedule(task)
    return data


@app.get("/tasks", response_class=HTMLResponse)
def tasks_page(
    request: Request,
    area: str | None = None,
    q: str | None = None,
    show_inactive: bool = False,
    db: Session = Depends(get_db),
):
    query = db.query(Task)
    if area:
        query = query.join(Area).filter(Area.slug == area)
    if q:
        query = query.filter(Task.title.ilike(f"%{q}%"))
    if not show_inactive:
        query = query.filter(Task.active.is_(True))
    tasks = query.order_by(Task.active.desc(), Task.title).all()
    areas = db.query(Area).order_by(Area.sort_order).all()
    return templates.TemplateResponse(
        request,
        "tasks.html",
        {
            "tasks": [_task_view(t) for t in tasks],
            "areas": areas,
            "filter_area": area or "",
            "filter_q": q or "",
            "show_inactive": show_inactive,
            "msg": _flash(request),
            "page": "tasks",
        },
    )


FORM_FIELDS = (
    "title", "description", "area", "category", "priority", "schedule_type",
    "interval_days", "window_start_month", "window_end_month", "repeat_months",
    "repeat_day", "due_date", "start_date", "estimated_minutes",
)


def _form_int(value: str | None) -> int | None:
    value = str(value or "").strip()
    try:
        return int(value) if value else None
    except ValueError:
        return None


def _payload_from_form(form: dict) -> tasks_api.TaskPayload:
    months = []
    for part in str(form.get("repeat_months") or "").replace(",", ";").split(";"):
        part = part.strip()
        if part.isdigit():
            months.append(int(part))
    return tasks_api.TaskPayload(
        title=form.get("title") or "",
        description=form.get("description") or None,
        area=form.get("area") or None,
        category=form.get("category") or None,
        priority=form.get("priority") or "normal",
        schedule_type=form.get("schedule_type") or "one_time",
        interval_days=_form_int(form.get("interval_days")),
        window_start_month=_form_int(form.get("window_start_month")),
        window_end_month=_form_int(form.get("window_end_month")),
        repeat_months=months or None,
        repeat_day=_form_int(form.get("repeat_day")) or 1,
        due_date=form.get("due_date") or None,
        start_date=form.get("start_date") or None,
        estimated_minutes=_form_int(form.get("estimated_minutes")),
        active=True,
    )


def _apply_task_form(db: Session, task: Task, form: dict) -> None:
    payload = _payload_from_form(form)
    tasks_api.apply_payload(db, task, payload)


@app.get("/tasks/new", response_class=HTMLResponse)
def task_new_page(request: Request, db: Session = Depends(get_db)):
    return _render_task_form(request, db, None)


@app.post("/tasks/new")
def task_new_submit(
    request: Request,
    db: Session = Depends(get_db),
    title: str = Form(""),
    description: str = Form(""),
    area: str = Form(""),
    category: str = Form(""),
    priority: str = Form("normal"),
    schedule_type: str = Form("one_time"),
    interval_days: str = Form(""),
    window_start_month: str = Form(""),
    window_end_month: str = Form(""),
    repeat_months: str = Form(""),
    repeat_day: str = Form("1"),
    due_date: str = Form(""),
    start_date: str = Form(""),
    estimated_minutes: str = Form(""),
):
    form = {
        "title": title, "description": description, "area": area, "category": category,
        "priority": priority, "schedule_type": schedule_type, "interval_days": interval_days,
        "window_start_month": window_start_month, "window_end_month": window_end_month,
        "repeat_months": repeat_months, "repeat_day": repeat_day, "due_date": due_date,
        "start_date": start_date, "estimated_minutes": estimated_minutes,
    }
    try:
        task = Task(slug=tasks_api.unique_slug(db, title or "aufgabe"), source="user")
        _apply_task_form(db, task, form)
        db.add(task)
        db.commit()
        scheduler.ensure_instances_for_task(db, task)
    except HTTPException as exc:
        return _render_task_form(request, db, None, error=exc.detail)
    except Exception as exc:
        return _render_task_form(request, db, None, error=str(exc))
    return RedirectResponse("/tasks?msg=Aufgabe+angelegt", status_code=303)


@app.get("/tasks/{task_id}/edit", response_class=HTMLResponse)
def task_edit_page(request: Request, task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden.")
    return _render_task_form(request, db, task)


@app.post("/tasks/{task_id}/edit")
def task_edit_submit(
    request: Request,
    task_id: int,
    db: Session = Depends(get_db),
    title: str = Form(""),
    description: str = Form(""),
    area: str = Form(""),
    category: str = Form(""),
    priority: str = Form("normal"),
    schedule_type: str = Form("one_time"),
    interval_days: str = Form(""),
    window_start_month: str = Form(""),
    window_end_month: str = Form(""),
    repeat_months: str = Form(""),
    repeat_day: str = Form("1"),
    due_date: str = Form(""),
    start_date: str = Form(""),
    estimated_minutes: str = Form(""),
):
    task = db.query(Task).filter(Task.id == task_id).one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden.")
    form = {
        "title": title, "description": description, "area": area, "category": category,
        "priority": priority, "schedule_type": schedule_type, "interval_days": interval_days,
        "window_start_month": window_start_month, "window_end_month": window_end_month,
        "repeat_months": repeat_months, "repeat_day": repeat_day, "due_date": due_date,
        "start_date": start_date, "estimated_minutes": estimated_minutes,
    }
    try:
        _apply_task_form(db, task, form)
        db.commit()
        scheduler.ensure_instances_for_task(db, task)
    except HTTPException as exc:
        return _render_task_form(request, db, task, error=exc.detail)
    except Exception as exc:
        return _render_task_form(request, db, task, error=str(exc))
    return RedirectResponse("/tasks?msg=Aufgabe+gespeichert", status_code=303)


def _render_task_form(request: Request, db: Session, task: Task | None, error=None):
    areas = db.query(Area).order_by(Area.sort_order).all()
    categories = db.query(Category).order_by(Category.name).all()
    return templates.TemplateResponse(
        request,
        "task_form.html",
        {
            "task": _task_view(task) if task else None,
            "areas": areas,
            "categories": categories,
            "error": error,
            "msg": None,
            "page": "tasks",
        },
    )


@app.post("/tasks/{task_id}/toggle-form")
def task_toggle_form(task_id: int, db: Session = Depends(get_db)):
    tasks_api.toggle_task(task_id, db)
    return RedirectResponse("/tasks?msg=Status+geändert", status_code=303)


@app.post("/tasks/{task_id}/delete-form")
def task_delete_form(task_id: int, db: Session = Depends(get_db)):
    tasks_api.delete_task(task_id, db)
    return RedirectResponse("/tasks?msg=Aufgabe+gelöscht", status_code=303)


def _flash(request: Request) -> str | None:
    return request.query_params.get("msg")


MONTH_NAMES = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]

@app.get("/jahresplan", response_class=HTMLResponse)
def jahresplan_page(
    request: Request,
    view: str = "month",
    month: int | None = None,
    priority: str = "all",
    db: Session = Depends(get_db),
):
    scheduler.ensure_all_instances(db)
    today = date.today()
    year = today.year
    view = "year" if view == "year" else "month"
    if month is None or not 1 <= month <= 12:
        month = today.month
    if priority not in ("all", "high", "normal", "low", "tip"):
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

    def task_months(task: Task) -> list[int]:
        if task.schedule_type == "annual_repeat":
            return sorted(parse_repeat_months(task.repeat_months))
        if task.schedule_type == "annual_window":
            return [int(task.window_start_month or 1)]
        if task.schedule_type == "one_time" and task.due_date:
            return [task.due_date.month]
        return []

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

    def build_item(task: Task, m: int | None) -> dict:
        key = (task.id, m) if m else (task.id, today.month)
        open_id = open_by_task_month.get(key)
        done_cnt = done_by_task_month.get(key, 0)
        status = "done" if (done_cnt and not open_id) else ("open" if open_id else "planned")
        prio = task.priority if task.priority in ("high", "normal", "low") else "normal"
        return {
            "task": task,
            "priority": prio,
            "is_tip": task.source == "tip",
            "open_id": open_id,
            "done": done_cnt,
            "overdue": overdue_by_task.get(task.id, 0),
            "schedule_text": recurrence.human_schedule(task),
            "status": status,
        }

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
            item = build_item(task, m)
            if task.schedule_type == "annual_window":
                item["window_end"] = window_bounds(task, year)[1].isoformat()
            items.append(item)
        items.sort(key=lambda i: ({"high": 0, "normal": 1, "low": 2}.get(i["priority"], 3), i["task"].title))
        months_out.append({"month": m, "name": MONTH_NAMES[m - 1], "items": items})

    running = []
    for task in tasks:
        if task.schedule_type not in ("interval_days", "one_time"):
            continue
        if not matches_priority(task):
            continue
        running.append(build_item(task, None))
    running.sort(key=lambda i: i["task"].title)

    all_items = [i for mrow in months_out for i in mrow["items"]] + running
    total = len(all_items)
    done_total = sum(1 for i in all_items if i["status"] == "done")
    return templates.TemplateResponse(
        request,
        "jahresplan.html",
        {
            "view": view,
            "show_month": month,
            "months": months_out,
            "running": running,
            "priority": priority,
            "total": total,
            "done_total": done_total,
            "year": year,
            "msg": _flash(request),
            "page": "jahresplan",
        },
    )



@app.post("/jahresplan/complete-month/{month}")
def complete_month_form(month: int, db: Session = Depends(get_db)):
    maintenance.complete_month(month, db)
    return RedirectResponse(f"/jahresplan?msg=Monat+abgehakt", status_code=303)


@app.post("/jahresplan/reopen-month/{month}")
def reopen_month_form(month: int, db: Session = Depends(get_db)):
    maintenance.reopen_month(month, db)
    return RedirectResponse(f"/jahresplan?msg=Monat+zurückgesetzt", status_code=303)


@app.post("/maintenance/instances/{instance_id}/complete-form")
def complete_instance_form(instance_id: int, db: Session = Depends(get_db)):
    maintenance.complete_instance(instance_id, None, db)
    return RedirectResponse("/?msg=Erledigt", status_code=303)


@app.post("/maintenance/instances/{instance_id}/skip-form")
def skip_instance_form(instance_id: int, db: Session = Depends(get_db)):
    maintenance.skip_instance(instance_id, db)
    return RedirectResponse("/?msg=Übersprungen", status_code=303)


@app.get("/history", response_class=HTMLResponse)
def history_page(request: Request, db: Session = Depends(get_db)):
    rows = (
        db.query(TaskCompletion)
        .order_by(TaskCompletion.completed_at.desc())
        .limit(200)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "history.html",
        {
            "completions": rows,
            "msg": _flash(request),
            "page": "history",
        },
    )


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db)):
    data = settings_api.settings_public(db)
    return templates.TemplateResponse(
        request,
        "settings.html",
        {"s": data, "msg": _flash(request), "page": "settings"},
    )


@app.post("/settings")
def settings_submit(
    request: Request,
    db: Session = Depends(get_db),
    property_name: str = Form(""),
    property_address: str = Form(""),
    email_enabled: bool = Form(False),
    smtp_host: str = Form(""),
    smtp_port: str = Form(""),
    smtp_security: str = Form("starttls"),
    smtp_user: str = Form(""),
    smtp_password: str = Form(""),
    smtp_from: str = Form(""),
    notify_email: str = Form(""),
    notify_days_ahead: str = Form("7"),
):
    payload = settings_api.SettingsPayload(
        property_name=property_name,
        property_address=property_address,
        email_enabled=email_enabled,
        smtp_host=smtp_host or None,
        smtp_port=_form_int(smtp_port),
        smtp_security=smtp_security,
        smtp_user=smtp_user,
        smtp_password=smtp_password or None,
        smtp_from=smtp_from,
        notify_email=notify_email,
        notify_days_ahead=_form_int(notify_days_ahead),
    )
    try:
        settings_api.update_settings(payload, db)
    except HTTPException as exc:
        return RedirectResponse(f"/settings?msg={exc.detail}", status_code=303)
    return RedirectResponse("/settings?msg=Einstellungen+gespeichert", status_code=303)


@app.post("/settings/test-email-form")
def settings_test_email_form(db: Session = Depends(get_db)):
    try:
        settings_api.test_email(None, db)
    except HTTPException as exc:
        return RedirectResponse(f"/settings?msg={exc.detail}", status_code=303)
    return RedirectResponse("/settings?msg=Test-E-Mail+versendet", status_code=303)


@app.post("/settings/import-checklist-form")
async def settings_import_checklist_form(file: UploadFile):
    import sys
    from importlib import util as importlib_util

    config.ensure_dirs()
    target = config.DATA_DIR / f"upload-{file.filename}"
    target.write_bytes(await file.read())
    script = Path(__file__).resolve().parent.parent / "scripts" / "import_checklist.py"
    spec = importlib_util.spec_from_file_location("import_checklist", script)
    module = importlib_util.module_from_spec(spec)
    sys.modules["import_checklist"] = module
    spec.loader.exec_module(module)
    try:
        result = module.run_import(target)
    except Exception as exc:
        target.unlink(missing_ok=True)
        return RedirectResponse(f"/settings?msg=Import+fehlgeschlagen:+{exc}", status_code=303)
    target.unlink(missing_ok=True)
    return RedirectResponse(
        f"/settings?msg=Import:+{result['created']}+neu,+{result['updated']}+aktualisiert",
        status_code=303,
    )


@app.post("/settings/backup-import-form")
async def settings_backup_import_form(file: UploadFile):
    data = await file.read()
    try:
        result = import_backup_zip(data)
    except HTTPException as exc:
        return RedirectResponse(f"/settings?msg={exc.detail}", status_code=303)
    return RedirectResponse(
        f"/settings?msg=Backup+importiert+({result['templates_restored']}+Vorlagen)",
        status_code=303,
    )


@app.get("/help/certificate", response_class=HTMLResponse)
def certificate_help(request: Request):
    return templates.TemplateResponse(
        request,
        "certificate.html",
        {"app_url": config.APP_URL, "msg": None, "page": "help"},
    )
