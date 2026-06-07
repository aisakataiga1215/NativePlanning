"""Tests for Execution Result Polish: action labels, skipped status, share message consistency."""
from __future__ import annotations

import os

import pytest

from src.schemas.order import ExecutionResult
from src.schemas.plan import ItineraryPlan, PlanStep, ScoreBreakdown
from src.schemas.user_intent import UserIntent
from src.tools.wrappers import TraceLog
from src.workflow.constraint_solver import validate_and_repair
from src.workflow.executor import execute_plan
from src.workflow.message_agent import (
    _filter_warnings,
    generate_share_message,
)
from src.ui.app import _ACTION_LABELS, _STATUS_LABELS


def _base_plan(restaurant_id: str | None = "rest_003",
               required_actions: list[str] | None = None) -> ItineraryPlan:
    if required_actions is None:
        required_actions = ["reserve_restaurant"] if restaurant_id else []
    steps = [
        PlanStep(step_type="travel", title="前往公园", location_name="城市湖边公园",
                 start_time="14:00", end_time="14:20", duration_minutes=20),
        PlanStep(step_type="activity", title="城市湖边公园散步", location_name="城市湖边公园",
                 start_time="14:20", end_time="15:50", duration_minutes=90,
                 related_entity_id="venue_002"),
    ]
    if restaurant_id:
        steps += [
            PlanStep(step_type="travel", title="前往餐厅", location_name="老街麻辣火锅",
                     start_time="15:50", end_time="16:05", duration_minutes=15),
            PlanStep(step_type="meal", title="在老街麻辣火锅用餐", location_name="老街麻辣火锅",
                     start_time="16:05", end_time="17:35", duration_minutes=90,
                     related_entity_id=restaurant_id),
        ]
    steps.append(
        PlanStep(step_type="return", title="返回", location_name="家",
                 start_time="17:35", end_time="17:50", duration_minutes=15)
    )
    return ItineraryPlan(
        id="plan_test",
        title="城市湖边公园 + 老街麻辣火锅" if restaurant_id else "城市湖边公园",
        scenario_type="friends",
        summary="14:00 出发，城市湖边公园",
        steps=steps,
        estimated_total_cost=300.0,
        total_duration_minutes=230,
        score=0.5,
        score_breakdown=ScoreBreakdown(
            distance_score=0.5, time_score=0.5,
            group_fit_score=0.5, restaurant_score=0.5, execution_score=0.5,
        ),
        reasons=[], risks=[],
        required_actions=required_actions,
        venue_id="venue_002", venue_ids=["venue_002"],
        restaurant_id=restaurant_id,
        stop_count=2,
    )


def _base_intent(group_size: int = 3) -> UserIntent:
    return UserIntent(
        scenario_type="friends",
        group_size=group_size,
        time="14:00",
        duration_hours=4.0,
        max_distance_km=5.0,
    )


# ── Phase 1: Action / status labels ──────────────────────────────────────────

def test_action_labels_chinese():
    assert _ACTION_LABELS["book_venue"] == "门票预订"
    assert _ACTION_LABELS["reserve_restaurant"] == "餐厅预约"
    assert _ACTION_LABELS.get("order_food") == "点餐/套餐"
    assert _STATUS_LABELS["success"] == "✅ 成功"
    assert _STATUS_LABELS["failed"] == "❌ 失败"
    assert _STATUS_LABELS["skipped"] == "⏭ 跳过"


# ── Phase 2: Executor skipped ────────────────────────────────────────────────

def test_skipped_status_no_restaurant():
    """reserve_restaurant in required_actions but restaurant_id=None → skipped result."""
    plan = _base_plan(restaurant_id=None, required_actions=["reserve_restaurant"])
    intent = _base_intent()
    log = TraceLog()
    results = execute_plan(plan, intent, log)
    reserve = next((r for r in results if r.action_type == "reserve_restaurant"), None)
    assert reserve is not None, "Must emit a result for reserve_restaurant"
    assert reserve.status == "skipped", f"Expected skipped, got {reserve.status!r}"


def test_no_required_actions_produces_no_results():
    """Normal no-meal plan with empty required_actions → no results at all."""
    plan = _base_plan(restaurant_id=None, required_actions=[])
    intent = _base_intent()
    log = TraceLog()
    results = execute_plan(plan, intent, log)
    assert results == [], f"Expected empty results, got {results!r}"


# ── Phase 3: No-meal share message ────────────────────────────────────────────

def test_no_meal_share_excludes_restaurant_keywords():
    """No-meal plan: share message must not contain meal-related words."""
    plan = _base_plan(restaurant_id=None, required_actions=[])
    intent = _base_intent()
    os.environ.pop("OPENAI_API_KEY", None)
    share = generate_share_message(plan, [], intent)
    msg = share.message
    for kw in ("餐厅", "用餐", "预约餐厅", "吃饭"):
        assert kw not in msg, (
            f"No-meal share message must not contain {kw!r}; got message={msg!r}"
        )


# ── Phase 4: Fallback consistency ────────────────────────────────────────────

def test_fallback_share_consistent_with_current_plan():
    """After hotpot fallback, share message references new restaurant name, not old."""
    from src.schemas.plan import ItineraryPlan, PlanStep, ScoreBreakdown
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
    hotpot_plan = ItineraryPlan(
        id="plan_hotpot", title="城市湖边公园 + 老街麻辣火锅",
        scenario_type="friends", summary="14:00 出发，城市湖边公园，之后在老街麻辣火锅用餐",
        steps=steps, estimated_total_cost=300.0, total_duration_minutes=230, score=0.5,
        score_breakdown=ScoreBreakdown(
            distance_score=0.5, time_score=0.5,
            group_fit_score=0.5, restaurant_score=0.5, execution_score=0.5,
        ),
        reasons=[], risks=[], required_actions=["reserve_restaurant"],
        venue_id="venue_002", venue_ids=["venue_002"], restaurant_id="rest_003", stop_count=2,
    )
    intent = _base_intent()
    log = TraceLog()
    repaired = validate_and_repair(hotpot_plan, intent, log, force_no_seats=True)

    import src.mock_api as mock
    new_rest = mock.get_restaurant(repaired.restaurant_id)
    new_name = new_rest.name if new_rest else repaired.restaurant_id

    os.environ.pop("OPENAI_API_KEY", None)
    share = generate_share_message(repaired, [], intent)
    msg = share.message

    assert new_name in msg, (
        f"Share message must contain new restaurant name '{new_name}'; got {msg!r}"
    )
    # Old name is allowed in the 备注/warning section (explains the switch) but
    # the main body (before 备注) must not mention the old restaurant.
    main_body = msg.split("\n备注：")[0]
    assert "老街麻辣火锅" not in main_body, (
        f"Main body of share message must not mention old restaurant; got main_body={main_body!r}"
    )
    assert "已切换至" in msg, (
        f"Share message must include switch explanation warning; got {msg!r}"
    )


# ── Phase 5: Return time ────────────────────────────────────────────────────

def test_return_time_in_share_message():
    """Family plan: share message contains the return step's end_time."""
    plan = _base_plan(restaurant_id="rest_003")
    intent = UserIntent(
        scenario_type="family", group_size=3,
        time="14:00", duration_hours=4.0, max_distance_km=5.0,
    )
    return_step = next((s for s in plan.steps if s.step_type == "return"), None)
    assert return_step is not None
    expected_time = return_step.end_time

    os.environ.pop("OPENAI_API_KEY", None)
    share = generate_share_message(plan, [], intent)
    assert expected_time in share.message, (
        f"Share message must contain return time {expected_time!r}; got {share.message!r}"
    )


# ── Phase 6: Filter warnings ────────────────────────────────────────────────

def test_filter_warnings_keeps_switch_explanations():
    """Warnings with '已切换至' are always kept, even if they name an old entity."""
    switch_warn = "⚠ 老街麻辣火锅暂无空位，已切换至「新餐厅」"
    result = _filter_warnings([switch_warn], None, None)
    assert result == [switch_warn], (
        f"Switch-explanation warning must not be filtered; got {result!r}"
    )


def test_filter_warnings_drops_stale_entity():
    """Warning naming a stale entity (not in current plan) without '已切换至' is dropped."""
    stale_warn = "⚠ 场馆「旧展馆」暂时关闭"
    current_warn = "⚠ 当前行程超出预期时间"
    result = _filter_warnings([stale_warn, current_warn], None, None)
    assert stale_warn not in result, f"Stale entity warning must be dropped; got {result!r}"
    assert current_warn in result, f"No-entity warning must be kept; got {result!r}"
