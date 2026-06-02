"""Tests for rule-based intent parser (_rule_fallback and helpers)."""
from __future__ import annotations

from datetime import datetime

import pytest

from src.workflow.intent_parser import (
    _classify_age_group,
    _parse_duration_hours,
    _rule_fallback,
)


# ── Age classification ────────────────────────────────────────────────────────

@pytest.mark.parametrize("age,expected", [
    (3,  "young_child"),
    (6,  "young_child"),
    (7,  "child"),
    (12, "child"),
    (13, "teenager"),
    (17, "teenager"),
    (18, "young_adult"),
    (25, "young_adult"),
    (26, "adult"),
    (59, "adult"),
    (60, "senior"),
    (75, "senior"),
])
def test_classify_age_group(age: int, expected: str) -> None:
    assert _classify_age_group(age) == expected


# ── Duration parsing ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("玩一整天",     8.0),
    ("全天活动",     8.0),
    ("整天出去玩",   8.0),
    ("玩一天",       8.0),
    ("玩半天",       4.0),
    ("三个小时",     3.0),
    ("玩3个小时",    3.0),
    ("几个小时",     4.0),
    ("几小时",       4.0),
    ("随便逛逛",     5.0),
])
def test_parse_duration_hours(text: str, expected: float) -> None:
    assert _parse_duration_hours(text) == expected


# ── Distance parsing ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,expected_km", [
    ("离家近一点就好",      6.0),
    ("附近就行",            6.0),
    ("别太远",              6.0),
    ("不用太远",            6.0),
    ("稍微远一点也没关系",  10.0),
    ("远一点都可以",        10.0),
    ("不限距离，越远越好",  20.0),
    ("今天下午去玩",        6.0),   # default when no distance keyword
])
def test_distance_parsing(text: str, expected_km: float) -> None:
    intent = _rule_fallback(text)
    assert intent.max_distance_km == expected_km


# ── Scenario: couple ──────────────────────────────────────────────────────────

def test_rule_fallback_sets_source() -> None:
    intent = _rule_fallback("今天随便出去逛逛")
    assert intent.source == "rule_based"


def test_couple_with_spouse_no_child() -> None:
    intent = _rule_fallback("今天和老婆二人出去走走")
    assert intent.scenario_type == "couple"
    roles = [p.role for p in intent.participants]
    assert "spouse" in roles
    assert "child" not in roles
    # Should NOT recommend kids content
    assert "parent_child" not in intent.activity_preferences
    assert "kids" not in intent.activity_preferences


def test_couple_keywords() -> None:
    intent = _rule_fallback("两人世界，情侣约会")
    assert intent.scenario_type == "couple"


# ── Scenario: family with both spouse and child ───────────────────────────────

def test_family_spouse_and_child() -> None:
    intent = _rule_fallback("今天和老婆孩子出去玩")
    assert intent.scenario_type == "family"
    roles = [p.role for p in intent.participants]
    assert "spouse" in roles
    assert "child" in roles
    assert "parent_child" in intent.activity_preferences


# ── Scenario: seniors ─────────────────────────────────────────────────────────

def test_seniors_two_participants() -> None:
    intent = _rule_fallback("带爷爷奶奶出去散散步")
    assert intent.scenario_type == "family"
    senior_participants = [p for p in intent.participants if p.age_group == "senior"]
    assert len(senior_participants) >= 2, f"Expected ≥2 seniors, got {len(senior_participants)}"
    assert "avoid_long_walk" in intent.hard_constraints
    assert "avoid_long_queue" in intent.hard_constraints
    assert "elderly_friendly" in intent.soft_preferences


# ── Scenario: friends ─────────────────────────────────────────────────────────

def test_friends_scenario() -> None:
    intent = _rule_fallback("和同学聚会")
    assert intent.scenario_type == "friends"
    assert "social" in intent.activity_preferences
    assert "business_casual" not in intent.soft_preferences
    assert "not_too_private" not in intent.soft_preferences


# ── Scenario: colleagues ─────────────────────────────────────────────────────

def test_colleagues_scenario() -> None:
    intent = _rule_fallback("公司团建活动")
    assert intent.scenario_type == "colleagues"
    assert "quiet" in intent.activity_preferences
    assert "group_friendly" in intent.activity_preferences
    assert "not_too_private" in intent.activity_preferences
    assert "business_casual" in intent.soft_preferences
    assert "not_too_private" in intent.soft_preferences


def test_colleagues_differs_from_friends() -> None:
    colleagues = _rule_fallback("同事聚餐团建")
    friends = _rule_fallback("朋友聚会吃饭")
    assert colleagues.scenario_type == "colleagues"
    assert friends.scenario_type == "friends"
    # colleagues has business_casual; friends does not
    assert "business_casual" in colleagues.soft_preferences
    assert "business_casual" not in friends.soft_preferences


# ── Explicit activity requests ────────────────────────────────────────────────

def test_explicit_kids_playground_no_child_adds_warning() -> None:
    intent = _rule_fallback("想带老婆去亲子乐园玩")
    # "老婆" is spouse keyword; no child-presence keywords → scenario=couple
    # "亲子乐园" → requested_activities includes kids_playground
    assert "kids_playground" in intent.requested_activities
    assert len(intent.warnings) > 0
    assert any("儿童家庭" in w for w in intent.warnings)


def test_no_child_no_explicit_request_no_kids_activity() -> None:
    intent = _rule_fallback("今天随便出去逛逛")
    assert "kids_playground" not in intent.activity_preferences
    assert "kids_playground" not in intent.requested_activities
    assert "parent_child" not in intent.activity_preferences


# ── Activity keyword → requested_activities ───────────────────────────────────

def test_dongwuyuan_sets_zoo_activity() -> None:
    intent = _rule_fallback("明天早上带孩子去动物园")
    assert "zoo" in intent.requested_activities


def test_zhuhuan_wancan_sets_western_romantic() -> None:
    intent = _rule_fallback("待会和老婆去吃烛光晚餐")
    assert "western" in intent.requested_meals
    assert "romantic" in intent.soft_preferences


def test_yeshi_sets_night_market_activity() -> None:
    intent = _rule_fallback("今晚去夜市逛逛")
    assert "night_market" in intent.requested_activities


# ── Integration: zoo intent → zoo plan ranks first ───────────────────────────

def test_dongwuyuan_top_plan_is_zoo() -> None:
    from src.services.plan_ranker import rank_plans
    from src.tools.wrappers import TraceLog
    from src.workflow.intent_parser import parse_free_text
    from src.workflow.planner import generate_plans

    now = datetime(2026, 6, 3, 9, 0)
    intent = parse_free_text("明天早上带孩子去动物园", _now=now)
    intent = intent.model_copy(update={"max_distance_km": 15.0})

    log = TraceLog()
    plans = generate_plans(intent, log)
    ranked = rank_plans(
        plans,
        intent.max_distance_km,
        intent.duration_hours,
        participants=intent.participants or None,
        requested_activities=intent.requested_activities or None,
        hard_constraints=intent.hard_constraints or None,
        location_anchor=intent.location_anchor,
        requested_meals=intent.requested_meals or None,
    )
    assert len(ranked) > 0
    zoo_plans = [p for p in ranked if p.venue_id == "venue_014"]
    assert len(zoo_plans) > 0, "Zoo (venue_014) should appear in plans when requested"
    assert ranked[0].venue_id == "venue_014", (
        f"Zoo should be top-ranked; got {ranked[0].venue_id} score={ranked[0].score:.3f}, "
        f"zoo score={zoo_plans[0].score:.3f}"
    )
