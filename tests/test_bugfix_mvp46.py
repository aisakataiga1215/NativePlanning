"""Tests for MVP-4.6 bugfixes (Bug A/B/C/D/E/F/G)."""
from src.workflow.planner import generate_plans, _recalculate_steps_after_truncation
from src.tools.wrappers import TraceLog
from src.schemas.user_intent import UserIntent
from src.schemas.plan import PlanStep
from src.services.itinerary_builder import time_to_minutes
from src.services.plan_ranker import rank_plans


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


# ── Phase 3: Candidate pinning (Bug A) ──────────────────────────────────────

def test_zoo_requested_top1_feasible():
    """09:00 start, zoo open 09:00-17:30 → zoo must be plans[0]."""
    intent = _make_intent(time="09:00", requested_activities=["zoo"])
    plans = generate_plans(intent, TraceLog())
    assert plans, "should produce plans"
    assert plans[0].venue_id == "venue_014", (
        f"Expected venue_014 as top1, got {plans[0].venue_id}"
    )


def test_zoo_infeasible_fallback_warning():
    """17:00 start, zoo closes 17:30 → zoo infeasible, other plan shown, warning present."""
    intent = _make_intent(time="17:00", requested_activities=["zoo"])
    plans = generate_plans(intent, TraceLog())
    assert plans, "should still produce fallback plans"
    assert plans[0].venue_id != "venue_014", (
        f"Zoo should not be top1 when infeasible, got {plans[0].venue_id}"
    )
    assert any("动物园" in w for p in plans for w in p.warnings), (
        "Expected a warning mentioning 动物园"
    )


# ── Phase 4: Destination activity (Bug C) ───────────────────────────────────

def test_destination_venue_single_venue_id():
    """zoo plan must contain exactly one venue_id (no secondary stop)."""
    intent = _make_intent(time="09:00", requested_activities=["zoo"])
    plans = generate_plans(intent, TraceLog())
    assert plans
    zoo_plan = plans[0]
    assert zoo_plan.venue_id == "venue_014"
    assert zoo_plan.venue_ids == ["venue_014"], (
        f"Expected single venue_ids=['venue_014'], got {zoo_plan.venue_ids}"
    )


def test_destination_with_lunch_segment():
    """09:00 + zoo + duration crosses noon → lunch step linked to rest_016."""
    intent = _make_intent(time="09:00", requested_activities=["zoo"])
    plans = generate_plans(intent, TraceLog())
    assert plans
    zoo_plan = plans[0]
    assert zoo_plan.venue_id == "venue_014"
    meal_steps = [s for s in zoo_plan.steps if s.step_type == "meal"]
    assert meal_steps, "Expected at least one meal step"
    assert meal_steps[0].related_entity_id == "rest_016", (
        f"Expected rest_016 as lunch restaurant, got {meal_steps[0].related_entity_id}"
    )


def test_destination_excluded_no_meal_step():
    """zoo + meal_policy excluded → no meal steps in destination plan."""
    intent = _make_intent(time="09:00", requested_activities=["zoo"], meal_policy="excluded")
    plans = generate_plans(intent, TraceLog())
    assert plans
    zoo_plan = plans[0]
    assert zoo_plan.venue_id == "venue_014"
    meal_steps = [s for s in zoo_plan.steps if s.step_type == "meal"]
    assert meal_steps == [], f"Expected no meal steps for excluded policy, got {meal_steps}"


# ── Phase 5: Opening hours truncation (Bug B) ──────────────────────────────

def test_recalculate_steps_truncates_activity_and_shifts_subsequent():
    """_recalculate_steps_after_truncation shrinks activity and shifts later steps."""
    travel = PlanStep(
        step_type="travel", title="出发", location_name="家",
        start_time="10:00", end_time="10:20", duration_minutes=20,
    )
    activity = PlanStep(
        step_type="activity", title="活动", location_name="场馆",
        start_time="10:20", end_time="12:20", duration_minutes=120,
        related_entity_id="venue_x",
    )
    meal = PlanStep(
        step_type="meal", title="午餐", location_name="餐厅",
        start_time="12:30", end_time="13:30", duration_minutes=60,
    )
    ret = PlanStep(
        step_type="return", title="返程", location_name="家",
        start_time="13:45", end_time="14:05", duration_minutes=20,
    )
    steps = [travel, activity, meal, ret]

    # Truncate activity from 12:20 to 11:50 → delta=30
    new_steps = _recalculate_steps_after_truncation(steps, activity, time_to_minutes("11:50"))

    assert new_steps[0].end_time == "10:20", "travel step should be unchanged"
    assert new_steps[1].end_time == "11:50", "activity end_time should be truncated"
    assert new_steps[1].duration_minutes == 90, "activity duration should shrink by 30"
    assert new_steps[2].start_time == "12:00", "meal start should shift 30 min earlier"
    assert new_steps[2].end_time == "13:00", "meal end should shift 30 min earlier"
    assert new_steps[3].start_time == "13:15", "return start should shift 30 min earlier"
    assert new_steps[3].end_time == "13:35", "return end should shift 30 min earlier"


def test_feasible_plans_activity_within_close_time():
    """Returned feasible plans must not have primary activity steps past venue close_time."""
    from src.mock_api.venues import VENUES
    venue_map = {v.id: v for v in VENUES}

    intent = _make_intent(time="14:00", duration_hours=6.0)
    plans = generate_plans(intent, TraceLog())

    for plan in plans:
        if not plan.feasible:
            continue
        venue = venue_map.get(plan.venue_id)
        if not venue:
            continue
        primary_act = next(
            (s for s in plan.steps if s.step_type == "activity" and s.related_entity_id == plan.venue_id),
            None,
        )
        if primary_act:
            assert time_to_minutes(primary_act.end_time) <= time_to_minutes(venue.close_time), (
                f"{venue.name}: activity ends {primary_act.end_time} but closes {venue.close_time}"
            )


# ── Phase 6: full_day meal timing (Bug D) ──────────────────────────────────

def test_fullday_14_start_no_lunch():
    """14:00 start 8h → plan has no 午餐 step (start >= 11:00 so needs_lunch=False)."""
    intent = _make_intent(time="14:00", duration_hours=8.0)
    plans = generate_plans(intent, TraceLog())
    assert plans
    for plan in plans:
        lunch_steps = [s for s in plan.steps if "午餐" in s.title]
        assert lunch_steps == [], f"Expected no 午餐 steps, got {[s.title for s in lunch_steps]}"


def test_fullday_09_start_9h_has_lunch_and_dinner():
    """09:00 start 9h → at least one plan has 午餐 step (needs_lunch=True for 09:00-18:00)."""
    intent = _make_intent(time="09:00", duration_hours=9.0)
    plans = generate_plans(intent, TraceLog())
    assert plans
    has_any_lunch = any(
        any("午餐" in s.title for s in p.steps if s.step_type == "meal")
        for p in plans
    )
    all_titles = [[s.title for s in p.steps if s.step_type == "meal"] for p in plans]
    assert has_any_lunch, f"Expected ≥1 plan with 午餐 for 09:00+9h, got: {all_titles}"


def test_fullday_10_start_9h_both_meals():
    """10:00 start 9h → at least one plan has 午餐 step (needs_lunch=True for 10:00-19:00)."""
    intent = _make_intent(time="10:00", duration_hours=9.0)
    plans = generate_plans(intent, TraceLog())
    assert plans
    has_any_lunch = any(
        any("午餐" in s.title for s in p.steps if s.step_type == "meal")
        for p in plans
    )
    all_titles = [[s.title for s in p.steps if s.step_type == "meal"] for p in plans]
    assert has_any_lunch, f"Expected ≥1 plan with 午餐 for 10:00+9h, got: {all_titles}"


# ── Phase 8: Tool duration format (Bug G) ──────────────────────────────────

def test_fmt_elapsed_zero():
    from src.ui.app import _fmt_elapsed
    assert _fmt_elapsed(0) == "<1ms"


def test_fmt_elapsed_sub_one():
    from src.ui.app import _fmt_elapsed
    assert _fmt_elapsed(0.2) == "<1ms"


def test_fmt_elapsed_normal():
    from src.ui.app import _fmt_elapsed
    assert _fmt_elapsed(1.2) == "1.2ms"


def test_fmt_elapsed_large():
    from src.ui.app import _fmt_elapsed
    assert _fmt_elapsed(120.5) == "120.5ms"


# ── Phase 9: Regression — no stale labels (Bug F) ──────────────────────────

def test_plan_reasons_no_multistop_label():
    """plan.reasons must not contain '多站点' (stale label from a removed feature)."""
    intent = _make_intent()
    plans = generate_plans(intent, TraceLog())
    for p in plans:
        assert all("多站点" not in r for r in p.reasons), (
            f"Found '多站点' in reasons: {p.reasons}"
        )


# ── Phase 1 (new): Opening-hours hard feasibility ───────────────────────────

def test_rank_plans_feasible_before_infeasible():
    """rank_plans output: all feasible plans precede all infeasible plans."""
    from src.schemas.plan import ItineraryPlan, ScoreBreakdown

    def _mock_plan(vid, feasible, score):
        return ItineraryPlan(
            id=f"plan_{vid}",
            title=vid,
            scenario_type="family",
            summary="",
            steps=[],
            estimated_total_cost=0,
            total_duration_minutes=60,
            score=score,
            score_breakdown=ScoreBreakdown(
                distance_score=0, time_score=0,
                group_fit_score=0, restaurant_score=0, execution_score=0,
            ),
            reasons=[],
            risks=[],
            required_actions=[],
            venue_id=vid,
            venue_ids=[vid],
            feasible=feasible,
        )

    plans = [
        _mock_plan("infeasible_1", feasible=False, score=0.9),
        _mock_plan("feasible_1",   feasible=True,  score=0.5),
        _mock_plan("infeasible_2", feasible=False, score=0.8),
        _mock_plan("feasible_2",   feasible=True,  score=0.3),
    ]
    ranked = rank_plans(plans, max_distance_km=20.0, duration_hours=5.0)
    assert ranked[0].feasible, f"ranked[0] must be feasible, got {ranked[0].venue_id}"
    assert ranked[1].feasible, f"ranked[1] must be feasible, got {ranked[1].venue_id}"
    assert not ranked[2].feasible, "ranked[2] must be infeasible"
    assert not ranked[3].feasible, "ranked[3] must be infeasible"


def test_late_start_infeasible_venue_not_top1():
    """19:00 start, venues close 20:00, available < suggested_min → ranked[0].feasible."""
    intent = _make_intent(time="19:00", duration_hours=4.0)
    plans = generate_plans(intent, TraceLog())
    assert plans, "should produce plans"
    ranked = rank_plans(plans, max_distance_km=20.0, duration_hours=4.0)
    feasible_exist = any(p.feasible for p in ranked)
    if feasible_exist:
        assert ranked[0].feasible, (
            f"ranked[0] must be feasible when feasible plans exist; got feasible={ranked[0].feasible}, "
            f"venue={ranked[0].venue_id}"
        )


def test_opening_hours_truncation_destination_recalculates_timeline():
    """14:00 start + zoo (closes 17:30, min=120, available=175 >= 120) →
    last activity end_time <= '17:30' and plan.feasible == True."""
    intent = _make_intent(
        time="14:00", duration_hours=5.0,
        requested_activities=["zoo"], max_distance_km=50.0,
    )
    plans = generate_plans(intent, TraceLog())
    zoo_plans = [p for p in plans if p.venue_id == "venue_014"]
    assert zoo_plans, "Should produce a feasible zoo plan for 14:00 start (175 min available >= 120 min)"
    zoo_plan = zoo_plans[0]
    act_steps = [s for s in zoo_plan.steps
                 if s.step_type == "activity" and s.related_entity_id == "venue_014"]
    if act_steps:
        assert time_to_minutes(act_steps[-1].end_time) <= time_to_minutes("17:30"), (
            f"Last activity step ends {act_steps[-1].end_time}, expected <= 17:30"
        )
    assert zoo_plan.feasible, (
        f"Zoo plan should be feasible (available 175 >= min 120), got feasible={zoo_plan.feasible}"
    )


def test_top1_never_has_opening_hours_conflict_if_feasible_exists():
    """End-to-end: generate_plans + rank_plans → ranked[0].feasible when any feasible plan exists."""
    intent = _make_intent(time="19:00", duration_hours=4.0)
    plans = generate_plans(intent, TraceLog())
    assert plans
    ranked = rank_plans(plans, max_distance_km=20.0, duration_hours=4.0)
    feasible_exist = any(p.feasible for p in plans)
    if feasible_exist:
        assert ranked[0].feasible, (
            f"ranked[0] must be feasible; venue={ranked[0].venue_id}, feasible={ranked[0].feasible}"
        )


# ── Phase 2 (new): Explicit request final top1 guarantee ────────────────────

def test_zoo_intent_parse_requested_activities():
    """'明天早上带孩子去动物园，不限距离' → intent.requested_activities contains 'zoo'."""
    from src.workflow.intent_parser import parse_free_text
    intent = parse_free_text("明天早上带孩子去动物园，不限距离")
    assert "zoo" in intent.requested_activities, (
        f"Expected 'zoo' in requested_activities, got {intent.requested_activities}"
    )


def test_zoo_intent_end_to_end_top1():
    """Full chain: generate_plans + rank_plans → ranked[0].venue_id == 'venue_014'."""
    from src.services.plan_ranker import get_explicit_venue_ids
    intent = _make_intent(time="09:00", duration_hours=6.0,
                          requested_activities=["zoo"], max_distance_km=50.0)
    plans = generate_plans(intent, TraceLog())
    pinned = get_explicit_venue_ids(intent.requested_activities)
    ranked = rank_plans(plans, max_distance_km=50.0, duration_hours=6.0,
                        pinned_venue_ids=pinned or None)
    assert ranked, "Should produce plans"
    assert ranked[0].venue_id == "venue_014", (
        f"Expected venue_014 as final ranked[0], got {ranked[0].venue_id}"
    )


def test_zoo_infeasible_explicit_fallback_warning_in_rank():
    """Late start (zoo infeasible) → ranked[0].venue_id != 'venue_014',
    and at least one plan.warnings mentions '动物园' or zoo venue name."""
    from src.services.plan_ranker import get_explicit_venue_ids
    intent = _make_intent(time="17:00", duration_hours=4.0,
                          requested_activities=["zoo"], max_distance_km=50.0)
    plans = generate_plans(intent, TraceLog())
    pinned = get_explicit_venue_ids(intent.requested_activities)
    ranked = rank_plans(plans, max_distance_km=50.0, duration_hours=4.0,
                        pinned_venue_ids=pinned or None)
    assert ranked, "Should produce fallback plans"
    assert ranked[0].venue_id != "venue_014", (
        f"Zoo should not be top1 when infeasible, got {ranked[0].venue_id}"
    )
    all_warnings = [w for p in ranked for w in p.warnings]
    assert any("动物园" in w or "城郊" in w for w in all_warnings), (
        f"Expected warning mentioning zoo; warnings: {all_warnings}"
    )


# ── Phase 3 (new): Meal-focused query / plan_mode ───────────────────────────

def test_meal_only_intent_extracts_plan_mode():
    """'待会和老婆去吃烛光晚餐' → plan_mode == 'meal_only'."""
    from src.workflow.intent_parser import parse_free_text
    intent = parse_free_text("待会和老婆去吃烛光晚餐")
    assert intent.plan_mode == "meal_only", (
        f"Expected plan_mode='meal_only', got '{intent.plan_mode}'"
    )


def test_meal_only_soft_preferences_include_romantic():
    """'待会和老婆去吃烛光晚餐' → soft_preferences contains 'romantic' or 'candlelight'."""
    from src.workflow.intent_parser import parse_free_text
    intent = parse_free_text("待会和老婆去吃烛光晚餐")
    assert any(p in intent.soft_preferences for p in ("romantic", "candlelight")), (
        f"Expected romantic/candlelight in soft_preferences, got {intent.soft_preferences}"
    )


def test_meal_only_no_activity_steps():
    """meal_only plans contain no step_type == 'activity'."""
    intent = _make_intent(
        scenario_type="couple", time="18:00", duration_hours=2.0,
        requested_meals=["western"],
        soft_preferences=["romantic", "candlelight"],
        plan_mode="meal_only",
    )
    plans = generate_plans(intent, TraceLog())
    assert plans, "Should produce meal_only plans"
    for plan in plans:
        act_steps = [s for s in plan.steps if s.step_type == "activity"]
        assert act_steps == [], (
            f"Expected no activity steps in meal_only plan, got {[s.title for s in act_steps]}"
        )


def test_meal_only_restaurant_has_western_or_romantic_tag():
    """meal_only → top restaurant has western/romantic/candlelight tag."""
    intent = _make_intent(
        scenario_type="couple", time="18:00", duration_hours=2.0,
        requested_meals=["western"],
        soft_preferences=["romantic", "candlelight"],
        plan_mode="meal_only",
    )
    plans = generate_plans(intent, TraceLog())
    assert plans, "Should produce meal_only plans"
    top = plans[0]
    assert top.restaurant_id is not None, "meal_only plan should have a restaurant_id"
    from src.mock_api import get_restaurant
    rest = get_restaurant(top.restaurant_id)
    assert rest, f"Restaurant {top.restaurant_id} not found in mock"
    assert any(tag in rest.tags for tag in ("western", "romantic", "candlelight")), (
        f"Expected western/romantic/candlelight tag in {rest.name}, got tags={rest.tags}"
    )


def test_meal_only_venue_id_is_empty():
    """meal_only plan → venue_id == '' and venue_ids == []."""
    intent = _make_intent(
        scenario_type="couple", time="18:00", duration_hours=2.0,
        requested_meals=["western"],
        soft_preferences=["romantic", "candlelight"],
        plan_mode="meal_only",
    )
    plans = generate_plans(intent, TraceLog())
    assert plans
    for plan in plans:
        assert plan.venue_id == "", f"Expected venue_id='', got '{plan.venue_id}'"
        assert plan.venue_ids == [], f"Expected venue_ids=[], got {plan.venue_ids}"


def test_meal_only_closed_restaurant_has_warning():
    """meal_only at 11:00 (烛光西餐厅 may not be open) → feasible plan or warning present."""
    intent = _make_intent(
        scenario_type="couple", time="11:00", duration_hours=2.0,
        requested_meals=["western"],
        soft_preferences=["romantic", "candlelight"],
        plan_mode="meal_only",
    )
    plans = generate_plans(intent, TraceLog())
    assert plans, "Should return plans even if some are infeasible"
    infeasible_with_warning = [p for p in plans if not p.feasible and p.warnings]
    feasible = [p for p in plans if p.feasible]
    assert feasible or infeasible_with_warning, (
        "Either a feasible plan or an infeasible plan with warning expected"
    )


# ── Opening Hours Gate Fix: unit tests ─────────────────────────────────────

def test_compute_step_opening_fit_fully_open():
    """Step fully within entity hours → fit == 1.0, no warnings, steps unchanged."""
    from src.workflow.planner import _compute_step_opening_fit
    fit, updated, warns = _compute_step_opening_fit(
        "test_venue", "09:00", "21:00", "v_test", 60,
        "10:00", "12:00", [],
    )
    assert fit == 1.0
    assert warns == []
    assert updated == []


def test_compute_step_opening_fit_truncatable():
    """Venue closes 17:30, activity 15:00–18:30, available=150 >= suggested=120 → fit == 0.7,
    last entity step truncated to 17:30."""
    from src.workflow.planner import _compute_step_opening_fit
    from src.schemas.plan import PlanStep
    act = PlanStep(
        step_type="activity", title="活动", location_name="场馆",
        start_time="15:00", end_time="18:30", duration_minutes=210,
        related_entity_id="v_trunc",
    )
    fit, updated, warns = _compute_step_opening_fit(
        "test_venue", "09:00", "17:30", "v_trunc", 120,
        "15:00", "18:30", [act],
    )
    assert fit == 0.7
    assert warns
    entity_steps = [s for s in updated if s.related_entity_id == "v_trunc"]
    assert entity_steps
    assert entity_steps[-1].end_time == "17:30", (
        f"Expected truncated to 17:30, got {entity_steps[-1].end_time}"
    )


def test_compute_step_opening_fit_infeasible_after_close():
    """Activity starts at/after close (19:00, venue closes 18:00) → fit == 0.0."""
    from src.workflow.planner import _compute_step_opening_fit
    fit, _, warns = _compute_step_opening_fit(
        "test_venue", "09:00", "18:00", "v_closed", 60,
        "19:00", "21:00", [],
    )
    assert fit == 0.0
    assert warns


def test_compute_step_opening_fit_infeasible_available_too_short():
    """Available 45 min < suggested_min 90 → fit == 0.0."""
    from src.workflow.planner import _compute_step_opening_fit
    fit, _, warns = _compute_step_opening_fit(
        "test_venue", "09:00", "20:00", "v_short", 90,
        "19:15", "21:00", [],
    )
    assert fit == 0.0, f"Expected 0.0, got {fit}"
    assert warns


def test_compute_step_opening_fit_start_before_open_wait_ok():
    """Activity 08:30, venue opens 09:00, wait=30 ≤ tolerance → fit == 0.7, step pushed to 09:00."""
    from src.workflow.planner import _compute_step_opening_fit
    from src.schemas.plan import PlanStep
    act = PlanStep(
        step_type="activity", title="活动", location_name="场馆",
        start_time="08:30", end_time="10:30", duration_minutes=120,
        related_entity_id="v_early",
    )
    fit, updated, warns = _compute_step_opening_fit(
        "test_venue", "09:00", "21:00", "v_early", 60,
        "08:30", "10:30", [act],
    )
    assert fit == 0.7
    entity_steps = [s for s in updated if s.related_entity_id == "v_early"]
    assert entity_steps
    assert entity_steps[0].start_time == "09:00", (
        f"Expected pushed to 09:00, got {entity_steps[0].start_time}"
    )


def test_compute_step_opening_fit_start_before_open_wait_too_long():
    """Activity 07:00, venue opens 09:00, wait=120 > tolerance → fit == 0.0."""
    from src.workflow.planner import _compute_step_opening_fit
    fit, _, warns = _compute_step_opening_fit(
        "test_venue", "09:00", "21:00", "v_tooearly", 60,
        "07:00", "09:00", [],
    )
    assert fit == 0.0
    assert warns


def test_rank_plans_infeasible_never_top1_when_feasible_exists_new():
    """A high-score infeasible plan (opening_fit=0.0) must not be ranked above feasible plans."""
    from src.schemas.plan import ItineraryPlan, ScoreBreakdown

    def _mk(vid, feasible, opening_fit):
        return ItineraryPlan(
            id=f"p_{vid}", title=vid, scenario_type="family", summary="",
            steps=[], estimated_total_cost=0, total_duration_minutes=60,
            score=0.0,
            score_breakdown=ScoreBreakdown(
                distance_score=0, time_score=0, group_fit_score=0,
                restaurant_score=0, execution_score=0,
            ),
            reasons=[], risks=[], required_actions=[],
            venue_id=vid, venue_ids=[vid],
            feasible=feasible, opening_fit=opening_fit,
        )

    plans = [
        _mk("infeasible_high", feasible=False, opening_fit=0.0),
        _mk("feasible_low",    feasible=True,  opening_fit=1.0),
    ]
    ranked = rank_plans(plans, max_distance_km=20.0, duration_hours=5.0)
    assert ranked[0].feasible, (
        f"ranked[0] must be feasible; got {ranked[0].venue_id}, feasible={ranked[0].feasible}"
    )


def test_evening_family_top1_is_night_viable():
    """Full pipeline: 19:00 family start → ranked[0].feasible and venue is night-viable."""
    intent = _make_intent(time="19:00", duration_hours=4.0, scenario_type="family")
    plans = generate_plans(intent, TraceLog())
    assert plans, "Should produce plans for evening family"
    ranked = rank_plans(plans, max_distance_km=20.0, duration_hours=4.0)
    assert ranked, "Should produce ranked plans"

    feasible_exist = any(p.feasible for p in ranked)
    if not feasible_exist:
        return  # no feasible plan available — skip, don't fail

    assert ranked[0].feasible, (
        f"ranked[0] must be feasible; got venue={ranked[0].venue_id}, "
        f"feasible={ranked[0].feasible}, warnings={ranked[0].warnings}"
    )
    assert not any("超出营业范围" in w for w in ranked[0].warnings), (
        f"ranked[0] must not have opening hours conflict; warnings={ranked[0].warnings}"
    )

    from src.mock_api.venues import VENUES
    venue_map = {v.id: v for v in VENUES}
    if ranked[0].venue_id:
        venue = venue_map.get(ranked[0].venue_id)
        if venue:
            night_types = {"indoor_kids_playground", "mall", "movie", "night_market"}
            night_tags = {"kids", "parent_child", "family", "child_friendly"}
            is_night_ok = (
                venue.type in night_types
                or bool(set(venue.tags) & night_tags)
                or time_to_minutes(venue.close_time) >= time_to_minutes("21:00")
            )
            assert is_night_ok, (
                f"ranked[0] venue {venue.name} (type={venue.type}, tags={venue.tags}, "
                f"close={venue.close_time}) is not night-viable or child-suitable"
            )

