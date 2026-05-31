"""Tests for participant-aware venue scoring and ranking."""
from __future__ import annotations

import pytest

from src.mock_api.venues import get_venue
from src.schemas.user_intent import Participant, UserIntent
from src.services.plan_ranker import _participant_fit_score, _participant_venue_fit, rank_plans


def _adult() -> Participant:
    return Participant(role="self", age_group="adult", age=35)


def _young_child() -> Participant:
    return Participant(role="child", age_group="young_child", age=5)


def _senior() -> Participant:
    return Participant(role="elderly", age_group="senior", age=70)


# ── venue_001 = 森林亲子乐园, suitable_age 3-12 ───────────────────────────────

def test_young_child_fits_kids_playground() -> None:
    venue = get_venue("venue_001")
    assert venue is not None
    fit = _participant_venue_fit(_young_child(), venue)
    assert fit == 1.0


def test_adult_does_not_fit_kids_playground() -> None:
    venue = get_venue("venue_001")
    assert venue is not None
    fit = _participant_venue_fit(_adult(), venue)
    assert fit < 0.4


# ── venue_002 = 城市湖边公园, suitable_age 0-99 ──────────────────────────────

def test_adult_and_senior_fit_lake_park() -> None:
    venue = get_venue("venue_002")
    assert venue is not None
    score = _participant_fit_score(venue, [_adult(), _senior()])
    assert score > 0.8


# ── _participant_fit_score ────────────────────────────────────────────────────

def test_fit_score_low_for_adults_at_kids_playground() -> None:
    venue = get_venue("venue_001")
    assert venue is not None
    score = _participant_fit_score(venue, [_adult()])
    assert score < 0.4


def test_fit_score_high_for_child_at_kids_playground() -> None:
    venue = get_venue("venue_001")
    assert venue is not None
    score = _participant_fit_score(venue, [_young_child()])
    assert score > 0.9


def test_fit_score_neutral_when_no_participants() -> None:
    venue = get_venue("venue_002")
    assert venue is not None
    score = _participant_fit_score(venue, [])
    assert score == 0.6


# ── Ranking: without children, kids_playground ranks last ────────────────────

def _make_minimal_plan(venue_id: str, restaurant_id: str, scenario_type: str = "unknown"):
    from src.schemas.plan import ItineraryPlan, ScoreBreakdown
    return ItineraryPlan(
        id=f"plan_{venue_id}_{restaurant_id}",
        title=f"{venue_id} + {restaurant_id}",
        scenario_type=scenario_type,
        summary="test plan",
        steps=[],
        estimated_total_cost=100.0,
        total_duration_minutes=300,
        score=0.0,
        score_breakdown=ScoreBreakdown(
            distance_score=0.0, time_score=0.0,
            group_fit_score=0.0, restaurant_score=0.0, execution_score=0.0,
        ),
        reasons=[], risks=[],
        required_actions=[],
        venue_id=venue_id,
        restaurant_id=restaurant_id,
    )


def test_kids_playground_ranks_last_for_adults() -> None:
    """Without children and no explicit request, kids_playground plan should rank last."""
    plan_kids = _make_minimal_plan("venue_001", "rest_001")   # kids_playground
    plan_park = _make_minimal_plan("venue_002", "rest_001")   # lake_park
    ranked = rank_plans(
        [plan_kids, plan_park],
        max_distance_km=6.0,
        duration_hours=5.0,
        participants=[_adult(), _adult()],
        requested_activities=None,
    )
    assert ranked[-1].venue_id == "venue_001", (
        f"Expected kids_playground last, but order: {[p.venue_id for p in ranked]}"
    )


def test_kids_playground_not_last_when_explicitly_requested() -> None:
    """Explicit request for kids_playground should prevent it from ranking last."""
    plan_kids = _make_minimal_plan("venue_001", "rest_001")
    plan_park = _make_minimal_plan("venue_002", "rest_001")
    ranked = rank_plans(
        [plan_kids, plan_park],
        max_distance_km=6.0,
        duration_hours=5.0,
        participants=[_adult(), _adult()],
        requested_activities=["kids_playground"],
    )
    assert ranked[-1].venue_id != "venue_001", (
        "kids_playground should not rank last when explicitly requested"
    )
