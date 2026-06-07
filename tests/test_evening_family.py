"""Tests for opening-hours gate (meal steps) and evening family ranking."""
from src.mock_api.venues import VENUES
from src.schemas.plan import ItineraryPlan, PlanStep, ScoreBreakdown
from src.schemas.user_intent import UserIntent
from src.services.plan_ranker import rank_plans
from src.tools.wrappers import TraceLog
from src.workflow.intent_parser import parse_free_text
from src.workflow.planner import _apply_opening_hours_gate, generate_plans


_NIGHT_VIABLE_TAGS = frozenset({
    "kids", "parent_child", "family", "indoor", "mall",
    "night_available", "indoor_kids_playground",
})


def _gate_plan(venue_id: str, rest_id: str, meal_start: str, meal_end: str) -> ItineraryPlan:
    """Minimal plan for opening-gate tests: one activity step + one meal step."""
    return ItineraryPlan(
        id="gate_test",
        title="Gate Test",
        scenario_type="family",
        summary="Test",
        steps=[
            PlanStep(
                step_type="activity",
                title="活动",
                location_name="场地",
                start_time="20:00",
                end_time="22:00",
                duration_minutes=120,
                related_entity_id=venue_id,
            ),
            PlanStep(
                step_type="meal",
                title="用餐",
                location_name="餐厅",
                start_time=meal_start,
                end_time=meal_end,
                duration_minutes=60,
                related_entity_id=rest_id,
            ),
        ],
        estimated_total_cost=0.0,
        total_duration_minutes=180,
        score=0.7,
        score_breakdown=ScoreBreakdown(
            distance_score=0.7, time_score=0.7, group_fit_score=0.7,
            restaurant_score=0.7, execution_score=0.9,
        ),
        reasons=[],
        risks=[],
        required_actions=[],
        venue_id=venue_id,
        restaurant_id=rest_id,
    )


# ── Phase 1: meal-step opening gate ───────────────────────────────────────────

def test_meal_step_restaurant_closed_makes_infeasible():
    """Meal step after restaurant close time → plan marked infeasible."""
    # venue_018 closes 22:00, activity 20:00-22:00 → fit=1.0
    # rest_013 closes 22:00, meal 22:30-23:30 → available_min=-20 → fit=0.0
    plan = _gate_plan("venue_018", "rest_013", "22:30", "23:30")
    result = _apply_opening_hours_gate(plan, VENUES)
    assert not result.feasible, (
        f"Plan with meal step after restaurant close must be infeasible, "
        f"got feasible={result.feasible!r}"
    )
    assert result.opening_fit == 0.0, f"opening_fit must be 0.0, got {result.opening_fit}"


def test_meal_step_open_restaurant_stays_feasible():
    """Meal step within overnight restaurant hours → plan stays feasible."""
    # venue_018 closes 22:00, activity 20:00-22:00 → fit=1.0
    # rest_012 closes 02:00 (overnight), meal 22:30-23:30 → within hours → fit=1.0
    plan = _gate_plan("venue_018", "rest_012", "22:30", "23:30")
    result = _apply_opening_hours_gate(plan, VENUES)
    assert result.feasible, (
        f"Plan with meal step within overnight restaurant hours must be feasible, "
        f"got feasible={result.feasible!r}"
    )


# ── Phase 2: evening family ranking ───────────────────────────────────────────

def _run_evening_family_chain():
    """Full chain for '今天晚上带孩子去亲子乐园'."""
    intent = parse_free_text("今天晚上带孩子去亲子乐园")
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


def test_evening_family_feasible_ranked_first():
    """'今天晚上带孩子去亲子乐园' full chain → ranked[0].feasible == True."""
    ranked, _ = _run_evening_family_chain()
    assert ranked, "Must produce at least one plan"
    assert ranked[0].feasible, (
        f"ranked[0] must be feasible for evening family outing, "
        f"got feasible={ranked[0].feasible!r}, venue_id={ranked[0].venue_id!r}"
    )


def test_evening_family_not_closed_venue():
    """Evening family outing → ranked[0] must not be 少儿科学实验馆 (venue_012, closes 18:00)."""
    ranked, _ = _run_evening_family_chain()
    assert ranked[0].venue_id != "venue_012", (
        f"ranked[0] must not be venue_012 (closes 18:00), got {ranked[0].venue_id!r}"
    )


def test_evening_family_night_viable_tags():
    """Evening family outing → top venue must have night/family/kids tags."""
    from src.mock_api.venues import get_venue
    ranked, _ = _run_evening_family_chain()
    top = ranked[0]
    venue = get_venue(top.venue_id) if top.venue_id else None
    venue_identifiers = set(getattr(venue, "tags", [])) | {getattr(venue, "type", "")}
    assert venue_identifiers & _NIGHT_VIABLE_TAGS, (
        f"ranked[0] venue must have night/family/kids tags; "
        f"venue_id={top.venue_id!r}, type={getattr(venue, 'type', '')!r}, "
        f"tags={getattr(venue, 'tags', [])!r}"
    )


def test_marginal_venue_infeasible_not_top1():
    """Venue closing at 18:00 with activity step 18:20-19:50 → plan is infeasible."""
    # venue_012 closes 18:00; available_min = 1080-1100 = -20 < 0 → fit=0.0
    plan = ItineraryPlan(
        id="marginal_test",
        title="Marginal Test",
        scenario_type="family",
        summary="Test",
        steps=[
            PlanStep(
                step_type="activity",
                title="少儿科学实验馆",
                location_name="少儿科学实验馆",
                start_time="18:20",
                end_time="19:50",
                duration_minutes=90,
                related_entity_id="venue_012",
            ),
        ],
        estimated_total_cost=0.0,
        total_duration_minutes=90,
        score=0.9,
        score_breakdown=ScoreBreakdown(
            distance_score=0.8, time_score=0.8, group_fit_score=0.8,
            restaurant_score=0.5, execution_score=0.9,
        ),
        reasons=[],
        risks=[],
        required_actions=[],
        venue_id="venue_012",
    )
    result = _apply_opening_hours_gate(plan, VENUES)
    assert not result.feasible, (
        f"venue_012 closes 18:00; activity 18:20-19:50 must be infeasible, "
        f"got feasible={result.feasible!r}"
    )


def test_threshold_18_triggers_evening_sort():
    """At 18:00 start + family scenario, closed venues must not appear as ranked[0]."""
    intent = UserIntent(
        scenario_type="family",
        group_size=3,
        time="18:00",
        duration_hours=4.0,
        max_distance_km=10.0,
    )
    log = TraceLog()
    plans = generate_plans(intent, log)
    ranked = rank_plans(
        plans,
        intent.max_distance_km,
        intent.duration_hours,
        participants=intent.participants or None,
        requested_activities=intent.requested_activities or None,
        location_anchor=intent.location_anchor,
        requested_meals=intent.requested_meals or None,
        soft_preferences=intent.soft_preferences or None,
    )
    assert ranked, "Must produce at least one plan at 18:00 start"
    # venue_012 closes 18:00 — must not be top-ranked when _is_evening_family fires
    assert ranked[0].venue_id != "venue_012", (
        f"venue_012 (closes 18:00) must not be ranked[0] at 18:00 start; "
        f"got {ranked[0].venue_id!r}"
    )
    # ranked[0] must itself be feasible
    assert ranked[0].feasible, (
        f"ranked[0] must be feasible at 18:00 start, got feasible={ranked[0].feasible!r}"
    )
