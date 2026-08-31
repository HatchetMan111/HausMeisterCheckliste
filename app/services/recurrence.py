from __future__ import annotations

import calendar
from datetime import date, timedelta

SCHEDULE_TYPES = ("one_time", "interval_days", "annual_window", "annual_repeat")


class Schedulable:
    schedule_type: str
    interval_days: int | None
    window_start_month: int | None
    window_end_month: int | None
    repeat_months: list | None
    repeat_day: int
    due_date: date | None
    start_date: date | None


def last_day_of_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def parse_repeat_months(value) -> list[int]:
    if value is None:
        return []
    if isinstance(value, str):
        months: list[int] = []
        for part in value.replace(",", ";").split(";"):
            part = part.strip()
            if not part:
                continue
            try:
                months.append(int(part))
            except ValueError:
                continue
        return months
    months = []
    for m in value:
        try:
            months.append(int(m))
        except (TypeError, ValueError):
            continue
    return months


def validate_schedule(data: dict) -> list[str]:
    errors: list[str] = []
    st = data.get("schedule_type", "one_time")
    if st not in SCHEDULE_TYPES:
        return [f"Unbekannter Zeitplan-Typ: {st} (erlaubt: {', '.join(SCHEDULE_TYPES)})"]
    if st == "one_time":
        if not data.get("due_date"):
            errors.append("one_time erfordert ein festes Fälligkeitsdatum (due_date).")
    elif st == "interval_days":
        interval = data.get("interval_days") or 0
        if interval < 1:
            errors.append("interval_days erfordert interval_days >= 1.")
    elif st == "annual_window":
        start_m, end_m = data.get("window_start_month"), data.get("window_end_month")
        for label, m in (("window_start_month", start_m), ("window_end_month", end_m)):
            if m is None or not 1 <= int(m) <= 12:
                errors.append(f"annual_window erfordert {label} zwischen 1 und 12.")
    elif st == "annual_repeat":
        months = parse_repeat_months(data.get("repeat_months"))
        if not months:
            errors.append("annual_repeat erfordert repeat_months (Liste 1–12).")
        elif not all(1 <= m <= 12 for m in months):
            errors.append("repeat_months muss Werte zwischen 1 und 12 enthalten.")
    return errors


def window_bounds(task, year: int) -> tuple[date, date]:
    start_m = int(task.window_start_month or 1)
    end_m = int(task.window_end_month or 12)
    if 1 <= start_m <= 12 and 1 <= end_m <= 12:
        if start_m <= end_m:
            return date(year, start_m, 1), date(year, end_m, last_day_of_month(year, end_m))
        return (
            date(year, start_m, 1),
            date(year + 1, end_m, last_day_of_month(year + 1, end_m)),
        )
    return date(year, 1, 1), date(year, 12, 31)


def occurrences(task, from_date: date, to_date: date) -> list[date]:
    if to_date < from_date:
        return []
    st = task.schedule_type
    out: list[date] = []
    if st == "one_time":
        d = task.due_date
        return [d] if (d and from_date <= d <= to_date) else []
    if st == "annual_window":
        for year in range(from_date.year - 1, to_date.year + 2):
            start, _ = window_bounds(task, year)
            if from_date <= start <= to_date:
                out.append(start)
        return out
    if st == "annual_repeat":
        for year in range(from_date.year, to_date.year + 1):
            for m in parse_repeat_months(task.repeat_months):
                if not 1 <= m <= 12:
                    continue
                day = min(max(int(task.repeat_day or 1), 1), last_day_of_month(year, m))
                d = date(year, m, day)
                if from_date <= d <= to_date:
                    out.append(d)
        return out
    if st == "interval_days":
        interval = max(int(task.interval_days or 1), 1)
        anchor = task.start_date or from_date
        if anchor >= from_date:
            first = anchor
        else:
            delta = (from_date - anchor).days
            steps = delta // interval + (1 if delta % interval else 0)
            first = anchor + timedelta(days=steps * interval)
        d = first
        while d <= to_date:
            out.append(d)
            d += timedelta(days=interval)
        return out
    return out


def status_for(task, instance, today: date) -> str:
    if instance.status in ("done", "skipped"):
        return instance.status
    if task.schedule_type == "annual_window":
        _, end = window_bounds(task, instance.year)
        if today > end:
            return "overdue"
        if today >= instance.due_date:
            return "due"
        return "upcoming"
    if instance.due_date < today:
        return "overdue"
    if instance.due_date == today:
        return "due"
    return "upcoming"


def human_schedule(task) -> str:
    st = task.schedule_type
    if st == "one_time":
        return f"Einmalig am {task.due_date.isoformat()}" if task.due_date else "Einmalig (ohne Datum)"
    if st == "interval_days":
        return f"Alle {task.interval_days} Tage"
    if st == "annual_window":
        months = ["Jan", "Feb", "Mrz", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
        s = int(task.window_start_month or 1)
        e = int(task.window_end_month or 12)
        return f"Jährlich, Fenster {months[s - 1]}–{months[e - 1]}"
    if st == "annual_repeat":
        months = ["Jan", "Feb", "Mrz", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
        ms = parse_repeat_months(task.repeat_months)
        return "Jedes Jahr: " + ", ".join(months[m - 1] for m in sorted(ms))
    return st
