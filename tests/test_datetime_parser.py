"""Tests for src/workflow/datetime_parser.py.

All tests use a fixed `now = datetime(2026, 6, 2, 10, 0, 0)` (Tuesday) to
ensure deterministic results regardless of when the test suite is executed.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from src.workflow.datetime_parser import parse_date_time

NOW = datetime(2026, 6, 2, 10, 0, 0)  # Tuesday, 10:00


# ---------------------------------------------------------------------------
# Date resolution
# ---------------------------------------------------------------------------


def test_jintian_wanshang():
    r = parse_date_time("今天晚上出去吃饭", now=NOW)
    assert r.date == "2026-06-02"
    assert r.weekday == "周二"
    assert r.time_period == "night"
    assert r.start_time == "19:00"


def test_mingtian_zaoshang():
    r = parse_date_time("明天早上去公园", now=NOW)
    assert r.date == "2026-06-03"
    assert r.weekday == "周三"
    assert r.time_period == "morning"
    assert r.start_time == "09:00"


def test_houtian():
    r = parse_date_time("后天下午出去逛逛", now=NOW)
    assert r.date == "2026-06-04"
    assert r.time_period == "afternoon"


def test_dahoutian():
    r = parse_date_time("大后天有空", now=NOW)
    assert r.date == "2026-06-05"


def test_30_hao_bangwan():
    r = parse_date_time("30号傍晚想去吃饭", now=NOW)
    assert r.date == "2026-06-30"
    assert r.time_period == "evening"
    assert r.start_time == "17:00"


def test_day_of_month_past_rolls_to_next_month():
    # now is June 2; "1号" already passed → July 1
    r = parse_date_time("1号早上出发", now=NOW)
    assert r.date == "2026-07-01"
    assert r.time_period == "morning"


def test_zhoumo():
    # nearest Saturday from Tuesday June 2 → June 6
    r = parse_date_time("周末去爬山", now=NOW)
    assert r.date == "2026-06-06"


def test_zhouliu():
    # same as 周末
    r = parse_date_time("周六带孩子出去玩", now=NOW)
    assert r.date == "2026-06-06"


def test_zhouri_next_week():
    # Sunday: from Tuesday, next Sunday = June 7
    r = parse_date_time("周日去看展", now=NOW)
    assert r.date == "2026-06-07"


def test_no_date_keyword_defaults_to_today():
    r = parse_date_time("想出去逛逛", now=NOW)
    assert r.date == "2026-06-02"


# ---------------------------------------------------------------------------
# Time period resolution
# ---------------------------------------------------------------------------


def test_zaoshang():
    r = parse_date_time("早上想吃早饭", now=NOW)
    assert r.time_period == "morning"
    assert r.start_time == "09:00"


def test_shangwu():
    r = parse_date_time("上午想出去逛逛", now=NOW)
    assert r.time_period == "morning"
    assert r.start_time == "09:00"


def test_zhongwu():
    r = parse_date_time("中午吃火锅", now=NOW)
    assert r.time_period == "noon"
    assert r.start_time == "12:00"


def test_xiawu():
    r = parse_date_time("下午两点出发", now=NOW)
    assert r.time_period == "afternoon"
    assert r.start_time == "14:00"  # explicit "两点" not parsed; no HHMM pattern


def test_wanshang():
    r = parse_date_time("晚上去夜市", now=NOW)
    assert r.time_period == "night"
    assert r.start_time == "19:00"


def test_bangwan():
    r = parse_date_time("傍晚散步", now=NOW)
    assert r.time_period == "evening"
    assert r.start_time == "17:00"


def test_no_time_period_defaults_to_unknown():
    r = parse_date_time("去动物园", now=NOW)
    assert r.time_period == "unknown"
    assert r.start_time == "10:00"


# ---------------------------------------------------------------------------
# soon keyword
# ---------------------------------------------------------------------------


def test_daihui_now_at_10_00():
    # now=10:00, +30min=10:30 → rounds to 10:30
    r = parse_date_time("待会出发", now=NOW)
    assert r.time_period == "soon"
    assert r.start_time == "10:30"


def test_mashang():
    r = parse_date_time("马上出门", now=NOW)
    assert r.time_period == "soon"
    assert r.start_time == "10:30"


def test_soon_wins_over_candlelight_dinner():
    # "待会" is checked first; "晚餐" should NOT override the period
    r = parse_date_time("待会和老婆出去吃一顿烛光晚餐", now=NOW)
    assert r.time_period == "soon"
    assert r.start_time == "10:30"


def test_soon_rounding_minute_20():
    # now=10:20, +30min=10:50 → minute=50 ≥45 → rounds up to 11:00
    now_20 = datetime(2026, 6, 2, 10, 20, 0)
    r = parse_date_time("一会儿出发", now=now_20)
    assert r.time_period == "soon"
    assert r.start_time == "11:00"


def test_soon_rounding_minute_10():
    # now=10:10, +30min=10:40 → minute=40, 15<=40<45 → rounds to :30 = 10:30
    now_10 = datetime(2026, 6, 2, 10, 10, 0)
    r = parse_date_time("待会出发", now=now_10)
    assert r.time_period == "soon"
    assert r.start_time == "10:30"


# ---------------------------------------------------------------------------
# Explicit time override
# ---------------------------------------------------------------------------


def test_explicit_hhmm_overrides_period_default():
    # "下午" → default 14:00 but explicit 19:30 wins
    r = parse_date_time("下午19:30见面", now=NOW)
    assert r.time_period == "afternoon"
    assert r.start_time == "19:30"


def test_explicit_hhmm_without_period():
    r = parse_date_time("7:30出发", now=NOW)
    assert r.start_time == "07:30"


# ---------------------------------------------------------------------------
# Full combined (date + time)
# ---------------------------------------------------------------------------


def test_mingtian_xiawu():
    r = parse_date_time("明天下午带孩子出去", now=NOW)
    assert r.date == "2026-06-03"
    assert r.time_period == "afternoon"
    assert r.start_time == "14:00"
    assert r.weekday == "周三"


def test_jintian_zhongwu():
    r = parse_date_time("今天中午出去吃饭", now=NOW)
    assert r.date == "2026-06-02"
    assert r.time_period == "noon"
    assert r.start_time == "12:00"
