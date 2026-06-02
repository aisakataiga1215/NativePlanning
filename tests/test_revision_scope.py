"""Tests for revision_scope behavior in apply_revision and planner dispatch."""
from __future__ import annotations

import pytest

from src.schemas.plan import ItineraryPlan, PlanStep, ScoreBreakdown
from src.schemas.user_intent import UserIntent
from src.tools.wrappers import TraceLog
from src.workflow.revision_parser import apply_revision


def _base_intent(**kwargs) -> UserIntent:
    defaults = dict(
        scenario_type="family",
        group_size=3,
        max_distance_km=5.0,
        duration_hours=4.0,
        budget_preference="medium",
        hard_constraints=[],
        soft_preferences=[],
        requested_activities=[],
        requested_meals=[],
        meal_preferences=[],
        activity_preferences=[],
        avoid_venue_ids=[],
        avoid_restaurant_ids=[],
    )
    defaults.update(kwargs)
    return UserIntent(**defaults)


def _dummy_plan(venue_id: str = "venue_001", restaurant_id: str = "rest_001") -> ItineraryPlan:
    step = PlanStep(
        step_type="activity",
        title="test", start_time="14:00", end_time="16:00",
        location_name="loc", duration_minutes=120,
    )
    return ItineraryPlan(
        id="plan_x",
        title="Test Plan",
        scenario_type="family",
        summary="test",
        steps=[step],
        estimated_total_cost=300.0,
        total_duration_minutes=240,
        score=0.8,
        score_breakdown=ScoreBreakdown(
            distance_score=0.8, time_score=0.8,
            group_fit_score=0.8, restaurant_score=0.8, execution_score=0.8,
        ),
        reasons=["good"],
        risks=[],
        required_actions=[],
        venue_id=venue_id,
        venue_ids=[venue_id],
        restaurant_id=restaurant_id,
    )


# ---------------------------------------------------------------------------
# Scope set correctly by revision type
# ---------------------------------------------------------------------------


def test_change_restaurant_sets_restaurant_scope():
    result = apply_revision(_base_intent(), "换个餐厅", current_plan=_dummy_plan())
    assert result.revision_scope == "restaurant_only"


def test_change_venue_sets_venue_scope():
    result = apply_revision(_base_intent(), "换个场地", current_plan=_dummy_plan())
    assert result.revision_scope == "venue_only"


def test_meal_preference_sets_restaurant_scope():
    result = apply_revision(_base_intent(), "想吃日料")
    assert result.revision_scope == "restaurant_only"


def test_hotpot_sets_restaurant_scope():
    result = apply_revision(_base_intent(), "想吃火锅")
    assert result.revision_scope == "restaurant_only"


def test_bbq_sets_restaurant_scope():
    result = apply_revision(_base_intent(), "想吃烤肉")
    assert result.revision_scope == "restaurant_only"


def test_coffee_sets_restaurant_scope():
    result = apply_revision(_base_intent(), "想喝咖啡下午茶")
    assert result.revision_scope == "restaurant_only"


def test_activity_preference_sets_venue_scope():
    result = apply_revision(_base_intent(), "想看展览")
    assert result.revision_scope == "venue_only"


def test_movie_sets_venue_scope():
    result = apply_revision(_base_intent(), "想看电影")
    assert result.revision_scope == "venue_only"


def test_board_game_sets_venue_scope():
    result = apply_revision(_base_intent(), "想玩桌游")
    assert result.revision_scope == "venue_only"


def test_escape_room_sets_venue_scope():
    result = apply_revision(_base_intent(), "想玩密室逃脱")
    assert result.revision_scope == "venue_only"


# ---------------------------------------------------------------------------
# Global constraint rules must NOT set a scope
# ---------------------------------------------------------------------------


def test_distance_revision_no_scope():
    result = apply_revision(_base_intent(), "太远了")
    assert result.revision_scope == ""


def test_budget_revision_no_scope():
    result = apply_revision(_base_intent(), "太贵了")
    assert result.revision_scope == ""


def test_queue_revision_no_scope():
    result = apply_revision(_base_intent(), "人太多了不想等")
    assert result.revision_scope == ""


def test_indoor_revision_no_scope():
    result = apply_revision(_base_intent(), "今天太晒了怕晒")
    assert result.revision_scope == ""


# ---------------------------------------------------------------------------
# Scope is cleared on subsequent revision (no cross-revision pollution)
# ---------------------------------------------------------------------------


def test_scope_cleared_on_second_revision():
    intent_after_first = apply_revision(_base_intent(), "换个餐厅", current_plan=_dummy_plan())
    assert intent_after_first.revision_scope == "restaurant_only"

    intent_after_second = apply_revision(intent_after_first, "太远了")
    assert intent_after_second.revision_scope == "", (
        "Scope must be cleared when the second revision is a global constraint rule"
    )


def test_scope_cleared_when_switching_scope_type():
    intent_after_restaurant = apply_revision(_base_intent(), "换个餐厅", current_plan=_dummy_plan())
    assert intent_after_restaurant.revision_scope == "restaurant_only"

    intent_after_venue = apply_revision(intent_after_restaurant, "换个场地", current_plan=_dummy_plan())
    assert intent_after_venue.revision_scope == "venue_only"


# ---------------------------------------------------------------------------
# revise_restaurant_only preserves venue_ids
# ---------------------------------------------------------------------------


def test_restaurant_only_preserves_venue_ids():
    from src.workflow.planner import revise_restaurant_only

    intent = _base_intent()
    plan = _dummy_plan(venue_id="venue_001", restaurant_id="rest_001")
    updated_intent = apply_revision(intent, "换个餐厅", current_plan=plan)
    assert updated_intent.revision_scope == "restaurant_only"

    log = TraceLog()
    new_plans = revise_restaurant_only(updated_intent, plan, log)
    assert len(new_plans) > 0
    assert all(
        "venue_001" in p.venue_ids for p in new_plans
    ), f"venue_ids should still contain venue_001: {new_plans[0].venue_ids}"


# ---------------------------------------------------------------------------
# revise_venue_only preserves restaurant_id
# ---------------------------------------------------------------------------


def test_venue_only_preserves_restaurant_id():
    from src.workflow.planner import revise_venue_only

    intent = _base_intent()
    plan = _dummy_plan(venue_id="venue_001", restaurant_id="rest_001")
    updated_intent = apply_revision(intent, "换个场地", current_plan=plan)
    assert updated_intent.revision_scope == "venue_only"

    log = TraceLog()
    new_plans = revise_venue_only(updated_intent, plan, log)
    assert len(new_plans) > 0
    assert all(
        p.restaurant_id == "rest_001" for p in new_plans
    ), f"restaurant_id should remain rest_001: {new_plans[0].restaurant_id}"
