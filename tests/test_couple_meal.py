"""Tests for couple / candlelight meal ranking (Bug 2)."""
from datetime import datetime

import src.mock_api as mock
from src.schemas.user_intent import UserIntent
from src.services.plan_ranker import _ROMANTIC_TAGS, rank_plans
from src.tools.wrappers import TraceLog
from src.workflow.intent_parser import parse_free_text
from src.workflow.planner import generate_plans


_CANDLELIGHT_INPUT = "待会和老婆去吃烛光晚餐"
_NOW = datetime(2026, 6, 7, 14, 0, 0)  # fixed 2pm — ensures western restaurants are open


# ── Intent parser (rule-based) ────────────────────────────────────────────────

def test_candlelight_plan_mode_meal_only():
    intent = parse_free_text(_CANDLELIGHT_INPUT)
    assert intent.plan_mode == "meal_only", (
        f"Expected plan_mode=='meal_only', got {intent.plan_mode!r}"
    )


def test_candlelight_scenario_couple():
    intent = parse_free_text(_CANDLELIGHT_INPUT)
    assert intent.scenario_type == "couple", (
        f"Expected scenario_type=='couple', got {intent.scenario_type!r}"
    )


def test_candlelight_requested_meals_western():
    intent = parse_free_text(_CANDLELIGHT_INPUT)
    assert "western" in intent.requested_meals, (
        f"Expected 'western' in requested_meals, got {intent.requested_meals!r}"
    )


# ── Full chain ─────────────────────────────────────────────────────────────────

def _run_candlelight_chain(extra_intent_kwargs=None):
    """Parse candlelight input, generate + rank plans, return (ranked, intent)."""
    intent = parse_free_text(_CANDLELIGHT_INPUT, _now=_NOW)
    if extra_intent_kwargs:
        intent = intent.model_copy(update=extra_intent_kwargs)
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
        soft_preferences=intent.soft_preferences or None,
    )
    return ranked, intent


def test_couple_meal_not_business_restaurant():
    """Full chain: candlelight dinner must not pick 商务简餐吧 (rest_009) as top choice."""
    ranked, _ = _run_candlelight_chain()
    assert ranked, "Must produce at least one plan"
    assert ranked[0].restaurant_id != "rest_009", (
        f"ranked[0] must not be rest_009 (business restaurant); "
        f"got {ranked[0].restaurant_id!r}"
    )


def test_couple_meal_top_restaurant_has_romantic_tags():
    """Full chain: top restaurant must have at least one romantic/western/date/couple tag."""
    ranked, _ = _run_candlelight_chain()
    assert ranked and ranked[0].restaurant_id, "Must have a restaurant in ranked[0]"
    top_rest = mock.get_restaurant(ranked[0].restaurant_id)
    assert top_rest is not None, "ranked[0].restaurant_id must exist in mock data"
    rest_tags = set(top_rest.tags or [])
    romantic_or_western = _ROMANTIC_TAGS | {"western"}
    assert rest_tags & romantic_or_western, (
        f"Top restaurant must have romantic/western/couple/date tag; "
        f"restaurant_id={ranked[0].restaurant_id!r}, tags={top_rest.tags!r}"
    )


def test_no_romantic_fallback_gets_warning():
    """When all feasible restaurants are business-tagged, a fallback warning is added."""
    # Construct intent directly to control meal_prefs precisely.
    # With requested_meals=["western"] and soft_preferences=["romantic","candlelight"],
    # search matches: rest_013, rest_010, rest_005, rest_009.
    # Excluding rest_005/rest_010/rest_013 leaves only rest_009 (business tags) feasible.
    intent = UserIntent(
        scenario_type="couple",
        group_size=2,
        plan_mode="meal_only",
        meal_policy="required",
        time="11:00",
        requested_meals=["western"],
        soft_preferences=["romantic", "candlelight"],
        avoid_restaurant_ids=["rest_005", "rest_010", "rest_013"],
    )
    log = TraceLog()
    plans = generate_plans(intent, log)
    ranked = rank_plans(
        plans,
        intent.max_distance_km,
        intent.duration_hours,
        requested_meals=intent.requested_meals or None,
        soft_preferences=intent.soft_preferences or None,
    )
    assert ranked, "Must produce at least one plan even with restrictions"
    top = ranked[0]
    fallback_keywords = ["暂无完全匹配的烛光晚餐方案", "17:00"]
    has_warning = any(
        any(kw in w for kw in fallback_keywords)
        for w in (top.warnings or [])
    )
    assert has_warning, (
        f"Expected fallback warning when only business restaurants are feasible; "
        f"warnings={top.warnings!r}, restaurant_id={top.restaurant_id!r}"
    )
