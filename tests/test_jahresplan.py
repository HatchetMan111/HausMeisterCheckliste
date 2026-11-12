from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from import_checklist import run_import  # noqa: E402


def test_jahresplan_import_count(db):
    result = run_import(ROOT / "data" / "templates" / "jahresplan.json")
    assert result["total"] == 156
    assert result["created"] + result["updated"] == 156


def test_jahresplan_import_is_idempotent(db):
    first = run_import(ROOT / "data" / "templates" / "jahresplan.json")
    second = run_import(ROOT / "data" / "templates" / "jahresplan.json")
    assert second["created"] == 0
    assert second["updated"] == first["total"]


def test_jahresplan_month_view_defaults_to_current_month(client):
    from datetime import date

    resp = client.get("/api/maintenance/jahresplan")
    assert resp.status_code == 200
    data = resp.json()
    assert data["view"] == "month"
    assert data["month"] == date.today().month
    assert len(data["months"]) == 1


def test_jahresplan_year_view_lists_all_months(client):
    resp = client.get("/api/maintenance/jahresplan?view=year")
    assert resp.status_code == 200
    data = resp.json()
    assert data["view"] == "year"
    months = [m["name"] for m in data["months"]]
    for month in ("Januar", "Februar", "März", "April", "Mai", "Juni",
                  "Juli", "August", "September", "Oktober", "November", "Dezember"):
        assert month in months
    assert len(data["months"]) == 12
    # Prioritäts-Badge-Daten sind in jedem Eintrag vorhanden
    items = [i for m in data["months"] for i in m["items"]]
    assert items, "Jahresplan-Bibliothek sollte Einträge liefern"
    assert all("priority" in i for i in items)
    assert any(i["priority"] == "high" for i in items)
    assert any(i["priority"] == "normal" for i in items)
    assert any(i["priority"] == "low" for i in items)


def test_jahresplan_priority_filter(client):
    all_data = client.get("/api/maintenance/jahresplan?view=year").json()
    high_data = client.get("/api/maintenance/jahresplan?view=year&priority=high").json()
    tip_data = client.get("/api/maintenance/jahresplan?view=year&priority=tip").json()

    all_items = [i for m in all_data["months"] for i in m["items"]]
    high_items = [i for m in high_data["months"] for i in m["items"]]
    assert high_items and all(i["priority"] == "high" for i in high_items)
    assert len(high_items) < len(all_items)

    tip_items = [i for m in tip_data["months"] for i in m["items"]]
    assert tip_items
    assert all(i["is_tip"] for i in tip_items), "tip-Filter darf nur Smart-Tipps liefern"


def test_jahresplan_month_actions(client):
    from datetime import date

    month = date.today().month
    # Aufgabe im aktuellen Monat anlegen
    resp = client.post(
        "/api/tasks",
        json={"title": "Jahresplan Monats-Test", "area": "hof",
              "schedule_type": "annual_repeat", "repeat_months": [month]},
    )
    assert resp.status_code == 201, resp.text

    # Monat vollständig abhaken
    resp = client.post(f"/api/maintenance/complete-month/{month}")
    assert resp.status_code == 200
    assert resp.json()["completed"] >= 1

    page = client.get(f"/api/maintenance/jahresplan?view=month&month={month}").json()
    mrow = next(m for m in page["months"] if m["month"] == month)
    item = next(i for i in mrow["items"] if i["title"] == "Jahresplan Monats-Test")
    assert item["status"] == "done"

    # Zurücksetzen öffnet wieder
    resp = client.post(f"/api/maintenance/reopen-month/{month}")
    assert resp.status_code == 200
    assert resp.json()["reopened"] >= 1
    page = client.get(f"/api/maintenance/jahresplan?view=month&month={month}").json()
    mrow = next(m for m in page["months"] if m["month"] == month)
    item = next(i for i in mrow["items"] if i["title"] == "Jahresplan Monats-Test")
    assert item["status"] == "open"
    assert item["open_id"], "Nach Reopen sollte eine offene Instanz existieren"

    # Ungültiger Monat
    assert client.post("/api/maintenance/complete-month/13").status_code == 422
    assert client.post("/api/maintenance/complete-month/0").status_code == 422


def test_jahresplan_totals(client):
    data = client.get("/api/maintenance/jahresplan?view=year").json()
    items = [i for m in data["months"] for i in m["items"]]
    assert data["total"] == len(items) + len(data["running"])
    assert data["done_total"] == sum(1 for i in items if i["status"] == "done") + sum(
        1 for i in data["running"] if i["status"] == "done"
    )
    assert data["open_total"] == data["total"] - data["done_total"]
