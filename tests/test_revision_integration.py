"""Integration tests for the plan revision loop."""
from __future__ import annotations

import pytest

from src.schemas.plan import ItineraryPlan, PlanStep, ScoreBreakdown
from src.schemas.user_intent import UserIntent
from src.tools.wrappers import TraceLog
from src.workflow.constraint_solver import validate_and_repair
from src.workflow.planner import generate_candidate_plans
from src.workflow.revision_parser import apply_revision
from src.services.plan_ranker import rank_plans


def _family_intent() -> UserIntent:
    return UserIntent(
        scenario_type="family",
        group_size=3,
        max_distance_km=5.0,
        duration_hours=4.0,
    )


def _get_best_plan(intent: UserIntent) -> ItineraryPlan:
    log = TraceLog()
    plans = generate_candidate_plans(intent, log)
    repaired = [validate_and_repair(p, intent, log) for p in plans]
    ranked = rank_plans(
        repaired, intent.max_distance_km, intent.duration_hours,
        participants=intent.participants or None,
    )
    return ranked[0]


def test_revise_returns_generate_response_shape():
    intent = _family_intent()
    plan = _get_best_plan(intent)
    updated_intent = apply_revision(intent, "太远了", current_plan=plan)

    log = TraceLog()
    plans = generate_candidate_plans(updated_intent, log)
    repaired = [validate_and_repair(p, updated_intent, log) for p in plans]
    ranked = rank_plans(repaired, updated_intent.max_distance_km, updated_intent.duration_hours)

    assert len(ranked) >= 1
    assert ranked[0].score > 0
    assert updated_intent.max_distance_km < intent.max_distance_km


def test_revise_avoids_current_restaurant():
    intent = _family_intent()
    plan = _get_best_plan(intent)
    original_restaurant_id = plan.restaurant_id

    updated_intent = apply_revision(intent, "换个餐厅", current_plan=plan)
    assert original_restaurant_id in updated_intent.avoid_restaurant_ids

    log = TraceLog()
    plans = generate_candidate_plans(updated_intent, log)
    repaired = [validate_and_repair(p, updated_intent, log) for p in plans]
    ranked = rank_plans(repaired, updated_intent.max_distance_km, updated_intent.duration_hours)

    if ranked:
        for p in ranked:
            assert p.restaurant_id != original_restaurant_id


def test_revise_too_far_reduces_distance():
    intent = _family_intent()
    updated = apply_revision(intent, "太远了")
    assert updated.max_distance_km == pytest.approx(3.0)
    log = TraceLog()
    plans = generate_candidate_plans(updated, log)
    assert all(p.steps[0].location_name is not None for p in plans)
