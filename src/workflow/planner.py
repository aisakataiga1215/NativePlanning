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
    build_destination_timeline,
    estimate_travel_minutes,
    time_to_minutes,
    minutes_to_time,
    add_minutes,
)
from src.services.opening_hours import is_open_during, opening_hours_warning
import src.mock_api as mock

# Venue types compatible with inserting a light stop after them.
_LIGHT_COMPATIBLE_TYPES = {
    "museum", "garden", "citywalk", "lake_park", "art_center",
    "kids_lab", "board_game", "tea_house",
}

# Night-family scoring constants (evening family candidate reordering)
_NIGHT_FAMILY_VENUE_TYPES = frozenset({"indoor_kids_playground", "mall", "movie", "night_market"})
_NIGHT_FAMILY_TAGS = frozenset({"kids", "parent_child", "family", "child_friendly"})
_ADULT_DOWNRANK_TAGS = frozenset({"bar", "nightclub", "adult", "alcohol", "high_noise"})

# Wait tolerance: push step start to open_time if wait is within this; else infeasible
_WAIT_TOLERANCE_MIN = 30

_MEAL_ALIAS_MAP: dict[str, set[str]] = {
    "hotpot":   {"hotpot", "火锅", "麻辣锅"},
    "japanese": {"japanese", "日料", "日本料理", "寿司", "居酒屋", "拉面"},
    "western":  {"western", "西餐", "牛排"},
    "bbq":      {"bbq", "烤肉"},
    "coffee":   {"coffee", "咖啡", "轻食"},
}


def _restaurant_matches_meal(restaurant, meal_keys: list[str]) -> bool:
    tags = set(getattr(restaurant, "tags", []) or [])
    name = getattr(restaurant, "name", "")
    for key in meal_keys:
        aliases = _MEAL_ALIAS_MAP.get(key, {key})
        if aliases & tags:
            return True
        if any(len(a) > 1 and a in name for a in aliases):
            return True
    return False


def _night_family_score(venue) -> float:
    """Score venue suitability for evening family trips (higher = better)."""
    score = 0.0
    close_min = time_to_minutes(getattr(venue, "close_time", "23:59"))
    if close_min >= time_to_minutes("21:00"):
        score += 3.0
    if getattr(venue, "type", "") in _NIGHT_FAMILY_VENUE_TYPES:
        score += 2.0
    tags = set(getattr(venue, "tags", []) or [])
    if tags & _NIGHT_FAMILY_TAGS:
        score += 2.0
    if getattr(venue, "indoor", False):
        score += 1.0
    if getattr(venue, "walk_intensity", "") == "low":
        score += 0.5
    if tags & _ADULT_DOWNRANK_TAGS:
        score -= 3.0
    return score


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


def _generate_meal_only_plans(intent: UserIntent, log: TraceLog) -> list[ItineraryPlan]:
    """Build restaurant-only plans: travel → dine → return. No venue search."""
    meal_prefs = (
        list(intent.requested_meals or [])
        + list(intent.meal_preferences or [])
        + list(intent.soft_preferences or [])
    )
    restaurants = traced_call(
        "search_restaurants_meal_only", mock.search_restaurants_any_location, log,
        group_size=intent.group_size,
        preferences=meal_prefs,
    )
    restaurants = [r for r in restaurants if r.id not in intent.avoid_restaurant_ids]
    if not restaurants:
        return []

    plans: list[ItineraryPlan] = []
    for r in restaurants[:3]:
        travel_min = max(15, estimate_travel_minutes(getattr(r, "distance_from_venue_km", 3.0)))
        meal_dur   = r.suggested_meal_duration_min
        t0 = intent.time
        t1 = minutes_to_time(time_to_minutes(t0) + travel_min)
        t2 = minutes_to_time(time_to_minutes(t1) + meal_dur)
        t3 = minutes_to_time(time_to_minutes(t2) + travel_min)

        feasible = is_open_during(r.open_time, r.close_time, t1, t2)
        warnings: list[str] = []
        if not feasible:
            warnings.append(opening_hours_warning(r.name, r.open_time, r.close_time, t1, t2))

        steps = [
            PlanStep(step_type="travel", title="前往餐厅", location_name=r.name,
                     start_time=t0, end_time=t1, duration_minutes=travel_min),
            PlanStep(step_type="meal",   title=f"在 {r.name} 用餐", location_name=r.name,
                     start_time=t1, end_time=t2, duration_minutes=meal_dur,
                     related_entity_id=r.id),
            PlanStep(step_type="return", title="返回", location_name="家",
                     start_time=t2, end_time=t3, duration_minutes=travel_min),
        ]
        cost = r.avg_price_per_person * intent.group_size
        plans.append(ItineraryPlan(
            id=f"plan_meal_only_{r.id}",
            title=r.name,
            scenario_type=intent.scenario_type,
            summary=f"{t1} 在 {r.name} 用餐",
            steps=steps,
            estimated_total_cost=round(cost, 0),
            total_duration_minutes=sum(s.duration_minutes for s in steps),
            score=0.0,
            score_breakdown=ScoreBreakdown(
                distance_score=0.0, time_score=0.0,
                group_fit_score=0.0, restaurant_score=0.0, execution_score=0.0,
            ),
            reasons=[f"{r.name} 评分 {r.rating}，适合{_group_label(intent.scenario_type)}"],
            risks=[f"排队约 {r.queue_minutes} 分钟"] if r.queue_minutes >= 20 else [],
            required_actions=(["reserve_restaurant"] if r.reservation_available else []),
            venue_id="",
            venue_ids=[],
            restaurant_id=r.id,
            stop_count=1,
            feasible=feasible,
            warnings=warnings,
        ))

    feasible_plans = [p for p in plans if p.feasible]

    # Sort feasible plans to prefer requested_meals type restaurants first
    if feasible_plans and intent.requested_meals:
        def _meal_type_match(mp):
            r = mock.get_restaurant(mp.restaurant_id) if mp.restaurant_id else None
            if not r:
                return False
            return any(m in (getattr(r, "tags", []) or []) for m in intent.requested_meals)
        _meal_matched = [p for p in feasible_plans if _meal_type_match(p)]
        _meal_others = [p for p in feasible_plans if not _meal_type_match(p)]
        feasible_plans = _meal_matched + _meal_others

    # No-romantic fallback warning: if romantic intent but all feasible restaurants are business
    _romantic_intent = any(p in ("romantic", "candlelight") for p in (intent.soft_preferences or []))
    if _romantic_intent and feasible_plans:
        from src.services.plan_ranker import _BUSINESS_TAGS
        non_business = [
            p for p in feasible_plans
            if p.restaurant_id and not (
                set(mock.get_restaurant(p.restaurant_id).tags) & _BUSINESS_TAGS
            )
        ]
        if not non_business:
            feasible_plans[0] = feasible_plans[0].model_copy(update={
                "warnings": list(feasible_plans[0].warnings or []) + [
                    "暂无完全匹配的烛光晚餐方案，建议17:00后出发以获得更佳体验"
                ]
            })

    return feasible_plans if feasible_plans else plans


def generate_plans(intent: UserIntent, log: TraceLog) -> list[ItineraryPlan]:
    """Main entry point for MVP-4+. Builds dynamic single- or multi-stop plans.

    - For half-day (< 7h): up to 3 non-travel stops (primary + optional light + meal)
    - For full-day (>= 7h): up to 5 non-travel stops (primary + light + secondary + meal×1-2)
    - Stop count is driven by remaining_minutes, never forced.
    - Guarantees total_duration_minutes <= intent.duration_hours * 60.
    """
    plan_mode   = getattr(intent, "plan_mode", "activity_first")
    meal_policy = getattr(intent, "meal_policy", "required")
    if plan_mode == "meal_only" and not intent.requested_activities and meal_policy != "excluded":
        return _generate_meal_only_plans(intent, log)

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

    _start_min = time_to_minutes(intent.time) if intent.time else 0

    # Coarse pre-filter: remove venues already closed at departure time
    if _start_min > 0:
        _open_at_start = [
            v for v in venues
            if time_to_minutes(getattr(v, "close_time", "23:59")) > _start_min
        ]
        if _open_at_start:
            venues = _open_at_start

    # For evening family scenarios, reorder candidates to prefer night-viable child-friendly venues
    _is_evening_family = (
        _start_min >= time_to_minutes("18:00") and intent.scenario_type in ("family", "kids")
    )
    if _is_evening_family:
        _arrival_approx = _start_min + 20  # 20-min typical travel estimate

        def _evening_score(venue) -> float:
            score = _night_family_score(venue)
            close_min = time_to_minutes(getattr(venue, "close_time", "23:59"))
            if close_min <= _arrival_approx:      # closed before arrival → strong downrank
                score -= 10.0
            if getattr(venue, "walk_intensity", "") == "high":
                score -= 1.0
            if "not_for_children" in getattr(venue, "tags", []):
                score -= 3.0
            return score

        venues = sorted(venues, key=_evening_score, reverse=True)
    else:
        _evening_score = _night_family_score  # fallback, unused outside evening block

    # Boost venues that have nearby restaurants matching requested_meals
    if intent.requested_meals:
        meal_keys = list(intent.requested_meals)
        def _has_meal_match(venue_id: str) -> bool:
            return any(
                r.near_location == venue_id and _restaurant_matches_meal(r, meal_keys)
                for r in mock.RESTAURANTS
            )
        matching_m = [v for v in venues if _has_meal_match(v.id)]
        non_matching_m = [v for v in venues if not _has_meal_match(v.id)]
        venues = matching_m + non_matching_m

    if intent.requested_activities:
        from src.services.plan_ranker import _ACTIVITY_TYPE_MAP
        target_types = {
            vtype
            for ra in intent.requested_activities
            for vtype in _ACTIVITY_TYPE_MAP.get(ra, [ra])
        }
        _is_kids_request = any(
            ra in ("kids_playground", "indoor_kids_playground")
            for ra in intent.requested_activities
        )
        _avoid = set(intent.avoid_venue_ids)
        # Search mock.VENUES directly by type — bypasses search_venues tag-only filter,
        # which misses venues whose type matches but lack the literal tag (e.g., venue_018).
        _orig_explicit_candidates = [
            v for v in mock.VENUES
            if v.type in target_types
            and v.id not in _avoid
        ]
        explicit_candidates = [
            v for v in _orig_explicit_candidates
            if getattr(v, "distance_km", 999) <= effective_radius
        ]
        # Apply same coarse pre-filter as the main venues list
        if _start_min > 0:
            _ec_open = [
                v for v in explicit_candidates
                if time_to_minutes(getattr(v, "close_time", "23:59")) > _start_min
            ]
            if _ec_open:
                explicit_candidates = _ec_open
        # For evening family scenarios, sort by evening score (indoor_kids_playground first)
        if _is_evening_family and explicit_candidates:
            explicit_candidates = sorted(explicit_candidates, key=_evening_score, reverse=True)

        other_candidates = [v for v in venues if v.type not in target_types]

        explicit_plans = []
        for v in explicit_candidates:
            p = _build_one_plan(intent, v, venues, log)
            if p is None:
                continue
            if not p.feasible:
                # Retry if venue opens soon (user arrived too early — e.g., zoo at 7am)
                open_min = time_to_minutes(getattr(v, "open_time", "00:00"))
                wait_needed = open_min - _start_min
                if 0 < wait_needed <= 120:
                    adj_intent = intent.model_copy(update={"time": getattr(v, "open_time", intent.time)})
                    p2 = _build_one_plan(adj_intent, v, venues, log)
                    if p2 and p2.feasible:
                        adj_warn = f"{v.name} {v.open_time} 开门，已将出发时间调整为开园后入园"
                        p = p2.model_copy(update={"warnings": list(p2.warnings or []) + [adj_warn]})
            explicit_plans.append(p)
        other_plans = [
            p
            for v in other_candidates[:3]
            for p in [_build_one_plan(intent, v, venues, log)]
            if p is not None
        ]

        # When all explicit candidates are too far and the general pool is also too small
        # (very tight radius), widen the search so we can return at least one fallback plan.
        if not explicit_candidates and _orig_explicit_candidates and not other_plans:
            _wide_fallback = traced_call(
                "search_venues_tooFar_wide", mock.search_venues, log,
                scenario_type=intent.scenario_type,
                max_distance_km=max(5.0, effective_radius),
                tags=[],
            )
            _wide_others = [v for v in _wide_fallback if v.type not in target_types]
            other_plans = [
                p
                for v in _wide_others[:3]
                for p in [_build_one_plan(intent, v, _wide_fallback, log)]
                if p is not None
            ]

        feasible_explicit = [p for p in explicit_plans if p.feasible]
        if feasible_explicit:
            return feasible_explicit[:1] + other_plans[:2]

        # Evening-family: if all explicit plans infeasible, widen search for night-viable venues
        if _is_evening_family and not feasible_explicit:
            _wide_venues = traced_call(
                "search_venues_evening_wide", mock.search_venues, log,
                scenario_type=intent.scenario_type,
                max_distance_km=effective_radius * 1.5,
                tags=["night_available", "family", "kids"],
            )
            _wide_venues = [
                v for v in _wide_venues
                if v.id not in intent.avoid_venue_ids
                and time_to_minutes(getattr(v, "close_time", "23:59")) > _start_min + 60
            ]
            _wide_venues = sorted(_wide_venues, key=_evening_score, reverse=True)
            for _wv in _wide_venues[:5]:
                if _wv.id in {v.id for v in explicit_candidates}:
                    continue  # already tried
                _wp = _build_one_plan(intent, _wv, _wide_venues, log)
                if _wp and _wp.feasible:
                    feasible_explicit.append(_wp)
                    break
            if feasible_explicit:
                # Add kids-specific warning when falling back from a kids request
                if _is_kids_request:
                    kids_warn = "当前时间亲子乐园多数已闭园，已推荐夜间亲子友好的替代方案"
                    feasible_explicit = [
                        p.model_copy(update={"warnings": list(p.warnings) + [kids_warn]})
                        for p in feasible_explicit
                    ]
                # Remove other_plans with same venue_id to prevent no-warning duplicate winning rank
                fallback_ids = {p.venue_id for p in feasible_explicit}
                other_plans_clean = [p for p in other_plans if p.venue_id not in fallback_ids]
                return feasible_explicit[:1] + other_plans_clean[:2]

        # Determine fallback warning reason
        _fallback_warn: str | None = None
        if not explicit_candidates and _orig_explicit_candidates:
            # All type-matching venues exceeded max_distance — too-far warning
            _too_far_names = [getattr(v, "name", v.id) for v in _orig_explicit_candidates[:2]]
            _too_far_km = max(getattr(v, "distance_km", 0) for v in _orig_explicit_candidates)
            _fallback_warn = (
                f"你想去的{'、'.join(_too_far_names)}距离较远（约{_too_far_km:.1f}km），"
                f"已推荐附近替代方案"
            )
        elif _is_kids_request:
            _fallback_warn = "当前时间亲子乐园多数已闭园，已推荐夜间亲子友好的替代方案"
        elif explicit_candidates:
            _act_labels = {"exhibition": "展览", "museum": "博物馆", "zoo": "动物园"}
            _act_label = next(
                (_act_labels[ra] for ra in (intent.requested_activities or []) if ra in _act_labels),
                explicit_candidates[0].name if explicit_candidates else "该活动",
            )
            _fallback_warn = f"当前范围内无合适{_act_label}场所，已推荐替代方案"
        if _fallback_warn:
            other_plans = [
                p.model_copy(update={"warnings": list(p.warnings) + [_fallback_warn]})
                for p in other_plans
            ]
        return other_plans if other_plans else explicit_plans

    plans: list[ItineraryPlan] = []
    initial_tried: set[str] = set()
    for pv in venues:
        initial_tried.add(pv.id)
        plan = _build_one_plan(intent, pv, venues, log)
        if plan:
            plans.append(plan)
        if len(plans) >= 3:
            break

    feasible_plans = [p for p in plans if p.feasible]
    if not feasible_plans:
        for pv in venues:
            if pv.id in initial_tried:
                continue
            extra = _build_one_plan(intent, pv, venues, log)
            if extra and extra.feasible:
                feasible_plans.append(extra)
    return feasible_plans if feasible_plans else plans


def _build_one_plan(
    intent: UserIntent,
    primary_venue,
    all_venues: list,
    log: TraceLog,
) -> ItineraryPlan | None:
    """Construct one ItineraryPlan with dynamic stop selection."""
    target_minutes = int(intent.duration_hours * 60)
    duration_type = get_duration_type(intent.duration_hours)
    meal_policy = getattr(intent, "meal_policy", "required")

    start_min = time_to_minutes(intent.time)
    end_min = start_min + target_minutes
    needs_lunch = start_min < 11 * 60 and end_min > 12 * 60 + 30
    needs_dinner = end_min >= 18 * 60

    travel_out = estimate_travel_minutes(primary_venue.distance_km)
    return_est = estimate_travel_minutes(primary_venue.distance_km)

    primary_restaurant = None
    restaurant_slots: list[RestaurantSlot] = []
    insert_meal_after_first = False
    rest_travel = 0
    meal_min = 0

    if meal_policy != "excluded":
        meal_prefs = list(intent.requested_meals or []) + list(intent.meal_preferences or [])
        restaurants = traced_call(
            "search_restaurants", mock.search_restaurants, log,
            near_location=primary_venue.id,
            group_size=intent.group_size,
            preferences=meal_prefs,
        )
        restaurants = [r for r in restaurants if r.id not in intent.avoid_restaurant_ids]

        if intent.requested_meals and restaurants:
            if not _restaurant_matches_meal(restaurants[0], list(intent.requested_meals)):
                wider = traced_call(
                    "search_restaurants_cuisine_wider", mock.search_restaurants_any_location, log,
                    group_size=intent.group_size,
                    preferences=list(intent.requested_meals),
                )
                avoid_ids = set(intent.avoid_restaurant_ids)
                wider = [r for r in wider if r.id not in avoid_ids]
                if wider:
                    seen = {r.id for r in wider}
                    restaurants = wider + [r for r in restaurants if r.id not in seen]

        if not restaurants:
            if meal_policy == "required":
                return None
            # optional: proceed without a restaurant
        else:
            primary_restaurant = restaurants[0]
            rest_travel = max(10, estimate_travel_minutes(primary_restaurant.distance_from_venue_km))
            meal_min = primary_restaurant.suggested_meal_duration_min
            restaurant_slots = [RestaurantSlot(restaurant=primary_restaurant, role="meal")]

            if duration_type == "full_day" and needs_lunch and len(restaurants) >= 2:
                lunch_restaurant = restaurants[1]
                restaurant_slots.insert(0, RestaurantSlot(restaurant=lunch_restaurant, role="light_meal"))
                insert_meal_after_first = True

    primary_dur_min = primary_venue.suggested_duration_min + primary_venue.queue_minutes
    core_budget = travel_out + primary_dur_min + rest_travel + meal_min + return_est
    remaining = target_minutes - core_budget

    # --- destination venue branch (zoo / theme_park) ---
    if getattr(primary_venue, "is_destination", False):
        start_min = time_to_minutes(intent.time)
        end_min = start_min + target_minutes
        needs_lunch = start_min < 11 * 60 and end_min > 12 * 60 + 30

        if meal_policy == "excluded" or not restaurant_slots:
            dest_slots: list[RestaurantSlot] = []
            use_lunch = False
        elif needs_lunch:
            dest_slots = restaurant_slots[:1]
            use_lunch = True
        else:
            dest_slots = []
            use_lunch = False

        raw_steps = build_destination_timeline(
            start_time=intent.time,
            venue=primary_venue,
            restaurant_slots=dest_slots,
            target_total_minutes=target_minutes,
            home_to_venue_km=primary_venue.distance_km,
            needs_lunch=use_lunch,
        )
        steps = [PlanStep(**s) for s in raw_steps]
        total_min = sum(s.duration_minutes for s in steps)

        cost = primary_venue.price_per_person * intent.group_size
        dest_restaurant = dest_slots[0].restaurant if dest_slots else None
        if dest_restaurant:
            cost += dest_restaurant.avg_price_per_person * intent.group_size

        if dest_restaurant:
            plan_title = f"{primary_venue.name} + {dest_restaurant.name}"
            plan_summary = f"{intent.time} 出发，{primary_venue.name}，午餐 {dest_restaurant.name}"
        else:
            plan_title = primary_venue.name
            plan_summary = f"{intent.time} 出发，全天游览 {primary_venue.name}"

        reasons = [
            f"{primary_venue.name} 评分 {primary_venue.rating}，适合{_group_label(intent.scenario_type)}"
        ]
        if meal_policy == "excluded":
            reasons.append("已按要求不安排餐饮")
        non_travel = [s for s in steps if s.step_type not in ("travel", "return")]
        rest_id_part = dest_restaurant.id if dest_restaurant else "no_rest"
        dest_plan = ItineraryPlan(
            id=f"plan_{primary_venue.id}_{rest_id_part}",
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
            risks=[],
            required_actions=_required_actions(primary_venue, dest_restaurant),
            venue_id=primary_venue.id,
            venue_ids=[primary_venue.id],
            restaurant_id=dest_restaurant.id if dest_restaurant else None,
            stop_count=len(non_travel),
        )

        # Apply unified opening-hours gate across all entity steps
        return _reflow_steps(_apply_opening_hours_gate(dest_plan, all_venues))
    core_budget = travel_out + primary_dur_min + rest_travel + meal_min + return_est
    remaining = target_minutes - core_budget

    venue_slots: list[VenueSlot] = [VenueSlot(venue=primary_venue, role="primary")]

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
    elif primary_restaurant is not None:
        plan_title = f"{venue_names} + {primary_restaurant.name}"
        plan_summary = f"{intent.time} 出发，{venue_names}，之后在 {primary_restaurant.name} 用餐"
    else:
        plan_title = venue_names
        plan_summary = f"{intent.time} 出发，前往 {venue_names}"

    reasons = [f"{primary_venue.name} 评分 {primary_venue.rating}，适合{_group_label(intent.scenario_type)}"]
    risks: list[str] = []
    if primary_restaurant and primary_restaurant.queue_minutes >= 30:
        risks.append(f"{primary_restaurant.name} 排队约 {primary_restaurant.queue_minutes} 分钟，建议提前预约")

    non_travel_steps = [s for s in steps if s.step_type not in ("travel", "return")]
    rest_id_part = primary_restaurant.id if primary_restaurant else "no_rest"
    plan_id = f"plan_{'_'.join(all_venue_ids)}_{rest_id_part}"

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
        restaurant_id=primary_restaurant.id if primary_restaurant else None,
        stop_count=len(non_travel_steps),
    )

    # Apply unified opening-hours gate across all entity steps
    return _reflow_steps(_apply_opening_hours_gate(plan, all_venues))


def _recalculate_steps_after_truncation(
    steps: list,
    activity_step,
    new_end_min: int,
) -> list:
    """Truncate activity_step to new_end_min and shift all subsequent steps earlier."""
    result = []
    delta = 0
    for s in steps:
        if s is activity_step:
            old_end_min = time_to_minutes(s.end_time)
            delta = old_end_min - new_end_min
            s = s.model_copy(update={
                "end_time": minutes_to_time(new_end_min),
                "duration_minutes": s.duration_minutes - delta,
            })
        elif delta > 0:
            s = s.model_copy(update={
                "start_time": minutes_to_time(time_to_minutes(s.start_time) - delta),
                "end_time": minutes_to_time(time_to_minutes(s.end_time) - delta),
            })
        result.append(s)
    return result


def _push_step_start(steps: list, entity_id: str, new_start: str) -> list:
    """Shift the first step with entity_id to new_start, cascading the offset to all subsequent steps."""
    result = list(steps)
    pushed = False
    offset = 0
    for i, s in enumerate(result):
        if not pushed and s.related_entity_id == entity_id:
            old_min = time_to_minutes(s.start_time)
            new_min = time_to_minutes(new_start)
            offset = new_min - old_min
            pushed = True
        if pushed and offset != 0:
            result[i] = s.model_copy(update={
                "start_time": add_minutes(s.start_time, offset),
                "end_time":   add_minutes(s.end_time,   offset),
            })
    return result


def _compute_step_opening_fit(
    entity_name: str,
    entity_open: str,
    entity_close: str,
    entity_id: str,
    suggested_min: int,
    step_start: str,
    step_end: str,
    all_steps: list,
    step_type: str = "activity",
) -> tuple[float, list, list[str]]:
    """Three-tier opening_fit for a single entity step.

    Returns (fit, updated_steps, warnings):
      fit 1.0 — step fully within entity's hours; steps unchanged
      fit 0.7 — step adjusted (pushed to open_time or truncated to close_time); steps updated
      fit 0.0 — infeasible (starts too early to wait, or available_min < suggested_min); steps unchanged
    """
    if is_open_during(entity_open, entity_close, step_start, step_end):
        return 1.0, all_steps, []

    oh_warn = opening_hours_warning(entity_name, entity_open, entity_close, step_start, step_end)
    open_min  = time_to_minutes(entity_open)
    close_min = time_to_minutes(entity_close)
    start_min = time_to_minutes(step_start)

    # Case A: step starts before entity opens
    if start_min < open_min:
        wait_min = open_min - start_min
        if wait_min <= _WAIT_TOLERANCE_MIN:
            updated = _push_step_start(all_steps, entity_id, entity_open)
            return 0.7, updated, [oh_warn]
        return 0.0, all_steps, [oh_warn]

    # Case B: step starts within hours but ends after close
    available_min = close_min - start_min
    if available_min <= 0 or available_min < suggested_min:
        return 0.0, all_steps, [oh_warn]

    entity_steps = [
        s for s in all_steps
        if s.step_type in ("activity", "meal") and s.related_entity_id == entity_id
    ]
    if entity_steps:
        updated = _recalculate_steps_after_truncation(list(all_steps), entity_steps[-1], close_min)
    else:
        updated = all_steps
    lbl = "用餐" if step_type == "meal" else "活动"
    adjust_warn = (
        f"因营业时间限制，已将{lbl}时长调整为 {available_min} 分钟"
        f"（{entity_name} {entity_open}–{entity_close}）"
    )
    return 0.7, updated, [adjust_warn]


def _find_venue_by_id(vid: str, all_venues: list):
    return next((v for v in all_venues if v.id == vid), None)


def _apply_opening_hours_gate(plan: ItineraryPlan, all_venues: list) -> ItineraryPlan:
    """Apply the three-tier opening_fit gate across all entity steps.

    Iterates steps in order so that a pushed activity step propagates its shifted
    timeline to subsequent meal steps before they are checked.
    Returns a new plan with opening_fit, warnings, feasible, infeasible_reasons updated.
    """
    plan_fit = 1.0
    updated_steps = list(plan.steps)
    all_warns = list(plan.warnings)
    infeasible_reasons: list[str] = []

    idx = 0
    while idx < len(updated_steps):
        step = updated_steps[idx]
        step_fit = 1.0
        step_warns: list[str] = []

        if step.step_type == "activity" and step.related_entity_id:
            venue = _find_venue_by_id(step.related_entity_id, all_venues)
            if venue and hasattr(venue, "open_time") and hasattr(venue, "close_time"):
                step_fit, updated_steps, step_warns = _compute_step_opening_fit(
                    venue.name, venue.open_time, venue.close_time,
                    venue.id, getattr(venue, "suggested_duration_min", 60),
                    step.start_time, step.end_time, updated_steps,
                    step_type="activity",
                )
                if step_fit == 0.0:
                    infeasible_reasons.append(
                        f"{venue.name} 营业时间 {venue.open_time}–{venue.close_time}，"
                        f"计划时段 {step.start_time}–{step.end_time} 超出营业时间"
                    )

        elif step.step_type == "meal" and step.related_entity_id:
            restaurant = mock.get_restaurant(step.related_entity_id)
            if restaurant and hasattr(restaurant, "open_time") and hasattr(restaurant, "close_time"):
                step_fit, updated_steps, step_warns = _compute_step_opening_fit(
                    restaurant.name, restaurant.open_time, restaurant.close_time,
                    restaurant.id,
                    getattr(restaurant, "suggested_meal_duration_min", 60),
                    step.start_time, step.end_time, updated_steps,
                    step_type="meal",
                )
                if step_fit == 0.0:
                    infeasible_reasons.append(
                        f"{restaurant.name} 营业时间 {restaurant.open_time}–{restaurant.close_time}，"
                        f"计划时段 {step.start_time}–{step.end_time} 超出营业时间"
                    )

        plan_fit = min(plan_fit, step_fit)
        for w in step_warns:
            if w not in all_warns:
                all_warns.append(w)
        idx += 1

    upd: dict = {
        "opening_fit": plan_fit,
        "steps": updated_steps,
        "total_duration_minutes": sum(s.duration_minutes for s in updated_steps),
        "warnings": all_warns,
    }
    if plan_fit == 0.0:
        upd["feasible"] = False
        upd["infeasible_reasons"] = infeasible_reasons or ["一个或多个关键步骤超出营业时间"]
    return plan.model_copy(update=upd)


def _reflow_steps(plan: ItineraryPlan) -> ItineraryPlan:
    """Cascade steps forward without reordering; force return last; recalculate durations."""
    if len(plan.steps) < 2:
        return plan

    def _dur(s_str: str, e_str: str, orig_dur: int) -> int:
        d = time_to_minutes(e_str) - time_to_minutes(s_str)
        if d < 0:
            d += 24 * 60
        return d if d > 0 else max(orig_dur, 1)

    non_ret = [s for s in plan.steps if s.step_type != "return"]
    ret_steps = [s for s in plan.steps if s.step_type == "return"]

    reflowed: list = []
    for s in non_ret:
        if reflowed:
            prev_end = time_to_minutes(reflowed[-1].end_time)
            s_start  = time_to_minutes(s.start_time)
            if s_start < prev_end:
                dur = _dur(s.start_time, s.end_time, s.duration_minutes)
                s = s.model_copy(update={
                    "start_time": minutes_to_time(prev_end),
                    "end_time":   minutes_to_time(prev_end + dur),
                })
        reflowed.append(s)

    cur = time_to_minutes(reflowed[-1].end_time) if reflowed else 0
    for rs in ret_steps:
        rs_dur = _dur(rs.start_time, rs.end_time, rs.duration_minutes)
        rs = rs.model_copy(update={
            "start_time": minutes_to_time(cur),
            "end_time":   minutes_to_time(cur + rs_dur),
        })
        reflowed.append(rs)
        cur += rs_dur

    final: list = []
    for s in reflowed:
        actual = _dur(s.start_time, s.end_time, s.duration_minutes)
        if actual != s.duration_minutes:
            s = s.model_copy(update={"duration_minutes": actual})
        final.append(s)

    if final:
        span = time_to_minutes(final[-1].end_time) - time_to_minutes(final[0].start_time)
        if span < 0:
            span += 24 * 60
        total_min = span
    else:
        total_min = plan.total_duration_minutes

    return plan.model_copy(update={"steps": final, "total_duration_minutes": total_min})


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
    if restaurant and restaurant.reservation_available:
        actions.append("reserve_restaurant")
    return actions


def revise_meal_policy_only(
    intent: UserIntent,
    current_plan: ItineraryPlan,
    log: TraceLog,
) -> list[ItineraryPlan]:
    """Re-plan with meal excluded, pinned to the original venue.

    Caller must merge current_plan.venue_id into pinned_venue_ids when calling rank_plans.
    """
    return generate_plans(intent, log)
