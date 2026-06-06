"""Tests for src/services/opening_hours.py including midnight-crossing edge cases."""
from __future__ import annotations

import pytest

from src.services.opening_hours import is_open_at, is_open_during, opening_hours_warning


# ---------------------------------------------------------------------------
# is_open_at — single point-in-time
# ---------------------------------------------------------------------------


def test_zoo_open_in_morning():
    assert is_open_at("09:00", "17:30", "10:00")


def test_zoo_open_exactly_at_open():
    assert is_open_at("09:00", "17:30", "09:00")


def test_zoo_closed_before_open():
    assert not is_open_at("09:00", "17:30", "08:00")


def test_zoo_closed_at_close():
    assert not is_open_at("09:00", "17:30", "17:30")


def test_zoo_closed_after_close():
    assert not is_open_at("09:00", "17:30", "19:00")


def test_ramen_open_at_evening():
    assert is_open_at("18:00", "02:00", "20:00")


def test_ramen_open_at_midnight():
    assert is_open_at("18:00", "02:00", "23:00")


def test_ramen_open_after_midnight():
    assert is_open_at("18:00", "02:00", "01:30")


def test_ramen_closed_in_afternoon():
    assert not is_open_at("18:00", "02:00", "14:00")


def test_ramen_closed_at_02_00():
    assert not is_open_at("18:00", "02:00", "02:00")


# ---------------------------------------------------------------------------
# is_open_during — full step containment
# ---------------------------------------------------------------------------


def test_zoo_step_fully_inside():
    # 10:00–12:00 within 09:00–17:30 → True
    assert is_open_during("09:00", "17:30", "10:00", "12:00")


def test_zoo_step_starts_at_open():
    assert is_open_during("09:00", "17:30", "09:00", "11:00")


def test_zoo_step_ends_before_close():
    assert is_open_during("09:00", "17:30", "15:00", "17:00")


def test_zoo_step_ending_at_close():
    assert is_open_during("09:00", "17:30", "15:00", "17:30")


def test_zoo_step_starts_after_close():
    # Step entirely after close
    assert not is_open_during("09:00", "17:30", "18:00", "19:00")


def test_zoo_step_ending_after_close():
    # Step 16:30–19:00 exceeds 17:30 close → False
    assert not is_open_during("09:00", "17:30", "16:30", "19:00")


def test_zoo_step_starting_before_open():
    # Step 08:00–10:00 starts before 09:00 → False
    assert not is_open_during("09:00", "17:30", "08:00", "10:00")


def test_ramen_step_fully_inside_same_day():
    # 20:00–22:00 within 18:00–02:00 → True
    assert is_open_during("18:00", "02:00", "20:00", "22:00")


def test_ramen_step_midnight_crossing_ok():
    # 23:30–00:30 within 18:00–02:00 → True
    assert is_open_during("18:00", "02:00", "23:30", "00:30")


def test_ramen_step_ending_at_02_00():
    # 23:00–02:00 → step end at close exactly → True
    assert is_open_during("18:00", "02:00", "23:00", "02:00")


def test_ramen_step_exceeding_02_00():
    # 01:00–03:00 exceeds close at 02:00 → False
    assert not is_open_during("18:00", "02:00", "01:00", "03:00")


def test_ramen_step_before_open():
    # 14:00–16:00 before open at 18:00 → False
    assert not is_open_during("18:00", "02:00", "14:00", "16:00")


# ---------------------------------------------------------------------------
# opening_hours_warning — format check
# ---------------------------------------------------------------------------


def test_warning_message_contains_venue_name():
    msg = opening_hours_warning("城郊动物园", "09:00", "17:30", "16:30", "19:00")
    assert "城郊动物园" in msg
    assert "09:00" in msg
    assert "17:30" in msg
    assert "16:30" in msg
    assert "19:00" in msg


# ---------------------------------------------------------------------------
# Integration: planner adds warning for out-of-hours venue
# ---------------------------------------------------------------------------


def test_planner_adds_warning_for_closed_venue():
    """A plan whose primary activity falls outside venue hours should have a warning."""
    from datetime import datetime

    from src.schemas.user_intent import UserIntent
    from src.tools.wrappers import TraceLog
    from src.workflow.intent_parser import parse_free_text
    from src.workflow.planner import generate_plans

    # Parse "今天晚上带孩子出去玩" → time_period=night, start_time=19:00
    # zoo (venue_014) open 09:00-17:30 — should not be in plans, or if it is should have warning
    now = datetime(2026, 6, 2, 10, 0, 0)
    intent = parse_free_text("今天晚上带孩子出去玩", _now=now)
    log = TraceLog()
    plans = generate_plans(intent, log)

    # Find any plan using venue_014 (zoo)
    zoo_plans = [p for p in plans if p.venue_id == "venue_014"]
    if zoo_plans:
        zoo_plan = zoo_plans[0]
        has_warning = any("城郊动物园" in w or "营业时间" in w for w in zoo_plan.warnings)
        assert has_warning, f"Zoo plan should have opening-hours warning; warnings={zoo_plan.warnings}"


# ---------------------------------------------------------------------------
# Integration: ranker penalises out-of-hours venue
# ---------------------------------------------------------------------------


def test_ranker_penalises_closed_venue():
    """Ranker multiplies by opening_fit: zoo plan (opening_fit=0.0) scores 0, kids plan (opening_fit=1.0) scores higher.

    In the new architecture the planner sets opening_fit before scoring; the ranker
    applies `final_score = opening_fit * aggregate` and never re-checks hours itself.
    """
    from src.schemas.plan import ItineraryPlan, PlanStep, ScoreBreakdown
    from src.services.plan_ranker import score_plan

    def _make_plan(venue_id: str, restaurant_id: str, plan_id: str, opening_fit: float) -> ItineraryPlan:
        return ItineraryPlan(
            id=plan_id,
            title="test",
            scenario_type="family",
            summary="test",
            steps=[PlanStep(
                step_type="activity",
                title="test",
                start_time="19:00",
                end_time="21:00",
                location_name="loc",
                duration_minutes=120,
                related_entity_id=venue_id,
            )],
            estimated_total_cost=300.0,
            total_duration_minutes=240,
            score=0.0,
            score_breakdown=ScoreBreakdown(
                distance_score=0.8, time_score=0.8,
                group_fit_score=0.8, restaurant_score=0.8, execution_score=0.8,
            ),
            reasons=["test"],
            risks=[],
            required_actions=[],
            venue_id=venue_id,
            restaurant_id=restaurant_id,
            opening_fit=opening_fit,
            feasible=(opening_fit > 0.0),
        )

    # Zoo closes at 17:30; planner would have set opening_fit=0.0 for a 19:00 activity
    zoo_plan = _make_plan("venue_014", "rest_001", "zoo_plan", opening_fit=0.0)
    # Kids playground open until 22:00; planner sets opening_fit=1.0
    kids_plan = _make_plan("venue_018", "rest_001", "kids_plan", opening_fit=1.0)

    zoo_scored = score_plan(zoo_plan, 15.0, 4.0)
    kids_scored = score_plan(kids_plan, 15.0, 4.0)

    assert kids_scored.score > zoo_scored.score, (
        f"Kids playground (opening_fit=1.0) should beat zoo (opening_fit=0.0); "
        f"kids={kids_scored.score:.3f}, zoo={zoo_scored.score:.3f}"
    )
    assert zoo_scored.score == 0.0, f"Zoo plan with opening_fit=0.0 must score 0; got {zoo_scored.score}"
    assert not zoo_scored.feasible, "Zoo plan with opening_fit=0.0 must be infeasible"
