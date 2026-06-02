"""Unit tests for src/workflow/revision_parser.py."""
from __future__ import annotations

import pytest

from src.schemas.plan import ItineraryPlan, PlanStep, ScoreBreakdown
from src.schemas.user_intent import UserIntent
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
        restaurant_id=restaurant_id,
    )


def test_too_far_reduces_max_distance_km():
    intent = _base_intent(max_distance_km=5.0)
    result = apply_revision(intent, "太远了")
    assert result.max_distance_km == pytest.approx(3.0)


def test_too_far_floor_at_2km():
    intent = _base_intent(max_distance_km=2.5)
    result = apply_revision(intent, "近一点")
    assert result.max_distance_km >= 2.0


def test_cheap_sets_budget_low():
    intent = _base_intent(budget_preference="medium")
    result = apply_revision(intent, "便宜点")
    assert result.budget_preference == "low"


def test_no_queue_adds_constraint():
    intent = _base_intent(hard_constraints=[])
    result = apply_revision(intent, "不想排队")
    assert "avoid_long_queue" in result.hard_constraints


def test_no_queue_deduped():
    intent = _base_intent(hard_constraints=["avoid_long_queue"])
    result = apply_revision(intent, "不想排队")
    assert result.hard_constraints.count("avoid_long_queue") == 1


def test_tired_adds_walk_and_burden_constraints():
    intent = _base_intent()
    result = apply_revision(intent, "太累了，不想走路")
    assert "avoid_long_walk" in result.hard_constraints
    assert "low_burden" in result.soft_preferences


def test_japanese_food_sets_requested_meals():
    intent = _base_intent()
    result = apply_revision(intent, "想吃日料")
    assert result.requested_meals == ["japanese"]


def test_hotpot_sets_requested_meals():
    intent = _base_intent()
    result = apply_revision(intent, "想吃火锅")
    assert result.requested_meals == ["hotpot"]


def test_bbq_sets_requested_meals():
    intent = _base_intent()
    result = apply_revision(intent, "想吃烤肉")
    assert result.requested_meals == ["bbq"]


def test_exhibition_sets_requested_activity():
    intent = _base_intent()
    result = apply_revision(intent, "想看展览")
    assert result.requested_activities == ["exhibition"]


def test_movie_sets_requested_activity():
    intent = _base_intent()
    result = apply_revision(intent, "想看电影")
    assert result.requested_activities == ["movie"]


def test_board_game_sets_requested_activity():
    intent = _base_intent()
    result = apply_revision(intent, "想玩桌游")
    assert result.requested_activities == ["board_game"]


def test_indoor_adds_indoor_constraint():
    intent = _base_intent(hard_constraints=[])
    result = apply_revision(intent, "室内一点，不想晒太阳")
    assert "indoor" in result.hard_constraints


def test_change_restaurant_adds_avoid_id_with_plan():
    intent = _base_intent()
    plan = _dummy_plan(restaurant_id="rest_003")
    result = apply_revision(intent, "换个餐厅", current_plan=plan)
    assert "rest_003" in result.avoid_restaurant_ids
    assert result.requested_meals == []
    assert result.meal_preferences == []


def test_change_restaurant_no_plan_no_avoid_ids():
    intent = _base_intent()
    result = apply_revision(intent, "换个餐厅")
    assert result.avoid_restaurant_ids == []


def test_change_venue_adds_avoid_id_with_plan():
    intent = _base_intent()
    plan = _dummy_plan(venue_id="venue_002")
    result = apply_revision(intent, "换个场地", current_plan=plan)
    assert "venue_002" in result.avoid_venue_ids
    assert result.requested_activities == []


def test_revise_preserves_unmentioned_fields():
    intent = _base_intent(group_size=4, scenario_type="friends", duration_hours=6.0)
    result = apply_revision(intent, "便宜点")
    assert result.group_size == 4
    assert result.scenario_type == "friends"
    assert result.duration_hours == 6.0


def test_revise_preserves_source():
    intent = _base_intent()
    intent = intent.model_copy(update={"source": "llm"})
    result = apply_revision(intent, "太远了")
    assert result.source == "llm"


def test_too_close_increases_max_distance_km():
    intent = _base_intent(max_distance_km=5.0)
    result = apply_revision(intent, "太近了")
    assert result.max_distance_km == pytest.approx(7.5)


def test_jin_le_increases_max_distance_km():
    intent = _base_intent(max_distance_km=6.0)
    result = apply_revision(intent, "近了，再远一点")
    assert result.max_distance_km > 6.0


def test_you_dian_yuan_reduces_distance():
    intent = _base_intent(max_distance_km=10.0)
    result = apply_revision(intent, "有点远")
    assert result.max_distance_km < 10.0


def test_too_expensive_sets_budget_low():
    intent = _base_intent(budget_preference="medium")
    result = apply_revision(intent, "太贵了")
    assert result.budget_preference == "low"


def test_gui_le_sets_budget_low():
    intent = _base_intent(budget_preference="medium")
    result = apply_revision(intent, "贵了点，换便宜的")
    assert result.budget_preference == "low"


def test_budget_not_matter_sets_high():
    intent = _base_intent(budget_preference="medium")
    result = apply_revision(intent, "贵一点没关系")
    assert result.budget_preference == "high"


def test_ren_tai_duo_adds_queue_constraint():
    intent = _base_intent(hard_constraints=[])
    result = apply_revision(intent, "人太多了不想等")
    assert "avoid_long_queue" in result.hard_constraints


def test_pa_shai_adds_indoor_constraint():
    intent = _base_intent(hard_constraints=[])
    result = apply_revision(intent, "今天太晒了，怕晒")
    assert "indoor" in result.hard_constraints


def test_combined_distance_and_queue():
    intent = _base_intent(max_distance_km=8.0)
    result = apply_revision(intent, "太远了，而且不想排队")
    assert result.max_distance_km < 8.0
    assert "avoid_long_queue" in result.hard_constraints
