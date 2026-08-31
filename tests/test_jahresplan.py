from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from import_checklist import run_import  # noqa: E402


def test_jahresplan_import_count(db):
    result = run_import(ROOT / "data" / "templates" / "jahresplan.json")
    assert result["created"] >= 150
    assert result["updated"] == 0


def test_jahresplan_import_is_idempotent(db):
    first = run_import(ROOT / "data" / "templates" / "jahresplan.json")
    second = run_import(ROOT / "data" / "templates" / "jahresplan.json")
    assert second["created"] == 0
    assert second["updated"] == first["total"]


def test_jahresplan_page_month_view(client):
    resp = client.get("/jahresplan")
    assert resp.status_code == 200
    text = resp.text
    assert "Jahres-Checkliste" in text
    assert "Monatsansicht" in text
    assert "Jahresübersicht" in text


def test_jahresplan_year_view_lists_all_months(client):
    resp = client.get("/jahresplan?view=year")
    assert resp.status_code == 200
    for month in ("Januar", "Februar", "März", "April", "Mai", "Juni",
                  "Juli", "August", "September", "Oktober", "November", "Dezember"):
        assert month in resp.text
    # Badges vorhanden
    assert "⚡ Wichtig" in resp.text
    assert "⏱ Empfohlen" in resp.text
    assert "📌 Optional" in resp.text


def test_jahresplan_priority_filter(client):
    all_resp = client.get("/jahresplan?view=year").text
    high_resp = client.get("/jahresplan?view=year&priority=high").text
    tip_resp = client.get("/jahresplan?view=year&priority=tip").text
    assert "Smart-Tipp" in tip_resp
    assert "💡 Smart-Tipp" in all_resp
    # gefiltert: weniger Einträge als "Alle"
    assert high_resp.count("task-item") < all_resp.count("task-item")


def test_jahresplan_month_actions(client):
    import json as jsonlib
    from datetime import date

    month = date.today().month
    # Aufgabe im aktuellen Monat anlegen
    today_iso = date.today().isoformat()
    resp = client.post(
        "/api/tasks",
        json={"title": "Jahresplan Monats-Test", "area": "hof",
              "schedule_type": "annual_repeat", "repeat_months": [m for m in range(1, 13) if m == month]},
    )
    assert resp.status_code == 201, resp.text

    # Monat vollständig abhaken
    resp = client.post(f"/api/maintenance/complete-month/{month}")
    assert resp.status_code == 200
    assert resp.json()["completed"] >= 1

    # Seite zeigt "erledigt"
    page = client.get(f"/jahresplan?view=month&month={month}").text
    assert "Jahresplan Monats-Test" in page
    assert "✓ erledigt" in page

    # Zurücksetzen öffnet wieder
    resp = client.post(f"/api/maintenance/reopen-month/{month}")
    assert resp.status_code == 200
    assert resp.json()["reopened"] >= 1
    page = client.get(f"/jahresplan?view=month&month={month}").text
    assert "data-instance=" in page

    # Ungültiger Monat
    assert client.post("/api/maintenance/complete-month/13").status_code == 422
    assert client.post("/api/maintenance/complete-month/0").status_code == 422
