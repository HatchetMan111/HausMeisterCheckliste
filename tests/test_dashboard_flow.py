from __future__ import annotations

from datetime import date, timedelta

from app.services import scheduler


def test_fresh_install_creates_no_backlog(client, db):
    """Erstinstallation: keine überfälligen Instanzen für vergangene Monate."""
    from app.models import Task, TaskInstance

    past_month = date.today().replace(day=1) - timedelta(days=1)
    task = Task(
        slug="backlog-test-aufgabe",
        title="Backlog Test",
        schedule_type="annual_repeat",
        repeat_months=[past_month.month, 12],
        active=True,
    )
    db.add(task)
    db.commit()
    scheduler.ensure_instances_for_task(db, task)
    insts = db.query(TaskInstance).filter(TaskInstance.task_id == task.id).all()
    dues = [i.due_date for i in insts]
    assert all(d >= date.today().replace(day=1) for d in dues)
    assert date(past_month.year, past_month.month, 1) not in dues


def test_retro_complete_month_creates_instances(client):
    """Rückwirkendes Abhaken im Jahresplan erzeugt fehlende Instanzen und erledigt sie."""
    past = date.today().replace(day=1) - timedelta(days=1)
    resp = client.post(
        "/api/tasks",
        json={"title": "Retro Monatsaufgabe", "schedule_type": "annual_repeat",
              "repeat_months": [past.month]},
    )
    assert resp.status_code == 201

    resp = client.post(f"/api/maintenance/complete-month/{past.month}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["completed"] >= 1

    history = client.get("/api/maintenance/history").json()["completions"]
    assert any(c["task_title"] == "Retro Monatsaufgabe" for c in history)


def test_skip_all_overdue(client, db):
    overdue_due = (date.today() - timedelta(days=10)).isoformat()
    resp = client.post(
        "/api/tasks",
        json={"title": "Skip-All Test", "schedule_type": "one_time", "due_date": overdue_due},
    )
    assert resp.status_code == 201

    dash = client.get("/api/maintenance/dashboard").json()
    assert any(i["title"] == "Skip-All Test" for i in dash["overdue"])

    resp = client.post("/api/maintenance/skip-all-overdue")
    assert resp.status_code == 200
    assert resp.json()["skipped"] >= 1

    dash = client.get("/api/maintenance/dashboard").json()
    assert not any(i["title"] == "Skip-All Test" for i in dash["overdue"])


def test_month_task_is_due_whole_month_not_overdue(client):
    """Monatsaufgaben sind den ganzen Monat fällig, erst danach überfällig."""
    from app.services import recurrence
    from types import SimpleNamespace

    task = SimpleNamespace(schedule_type="annual_repeat", window_start_month=None,
                           window_end_month=None, due_date=None, start_date=None)
    inst = SimpleNamespace(due_date=date(2026, 8, 1), year=2026, status="open")
    assert recurrence.status_for(task, inst, date(2026, 8, 15)) == "due"
    assert recurrence.status_for(task, inst, date(2026, 8, 31)) == "due"
    assert recurrence.status_for(task, inst, date(2026, 9, 1)) == "overdue"
    assert recurrence.status_for(task, inst, date(2026, 7, 15)) == "upcoming"


def test_dashboard_does_not_roll_new_install(client):
    """Dashboard-Panel erscheint erst ab 10 überfälligen; Monatsaufgaben im Fokus."""
    resp = client.get("/")
    assert resp.status_code == 200
    # keine Onboarding-Panel bei wenig Rückstand
    assert "Viel Rückstand entdeckt" not in resp.text

    # viele überfällige erzeugen
    for n in range(12):
        client.post(
            "/api/tasks",
            json={"title": f"Rückstand {n}", "schedule_type": "one_time",
                  "due_date": (date.today() - timedelta(days=n + 1)).isoformat()},
        )
    resp = client.get("/")
    assert "Viel Rückstand entdeckt" in resp.text
    assert "Alle überfälligen überspringen" in resp.text


def test_jahresplan_library_without_duplicates(db):
    from pathlib import Path

    import json as jsonlib
    import collections

    data = jsonlib.loads((Path(__file__).resolve().parent.parent / "data" / "templates" / "jahresplan.json").read_text())
    tasks = data["tasks"]
    titles = collections.Counter(t["title"].lower().strip() for t in tasks)
    dupes = [t for t, c in titles.items() if c > 1]
    assert not dupes, f"Doppelte Titel: {dupes}"
    assert len(tasks) == 156


def test_import_deactivate_keeps_user_tasks(db):
    from pathlib import Path

    sys_path = Path(__file__).resolve().parent.parent / "scripts"
    import sys

    if str(sys_path) not in sys.path:
        sys.path.insert(0, str(sys_path))
    from import_checklist import run_import

    run_import(Path(__file__).resolve().parent.parent / "data" / "templates" / "jahresplan.json")

    from app.db import SessionLocal
    from app.models import Task

    session = SessionLocal()
    user_task = Task(slug="mein-eigenes-projekt-aufgabe", title="Mein eigenes Projekt",
                     schedule_type="one_time", due_date=date(2030, 5, 5), active=True, source="user")
    session.add(user_task)
    session.commit()

    result = run_import(
        Path(__file__).resolve().parent.parent / "data" / "templates" / "jahresplan.json",
        deactivate_missing=True,
    )
    session.refresh(user_task)
    assert user_task.active is True, "Nutzer-Aufgaben dürfen nicht deaktiviert werden"
    session.close()
