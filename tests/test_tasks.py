from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from app.services import scheduler


def test_create_task_api_and_instance(client, db):
    today = date.today().isoformat()
    resp = client.post(
        "/api/tasks",
        json={
            "title": "Test Rauchmelder",
            "area": "sicherheit",
            "schedule_type": "one_time",
            "due_date": today,
            "priority": "high",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["slug"] == "test-rauchmelder"
    assert data["area"] == "sicherheit"
    assert data["next_due"] == today

    dash = client.get("/api/maintenance/dashboard").json()
    titles = [i["title"] for i in dash["today"]]
    assert "Test Rauchmelder" in titles


def test_task_validation_errors(client):
    resp = client.post(
        "/api/tasks",
        json={"title": "Ohne Datum", "schedule_type": "one_time"},
    )
    assert resp.status_code == 422
    resp = client.post(
        "/api/tasks",
        json={"title": "Falsches Intervall", "schedule_type": "interval_days", "interval_days": 0},
    )
    assert resp.status_code == 422
    resp = client.post(
        "/api/tasks",
        json={"title": "Unbekannter Bereich", "schedule_type": "one_time", "due_date": "2026-01-01", "area": "unicorn"},
    )
    assert resp.status_code == 422


def test_toggle_and_delete_task(client, db):
    resp = client.post(
        "/api/tasks",
        json={"title": "Toggle Aufgabe", "schedule_type": "one_time", "due_date": "2030-01-01"},
    )
    task_id = resp.json()["id"]

    resp = client.post(f"/api/tasks/{task_id}/toggle")
    assert resp.json()["active"] is False

    resp = client.delete(f"/api/tasks/{task_id}")
    assert resp.status_code == 204
    resp = client.get(f"/api/tasks/{task_id}")
    assert resp.status_code == 404


def test_update_task_keeps_slug(client):
    resp = client.post(
        "/api/tasks",
        json={"title": "Umbenennen Test", "schedule_type": "one_time", "due_date": "2030-01-01"},
    )
    data = resp.json()
    resp = client.put(
        f"/api/tasks/{data['id']}",
        json={"title": "Umbenennen Test neu", "slug": data["slug"], "schedule_type": "one_time", "due_date": "2030-02-01"},
    )
    assert resp.status_code == 200
    assert resp.json()["slug"] == data["slug"]
    assert resp.json()["title"] == "Umbenennen Test neu"


def test_checklist_import_upsert_by_slug(db):
    from pathlib import Path

    import sys

    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "scripts"))
    import import_checklist

    check_path = root / "data" / "templates" / "checklist.json"
    first = import_checklist.run_import(check_path)
    assert first["created"] > 20

    second = import_checklist.run_import(check_path)
    assert second["created"] == 0
    assert second["updated"] == first["created"]

    tmp = Path("/tmp/opencode/hm-import-test.json")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "placeholder",
        "tasks": [
            {
                "slug": "import-test-aufgabe",
                "title": "Import Test",
                "area": "haus",
                "schedule_type": "annual_window",
                "window_start_month": 3,
                "window_end_month": 4,
                "source": "placeholder",
            }
        ],
    }
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    r1 = import_checklist.run_import(tmp)
    assert r1["created"] == 1

    from app.db import SessionLocal
    from app.models import Task, TaskCompletion

    session = SessionLocal()
    task = session.query(Task).filter(Task.slug == "import-test-aufgabe").one()
    session.add(
        TaskCompletion(task_id=task.id, completed_at=datetime.utcnow(), note="historisch")
    )
    session.commit()
    task_id = task.id
    session.close()

    payload["tasks"][0]["title"] = "Import Test aktualisiert"
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    import_checklist.run_import(tmp)

    session = SessionLocal()
    task = session.query(Task).filter(Task.slug == "import-test-aufgabe").one()
    assert task.id == task_id
    assert task.title == "Import Test aktualisiert"
    completions = session.query(TaskCompletion).filter(TaskCompletion.task_id == task_id).all()
    assert len(completions) == 1
    session.close()
    tmp.unlink(missing_ok=True)


def test_scheduler_run_daily_creates_instances_and_backup(db):
    from app import config
    from app.models import Task

    task = Task(
        slug="scheduler-test-aufgabe",
        title="Scheduler Test",
        schedule_type="annual_window",
        window_start_month=date.today().month,
        window_end_month=min(date.today().month + 1, 12) or 12,
        active=True,
    )
    db.add(task)
    db.commit()

    result = scheduler.run_daily(db)
    assert result["instances_created"] >= 1
    backup = result["backup"]
    assert backup
    assert config.DB_PATH.exists()


def test_scheduler_daily_timer_command_runs():
    from app.services.scheduler import main

    assert main(["--run-daily"]) == 0


def test_interval_next_instance_after_complete(client, db):
    today = date.today()
    resp = client.post(
        "/api/tasks",
        json={
            "title": "Intervall Aufgabe",
            "schedule_type": "interval_days",
            "interval_days": 10,
            "start_date": (today - timedelta(days=10)).isoformat(),
        },
    )
    assert resp.status_code == 201, resp.text
    dash = client.get("/api/maintenance/dashboard").json()
    item = next(i for i in dash["today"] if i["title"] == "Intervall Aufgabe")
    assert item["status"] == "due"

    resp = client.post(f"/api/maintenance/instances/{item['instance_id']}/complete", json={"note": "ok"})
    assert resp.status_code == 200

    instances = client.get("/api/maintenance/instances").json()["instances"]
    nxt = [
        i
        for i in instances
        if i["title"] == "Intervall Aufgabe" and i["status"] == "upcoming"
    ]
    assert len(nxt) == 1
    assert nxt[0]["due_date"] == (today + timedelta(days=10)).isoformat()

    history = client.get("/api/maintenance/history").json()["completions"]
    assert any(c["task_title"] == "Intervall Aufgabe" and c["note"] == "ok" for c in history)
