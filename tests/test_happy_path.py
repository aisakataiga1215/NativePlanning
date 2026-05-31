"""Happy path tests: family and friends scenarios run end-to-end."""
from src.tools.wrappers import TraceLog
from src.workflow.intent_parser import parse_intent
from src.workflow.planner import generate_candidate_plans
from src.workflow.constraint_solver import validate_and_repair
from src.workflow.executor import execute_plan
from src.workflow.message_agent import generate_share_message
from src.services.plan_ranker import rank_plans


def _run_scenario(scenario_key: str):
    log = TraceLog()
    intent = parse_intent(scenario_key)
    plans = generate_candidate_plans(intent, log)
    repaired = [validate_and_repair(p, intent, log) for p in plans]
    ranked = rank_plans(repaired, intent.max_distance_km, intent.duration_hours)
    best = ranked[0]
    results = execute_plan(best, intent, log)
    msg = generate_share_message(best, results, intent)
    return intent, best, results, msg, log


def test_family_scenario_produces_plan():
    intent, plan, results, msg, log = _run_scenario("family")
    assert plan.scenario_type == "family"
    assert plan.venue_id is not None
    assert plan.restaurant_id is not None
    assert len(plan.steps) >= 4


def test_family_scenario_has_share_message():
    _, _, _, msg, _ = _run_scenario("family")
    assert msg.receiver_type == "wife"
    assert len(msg.message) > 20


def test_family_scenario_execution_succeeds():
    _, plan, results, _, _ = _run_scenario("family")
    assert len(results) >= 1
    assert all(r.status == "success" for r in results)


def test_family_scenario_tools_are_traced():
    _, _, _, _, log = _run_scenario("family")
    tool_names = [t.tool_name for t in log.traces]
    assert "search_venues" in tool_names
    assert "search_restaurants" in tool_names


def test_friends_scenario_produces_plan():
    intent, plan, results, msg, _ = _run_scenario("friends")
    assert plan.scenario_type == "friends"
    assert plan.venue_id is not None
    assert plan.restaurant_id is not None


def test_friends_scenario_share_message():
    _, _, _, msg, _ = _run_scenario("friends")
    assert msg.receiver_type == "friend_group"
    assert len(msg.message) > 20


def test_plan_score_is_between_0_and_1():
    _, plan, _, _, _ = _run_scenario("family")
    assert 0.0 <= plan.score <= 1.0


def test_plan_has_activity_and_meal_steps():
    _, plan, _, _, _ = _run_scenario("family")
    step_types = {s.step_type for s in plan.steps}
    assert "activity" in step_types
    assert "meal" in step_types
