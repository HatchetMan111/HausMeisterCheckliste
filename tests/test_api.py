from __future__ import annotations

from datetime import date


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_dashboard_buckets_complete_flow(client):
    today = date.today().isoformat()
    resp = client.post(
        "/api/tasks",
        json={
            "title": "Dashboard Durchlauf",
            "area": "technik",
            "schedule_type": "one_time",
            "due_date": today,
        },
    )
    assert resp.status_code == 201

    dash = client.get("/api/maintenance/dashboard").json()
    item = next(i for i in dash["today"] if i["title"] == "Dashboard Durchlauf")
    assert item["priority"] == "normal"

    resp = client.post(f"/api/maintenance/instances/{item['instance_id']}/complete", json={})
    assert resp.status_code == 200

    dash = client.get("/api/maintenance/dashboard").json()
    assert not any(i["title"] == "Dashboard Durchlauf" for i in dash["today"])

    history = client.get("/api/maintenance/history").json()["completions"]
    assert any(c["task_title"] == "Dashboard Durchlauf" for c in history)

    resp = client.post(f"/api/maintenance/instances/{item['instance_id']}/complete", json={})
    assert resp.status_code == 409


def test_defects_are_inactive(client):
    resp = client.get("/api/defects")
    assert resp.status_code == 501
    resp = client.post("/api/defects")
    assert resp.status_code == 501


def test_settings_roundtrip_encrypted_password(client, db):
    from app.models import Setting
    from app.services.notifications import get_smtp_config

    resp = client.put(
        "/api/settings",
        json={
            "smtp_host": "mail.example.org",
            "smtp_port": 587,
            "smtp_security": "starttls",
            "smtp_user": "wartung",
            "smtp_password": "geheim-123",
            "smtp_from": "wartung@example.org",
            "notify_email": "empfang@example.org",
            "notify_days_ahead": 3,
            "email_enabled": True,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["smtp"]["password_set"] is True
    assert "geheim" not in str(data)

    row = db.query(Setting).filter(Setting.key == "smtp_password").one()
    assert row.value != "geheim-123"
    assert row.value.startswith("gAAAA")

    cfg = get_smtp_config(db)
    assert cfg["password"] == "geheim-123"
    assert cfg["host"] == "mail.example.org"

    resp = client.put("/api/settings", json={"smtp_user": "wartung2"})
    assert resp.status_code == 200
    cfg = get_smtp_config(db)
    assert cfg["password"] == "geheim-123"
    assert cfg["user"] == "wartung2"

    resp = client.put("/api/settings", json={"smtp_clear_password": True})
    assert resp.status_code == 200
    db.expire_all()
    cfg = get_smtp_config(db)
    assert cfg["password"] == ""


def test_settings_validation(client):
    resp = client.put("/api/settings", json={"smtp_security": "bogus"})
    assert resp.status_code == 422
    resp = client.put("/api/settings", json={"smtp_port": 99999})
    assert resp.status_code == 422
    resp = client.put("/api/settings", json={"notify_days_ahead": 999})
    assert resp.status_code == 422


def test_test_email_requires_configuration(client):
    resp = client.put("/api/settings", json={"smtp_host": "", "notify_email": ""})
    assert resp.status_code == 200
    resp = client.post("/api/settings/test-email", json={})
    assert resp.status_code == 400


def test_push_disabled_by_default(client):
    resp = client.get("/api/settings/push/vapid-key")
    assert resp.status_code == 404
    resp = client.post("/api/settings/push/test")
    assert resp.status_code == 404


def test_backup_export_is_zip(client):
    resp = client.get("/api/maintenance/backup/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    assert resp.content[:4] == b"PK\x03\x04"
    assert b"hausmeister.sqlite3" in resp.content


def test_backup_import_restores_state(client):
    resp = client.post(
        "/api/tasks",
        json={"title": "Backup Bestand", "schedule_type": "one_time", "due_date": "2031-01-01"},
    )
    assert resp.status_code == 201

    backup = client.get("/api/maintenance/backup/export").content

    tasks = client.get("/api/tasks").json()["tasks"]
    task_id = next(t["id"] for t in tasks if t["title"] == "Backup Bestand")
    assert client.delete(f"/api/tasks/{task_id}").status_code == 204
    assert not any(
        t["title"] == "Backup Bestand" for t in client.get("/api/tasks").json()["tasks"]
    )

    resp = client.post(
        "/api/maintenance/backup/import",
        files={"file": ("backup.zip", backup, "application/zip")},
    )
    assert resp.status_code == 200, resp.text
    titles = [t["title"] for t in client.get("/api/tasks").json()["tasks"]]
    assert "Backup Bestand" in titles


def test_backup_import_rejects_non_zip(client):
    resp = client.post(
        "/api/maintenance/backup/import",
        files={"file": ("x.zip", b"kein zip", "application/zip")},
    )
    assert resp.status_code == 400


def test_pages_render(client):
    for path in ("/", "/tasks", "/tasks/new", "/history", "/settings", "/help/certificate", "/jahresplan"):
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert "Hausmeister" in resp.text


def test_import_checklist_filename_is_sanitized(client):
    """file.filename darf trotz ../ keine Datei außerhalb des Datenverzeichnisses anlegen."""
    from app import config

    resp = client.post(
        "/api/settings/import-checklist",
        files={"file": ("../../escaped.json", b"{\"tasks\": []}", "application/json")},
    )
    # Der Import selbst scheitert evtl., aber es darf nichts außerhalb liegen:
    outside = config.DATA_DIR.parent / "escaped.json"
    assert not outside.exists(), "Path-Traversal: Datei landete außerhalb des Datenverzeichnisses!"
    stray = list(config.DATA_DIR.parent.glob("escaped*"))
    assert not stray, f"Unerwartete Dateien: {stray}"


def test_root_ca_endpoint_absent_by_default(client):
    resp = client.get("/certs/root-ca.crt")
    assert resp.status_code == 404


def test_annual_window_overdue_after_window(client, db):
    task_payload = {
        "title": "Fenster Jahresaufgabe",
        "schedule_type": "annual_window",
        "window_start_month": 10,
        "window_end_month": 11,
    }
    resp = client.post("/api/tasks", json=task_payload)
    assert resp.status_code == 201

    client.post("/api/maintenance/ensure-instances")
    instances = client.get("/api/maintenance/instances").json()["instances"]
    task_inst = [i for i in instances if i["title"] == "Fenster Jahresaufgabe"]
    assert task_inst, "Instanz für Jahresfenster sollte existieren"

    from datetime import timedelta

    today = date.today()
    current_year_window_start = date(today.year, 10, 1)
    future = current_year_window_start > today
    assert all(
        (i["status"] == "upcoming") == future or i["status"] in ("due", "overdue", "upcoming")
        for i in task_inst
    )

    if today.month >= 12:
        assert all(i["status"] == "overdue" for i in task_inst if i["due_date"] < (today - timedelta(days=31)).isoformat())


def test_dashboard_sections_order(client):
    from datetime import date, timedelta

    client.post(
        "/api/tasks",
        json={"title": "Dringend Sektion", "schedule_type": "one_time",
              "due_date": (date.today() - timedelta(days=3)).isoformat(), "priority": "high"},
    )
    client.post(
        "/api/tasks",
        json={"title": "Demnaechst Sektion", "schedule_type": "one_time",
              "due_date": (date.today() + timedelta(days=20)).isoformat()},
    )
    sections = client.get("/api/maintenance/sections").json()
    assert any(i["title"] == "Dringend Sektion" for i in sections["urgent"])
    assert any(i["title"] == "Demnaechst Sektion" for i in sections["later"])

    buckets = client.get("/api/maintenance/dashboard").json()
    assert any(i["title"] == "Dringend Sektion" for i in buckets["overdue"])


def test_settings_notify_days_ahead_roundtrip(client):
    resp = client.get("/api/settings")
    assert isinstance(resp.json()["notify_days_ahead"], int)
    resp = client.put("/api/settings", json={"notify_days_ahead": 14})
    assert resp.status_code == 200
    assert resp.json()["notify_days_ahead"] == 14
    resp = client.get("/api/settings")
    assert resp.json()["notify_days_ahead"] == 14


def test_history_returns_local_timezone(client, db):
    from datetime import date, datetime

    from app.models import Task, TaskCompletion

    task = Task(slug="tz-test-aufgabe", title="TZ Test", schedule_type="one_time",
                due_date=date(2030, 1, 1), active=True)
    db.add(task)
    db.commit()
    db.add(TaskCompletion(task_id=task.id, completed_at=datetime(2026, 11, 12, 23, 30)))
    db.commit()

    resp = client.get("/api/maintenance/history?limit=1")
    assert resp.status_code == 200
    completed_at = resp.json()["completions"][0]["completed_at"]
    # Europe/Berlin = UTC+1 (im November): 23:30 UTC → 00:30+01:00
    assert completed_at.startswith("2026-11-13T00:30:00+01:00")


def test_search_escapes_like_wildcards(client):
    client.post("/api/tasks", json={"title": "Rauchmelder 100%", "schedule_type": "one_time", "due_date": "2030-01-01"})
    client.post("/api/tasks", json={"title": "Gartenhaus streichen", "schedule_type": "one_time", "due_date": "2030-01-01"})

    resp = client.get("/api/tasks", params={"q": "100%"}).json()
    titles = [t["title"] for t in resp["tasks"]]
    assert "Rauchmelder 100%" in titles

    resp = client.get("/api/tasks", params={"q": "haus"}).json()
    assert any(t["title"] == "Gartenhaus streichen" for t in resp["tasks"])


def test_meta_endpoint(client):
    resp = client.get("/api/meta")
    assert resp.status_code == 200
    data = resp.json()
    slugs = {a["slug"] for a in data["areas"]}
    assert {"haus", "hof", "technik", "garten", "sicherheit"} <= slugs
    assert data["app_name"] == "Hausmeister"
    assert isinstance(data["categories"], list)


def test_import_checklist_rejects_wrong_suffix(client):
    resp = client.post(
        "/api/settings/import-checklist",
        files={"file": ("boese.exe", b"x", "application/octet-stream")},
    )
    assert resp.status_code == 422
