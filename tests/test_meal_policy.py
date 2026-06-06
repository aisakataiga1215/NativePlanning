"""Tests for meal_policy: required / optional / excluded."""
from src.workflow.intent_parser import _extract_meal_policy, parse_free_text
from src.workflow.planner import generate_plans
from src.tools.wrappers import TraceLog
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
