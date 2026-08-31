from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

from app.services import recurrence


def make_task(**kwargs):
    defaults = {
        "schedule_type": "one_time",
        "interval_days": None,
        "window_start_month": None,
        "window_end_month": None,
        "repeat_months": None,
        "repeat_day": 1,
        "due_date": None,
        "start_date": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_annual_window_within_window_is_due():
    task = make_task(schedule_type="annual_window", window_start_month=10, window_end_month=11)
    today = date(2026, 10, 15)
    assert recurrence.validate_schedule({**task.__dict__}) == []
    assert recurrence.window_bounds(task, 2026) == (date(2026, 10, 1), date(2026, 11, 30))
    assert recurrence.status_for(task, SimpleNamespace(due_date=date(2026, 10, 1), year=2026, status="open"), today) == "due"


def test_annual_window_after_end_is_overdue():
    task = make_task(schedule_type="annual_window", window_start_month=10, window_end_month=11)
    today = date(2026, 12, 5)
    assert recurrence.status_for(task, SimpleNamespace(due_date=date(2026, 10, 1), year=2026, status="open"), today) == "overdue"


def test_annual_window_before_start_is_upcoming():
    task = make_task(schedule_type="annual_window", window_start_month=10, window_end_month=11)
    today = date(2026, 6, 1)
    assert recurrence.status_for(task, SimpleNamespace(due_date=date(2026, 10, 1), year=2026, status="open"), today) == "upcoming"


def test_annual_window_wrapped_around_year():
    task = make_task(schedule_type="annual_window", window_start_month=11, window_end_month=2)
    start, end = recurrence.window_bounds(task, 2026)
    assert start == date(2026, 11, 1)
    assert end == date(2027, 2, 28)


def test_annual_repeat_creates_own_instance_per_month():
    task = make_task(schedule_type="annual_repeat", repeat_months=[1, 4, 7, 10])
    occ = recurrence.occurrences(task, date(2026, 1, 1), date(2026, 12, 31))
    assert occ == [date(2026, 1, 1), date(2026, 4, 1), date(2026, 7, 1), date(2026, 10, 1)]


def test_annual_repeat_respects_repeat_day():
    task = make_task(schedule_type="annual_repeat", repeat_months=[2], repeat_day=15)
    occ = recurrence.occurrences(task, date(2026, 1, 1), date(2026, 12, 31))
    assert occ == [date(2026, 2, 15)]


def test_one_time_occurs_once():
    task = make_task(schedule_type="one_time", due_date=date(2026, 5, 1))
    assert recurrence.occurrences(task, date(2026, 1, 1), date(2026, 12, 31)) == [date(2026, 5, 1)]
    assert recurrence.occurrences(task, date(2027, 1, 1), date(2027, 12, 31)) == []


def test_interval_days_is_calendar_independent():
    task = make_task(schedule_type="interval_days", interval_days=90, start_date=date(2026, 1, 10))
    occ = recurrence.occurrences(task, date(2026, 1, 1), date(2026, 12, 31))
    assert occ[0] == date(2026, 1, 10)
    assert occ[1] == date(2026, 1, 10) + timedelta(days=90)
    assert all((b - a).days == 90 for a, b in zip(occ, occ[1:]))


def test_interval_days_first_occurrence_after_start_in_future():
    task = make_task(schedule_type="interval_days", interval_days=30, start_date=date(2026, 12, 24))
    occ = recurrence.occurrences(task, date(2026, 6, 1), date(2027, 6, 1))
    assert occ[0] == date(2026, 12, 24)


def test_interval_validation_requires_positive_interval():
    errors = recurrence.validate_schedule({"schedule_type": "interval_days", "interval_days": 0})
    assert errors
    assert recurrence.validate_schedule({"schedule_type": "interval_days", "interval_days": 90}) == []


def test_annual_repeat_validation_requires_months():
    assert recurrence.validate_schedule({"schedule_type": "annual_repeat"}) != []
    assert recurrence.validate_schedule({"schedule_type": "annual_repeat", "repeat_months": [3, 6]}) == []
    assert recurrence.validate_schedule({"schedule_type": "annual_repeat", "repeat_months": [13]}) != []


def test_annual_window_validation_requires_months():
    assert recurrence.validate_schedule({"schedule_type": "annual_window", "window_start_month": 10}) != []
    ok = recurrence.validate_schedule({"schedule_type": "annual_window", "window_start_month": 10, "window_end_month": 11})
    assert ok == []


def test_status_done_and_skipped():
    task = make_task(schedule_type="one_time", due_date=date(2026, 5, 1))
    for status in ("done", "skipped"):
        assert recurrence.status_for(task, SimpleNamespace(due_date=date(2026, 5, 1), year=2026, status=status), date(2026, 5, 2)) == status


def test_human_schedule_texts():
    assert "90 Tage" in recurrence.human_schedule(make_task(schedule_type="interval_days", interval_days=90))
    assert "Okt" in recurrence.human_schedule(make_task(schedule_type="annual_window", window_start_month=10, window_end_month=11))
    text = recurrence.human_schedule(make_task(schedule_type="annual_repeat", repeat_months=[3, 6, 9, 12]))
    for month in ("Mrz", "Jun", "Sep", "Dez"):
        assert month in text
    assert "2026-05-01" in recurrence.human_schedule(make_task(schedule_type="one_time", due_date=date(2026, 5, 1)))
