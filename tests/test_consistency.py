"""Consistency Fix tests: timeline reflow, restaurant fallback title/cuisine sync."""
from __future__ import annotations

from datetime import datetime

import pytest

from src.mock_api import get_restaurant
from src.schemas.plan import ItineraryPlan, PlanStep, ScoreBreakdown
from src.schemas.user_intent import UserIntent
from src.services.itinerary_builder import time_to_minutes
from src.services.plan_ranker import rank_plans
from src.tools.wrappers import TraceLog
from src.workflow.constraint_solver import validate_and_repair
from src.workflow.intent_parser import parse_free_text
from src.workflow.planner import generate_plans

_NOW = datetime(2026, 6, 7, 10, 0, 0)


def _hotpot_plan() -> ItineraryPlan:
    """A plan with rest_003 (老街麻辣火锅, available_seats=0) as the restaurant."""
    steps = [
        PlanStep(step_type="travel", title="前往公园", location_name="城市湖边公园",
                 start_time="14:00", end_time="14:20", duration_minutes=20),
        PlanStep(step_type="activity", title="城市湖边公园散步", location_name="城市湖边公园",
                 start_time="14:20", end_time="15:50", duration_minutes=90,
                 related_entity_id="venue_002"),
        PlanStep(step_type="travel", title="前往餐厅", location_name="老街麻辣火锅",
                 start_time="15:50", end_time="16:05", duration_minutes=15),
        PlanStep(step_type="meal", title="在老街麻辣火锅用餐", location_name="老街麻辣火锅",
                 start_time="16:05", end_time="17:35", duration_minutes=90,
                 related_entity_id="rest_003"),
        PlanStep(step_type="return", title="返回", location_name="家",
                 start_time="17:35", end_time="17:50", duration_minutes=15),
    ]
    return ItineraryPlan(
        id="plan_test_hotpot",
        title="城市湖边公园 + 老街麻辣火锅",
        scenario_type="friends",
        summary="14:00 出发，城市湖边公园，之后在老街麻辣火锅用餐",
        steps=steps,
        estimated_total_cost=300.0,
        total_duration_minutes=230,
        score=0.0,
        score_breakdown=ScoreBreakdown(
            distance_score=0.0, time_score=0.0,
            group_fit_score=0.0, restaurant_score=0.0, execution_score=0.0,
        ),
        reasons=[], risks=[], required_actions=["reserve_restaurant"],
        venue_id="venue_002", venue_ids=["venue_002"],
        restaurant_id="rest_003", stop_count=2,
    )


def _zoo_intent() -> UserIntent:
    return UserIntent(
        scenario_type="family",
        group_size=3,
        time="07:00",
        duration_hours=5.0,
        max_distance_km=6.0,  # effective_radius = 6.0 * 2.5 = 15km, covers zoo at 12km
        requested_activities=["zoo"],
    )


# ---------------------------------------------------------------------------
# Bug 2 — Timeline reflow: monotonic steps after zoo open-retry
# ---------------------------------------------------------------------------


def test_timeline_monotonic_after_zoo_open_retry():
    """Zoo at 07:00 (opens 09:00) triggers retry; reflow must produce monotonic timeline."""
    intent = _zoo_intent()
    log = TraceLog()
    plans = generate_plans(intent, log)
    assert plans, "Must produce at least one plan for zoo request"
    ranked = rank_plans(
        plans, intent.max_distance_km, intent.duration_hours,
        requested_activities=intent.requested_activities or None,
    )
    assert ranked, "rank_plans must return at least one plan"
    top = ranked[0]

    for i in range(1, len(top.steps)):
        prev = top.steps[i - 1]
        curr = top.steps[i]
        prev_end_min = time_to_minutes(prev.end_time)
        curr_start_min = time_to_minutes(curr.start_time)
        assert curr_start_min >= prev_end_min, (
            f"Timeline must be monotonic: steps[{i-1}].end_time={prev.end_time} "
            f"> steps[{i}].start_time={curr.start_time}. "
            f"Steps: {[(s.step_type, s.start_time, s.end_time) for s in top.steps]!r}"
        )

    assert top.steps[-1].step_type == "return", (
        f"Last step must be 'return'; got step_type={top.steps[-1].step_type!r}"
    )


def test_step_duration_matches_start_end():
    """After reflow, each step.duration_minutes must match its start_time → end_time span."""
    intent = _zoo_intent()
    log = TraceLog()
    plans = generate_plans(intent, log)
    ranked = rank_plans(
        plans, intent.max_distance_km, intent.duration_hours,
        requested_activities=intent.requested_activities or None,
    )
    assert ranked, "rank_plans must return at least one plan"
    top = ranked[0]

    for step in top.steps:
        d = time_to_minutes(step.end_time) - time_to_minutes(step.start_time)
        if d < 0:
            d += 24 * 60  # cross-midnight
        assert step.duration_minutes == d, (
            f"step '{step.title}' duration_minutes={step.duration_minutes} "
            f"does not match end-start={d} "
            f"({step.start_time}→{step.end_time})"
        )


# ---------------------------------------------------------------------------
# Bug 3 — requested_meals not persisting: exhibition + japanese meal
# ---------------------------------------------------------------------------


def test_exhibition_then_japanese_meal():
    """'看展然后吃日料' must produce art_center/museum venue + japanese restaurant."""
    intent = parse_free_text("明天和老婆去看展，然后吃日料", _now=_NOW)
    log = TraceLog()
    plans = generate_plans(intent, log)
    assert plans, "Must produce at least one plan"
    ranked = rank_plans(
        plans, intent.max_distance_km, intent.duration_hours,
        requested_activities=intent.requested_activities or None,
    )
    assert ranked, "rank_plans must return at least one plan"
    top = ranked[0]

    from src.mock_api.venues import get_venue
    top_venue = get_venue(top.venue_id) if top.venue_id else None
    venue_type = getattr(top_venue, "type", "")
    assert venue_type in ("art_center", "museum"), (
        f"Exhibition request must use art_center or museum; "
        f"got venue_type={venue_type!r}, venue_id={top.venue_id!r}"
    )

    rest = get_restaurant(top.restaurant_id) if top.restaurant_id else None
    _JAPANESE = {"japanese", "日料", "日本料理", "寿司", "居酒屋", "拉面"}
    is_japanese = rest and (
        bool(set(getattr(rest, "tags", []) or []) & _JAPANESE)
        or any(kw in getattr(rest, "name", "") for kw in ("日料", "寿司", "居酒屋", "拉面", "日本"))
    )
    warn_text = " ".join(top.warnings or [])
    assert is_japanese or "日料" in warn_text, (
        f"Restaurant must be japanese type or warning must mention '日料'; "
        f"got restaurant_name={getattr(rest, 'name', 'None')!r}, "
        f"tags={getattr(rest, 'tags', [])!r}, warnings={top.warnings!r}"
    )


# ---------------------------------------------------------------------------
# Bug 1 — Restaurant fallback: same-cuisine preferred
# ---------------------------------------------------------------------------


def test_hotpot_fallback_same_cuisine_preferred():
    """Force hotpot restaurant (rest_003) no seats → fallback is hotpot OR warning explains."""
    plan = _hotpot_plan()
    intent = UserIntent(
        scenario_type="friends", group_size=3,
        time="14:00", duration_hours=4.0, max_distance_km=5.0,
    )
    log = TraceLog()
    repaired = validate_and_repair(plan, intent, log, force_no_seats=True)

    new_rest = get_restaurant(repaired.restaurant_id) if repaired.restaurant_id else None
    _HOTPOT = {"hotpot", "火锅", "麻辣锅"}
    is_hotpot = new_rest and (
        bool(set(getattr(new_rest, "tags", []) or []) & {"hotpot"})
        or any(kw in getattr(new_rest, "name", "") for kw in ("火锅", "麻辣锅"))
    )
    warn_text = " ".join(repaired.warnings or [])
    same_cuisine_warn = "暂无同类" in warn_text or "火锅" in warn_text

    assert is_hotpot or same_cuisine_warn, (
        f"Fallback must be hotpot type or warning must mention same-cuisine info; "
        f"got new_restaurant={getattr(new_rest, 'name', 'None')!r}, "
        f"warnings={repaired.warnings!r}"
    )


def test_restaurant_fallback_title_consistency():
    """After no-seats fallback, plan.title must not contain old restaurant name."""
    plan = _hotpot_plan()
    intent = UserIntent(
        scenario_type="friends", group_size=3,
        time="14:00", duration_hours=4.0, max_distance_km=5.0,
    )
    log = TraceLog()
    repaired = validate_and_repair(plan, intent, log, force_no_seats=True)

    orig_name = "老街麻辣火锅"
    new_rest = get_restaurant(repaired.restaurant_id) if repaired.restaurant_id else None

    assert orig_name not in repaired.title, (
        f"After fallback, title must not contain old name '{orig_name}'; "
        f"got title={repaired.title!r}"
    )
    if new_rest:
        assert new_rest.name in repaired.title, (
            f"After fallback, title must contain new restaurant name '{new_rest.name}'; "
            f"got title={repaired.title!r}"
        )
