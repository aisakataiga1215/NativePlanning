from __future__ import annotations

from src.schemas.plan import ItineraryPlan, ScoreBreakdown
from src.schemas.user_intent import Participant

_WEIGHTS = {
    "distance_score": 0.25,
    "time_score": 0.20,
    "group_fit_score": 0.25,
    "restaurant_score": 0.20,
    "execution_score": 0.10,
}

_AGE_GROUP_WEIGHTS: dict[str, float] = {
    "young_child": 2.0, "child": 1.8, "teenager": 1.5,
    "young_adult": 1.2, "adult": 1.0, "senior": 2.0, "unknown": 1.0,
}
_AGE_GROUP_MIDPOINTS: dict[str, int] = {
    "young_child": 3, "child": 9, "teenager": 15,
    "young_adult": 21, "adult": 40, "senior": 70, "unknown": 30,
}


def _participant_venue_fit(p: Participant, venue) -> float:
    age = p.age if p.age is not None else _AGE_GROUP_MIDPOINTS.get(p.age_group, 30)
    if venue.suitable_age_min <= age <= venue.suitable_age_max:
        return 1.0
    gap = max(venue.suitable_age_min - age, age - venue.suitable_age_max, 0)
    return max(0.1, 1.0 - gap * 0.08)


def _participant_fit_score(venue, participants: list[Participant]) -> float:
    if not participants:
        return 0.6
    total_w = sum(_AGE_GROUP_WEIGHTS.get(p.age_group, 1.0) for p in participants)
    total_s = sum(
        _AGE_GROUP_WEIGHTS.get(p.age_group, 1.0) * _participant_venue_fit(p, venue)
        for p in participants
    )
    return total_s / total_w if total_w else 0.6


def score_plan(
    plan: ItineraryPlan,
    max_distance_km: float,
    duration_hours: float,
    participants: list[Participant] | None = None,
    requested_activities: list[str] | None = None,
    hard_constraints: list[str] | None = None,
) -> ItineraryPlan:
    from src.mock_api.venues import get_venue
    from src.mock_api.restaurants import get_restaurant

    venue = get_venue(plan.venue_id) if plan.venue_id else None
    restaurant = get_restaurant(plan.restaurant_id) if plan.restaurant_id else None

    # distance_score: 1.0 if within 50% of limit, degrades linearly beyond that
    if venue:
        ratio = venue.distance_km / max(max_distance_km, 0.1)
        distance_score = max(0.0, 1.0 - max(0.0, ratio - 0.5))
    else:
        distance_score = 0.5

    # time_score: how well total duration fits the window (target ±30 min is perfect)
    target_min = duration_hours * 60
    diff = abs(plan.total_duration_minutes - target_min)
    time_score = max(0.0, 1.0 - diff / 120)

    # group_fit_score — use participant_fit_score when participants known
    if venue and participants:
        group_fit_score = _participant_fit_score(venue, participants)
    else:
        group_fit_score = 0.6
        if venue:
            if "family_friendly" in venue.tags or "parent_child" in venue.tags:
                group_fit_score += 0.2
            if venue.indoor:
                group_fit_score += 0.1
        if restaurant:
            if restaurant.has_kids_menu:
                group_fit_score += 0.05
            if restaurant.has_low_calorie_options:
                group_fit_score += 0.05
    group_fit_score = min(1.0, group_fit_score)

    # restaurant_score
    restaurant_score = 0.5
    if restaurant:
        restaurant_score = restaurant.rating / 5.0
        if restaurant.reservation_available:
            restaurant_score += 0.1
        if restaurant.queue_minutes < 20:
            restaurant_score += 0.1
        restaurant_score = min(1.0, restaurant_score)

    # execution_score: penalise risks
    execution_score = max(0.5, 1.0 - len(plan.risks) * 0.1 - len(plan.warnings) * 0.15)

    # Priority 1: explicit_request bonus — also neutralizes participant_fit penalty
    explicit_bonus = 0.0
    if requested_activities and venue:
        venue_identifiers = set(venue.tags) | {venue.type}
        if any(ra in venue_identifiers for ra in requested_activities):
            group_fit_score = max(group_fit_score, 0.6)  # honor explicit > participant_fit
            explicit_bonus = 0.15

    # Priority 2: hard_constraint penalty
    constraint_penalty = 0.0
    if hard_constraints and venue:
        if "avoid_long_walk" in hard_constraints and not venue.indoor and venue.distance_km > 3:
            constraint_penalty += 0.1
        if "avoid_long_queue" in hard_constraints and any("queue" in r.lower() for r in plan.risks):
            constraint_penalty += 0.1

    breakdown = ScoreBreakdown(
        distance_score=round(distance_score, 3),
        time_score=round(time_score, 3),
        group_fit_score=round(group_fit_score, 3),
        restaurant_score=round(restaurant_score, 3),
        execution_score=round(execution_score, 3),
    )
    aggregate = (
        sum(getattr(breakdown, k) * w for k, w in _WEIGHTS.items())
        + explicit_bonus
        - constraint_penalty
    )

    return plan.model_copy(update={
        "score": round(aggregate, 3),
        "score_breakdown": breakdown,
    })


def rank_plans(
    plans: list[ItineraryPlan],
    max_distance_km: float,
    duration_hours: float,
    participants: list[Participant] | None = None,
    requested_activities: list[str] | None = None,
    hard_constraints: list[str] | None = None,
) -> list[ItineraryPlan]:
    scored = [
        score_plan(p, max_distance_km, duration_hours, participants, requested_activities, hard_constraints)
        for p in plans
    ]
    return sorted(scored, key=lambda p: -p.score)
