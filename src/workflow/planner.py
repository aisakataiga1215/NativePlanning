from __future__ import annotations

from typing import Literal

from src.schemas.plan import ItineraryPlan, PlanStep, ScoreBreakdown
from src.schemas.user_intent import UserIntent
from src.tools.wrappers import TraceLog, traced_call
from src.services.itinerary_builder import (
    VenueSlot,
    RestaurantSlot,
    build_family_timeline,
    build_dynamic_timeline,
    estimate_travel_minutes,
)
from src.services.opening_hours import is_open_during, opening_hours_warning
import src.mock_api as mock

# Venue types compatible with inserting a light stop after them.
_LIGHT_COMPATIBLE_TYPES = {
    "museum", "garden", "citywalk", "lake_park", "art_center",
    "kids_lab", "board_game", "tea_house",
}


def get_duration_type(duration_hours: float) -> Literal["half_day", "full_day"]:
    """Derive duration category from hours. Does not live in UserIntent to avoid drift."""
    return "full_day" if duration_hours >= 7.0 else "half_day"


def generate_candidate_plans(
    intent: UserIntent,
    log: TraceLog,
    force_no_tickets_venue_id: str | None = None,
    force_no_seats_restaurant_id: str | None = None,
) -> list[ItineraryPlan]:
    """Original single-stop planner. Kept unchanged for backward compatibility."""
    tags = (
        list(intent.requested_activities)
        + list(intent.activity_preferences or [])
        + list(intent.soft_preferences)
    ) or []

    venues = traced_call(
        "search_venues", mock.search_venues, log,
        scenario_type=intent.scenario_type,
        max_distance_km=intent.max_distance_km,
        tags=tags,
    )

    if not venues:
        venues = traced_call(
            "search_venues_fallback", mock.search_venues, log,
            scenario_type=intent.scenario_type,
            max_distance_km=intent.max_distance_km * 1.5,
            tags=[],
        )

    venues = [v for v in venues if v.id not in intent.avoid_venue_ids]

    plans: list[ItineraryPlan] = []
    for venue in venues[:3]:
        restaurants = traced_call(
            "search_restaurants", mock.search_restaurants, log,
            near_location=venue.id,
            group_size=intent.group_size,
            preferences=intent.meal_preferences or [],
        )
        restaurants = [r for r in restaurants if r.id not in intent.avoid_restaurant_ids]
        if not restaurants:
            continue

        restaurant = restaurants[0]
        raw_steps = build_family_timeline(
            start_time=intent.time,
            venue_name=venue.name,
            venue_id=venue.id,
            venue_duration_min=venue.suggested_duration_minutes,
            venue_distance_km=venue.distance_km,
            restaurant_name=restaurant.name,
            restaurant_id=restaurant.id,
            restaurant_distance_km=restaurant.distance_from_venue_km,
            target_total_minutes=int(intent.duration_hours * 60),
        )
        steps = [PlanStep(**s) for s in raw_steps]
        total_min = sum(s.duration_minutes for s in steps)
        cost = venue.price_per_person * intent.group_size + restaurant.avg_price_per_person * intent.group_size

        reasons = [f"{venue.name} 评分 {venue.rating}，适合{_group_label(intent.scenario_type)}"]
        risks: list[str] = []

        if restaurant.queue_minutes >= 30:
            risks.append(f"{restaurant.name} 排队约 {restaurant.queue_minutes} 分钟，建议提前预约")

        plan_id = f"plan_{venue.id}_{restaurant.id}"
        plan = ItineraryPlan(
            id=plan_id,
            title=f"{venue.name} + {restaurant.name}",
            scenario_type=intent.scenario_type,
            summary=f"{intent.time} 出发，前往 {venue.name}，之后在 {restaurant.name} 用餐",
            steps=steps,
            estimated_total_cost=round(cost, 0),
            total_duration_minutes=total_min,
            score=0.0,
            score_breakdown=ScoreBreakdown(
                distance_score=0.0, time_score=0.0,
                group_fit_score=0.0, restaurant_score=0.0, execution_score=0.0,
            ),
            reasons=reasons,
            risks=risks,
            required_actions=_required_actions(venue, restaurant),
            venue_id=venue.id,
            venue_ids=[venue.id],
            restaurant_id=restaurant.id,
            stop_count=2,
        )
        plans.append(plan)

    return plans


def generate_plans(intent: UserIntent, log: TraceLog) -> list[ItineraryPlan]:
    """Main entry point for MVP-4+. Builds dynamic single- or multi-stop plans.

    - For half-day (< 7h): up to 3 non-travel stops (primary + optional light + meal)
    - For full-day (>= 7h): up to 5 non-travel stops (primary + light + secondary + meal×1-2)
    - Stop count is driven by remaining_minutes, never forced.
    - Guarantees total_duration_minutes <= intent.duration_hours * 60.
    """
    tags = (
        list(intent.requested_activities)
        + list(intent.activity_preferences or [])
    ) or []

    effective_radius = intent.max_distance_km * 2.5 if intent.requested_activities else intent.max_distance_km
    venues = traced_call(
        "search_venues", mock.search_venues, log,
        scenario_type=intent.scenario_type,
        max_distance_km=effective_radius,
        tags=tags,
    )

    if not venues:
        venues = traced_call(
            "search_venues_fallback", mock.search_venues, log,
            scenario_type=intent.scenario_type,
            max_distance_km=effective_radius * 1.5,
            tags=[],
        )

    venues = [v for v in venues if v.id not in intent.avoid_venue_ids]

    # Boost venues whose type matches requested_activities to the front
    if intent.requested_activities:
        from src.services.plan_ranker import _ACTIVITY_TYPE_MAP
        target_types = {
            vtype
            for ra in intent.requested_activities
            for vtype in _ACTIVITY_TYPE_MAP.get(ra, [ra])
        }
        matching = [v for v in venues if v.type in target_types]
        non_matching = [v for v in venues if v.type not in target_types]
        venues = matching + non_matching

    # Boost venues that have nearby restaurants matching requested_meals
    if intent.requested_meals:
        meal_tags = set(intent.requested_meals)
        def _has_meal_match(venue_id: str) -> bool:
            return any(
                r.near_location == venue_id and any(t in r.tags for t in meal_tags)
                for r in mock.RESTAURANTS
            )
        matching_m = [v for v in venues if _has_meal_match(v.id)]
        non_matching_m = [v for v in venues if not _has_meal_match(v.id)]
        venues = matching_m + non_matching_m

    plans: list[ItineraryPlan] = []
    for primary_venue in venues[:3]:
        plan = _build_one_plan(intent, primary_venue, venues, log)
        if plan:
            plans.append(plan)

    return plans


def _build_one_plan(
    intent: UserIntent,
    primary_venue,
    all_venues: list,
    log: TraceLog,
) -> ItineraryPlan | None:
    """Construct one ItineraryPlan with dynamic stop selection."""
    target_minutes = int(intent.duration_hours * 60)
    duration_type = get_duration_type(intent.duration_hours)

    # --- estimate budget ---
    travel_out = estimate_travel_minutes(primary_venue.distance_km)
    return_est = estimate_travel_minutes(primary_venue.distance_km)

    # search restaurants near primary venue
    meal_prefs = list(intent.requested_meals or []) + list(intent.meal_preferences or [])
    restaurants = traced_call(
        "search_restaurants", mock.search_restaurants, log,
        near_location=primary_venue.id,
        group_size=intent.group_size,
        preferences=meal_prefs,
    )
    restaurants = [r for r in restaurants if r.id not in intent.avoid_restaurant_ids]
    if not restaurants:
        return None

    primary_restaurant = restaurants[0]
    rest_travel = max(10, estimate_travel_minutes(primary_restaurant.distance_from_venue_km))
    meal_min = primary_restaurant.suggested_meal_duration_min

    primary_dur_min = primary_venue.suggested_duration_min + primary_venue.queue_minutes
    core_budget = travel_out + primary_dur_min + rest_travel + meal_min + return_est
    remaining = target_minutes - core_budget

    venue_slots: list[VenueSlot] = [VenueSlot(venue=primary_venue, role="primary")]
    restaurant_slots: list[RestaurantSlot] = [RestaurantSlot(restaurant=primary_restaurant, role="meal")]

    # --- try to insert light stop ---
    can_add_light = (
        remaining >= 40
        and primary_venue.duration_flexibility != "low"
        and primary_venue.type in _LIGHT_COMPATIBLE_TYPES
    )
    if can_add_light:
        light_venue = _find_light_stop(primary_venue, all_venues, intent)
        if light_venue:
            light_travel = estimate_travel_minutes(1.5, same_area=(light_venue.area == primary_venue.area))
            light_dur = min(light_venue.suggested_duration_max, remaining - light_travel - 10)
            if light_dur >= light_venue.suggested_duration_min:
                venue_slots.insert(0, VenueSlot(venue=light_venue, role="light"))
                remaining -= (light_dur + light_travel)

    # --- try to insert second activity (full_day only) ---
    if duration_type == "full_day" and remaining >= 90:
        second = _find_secondary_venue(primary_venue, all_venues, intent, venue_slots)
        if second and second.duration_flexibility != "low":
            sec_travel = estimate_travel_minutes(1.5, same_area=(second.area == primary_venue.area))
            sec_dur = min(second.suggested_duration_max, remaining - sec_travel - 10)
            if sec_dur >= second.suggested_duration_min:
                venue_slots.append(VenueSlot(venue=second, role="secondary"))
                remaining -= (sec_dur + sec_travel)

    # --- add lunch for full_day plans ---
    insert_meal_after_first = False
    if duration_type == "full_day" and len(restaurants) >= 2:
        lunch_restaurant = restaurants[1]
        restaurant_slots.insert(0, RestaurantSlot(restaurant=lunch_restaurant, role="light_meal"))
        insert_meal_after_first = True

    # --- build timeline ---
    raw_steps = build_dynamic_timeline(
        start_time=intent.time,
        venue_slots=venue_slots,
        restaurant_slots=restaurant_slots,
        target_total_minutes=target_minutes,
        home_to_first_km=venue_slots[0].venue.distance_km,
        insert_meal_after_first=insert_meal_after_first,
    )
    steps = [PlanStep(**s) for s in raw_steps]
    total_min = sum(s.duration_minutes for s in steps)

    cost = sum(vs.venue.price_per_person for vs in venue_slots) * intent.group_size
    cost += sum(rs.restaurant.avg_price_per_person for rs in restaurant_slots) * intent.group_size

    all_venue_ids = [vs.venue.id for vs in venue_slots]
    venue_names = " → ".join(vs.venue.name for vs in venue_slots)
    if insert_meal_after_first and len(restaurant_slots) >= 2:
        lunch_r = restaurant_slots[0].restaurant
        plan_title = f"{venue_names} + {lunch_r.name} & {primary_restaurant.name}"
        plan_summary = f"{intent.time} 出发，{venue_names}，午餐 {lunch_r.name}，晚餐 {primary_restaurant.name}"
    else:
        plan_title = f"{venue_names} + {primary_restaurant.name}"
        plan_summary = f"{intent.time} 出发，{venue_names}，之后在 {primary_restaurant.name} 用餐"
    reasons = [f"{primary_venue.name} 评分 {primary_venue.rating}，适合{_group_label(intent.scenario_type)}"]
    risks: list[str] = []
    if primary_restaurant.queue_minutes >= 30:
        risks.append(f"{primary_restaurant.name} 排队约 {primary_restaurant.queue_minutes} 分钟，建议提前预约")

    non_travel_steps = [s for s in steps if s.step_type not in ("travel", "return")]

    plan_id = f"plan_{'_'.join(all_venue_ids)}_{primary_restaurant.id}"
    plan = ItineraryPlan(
        id=plan_id,
        title=plan_title,
        scenario_type=intent.scenario_type,
        summary=plan_summary,
        steps=steps,
        estimated_total_cost=round(cost, 0),
        total_duration_minutes=total_min,
        score=0.0,
        score_breakdown=ScoreBreakdown(
            distance_score=0.0, time_score=0.0,
            group_fit_score=0.0, restaurant_score=0.0, execution_score=0.0,
        ),
        reasons=reasons,
        risks=risks,
        required_actions=_required_actions(primary_venue, primary_restaurant),
        venue_id=primary_venue.id,
        venue_ids=all_venue_ids,
        restaurant_id=primary_restaurant.id,
        stop_count=len(non_travel_steps),
    )

    # --- opening hours warning for primary venue ---
    primary_activity_step = next(
        (
            s for s in steps
            if s.step_type == "activity" and s.related_entity_id == primary_venue.id
        ),
        None,
    )
    if (
        primary_activity_step is not None
        and hasattr(primary_venue, "open_time")
        and hasattr(primary_venue, "close_time")
        and not is_open_during(
            primary_venue.open_time,
            primary_venue.close_time,
            primary_activity_step.start_time,
            primary_activity_step.end_time,
        )
    ):
        warnings = list(plan.warnings) + [
            opening_hours_warning(
                primary_venue.name,
                primary_venue.open_time,
                primary_venue.close_time,
                primary_activity_step.start_time,
                primary_activity_step.end_time,
            )
        ]
        plan = plan.model_copy(update={"warnings": warnings})

    return plan


def _find_light_stop(primary_venue, all_venues: list, intent: UserIntent):
    """Find a suitable light stop (tea/coffee/citywalk) near the primary venue."""
    light_types = {"tea_house", "citywalk"}
    candidates = [
        v for v in all_venues
        if v.id != primary_venue.id
        and v.id not in intent.avoid_venue_ids
        and v.type in light_types
        and v.duration_flexibility == "high"
        and v.distance_km <= intent.max_distance_km
    ]
    if not candidates:
        return None
    # prefer same area
    same = [c for c in candidates if c.area == primary_venue.area]
    return (same or candidates)[0]


def _find_secondary_venue(primary_venue, all_venues: list, intent: UserIntent, already_used: list[VenueSlot]):
    """Find a secondary activity venue for full-day plans."""
    used_ids = {vs.venue.id for vs in already_used}
    candidates = [
        v for v in all_venues
        if v.id not in used_ids
        and v.id not in intent.avoid_venue_ids
        and v.duration_flexibility != "low"
        and v.distance_km <= intent.max_distance_km
    ]
    return candidates[0] if candidates else None


def revise_restaurant_only(
    intent: UserIntent,
    current_plan: ItineraryPlan,
    log: TraceLog,
) -> list[ItineraryPlan]:
    """Re-search only the restaurant; preserve current_plan.venue_ids unchanged."""
    venues = [mock.get_venue(vid) for vid in current_plan.venue_ids if mock.get_venue(vid)]
    if not venues:
        return generate_plans(intent, log)
    primary_venue = next((v for v in venues if v.id == current_plan.venue_id), venues[0])

    meal_prefs = intent.requested_meals if intent.requested_meals else (intent.meal_preferences or [])
    restaurants = traced_call(
        "search_restaurants", mock.search_restaurants, log,
        near_location=primary_venue.id,
        group_size=intent.group_size,
        preferences=meal_prefs,
    )
    restaurants = [r for r in restaurants if r.id not in intent.avoid_restaurant_ids]
    if not restaurants:
        return generate_plans(intent, log)

    venue_slots = [VenueSlot(venue=v, role="primary") for v in venues]
    all_venue_ids = [v.id for v in venues]
    venue_names = " → ".join(v.name for v in venues)

    plans: list[ItineraryPlan] = []
    for restaurant in restaurants[:3]:
        restaurant_slots = [RestaurantSlot(restaurant=restaurant, role="meal")]

        raw_steps = build_dynamic_timeline(
            start_time=intent.time,
            venue_slots=venue_slots,
            restaurant_slots=restaurant_slots,
            target_total_minutes=int(intent.duration_hours * 60),
            home_to_first_km=venues[0].distance_km,
        )
        steps = [PlanStep(**s) for s in raw_steps]
        total_min = sum(s.duration_minutes for s in steps)
        cost = sum(v.price_per_person for v in venues) * intent.group_size
        cost += restaurant.avg_price_per_person * intent.group_size
        non_travel_steps = [s for s in steps if s.step_type not in ("travel", "return")]

        plan = ItineraryPlan(
            id=f"plan_rev_r_{'_'.join(all_venue_ids)}_{restaurant.id}",
            title=f"{venue_names} + {restaurant.name}",
            scenario_type=intent.scenario_type,
            summary=f"{intent.time} 出发，{venue_names}，之后在 {restaurant.name} 用餐",
            steps=steps,
            estimated_total_cost=round(cost, 0),
            total_duration_minutes=total_min,
            score=0.0,
            score_breakdown=ScoreBreakdown(
                distance_score=0.0, time_score=0.0,
                group_fit_score=0.0, restaurant_score=0.0, execution_score=0.0,
            ),
            reasons=[f"保留原场馆 {primary_venue.name}，替换餐厅为 {restaurant.name}"],
            risks=[],
            required_actions=_required_actions(primary_venue, restaurant),
            venue_id=primary_venue.id,
            venue_ids=all_venue_ids,
            restaurant_id=restaurant.id,
            stop_count=len(non_travel_steps),
        )
        plans.append(plan)

    return plans


def revise_venue_only(
    intent: UserIntent,
    current_plan: ItineraryPlan,
    log: TraceLog,
) -> list[ItineraryPlan]:
    """Re-search only venues; preserve current_plan.restaurant_id unchanged."""
    fixed_restaurant = mock.get_restaurant(current_plan.restaurant_id) if current_plan.restaurant_id else None
    if not fixed_restaurant:
        return generate_plans(intent, log)

    tags = (
        list(intent.requested_activities)
        + list(intent.activity_preferences or [])
        + list(intent.soft_preferences)
    ) or []
    venues = traced_call(
        "search_venues", mock.search_venues, log,
        scenario_type=intent.scenario_type,
        max_distance_km=intent.max_distance_km,
        tags=tags,
    )
    venues = [v for v in venues if v.id not in intent.avoid_venue_ids]
    if not venues:
        return generate_plans(intent, log)

    plans: list[ItineraryPlan] = []
    for primary_venue in venues[:3]:
        venue_slots = [VenueSlot(venue=primary_venue, role="primary")]
        restaurant_slots = [RestaurantSlot(restaurant=fixed_restaurant, role="meal")]

        raw_steps = build_dynamic_timeline(
            start_time=intent.time,
            venue_slots=venue_slots,
            restaurant_slots=restaurant_slots,
            target_total_minutes=int(intent.duration_hours * 60),
            home_to_first_km=primary_venue.distance_km,
        )
        steps = [PlanStep(**s) for s in raw_steps]
        total_min = sum(s.duration_minutes for s in steps)
        cost = primary_venue.price_per_person * intent.group_size
        cost += fixed_restaurant.avg_price_per_person * intent.group_size

        non_travel_steps = [s for s in steps if s.step_type not in ("travel", "return")]
        plan = ItineraryPlan(
            id=f"plan_rev_v_{primary_venue.id}_{fixed_restaurant.id}",
            title=f"{primary_venue.name} + {fixed_restaurant.name}",
            scenario_type=intent.scenario_type,
            summary=f"{intent.time} 出发，{primary_venue.name}，之后在 {fixed_restaurant.name} 用餐",
            steps=steps,
            estimated_total_cost=round(cost, 0),
            total_duration_minutes=total_min,
            score=0.0,
            score_breakdown=ScoreBreakdown(
                distance_score=0.0, time_score=0.0,
                group_fit_score=0.0, restaurant_score=0.0, execution_score=0.0,
            ),
            reasons=[f"{primary_venue.name} 评分 {primary_venue.rating}，保留原餐厅 {fixed_restaurant.name}"],
            risks=[],
            required_actions=_required_actions(primary_venue, fixed_restaurant),
            venue_id=primary_venue.id,
            venue_ids=[primary_venue.id],
            restaurant_id=fixed_restaurant.id,
            stop_count=len(non_travel_steps),
        )
        plans.append(plan)

    return plans if plans else generate_plans(intent, log)


def _group_label(scenario_type: str) -> str:
    return {
        "family": "家庭出行", "friends": "朋友聚会",
        "couple": "情侣出行", "colleagues": "团队出行", "solo": "独自出行",
    }.get(scenario_type, "出行")


def _required_actions(venue, restaurant) -> list[str]:
    actions = []
    if venue.requires_ticket:
        actions.append("book_venue")
    if restaurant.reservation_available:
        actions.append("reserve_restaurant")
    return actions
