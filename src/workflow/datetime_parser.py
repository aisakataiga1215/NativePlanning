"""Date/time parsing utilities for Chinese natural language input.

This module is intentionally standalone. It depends only on the Python
standard library, so it can be reused by intent parsing, revision parsing,
or anywhere we need to interpret loose date/time phrases like "明天早上",
"30号傍晚", or "待会".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass
class DateTimeResult:
    """Structured result of parsing a date/time hint from free text."""

    date: str        # "YYYY-MM-DD"
    weekday: str     # "周一"…"周日"
    time_period: str # "morning"|"noon"|"afternoon"|"evening"|"night"|"soon"|"unknown"
    start_time: str  # "HH:MM"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# Ordered list of (cn_name, weekday_index) for matching 周一..周日 in text.
_WEEKDAY_TOKENS = [
    ("周一", 0),
    ("周二", 1),
    ("周三", 2),
    ("周四", 3),
    ("周五", 4),
    ("周六", 5),
    ("周日", 6),
    ("周天", 6),
]

# Time period keywords. Order matters for the *check sequence* only, not for
# precedence within this group: "soon" is handled separately and checked first.
_SOON_KEYWORDS = ["待会", "一会儿", "马上", "现在出发", "立刻"]
_MORNING_KEYWORDS = ["早上", "上午", "早晨", "早点", "一早"]
_NOON_KEYWORDS = ["中午", "午饭", "午餐", "午间"]
_AFTERNOON_KEYWORDS = ["下午", "午后"]
_EVENING_KEYWORDS = ["傍晚", "黄昏", "日落"]
_NIGHT_KEYWORDS = ["晚上", "夜里", "夜间", "晚间", "深夜", "夜晚"]

_DEFAULT_START_TIMES = {
    "morning": "09:00",
    "noon": "12:00",
    "afternoon": "14:00",
    "evening": "17:00",
    "night": "19:00",
}

_UNKNOWN_START_TIME = "10:00"

# Hour past which "today + matching weekday" should roll forward to next week.
# We use the boundary "not yet evening" -> stay today; otherwise next occurrence.
_EVENING_HOUR_BOUNDARY = 17

# Regex patterns
_DAY_OF_MONTH_RE = re.compile(r"(\d{1,2})[号日]")
_EXPLICIT_HHMM_RE = re.compile(r"(?<!\d)(\d{1,2})[:\:：](\d{2})(?!\d)")
_EXPLICIT_HOUR_RE = re.compile(r"(\d{1,2})点(\d{0,2})")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_date_time(text: str, now: datetime | None = None) -> DateTimeResult:
    """Parse a date/time hint from Chinese free text.

    Parameters
    ----------
    text:
        Raw user text. May contain date phrases ("明天", "周六", "30号"),
        time-period keywords ("早上", "晚上"), or explicit times ("19:30",
        "7点半"). Empty / unrecognized input falls back to today + "10:00".
    now:
        Reference "now". Defaults to ``datetime.now()``. Tests inject a
        fixed value to keep behavior deterministic.
    """

    if now is None:
        now = datetime.now()
    if text is None:
        text = ""

    result_date = _resolve_date(text, now)
    weekday = WEEKDAYS[result_date.weekday()]

    time_period, default_start = _resolve_time_period(text, now)
    start_time = _resolve_explicit_time(text) or default_start

    return DateTimeResult(
        date=result_date.strftime("%Y-%m-%d"),
        weekday=weekday,
        time_period=time_period,
        start_time=start_time,
    )


# ---------------------------------------------------------------------------
# Date resolution
# ---------------------------------------------------------------------------


def _resolve_date(text: str, now: datetime):
    """Resolve a calendar date from text. Returns a ``date`` object."""

    today = now.date()

    # Rule 1: 今天/今日/今晚/今天晚上 (all map to today)
    if any(token in text for token in ("今天", "今日", "今晚")):
        return today

    # Rule 2: 明天/明日
    if "明天" in text or "明日" in text:
        return today + timedelta(days=1)

    # Rule 4 must be checked before Rule 3 because "大后天" contains "后天".
    if "大后天" in text:
        return today + timedelta(days=3)

    # Rule 3: 后天
    if "后天" in text:
        return today + timedelta(days=2)

    # Rule 5: weekday / 周末
    weekday_date = _resolve_weekday(text, now)
    if weekday_date is not None:
        return weekday_date

    # Rule 6: N号 / N日
    day_match = _DAY_OF_MONTH_RE.search(text)
    if day_match:
        day = int(day_match.group(1))
        if 1 <= day <= 31:
            return _resolve_day_of_month(day, today)

    # Rule 7: nothing recognised -> today
    return today


def _resolve_weekday(text: str, now: datetime):
    """Return the target date for a 周X / 周末 token, or None if absent."""

    target_index: int | None = None

    # 周末: prefer 周六 (Saturday) as the nearest weekend day.
    if "周末" in text:
        target_index = 5
    else:
        for token, idx in _WEEKDAY_TOKENS:
            if token in text:
                target_index = idx
                break

    if target_index is None:
        return None

    today = now.date()
    today_index = today.weekday()

    if target_index == today_index:
        # Same weekday as today: stay today only if it's not yet evening.
        if now.hour < _EVENING_HOUR_BOUNDARY:
            return today
        return today + timedelta(days=7)

    # Otherwise, walk forward to the next matching weekday (1..6 days ahead).
    delta = (target_index - today_index) % 7
    if delta == 0:
        delta = 7
    return today + timedelta(days=delta)


def _resolve_day_of_month(day: int, today):
    """Return a date for the given day-of-month, choosing this or next month."""

    if day >= today.day:
        # Stay in the current month if possible.
        try:
            return today.replace(day=day)
        except ValueError:
            # Day doesn't exist in this month (e.g. Feb 30); roll to next month.
            pass

    # Next month's Nth day.
    if today.month == 12:
        next_year, next_month = today.year + 1, 1
    else:
        next_year, next_month = today.year, today.month + 1

    try:
        return today.replace(year=next_year, month=next_month, day=day)
    except ValueError:
        # Day doesn't exist next month either; fall back to last valid day.
        # This keeps the function total instead of raising on edge inputs.
        from calendar import monthrange

        last_day = monthrange(next_year, next_month)[1]
        return today.replace(year=next_year, month=next_month, day=last_day)


# ---------------------------------------------------------------------------
# Time period resolution
# ---------------------------------------------------------------------------


def _resolve_time_period(text: str, now: datetime) -> tuple[str, str]:
    """Return (time_period, default_start_time) for the text.

    "soon" keywords are checked first so phrases like "待会和老婆出去吃一顿烛
    光晚餐" classify as ``soon`` rather than ``night``.
    """

    if any(token in text for token in _SOON_KEYWORDS):
        return "soon", _round_to_half_hour(now + timedelta(minutes=30))

    if any(token in text for token in _MORNING_KEYWORDS):
        return "morning", _DEFAULT_START_TIMES["morning"]

    if any(token in text for token in _NOON_KEYWORDS):
        return "noon", _DEFAULT_START_TIMES["noon"]

    if any(token in text for token in _AFTERNOON_KEYWORDS):
        return "afternoon", _DEFAULT_START_TIMES["afternoon"]

    if any(token in text for token in _EVENING_KEYWORDS):
        return "evening", _DEFAULT_START_TIMES["evening"]

    if any(token in text for token in _NIGHT_KEYWORDS):
        return "night", _DEFAULT_START_TIMES["night"]

    return "unknown", _UNKNOWN_START_TIME


def _round_to_half_hour(base: datetime) -> str:
    """Round ``base`` to the nearest :00 or :30 boundary, formatted HH:MM."""

    minute = base.minute
    if minute < 15:
        rounded = base.replace(minute=0, second=0, microsecond=0)
    elif minute < 45:
        rounded = base.replace(minute=30, second=0, microsecond=0)
    else:
        rounded = (base + timedelta(hours=1)).replace(
            minute=0, second=0, microsecond=0
        )
    return rounded.strftime("%H:%M")


# ---------------------------------------------------------------------------
# Explicit time resolution
# ---------------------------------------------------------------------------


def _resolve_explicit_time(text: str) -> str | None:
    """Return an explicit HH:MM string if the text contains one, else None.

    Supports both "19:30" / "19:30" (full-width colon) and "7点30" / "7点".
    A bare "7点" yields "07:00". Invalid hours/minutes are ignored.
    """

    match = _EXPLICIT_HHMM_RE.search(text)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        if _is_valid_clock(hour, minute):
            return f"{hour:02d}:{minute:02d}"

    match = _EXPLICIT_HOUR_RE.search(text)
    if match:
        hour = int(match.group(1))
        minute_str = match.group(2)
        minute = int(minute_str) if minute_str else 0
        if _is_valid_clock(hour, minute):
            return f"{hour:02d}:{minute:02d}"

    return None


def _is_valid_clock(hour: int, minute: int) -> bool:
    return 0 <= hour <= 23 and 0 <= minute <= 59
