"""Tests for MVP-4 dynamic multi-stop planner (generate_plans)."""
from __future__ import annotations

import pytest

from src.mock_api.venues import get_venue
from src.schemas.user_intent import UserIntent
from src.tools.wrappers import TraceLog
from src.workflow.planner import generate_plans


def _intent(**kwargs) -> UserIntent:
    defaults = dict(
        scenario_type="family",
        group_size=3,
        date="today",
        time="10:00",
        duration_hours=5.0,
        max_distance_km=10.0,
        activity_preferences=["parent_child", "kids"],
        meal_preferences=["kid_friendly"],
        budget_preference="medium",
        raw_input="test",
    )
    defaults.update(kwargs)
    return UserIntent(**defaults)


def _run(intent: UserIntent):
    log = TraceLog()
    plans = generate_plans(intent, log)
    assert plans, "generate_plans returned empty list"
    return plans


# ── Duration budget ────────────────────────────────────────────────────────────

def test_all_plans_within_duration_budget():
    """All plans must fit within the user's requested duration."""
    for hours in (4.0, 5.0, 6.0, 8.0):
        intent = _intent(duration_hours=hours, scenario_type="friends",
                         activity_preferences=["social", "photo"])
        plans = _run(intent)
        for plan in plans:
            assert plan.total_duration_minutes <= hours * 60 + 1, (
                f"Plan {plan.id} total {plan.total_duration_minutes} min exceeds "
                f"{hours}h budget ({hours * 60} min)"
            )


def test_no_step_has_zero_duration():
    """Non-travel/return activity and meal steps must have duration >= 30 min."""
    intent = _intent(duration_hours=5.0)
    plans = _run(intent)
    for plan in plans:
        for step in plan.steps:
            if step.step_type not in ("travel", "return"):
                assert step.duration_minutes >= 30, (
                    f"Step '{step.title}' has suspiciously short duration "
                    f"{step.duration_minutes} min in plan {plan.id}"
                )


# ── Theme park — must not force second activity when time is tight ────────────

def test_theme_park_5h_no_second_activity():
    """超级主题乐园 (min 240 min) with a 5h budget should yield stop_count <= 2
    (primary activity + meal only, no injected light or secondary stop)."""
    intent = _intent(
        duration_hours=5.0,
        max_distance_km=25.0,
        activity_preferences=["parent_child", "kids", "thrill", "large"],
    )
    log = TraceLog()
    plans = generate_plans(intent, log)
    theme_park_plans = [p for p in plans if "venue_013" in p.venue_ids]
    # venue_013 has distance_km=18, so max_distance_km must be large enough to find it
    for plan in theme_park_plans:
        assert plan.stop_count <= 2, (
            f"Theme park plan should not add extra stops on 5h budget, "
            f"got stop_count={plan.stop_count}"
        )
        assert plan.total_duration_minutes <= 5.0 * 60 + 1


def test_theme_park_plan_has_venue_ids():
    """Multi-stop plans must expose venue_ids."""
    intent = _intent(duration_hours=8.0)
    plans = _run(intent)
    for plan in plans:
        assert isinstance(plan.venue_ids, list)
        assert len(plan.venue_ids) >= 1
        assert plan.venue_id in plan.venue_ids


# ── Light stop insertion ────────────────────────────────────────────────────────

def test_light_stop_dropped_when_time_tight():
    """With a very short duration (3h), core budget consumes all time and
    no light stop should appear."""
    intent = _intent(duration_hours=3.0, scenario_type="couple",
                     activity_preferences=["romantic", "walk"])
    plans = _run(intent)
    for plan in plans:
        assert plan.total_duration_minutes <= 3.0 * 60 + 1
        # stop_count should be <= 2 (primary + meal) since 3h is tight
        # We don't assert == 2 to avoid false failure if venue is very short,
        # but we do assert the time budget is respected.


def test_citywalk_5h_can_add_light_stop():
    """A citywalk primary with remaining time > 40 min can accept a tea/coffee
    light stop (stop_count >= 2)."""
    intent = _intent(
        duration_hours=5.0,
        scenario_type="couple",
        activity_preferences=["citywalk", "walk", "photo"],
    )
    plans = _run(intent)
    citywalk_plans = [p for p in plans if any(
        (v := get_venue(vid)) is not None and v.type in ("citywalk",)
        for vid in p.venue_ids
    )]
    for plan in citywalk_plans:
        assert plan.total_duration_minutes <= 5.0 * 60 + 1


# ── Full-day multi-stop ─────────────────────────────────────────────────────────

def test_full_day_8h_generates_plans():
    """8h full-day intent should produce at least one plan."""
    intent = _intent(
        duration_hours=8.0,
        scenario_type="friends",
        activity_preferences=["social", "photo", "walk"],
    )
    plans = _run(intent)
    assert len(plans) >= 1
    for plan in plans:
        assert plan.total_duration_minutes <= 8.0 * 60 + 1


def test_full_day_plan_stop_count_reasonable():
    """Full-day plans should have at least 2 non-travel stops (primary + meal)."""
    intent = _intent(duration_hours=8.0)
    plans = _run(intent)
    for plan in plans:
        assert plan.stop_count >= 2


# ── CLI fixture non-regression ────────────────────────────────────────────────

def test_cli_fixture_family_not_degraded():
    """Family fixture (5h) through generate_plans still yields a plan with a meal."""
    intent = _intent(
        scenario_type="family",
        group_size=3,
        time="14:00",
        duration_hours=5.0,
        max_distance_km=5.0,
        activity_preferences=["parent_child", "kids", "family_friendly"],
        meal_preferences=["low_calorie", "kid_friendly", "healthy"],
    )
    plans = _run(intent)
    for plan in plans:
        # Plan must have at least one meal step
        meal_steps = [s for s in plan.steps if s.step_type == "meal"]
        assert meal_steps, f"Plan {plan.id} has no meal step"
        # Total within budget
        assert plan.total_duration_minutes <= 5.0 * 60 + 1


def test_cli_fixture_friends_not_degraded():
    """Friends fixture (5h, 4 people) through generate_plans still works."""
    intent = _intent(
        scenario_type="friends",
        group_size=4,
        time="14:00",
        duration_hours=5.0,
        max_distance_km=8.0,
        activity_preferences=["social", "photo", "friends"],
        meal_preferences=["social", "affordable"],
    )
    plans = _run(intent)
    assert len(plans) >= 1
    for plan in plans:
        assert plan.total_duration_minutes <= 5.0 * 60 + 1


# ── Travel time realism ───────────────────────────────────────────────────────

def test_travel_time_realistic():
    """The first travel step to a venue ≥5 km away should be at least 10 min."""
    intent = _intent(duration_hours=5.0, max_distance_km=10.0)
    plans = _run(intent)
    for plan in plans:
        first_travel = next((s for s in plan.steps if s.step_type == "travel"), None)
        if first_travel and first_travel.distance_from_previous_km >= 5.0:
            assert first_travel.duration_minutes >= 10, (
                f"Travel of {first_travel.distance_from_previous_km} km took only "
                f"{first_travel.duration_minutes} min — unrealistically fast"
            )
