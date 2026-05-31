from __future__ import annotations

from src.schemas.plan import ItineraryPlan, PlanStep, ScoreBreakdown
from src.schemas.user_intent import UserIntent
from src.tools.wrappers import TraceLog, traced_call
from src.services.itinerary_builder import build_family_timeline
import src.mock_api as mock


def generate_candidate_plans(
    intent: UserIntent,
    log: TraceLog,
    force_no_tickets_venue_id: str | None = None,
    force_no_seats_restaurant_id: str | None = None,
) -> list[ItineraryPlan]:
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

    plans: list[ItineraryPlan] = []
    for venue in venues[:3]:
        restaurants = traced_call(
            "search_restaurants", mock.search_restaurants, log,
            near_location=venue.id,
            group_size=intent.group_size,
            preferences=intent.meal_preferences or [],
        )
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
            restaurant_id=restaurant.id,
        )
        plans.append(plan)

    return plans


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
