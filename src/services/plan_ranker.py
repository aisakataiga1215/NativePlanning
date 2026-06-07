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

MEAL_TAG_TO_DISH_KEYWORDS: dict[str, list[str]] = {
    "japanese": ["寿司", "刺身", "拉面", "鳗鱼", "天妇罗"],
    "hotpot":   ["火锅", "毛肚", "肥牛", "虾滑"],
    "bbq":      ["烤肉", "五花肉", "牛肉", "烤串"],
    "coffee":   ["咖啡", "拿铁", "甜点"],
    "western":  ["牛排", "意面", "披萨"],
}

_ACTIVITY_TYPE_MAP: dict[str, list[str]] = {
    "zoo":             ["zoo"],
    "theme_park":      ["theme_park"],
    "night_market":    ["night_market"],
    "mall":            ["mall", "indoor_kids_playground"],
    "exhibition":      ["museum", "art_center"],
    "museum":          ["museum"],
    "movie":           ["movie"],
    "board_game":      ["board_game"],
    "escape_room":     ["escape_room"],
    "park_walk":       ["park", "park_walk"],
    "kids_playground": ["indoor_kids_playground", "kids_playground"],
    "citywalk":        ["citywalk", "shopping_street"],
    "tea_house":       ["tea_house"],
    "climbing":        ["climbing"],
    "cycling":         ["cycling"],
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
    location_anchor: str = "",
    requested_meals: list[str] | None = None,
    activity_start_time: str = "",
    activity_end_time: str = "",
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
        venue_types_mapped = {
            vtype
            for ra in requested_activities
            for vtype in _ACTIVITY_TYPE_MAP.get(ra, [ra])
        }
        venue_identifiers = set(venue.tags) | {venue.type}
        if venue_identifiers & (venue_types_mapped | set(requested_activities)):
            group_fit_score = max(group_fit_score, 0.6)  # honor explicit > participant_fit
            explicit_bonus = 0.30
            distance_score = max(distance_score, 0.50)  # floor: prevent distance from killing explicit plans

    # Priority 2: hard_constraint penalty
    constraint_penalty = 0.0
    if hard_constraints and venue:
        if "avoid_long_walk" in hard_constraints and not venue.indoor and venue.distance_km > 3:
            constraint_penalty += 0.1
        if "avoid_long_walk" in hard_constraints and hasattr(venue, "walk_intensity") and venue.walk_intensity == "high":
            constraint_penalty += 0.2
        if "avoid_long_queue" in hard_constraints and any("queue" in r.lower() for r in plan.risks):
            constraint_penalty += 0.1
        if "avoid_long_queue" in hard_constraints and restaurant and hasattr(restaurant, "queue_minutes") and restaurant.queue_minutes > 20:
            constraint_penalty += 0.15
        if "indoor" in hard_constraints and not venue.indoor:
            constraint_penalty += 0.3
    # negative_review_tags × hard_constraints penalty
    if hard_constraints and restaurant:
        if "avoid_long_queue" in hard_constraints:
            if any("排队" in t for t in restaurant.negative_review_tags):
                constraint_penalty += 0.05

    # senior / quiet preference penalties
    has_senior = any(p.age_group == "senior" for p in (participants or []))
    if has_senior:
        if venue and hasattr(venue, "noise_level") and venue.noise_level == "loud":
            constraint_penalty += 0.15
        if restaurant and hasattr(restaurant, "noise_level") and restaurant.noise_level == "loud":
            constraint_penalty += 0.10

    # colleagues: prefer quiet/moderate
    if plan.scenario_type == "colleagues":
        if venue and hasattr(venue, "noise_level") and venue.noise_level == "loud":
            constraint_penalty += 0.10

    # location_anchor bonus
    anchor_bonus = 0.0
    if location_anchor:
        anchor = location_anchor.lower()
        if venue and (anchor in venue.area.lower()
                      or any(anchor in a.lower() for a in venue.nearby_areas)):
            anchor_bonus += 0.15
        if restaurant and (anchor in restaurant.area.lower()
                           or any(anchor in a.lower() for a in restaurant.nearby_areas)):
            anchor_bonus += 0.10

    # promo_bonus: coupon or package present
    promo_bonus = 0.0
    if venue and (venue.venue_coupons or venue.packages):
        promo_bonus += 0.05
    if restaurant and (restaurant.restaurant_coupons or restaurant.packages):
        promo_bonus += 0.05

    # dishes_bonus: requested_meals × recommended_dishes keyword match
    dishes_bonus = 0.0
    if requested_meals and restaurant:
        dish_text = " ".join(restaurant.recommended_dishes)
        tag_match = any(meal in restaurant.tags for meal in requested_meals)
        keyword_match = any(
            kw in dish_text
            for meal in requested_meals
            for kw in MEAL_TAG_TO_DISH_KEYWORDS.get(meal, [])
        )
        if tag_match or keyword_match:
            dishes_bonus += 0.10

    breakdown = ScoreBreakdown(
        distance_score=round(distance_score, 3),
        time_score=round(time_score, 3),
        group_fit_score=round(group_fit_score, 3),
        restaurant_score=round(restaurant_score, 3),
        execution_score=round(execution_score, 3),
    )
    aggregate = max(0.0, min(1.0,
        sum(getattr(breakdown, k) * w for k, w in _WEIGHTS.items())
        + explicit_bonus
        + anchor_bonus
        + promo_bonus
        + dishes_bonus
        - constraint_penalty
    ))

    opening_fit = getattr(plan, "opening_fit", 1.0)
    final_score = round(opening_fit * aggregate, 3)
    update: dict = {"score": final_score, "score_breakdown": breakdown}
    if opening_fit == 0.0:
        update["feasible"] = False
    return plan.model_copy(update=update)


def rank_plans(
    plans: list[ItineraryPlan],
    max_distance_km: float,
    duration_hours: float,
    participants: list[Participant] | None = None,
    requested_activities: list[str] | None = None,
    hard_constraints: list[str] | None = None,
    location_anchor: str = "",
    requested_meals: list[str] | None = None,
    activity_start_time: str = "",
    activity_end_time: str = "",
    pinned_venue_ids: list[str] | None = None,
) -> list[ItineraryPlan]:
    scored = [
        score_plan(
            p, max_distance_km, duration_hours,
            participants, requested_activities, hard_constraints,
            location_anchor, requested_meals,
            activity_start_time, activity_end_time,
        )
        for p in plans
    ]
    ranked = sorted(scored, key=lambda p: (
        0 if p.feasible else 1,       # feasible before infeasible
        0 if p.score > 0.05 else 1,   # high-quality before near-zero
        -p.score,                      # descending score within each tier
    ))
    if pinned_venue_ids:
        pinned = [p for p in ranked if p.venue_id in pinned_venue_ids and p.feasible]
        others = [p for p in ranked if p not in pinned]
        ranked = pinned + others
    return ranked


def get_explicit_venue_ids(requested_activities: list[str]) -> list[str]:
    """Return IDs of venues whose type matches any of the requested activity types."""
    from src.mock_api.venues import VENUES
    target_types = {vt for ra in requested_activities for vt in _ACTIVITY_TYPE_MAP.get(ra, [ra])}
    return [v.id for v in VENUES if v.type in target_types]
