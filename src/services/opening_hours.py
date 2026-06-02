"""Opening hours utilities.

All times are HH:MM strings. Midnight-crossing hours (e.g., 18:00-02:00) are
supported by detecting when close_time < open_time and adding 1440 to
close_minutes (and check / step minutes when they fall in the after-midnight
half of the window).
"""
from __future__ import annotations


def _to_minutes(hhmm: str) -> int:
    """Convert 'HH:MM' to total minutes since midnight."""
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def is_open_at(open_time: str, close_time: str, check_time: str) -> bool:
    """Return True if check_time is within [open_time, close_time).

    Supports midnight-crossing hours (e.g., open=18:00, close=02:00).
    """
    o = _to_minutes(open_time)
    c = _to_minutes(close_time)
    t = _to_minutes(check_time)
    if c < o:  # crosses midnight
        c += 1440
        if t < o:
            t += 1440
    return o <= t < c


def is_open_during(
    open_time: str,
    close_time: str,
    step_start: str,
    step_end: str,
) -> bool:
    """Return True only if the ENTIRE step is within operating hours.

    A step that starts before close but ends after close returns False.
    Supports midnight-crossing hours.

    Examples:
        zoo 09:00-17:30, step 16:30-19:00 -> False (ends after 17:30)
        zoo 09:00-17:30, step 10:00-12:00 -> True
        ramen 18:00-02:00, step 23:30-00:30 -> True (both within 18:00-02:00)
        ramen 18:00-02:00, step 01:00-03:00 -> False (ends after 02:00)
    """
    o = _to_minutes(open_time)
    c = _to_minutes(close_time)
    s = _to_minutes(step_start)
    e = _to_minutes(step_end)
    if c < o:  # crosses midnight
        c += 1440
        if s < o:
            s += 1440
        if e < o:
            e += 1440
    return o <= s and e <= c


def opening_hours_warning(
    venue_name: str,
    open_time: str,
    close_time: str,
    step_start: str,
    step_end: str,
) -> str:
    """Return a human-readable warning when a step falls outside operating hours."""
    return (
        f"⚠️ {venue_name} 营业时间 {open_time}–{close_time}，"
        f"活动时段 {step_start}–{step_end} 超出营业范围"
    )
