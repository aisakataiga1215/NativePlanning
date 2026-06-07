"""Tests for meal_policy: required / optional / excluded."""
from src.schemas.plan import ItineraryPlan, PlanStep, ScoreBreakdown
from src.services.plan_ranker import rank_plans
from src.tools.wrappers import TraceLog
from src.workflow.intent_parser import _extract_meal_policy, parse_free_text
from src.workflow.planner import generate_plans, revise_meal_policy_only
from src.workflow.revision_parser import apply_revision
from src.schemas.user_intent import UserIntent


def _make_intent(**kwargs) -> UserIntent:
    base = dict(
        scenario_type="family",
        group_size=3,
        date="today",
        time="10:00",
        duration_hours=5.0,
        max_distance_km=20.0,
        activity_preferences=["parent_child", "kids"],
        meal_preferences=[],
        budget_preference="medium",
    )
    base.update(kwargs)
    return UserIntent(**base)


# ── Parser-level tests ─────────────────────────────────────────────────────────

def test_excluded_keyword_bu_chi_fan():
    assert _extract_meal_policy("明天带孩子去玩，不吃饭") == "excluded"


def test_excluded_keyword_fan_wo_zi_ji():
    assert _extract_meal_policy("饭我自己解决，帮我安排活动") == "excluded"


def test_excluded_keyword_bu_yao_can_ting():
    assert _extract_meal_policy("不要安排餐厅，我们自己带吃的") == "excluded"


def test_optional_keyword():
    assert _extract_meal_policy("随便吃点就好，不用特别安排") == "optional"


def test_optional_shun_bian():
    assert _extract_meal_policy("顺便吃点东西就行了") == "optional"


def test_default_required():
    assert _extract_meal_policy("今天带孩子出去玩，安排顿饭") == "required"


def test_parse_free_text_excluded():
    intent = parse_free_text("带孩子去动物园，不吃饭，距离不限")
    assert intent.meal_policy == "excluded"


def test_parse_free_text_optional():
    intent = parse_free_text("朋友一起出去玩，可吃可不吃")
    assert intent.meal_policy == "optional"


# ── Planner-level tests ────────────────────────────────────────────────────────

def test_excluded_no_meal_steps():
    intent = _make_intent(meal_policy="excluded")
    plans = generate_plans(intent, TraceLog())
    assert plans, "excluded policy should still produce plans"
    for plan in plans:
        meal_steps = [s for s in plan.steps if s.step_type == "meal"]
        assert meal_steps == [], f"Found meal steps in excluded plan: {meal_steps}"


def test_excluded_restaurant_id_none():
    intent = _make_intent(meal_policy="excluded")
    plans = generate_plans(intent, TraceLog())
    assert plans
    for plan in plans:
        assert plan.restaurant_id is None, f"restaurant_id should be None for excluded: {plan.restaurant_id}"


def test_excluded_no_reserve_restaurant_action():
    intent = _make_intent(meal_policy="excluded")
    plans = generate_plans(intent, TraceLog())
    assert plans
    for plan in plans:
        assert "reserve_restaurant" not in plan.required_actions, (
            f"reserve_restaurant must not be in required_actions for excluded: {plan.required_actions}"
        )


def test_optional_no_match_returns_plan():
    """optional policy on a venue with no nearby restaurants should still return a plan."""
    intent = _make_intent(
        meal_policy="optional",
        requested_activities=["zoo"],
    )
    plans = generate_plans(intent, TraceLog())
    assert plans, "optional policy should return plans even if restaurant search fails"


# ── Group 1: Direct input (parse + generate) ──────────────────────────────────

def test_parse_direct_no_meal_excluded():
    """parse_free_text('明天去动物园，不吃饭') → meal_policy == 'excluded'."""
    intent = parse_free_text("明天去动物园，不吃饭")
    assert intent.meal_policy == "excluded", f"Expected excluded, got {intent.meal_policy!r}"


def test_generate_zoo_no_meal_no_restaurant_id():
    """generate_plans with zoo + meal_policy=excluded → top plan has restaurant_id=None."""
    intent = _make_intent(
        requested_activities=["zoo"],
        meal_policy="excluded",
    )
    plans = generate_plans(intent, TraceLog())
    assert plans
    ranked = rank_plans(
        plans, intent.max_distance_km, intent.duration_hours,
        requested_activities=["zoo"],
        pinned_venue_ids=["venue_014"],
    )
    best = ranked[0]
    assert best.restaurant_id is None, (
        f"restaurant_id should be None when meal_policy=excluded, got {best.restaurant_id!r}"
    )


def test_generate_zoo_no_meal_no_meal_step():
    """generate_plans with zoo + meal_policy=excluded → no meal-type step in any plan."""
    intent = _make_intent(
        requested_activities=["zoo"],
        meal_policy="excluded",
    )
    plans = generate_plans(intent, TraceLog())
    assert plans
    for plan in plans:
        meal_steps = [s for s in plan.steps if s.step_type == "meal"]
        assert meal_steps == [], f"Plan {plan.id} has unexpected meal steps: {meal_steps}"


def test_generate_zoo_no_meal_no_reserve_action():
    """generate_plans with zoo + meal_policy=excluded → no reserve_restaurant required."""
    intent = _make_intent(
        requested_activities=["zoo"],
        meal_policy="excluded",
    )
    plans = generate_plans(intent, TraceLog())
    assert plans
    for plan in plans:
        assert "reserve_restaurant" not in plan.required_actions, (
            f"Plan {plan.id} has reserve_restaurant in required_actions: {plan.required_actions}"
        )


# ── Group 2: Revision flow ─────────────────────────────────────────────────────

def _make_zoo_intent() -> UserIntent:
    return _make_intent(
        requested_activities=["zoo"],
        meal_policy="required",
        raw_input="明天去动物园",
    )


def test_revision_not_eating_sets_meal_policy_excluded():
    """apply_revision(zoo_intent, '不吃饭') → meal_policy == 'excluded'."""
    updated = apply_revision(_make_zoo_intent(), "不吃饭")
    assert updated.meal_policy == "excluded", (
        f"Expected excluded, got {updated.meal_policy!r}"
    )


def test_revision_not_eating_preserves_zoo_activity():
    """apply_revision(zoo_intent, '不吃饭') → requested_activities still ['zoo']."""
    updated = apply_revision(_make_zoo_intent(), "不吃饭")
    assert updated.requested_activities == ["zoo"], (
        f"Zoo activity should be preserved, got {updated.requested_activities!r}"
    )


def test_revision_not_eating_sets_meal_policy_only_scope():
    """apply_revision(zoo_intent, '不吃饭') only → revision_scope == 'meal_policy_only'."""
    updated = apply_revision(_make_zoo_intent(), "不吃饭")
    assert updated.revision_scope == "meal_policy_only", (
        f"Expected meal_policy_only scope, got {updated.revision_scope!r}"
    )


def test_revision_not_eating_plus_too_far_sets_global_scope():
    """apply_revision(zoo_intent, '太远了，不吃饭') → revision_scope == '' (global re-plan)."""
    updated = apply_revision(_make_zoo_intent(), "太远了，不吃饭")
    assert updated.meal_policy == "excluded", f"meal_policy should be excluded, got {updated.meal_policy!r}"
    assert updated.revision_scope == "", (
        f"Combined distance+meal revision must not use meal_policy_only scope, got {updated.revision_scope!r}"
    )


def test_revision_raw_input_accumulates():
    """apply_revision appends revision_text to raw_input."""
    updated = apply_revision(_make_zoo_intent(), "不吃饭")
    assert "明天去动物园" in updated.raw_input
    assert "不吃饭" in updated.raw_input


def test_revise_meal_policy_only_venue_preserved():
    """revise_meal_policy_only + rank with pin → zoo venue preserved, no restaurant, no meal step."""
    zoo_intent = _make_intent(
        requested_activities=["zoo"],
        meal_policy="excluded",
    )
    zoo_plan_stub = ItineraryPlan(
        id="test_zoo", title="Zoo stub", scenario_type="family",
        summary="Zoo visit", steps=[],
        estimated_total_cost=0.0, total_duration_minutes=240, score=0.8,
        score_breakdown=ScoreBreakdown(
            distance_score=0.8, time_score=0.8, group_fit_score=0.8,
            restaurant_score=0.5, execution_score=0.9,
        ),
        reasons=[], risks=[], required_actions=[],
        venue_id="venue_014",
    )
    log = TraceLog()
    plans = revise_meal_policy_only(zoo_intent, zoo_plan_stub, log)
    assert plans, "revise_meal_policy_only must return plans"
    ranked = rank_plans(
        plans, zoo_intent.max_distance_km, zoo_intent.duration_hours,
        requested_activities=["zoo"],
        pinned_venue_ids=["venue_014"],
    )
    best = ranked[0]
    assert best.venue_id == "venue_014", f"Zoo venue should be pinned to top, got {best.venue_id!r}"
    assert best.restaurant_id is None, f"No restaurant expected, got {best.restaurant_id!r}"
    meal_steps = [s for s in best.steps if s.step_type == "meal"]
    assert meal_steps == [], f"No meal steps expected, got {meal_steps}"


# ── Group 3: Execute / share message ──────────────────────────────────────────

def test_execute_no_restaurant_skips_reserve():
    """execute_plan on a plan with restaurant_id=None → no reserve_restaurant executed."""
    from src.workflow.executor import execute_plan

    intent = _make_intent()
    plan = ItineraryPlan(
        id="test_no_rest", title="No Restaurant Plan", scenario_type="family",
        summary="Test", steps=[
            PlanStep(
                step_type="travel", title="前往", location_name="出发地",
                start_time="10:00", end_time="10:30", duration_minutes=30,
            ),
            PlanStep(
                step_type="activity", title="活动", location_name="动物园",
                start_time="10:30", end_time="14:30", duration_minutes=240,
                related_entity_id="venue_014",
            ),
        ],
        estimated_total_cost=0.0, total_duration_minutes=270, score=0.7,
        score_breakdown=ScoreBreakdown(
            distance_score=0.7, time_score=0.7, group_fit_score=0.7,
            restaurant_score=0.5, execution_score=0.9,
        ),
        reasons=[], risks=[], required_actions=["book_venue"],
        venue_id="venue_014",
        restaurant_id=None,
    )
    log = TraceLog()
    results = execute_plan(plan, intent, log)
    action_types = [r.action_type for r in results]
    assert "reserve_restaurant" not in action_types, (
        f"reserve_restaurant must not execute when restaurant_id is None, got {action_types}"
    )
