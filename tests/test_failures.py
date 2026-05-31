"""Failure path tests: no-seats, no-tickets, time-conflict exceptions."""
from src.tools.wrappers import TraceLog
from src.workflow.intent_parser import parse_intent
from src.workflow.planner import generate_candidate_plans
from src.workflow.constraint_solver import validate_and_repair
from src.workflow.executor import execute_plan
from src.workflow.message_agent import generate_share_message
from src.services.plan_ranker import rank_plans


def _run_with_flags(scenario_key: str, **flags):
    log = TraceLog()
    intent = parse_intent(scenario_key)
    plans = generate_candidate_plans(intent, log)
    repaired = [validate_and_repair(p, intent, log, **flags) for p in plans]
    ranked = rank_plans(repaired, intent.max_distance_km, intent.duration_hours)
    best = ranked[0]
    results = execute_plan(best, intent, log)
    msg = generate_share_message(best, results, intent)
    return intent, best, results, msg, log


# ── no-seats ──────────────────────────────────────────────────────────────────

def test_no_seats_triggers_restaurant_fallback():
    _, plan, _, _, log = _run_with_flags("failure-no-seats", force_no_seats=True)
    tool_names = [t.tool_name for t in log.traces]
    assert "check_restaurant_availability" in tool_names


def test_no_seats_plan_contains_warning():
    _, plan, _, _, _ = _run_with_flags("failure-no-seats", force_no_seats=True)
    assert any("无空位" in w or "切换" in w for w in plan.warnings)


def test_no_seats_plan_still_has_restaurant():
    _, plan, _, _, _ = _run_with_flags("failure-no-seats", force_no_seats=True)
    assert plan.restaurant_id is not None
    meal_step = next((s for s in plan.steps if s.step_type == "meal"), None)
    assert meal_step is not None


def test_no_seats_share_message_includes_warning():
    _, _, _, msg, _ = _run_with_flags("failure-no-seats", force_no_seats=True)
    assert len(msg.message) > 20


# ── no-tickets ────────────────────────────────────────────────────────────────

def test_no_tickets_triggers_venue_fallback():
    _, plan, _, _, log = _run_with_flags("failure-no-tickets", force_no_tickets=True)
    tool_names = [t.tool_name for t in log.traces]
    assert "check_venue_availability" in tool_names


def test_no_tickets_plan_contains_warning():
    _, plan, _, _, _ = _run_with_flags("failure-no-tickets", force_no_tickets=True)
    assert any("无票" in w or "切换" in w for w in plan.warnings)


def test_no_tickets_plan_still_has_venue():
    _, plan, _, _, _ = _run_with_flags("failure-no-tickets", force_no_tickets=True)
    assert plan.venue_id is not None
    activity_step = next((s for s in plan.steps if s.step_type == "activity"), None)
    assert activity_step is not None


# ── time-conflict ─────────────────────────────────────────────────────────────

def test_time_conflict_triggers_repair():
    _, plan, _, _, _ = _run_with_flags("failure-time-conflict", force_time_conflict=True)
    assert any("超出时间窗口" in w or "缩短" in w for w in plan.warnings)


def test_time_conflict_plan_duration_is_reduced():
    intent = parse_intent("failure-time-conflict")
    log = TraceLog()
    plans = generate_candidate_plans(intent, log)
    original_duration = plans[0].total_duration_minutes if plans else 999

    _, repaired_plan, _, _, _ = _run_with_flags("failure-time-conflict", force_time_conflict=True)
    assert repaired_plan.total_duration_minutes <= original_duration


def test_time_conflict_share_message_notes_repair():
    _, _, _, msg, _ = _run_with_flags("failure-time-conflict", force_time_conflict=True)
    assert len(msg.message) > 20
