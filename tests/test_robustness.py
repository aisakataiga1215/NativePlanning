"""Tests for Demo Robustness Fix: datetime keywords, meal triggers, explicit activity handling,
truncation warnings."""
from __future__ import annotations

from datetime import datetime

import pytest

from src.mock_api.venues import VENUES, get_venue
from src.schemas.plan import ItineraryPlan, PlanStep, ScoreBreakdown
from src.schemas.user_intent import UserIntent
from src.services.plan_ranker import rank_plans
from src.tools.wrappers import TraceLog
from src.workflow.intent_parser import parse_free_text
from src.workflow.planner import _apply_opening_hours_gate, generate_plans

_NOW = datetime(2026, 6, 7, 10, 0, 0)  # fixed reference: 2026-06-07 10:00 Saturday

# ---------------------------------------------------------------------------
# Phase 1 — Datetime parser: "今晚" and late-night keywords
# ---------------------------------------------------------------------------


def test_jingwan_parses_to_evening_time():
    """'今晚带孩子出去玩' must not fall back to 10:00 (the unknown default)."""
    intent = parse_free_text("今晚带孩子出去玩", _now=_NOW)
    assert intent.time != "10:00", (
        f"'今晚' must not map to unknown default 10:00; got time={intent.time!r}"
    )
    assert intent.time in ("18:00", "19:00"), (
        f"'今晚' should map to 18:00 or 19:00; got time={intent.time!r}"
    )


def test_jintian_wanshang_parses_night():
    """'今天晚上去吃饭' must be recognized as evening/night time."""
    intent = parse_free_text("今天晚上去吃饭", _now=_NOW)
    assert intent.time in ("18:00", "19:00"), (
        f"'今天晚上' should map to 18:00 or 19:00; got time={intent.time!r}"
    )


def test_shenye_parses_late_night():
    """'深夜想吃夜宵' must map to late-night default time 21:00."""
    intent = parse_free_text("深夜想吃夜宵", _now=_NOW)
    assert intent.time == "21:00", (
        f"'深夜' should map to 21:00; got time={intent.time!r}"
    )


# ---------------------------------------------------------------------------
# Phase 2 — Intent parser: meal-type keywords trigger meal_only + requested_meals
# ---------------------------------------------------------------------------


def test_hotpot_triggers_meal_only():
    """'今晚和朋友吃火锅' must trigger plan_mode='meal_only'."""
    intent = parse_free_text("今晚和朋友吃火锅", _now=_NOW)
    assert intent.plan_mode == "meal_only", (
        f"'吃火锅' must set plan_mode='meal_only'; got {intent.plan_mode!r}"
    )


def test_hotpot_binds_requested_meals():
    """'今晚和朋友吃火锅' must bind requested_meals to include 'hotpot'."""
    intent = parse_free_text("今晚和朋友吃火锅", _now=_NOW)
    assert "hotpot" in (intent.requested_meals or []), (
        f"'吃火锅' must set requested_meals containing 'hotpot'; "
        f"got requested_meals={intent.requested_meals!r}"
    )


def test_hotpot_full_chain_no_business_restaurant():
    """'今晚和朋友吃火锅' full chain: meal_only, no activity step, hotpot restaurant wins."""
    intent = parse_free_text("今晚和朋友吃火锅", _now=_NOW)
    log = TraceLog()
    plans = generate_plans(intent, log)
    assert plans, "Must produce at least one plan for hotpot request"
    ranked = rank_plans(
        plans,
        intent.max_distance_km,
        intent.duration_hours,
        participants=intent.participants or None,
        requested_meals=intent.requested_meals or None,
        soft_preferences=intent.soft_preferences or None,
    )
    assert ranked, "rank_plans must return at least one plan"
    top = ranked[0]
    # Must be meal-only: no activity step
    activity_steps = [s for s in top.steps if s.step_type == "activity"]
    assert not activity_steps, (
        f"Meal-only plan must have no activity steps; got {[s.title for s in activity_steps]!r}"
    )
    # Top restaurant must have hotpot-related tag or name; must NOT be 商务简餐
    from src.mock_api.restaurants import get_restaurant
    rest = get_restaurant(top.restaurant_id) if top.restaurant_id else None
    assert rest is not None, "ranked[0] must have a restaurant"
    rest_tags = set(getattr(rest, "tags", []) or [])
    assert "hotpot" in rest_tags or "火锅" in rest.name, (
        f"Top restaurant must be hotpot type; got name={rest.name!r}, tags={list(rest_tags)!r}"
    )
    _BUSINESS = {"business_casual", "colleagues", "not_too_private"}
    assert not (rest_tags & _BUSINESS), (
        f"Top restaurant must not be business type; tags={list(rest_tags)!r}"
    )


def test_jvcan_triggers_meal_only():
    """'周末和同事聚餐' must trigger plan_mode='meal_only'."""
    intent = parse_free_text("周末和同事聚餐", _now=_NOW)
    assert intent.plan_mode == "meal_only", (
        f"'聚餐' must set plan_mode='meal_only'; got {intent.plan_mode!r}"
    )


# ---------------------------------------------------------------------------
# Phase 2D — "看展" must produce exhibition venue (museum or art_center)
# ---------------------------------------------------------------------------


def test_exhibition_maps_to_art_center():
    """'明天下午和朋友去看展' must extract requested_activities containing 'exhibition'."""
    intent = parse_free_text("明天下午和朋友去看展", _now=_NOW)
    assert "exhibition" in (intent.requested_activities or []), (
        f"'看展' must set requested_activities=['exhibition']; "
        f"got {intent.requested_activities!r}"
    )


def test_exhibition_full_chain_prefers_art_center():
    """'看展' full chain → ranked[0] must be art_center or museum type, not 文创集市."""
    intent = parse_free_text("明天下午和朋友去看展，别太远", _now=_NOW)
    log = TraceLog()
    plans = generate_plans(intent, log)
    assert plans, "Must produce at least one plan for exhibition request"
    ranked = rank_plans(
        plans,
        intent.max_distance_km,
        intent.duration_hours,
        participants=intent.participants or None,
        requested_activities=intent.requested_activities or None,
    )
    assert ranked, "rank_plans must return at least one plan"
    top = ranked[0]
    top_venue = get_venue(top.venue_id) if top.venue_id else None
    venue_type = getattr(top_venue, "type", "")
    assert venue_type in ("art_center", "museum"), (
        f"Exhibition request must rank art_center/museum first; "
        f"got venue_id={top.venue_id!r}, type={venue_type!r}"
    )


def test_exhibition_fallback_gets_warning():
    """When all exhibition venues exceed max_distance, warning must mention 展览 or 替代."""
    intent = UserIntent(
        scenario_type="friends",
        group_size=3,
        time="14:00",
        duration_hours=3.0,
        max_distance_km=0.1,  # too small — all art_center/museum venues are > 0.1km away
        requested_activities=["exhibition"],
    )
    log = TraceLog()
    plans = generate_plans(intent, log)
    ranked = rank_plans(
        plans,
        intent.max_distance_km,
        intent.duration_hours,
        requested_activities=intent.requested_activities or None,
    )
    assert ranked, "Must produce fallback plans even when exhibition is too far"
    all_warns = " ".join(w for w in (ranked[0].warnings or []))
    assert any(kw in all_warns for kw in ("展览", "替代", "距离", "较远")), (
        f"Fallback warning must mention 展览/替代/距离; "
        f"got warnings={ranked[0].warnings!r}"
    )


# ---------------------------------------------------------------------------
# Phase 3A — Zoo early-start retry
# ---------------------------------------------------------------------------


def test_zoo_7am_retries_to_open_time():
    """Zoo request at 07:00 (before 09:00 open) must retry to open_time, produce feasible plan."""
    intent = UserIntent(
        scenario_type="family",
        group_size=3,
        time="07:00",
        duration_hours=5.0,
        max_distance_km=6.0,
        requested_activities=["zoo"],
    )
    log = TraceLog()
    plans = generate_plans(intent, log)
    ranked = rank_plans(
        plans,
        intent.max_distance_km,
        intent.duration_hours,
        requested_activities=intent.requested_activities or None,
    )
    assert ranked, "Must produce at least one plan for zoo request at 07:00"
    top = ranked[0]
    assert top.feasible, (
        f"Zoo plan at 07:00 must be feasible after retry; got feasible={top.feasible!r}"
    )
    top_venue = get_venue(top.venue_id) if top.venue_id else None
    assert getattr(top_venue, "type", "") == "zoo", (
        f"ranked[0] must be a zoo venue; got type={getattr(top_venue, 'type', '')!r}, "
        f"venue_id={top.venue_id!r}"
    )
    has_timing_warn = any(
        ("开门" in w or "调整" in w)
        for w in (top.warnings or [])
    )
    assert has_timing_warn, (
        f"Plan must have a timing adjustment warning (开门/调整); "
        f"got warnings={top.warnings!r}"
    )


# ---------------------------------------------------------------------------
# Phase 3B — Too-far warning for explicit activity
# ---------------------------------------------------------------------------


def test_too_far_explicit_activity_gets_warning():
    """When all zoo venues exceed max_distance, fallback must warn about distance."""
    intent = UserIntent(
        scenario_type="family",
        group_size=3,
        time="10:00",
        duration_hours=5.0,
        max_distance_km=1.0,  # all zoo venues (venue_014, 12km) are > 1km
        requested_activities=["zoo"],
    )
    log = TraceLog()
    plans = generate_plans(intent, log)
    ranked = rank_plans(
        plans,
        intent.max_distance_km,
        intent.duration_hours,
        requested_activities=intent.requested_activities or None,
    )
    assert ranked, "Must produce fallback plans when zoo is too far"
    all_warns = " ".join(w for w in (ranked[0].warnings or []))
    assert any(kw in all_warns for kw in ("距离", "较远", "推荐")), (
        f"Fallback warning must mention 距离/较远/推荐; "
        f"got warnings={ranked[0].warnings!r}"
    )


# ---------------------------------------------------------------------------
# Phase 4 — Truncation warning text fix
# ---------------------------------------------------------------------------


def _make_activity_plan_ending_late(venue_id: str, step_start: str, step_end: str) -> ItineraryPlan:
    """Build a minimal plan with one activity step ending after venue close."""
    return ItineraryPlan(
        id="trunc_test",
        title="Truncation Test",
        scenario_type="family",
        summary="Test",
        steps=[
            PlanStep(
                step_type="activity",
                title="活动",
                location_name="场地",
                start_time=step_start,
                end_time=step_end,
                duration_minutes=60,
                related_entity_id=venue_id,
            ),
        ],
        estimated_total_cost=0.0,
        total_duration_minutes=60,
        score=0.7,
        score_breakdown=ScoreBreakdown(
            distance_score=0.7, time_score=0.7, group_fit_score=0.7,
            restaurant_score=0.7, execution_score=0.9,
        ),
        reasons=[], risks=[], required_actions=[],
        venue_id=venue_id,
    )


def test_truncated_step_no_overshoot_warning():
    """Activity step ending after close → warning must say '调整' NOT '超出营业范围'."""
    # venue_005 (创意艺术中心) closes 21:00; step 20:00-21:30 → truncate to 21:00
    plan = _make_activity_plan_ending_late("venue_005", "20:00", "21:30")
    result = _apply_opening_hours_gate(plan, VENUES)
    warnings_text = " ".join(result.warnings or [])
    assert "超出营业范围" not in warnings_text, (
        f"Truncated step must NOT show '超出营业范围'; got warnings={result.warnings!r}"
    )
    assert any(kw in warnings_text for kw in ("调整", "已将")), (
        f"Truncated step must mention '调整'/'已将'; got warnings={result.warnings!r}"
    )
    assert result.feasible, (
        f"Plan with truncated step (fit=0.7) must still be feasible; got feasible={result.feasible!r}"
    )


def test_truncated_meal_step_adjustment_warning():
    """Meal step ending after restaurant close → warning must say '用餐' and NOT '超出营业范围'."""
    # rest_017 (商场美食广场) closes 23:00; meal step 22:00-23:30 → truncate to 23:00
    from src.mock_api.venues import VENUES as _VENUES
    plan = ItineraryPlan(
        id="trunc_meal_test",
        title="Truncation Meal Test",
        scenario_type="family",
        summary="Test",
        steps=[
            PlanStep(
                step_type="activity",
                title="活动",
                location_name="商场亲子乐园",
                start_time="20:00",
                end_time="22:00",
                duration_minutes=120,
                related_entity_id="venue_018",
            ),
            PlanStep(
                step_type="meal",
                title="用餐",
                location_name="商场美食广场",
                start_time="22:00",
                end_time="23:30",
                duration_minutes=90,
                related_entity_id="rest_017",
            ),
        ],
        estimated_total_cost=0.0,
        total_duration_minutes=210,
        score=0.7,
        score_breakdown=ScoreBreakdown(
            distance_score=0.7, time_score=0.7, group_fit_score=0.7,
            restaurant_score=0.7, execution_score=0.9,
        ),
        reasons=[], risks=[], required_actions=[],
        venue_id="venue_018",
        restaurant_id="rest_017",
    )
    result = _apply_opening_hours_gate(plan, _VENUES)
    warnings_text = " ".join(result.warnings or [])
    assert "超出营业范围" not in warnings_text, (
        f"Truncated meal step must NOT show '超出营业范围'; got warnings={result.warnings!r}"
    )
    assert "用餐" in warnings_text and any(kw in warnings_text for kw in ("调整", "已将")), (
        f"Truncated meal warning must mention '用餐' and '调整'/'已将'; "
        f"got warnings={result.warnings!r}"
    )


# ---------------------------------------------------------------------------
# Phase 5 — Revision regression tests
# ---------------------------------------------------------------------------


def test_revision_restaurant_only_preserves_venue():
    """'换个餐厅' must set revision_scope='restaurant_only'."""
    from src.workflow.revision_parser import apply_revision

    base_intent = UserIntent(
        scenario_type="family",
        group_size=3,
        time="14:00",
        duration_hours=5.0,
        max_distance_km=6.0,
    )
    revised = apply_revision(base_intent, "换个餐厅", current_plan=None)
    assert revised.revision_scope == "restaurant_only", (
        f"'换个餐厅' must set revision_scope='restaurant_only'; "
        f"got {revised.revision_scope!r}"
    )


def test_too_far_revision_explains_switch():
    """When zoo is too far, fallback warning must explain the switch (mention 距离/较远)."""
    # Simulates: original plan had zoo, user says "太远了" → new intent with small max_distance
    intent = UserIntent(
        scenario_type="family",
        group_size=3,
        time="10:00",
        duration_hours=5.0,
        max_distance_km=2.0,  # zoo is 12km → too far
        requested_activities=["zoo"],
    )
    log = TraceLog()
    plans = generate_plans(intent, log)
    ranked = rank_plans(
        plans,
        intent.max_distance_km,
        intent.duration_hours,
        requested_activities=intent.requested_activities or None,
    )
    assert ranked, "Must produce plans when zoo is too far (fallback)"
    top = ranked[0]
    # If venue changed (not zoo), warning must explain
    top_venue = get_venue(top.venue_id) if top.venue_id else None
    if getattr(top_venue, "type", "") != "zoo":
        all_warns = " ".join(w for w in (top.warnings or []))
        assert any(kw in all_warns for kw in ("距离", "较远", "原本想去")), (
            f"When zoo too far and switched venue, warning must explain; "
            f"got venue_type={getattr(top_venue, 'type', '')!r}, warnings={top.warnings!r}"
        )
