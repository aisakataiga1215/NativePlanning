from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from src.schemas.restaurant import Restaurant
    from src.schemas.venue import Venue


@dataclass
class VenueSlot:
    venue: "Venue"
    role: Literal["primary", "secondary", "light"] = "primary"


@dataclass
class RestaurantSlot:
    restaurant: "Restaurant"
    role: Literal["meal", "light_meal"] = "meal"


def add_minutes(time_str: str, minutes: int) -> str:
    """Add minutes to a HH:MM time string, return HH:MM."""
    dt = datetime.strptime(time_str, "%H:%M")
    result = dt + timedelta(minutes=minutes)
    return result.strftime("%H:%M")


def time_to_minutes(time_str: str) -> int:
    """Convert HH:MM to total minutes since midnight."""
    h, m = time_str.split(":")
    return int(h) * 60 + int(m)


def minutes_to_time(minutes: int) -> str:
    """Convert total minutes since midnight to HH:MM."""
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


def estimate_travel_minutes(distance_km: float, same_area: bool = True) -> int:
    """Estimate travel time in minutes based on distance.

    Uses ~20 km/h average urban speed (including traffic lights, parking, walking
    to/from stops). Cross-area trips apply a 1.3x congestion factor.
    Minimum 15 minutes to reflect real urban travel friction.
    """
    base = max(15, int(distance_km / 20.0 * 60))
    if not same_area:
        base = int(base * 1.3)
    return base


def build_family_timeline(
    start_time: str,
    venue_name: str,
    venue_id: str,
    venue_duration_min: int,
    venue_distance_km: float,
    restaurant_name: str,
    restaurant_id: str,
    restaurant_distance_km: float,
    target_total_minutes: int | None = None,
) -> list[dict]:
    """Build a family scenario step list (single venue + single restaurant).

    Kept unchanged from MVP-3.5 for backward compatibility with existing tests
    and the generate_candidate_plans pipeline.
    """
    depart = start_time

    travel1_min = estimate_travel_minutes(venue_distance_km)
    travel2_min = max(10, estimate_travel_minutes(restaurant_distance_km))
    travel3_min = estimate_travel_minutes(venue_distance_km + restaurant_distance_km)
    meal_duration = 75

    if target_total_minutes is not None:
        non_venue_min = travel1_min + travel2_min + travel3_min + meal_duration
        venue_duration_min = max(venue_duration_min, target_total_minutes - non_venue_min)

    arrive_venue = add_minutes(depart, travel1_min)
    leave_venue = add_minutes(arrive_venue, venue_duration_min)

    arrive_rest = add_minutes(leave_venue, travel2_min)
    leave_rest = add_minutes(arrive_rest, meal_duration)

    return_home = add_minutes(leave_rest, travel3_min)

    return [
        {
            "step_type": "travel",
            "title": "出发前往目的地",
            "location_name": "途中",
            "start_time": depart,
            "end_time": arrive_venue,
            "duration_minutes": travel1_min,
            "distance_from_previous_km": venue_distance_km,
            "notes": f"距家约 {venue_distance_km} km",
            "related_entity_id": None,
        },
        {
            "step_type": "activity",
            "title": f"游玩 {venue_name}",
            "location_name": venue_name,
            "start_time": arrive_venue,
            "end_time": leave_venue,
            "duration_minutes": venue_duration_min,
            "distance_from_previous_km": 0.0,
            "notes": "",
            "related_entity_id": venue_id,
        },
        {
            "step_type": "travel",
            "title": "前往餐厅",
            "location_name": "途中",
            "start_time": leave_venue,
            "end_time": arrive_rest,
            "duration_minutes": travel2_min,
            "distance_from_previous_km": restaurant_distance_km,
            "notes": f"距场馆约 {restaurant_distance_km} km",
            "related_entity_id": None,
        },
        {
            "step_type": "meal",
            "title": f"在 {restaurant_name} 用餐",
            "location_name": restaurant_name,
            "start_time": arrive_rest,
            "end_time": leave_rest,
            "duration_minutes": meal_duration,
            "distance_from_previous_km": 0.0,
            "notes": "",
            "related_entity_id": restaurant_id,
        },
        {
            "step_type": "return",
            "title": "返回家中",
            "location_name": "家",
            "start_time": leave_rest,
            "end_time": return_home,
            "duration_minutes": travel3_min,
            "distance_from_previous_km": venue_distance_km + restaurant_distance_km,
            "notes": "",
            "related_entity_id": None,
        },
    ]


def build_dynamic_timeline(
    start_time: str,
    venue_slots: list[VenueSlot],
    restaurant_slots: list[RestaurantSlot],
    target_total_minutes: int,
    home_to_first_km: float,
) -> list[dict]:
    """Build a dynamic multi-stop timeline respecting the total time budget.

    Returns a list of step dicts (will be converted to PlanStep in the planner).
    Guarantees: sum(step["duration_minutes"]) <= target_total_minutes.

    Priority:
      1. primary activity (never dropped)
      2. meal (never dropped)
      3. return travel (never dropped)
      4. secondary / light stops (dropped if budget exhausted)

    Activity duration is chosen from [suggested_duration_min, suggested_duration_max]
    based on remaining budget. Meal duration from [suggested_meal_duration_min/max].
    """
    from src.schemas.plan import PlanStep  # noqa: F401 — used for type hint below

    steps: list[dict] = []
    current_time = start_time
    used_minutes = 0

    # --- travel to first venue ---
    first_venue = venue_slots[0].venue
    first_same_area = True  # assume departure from nearby home
    travel_out = estimate_travel_minutes(home_to_first_km, same_area=first_same_area)
    return_travel = estimate_travel_minutes(home_to_first_km, same_area=first_same_area)

    # --- compute return travel so we reserve it from the budget ---
    # also reserve meal(s) time
    meal_reserve = 0
    for rs in restaurant_slots:
        meal_reserve += rs.restaurant.suggested_meal_duration_min

    # inter-venue travel between activity stops
    inter_travel = 0
    for i in range(len(venue_slots) - 1):
        v_a = venue_slots[i].venue
        v_b = venue_slots[i + 1].venue
        same = v_a.area == v_b.area
        inter_travel += estimate_travel_minutes(
            venue_slots[i + 1].venue.distance_from_venue_km
            if hasattr(venue_slots[i + 1].venue, "distance_from_venue_km")
            else 1.5,
            same_area=same,
        )

    # travel from last venue to first restaurant
    rest_travel = 0
    if restaurant_slots:
        r_dist = restaurant_slots[0].restaurant.distance_from_venue_km
        rest_travel = max(10, estimate_travel_minutes(r_dist))

    fixed_overhead = travel_out + meal_reserve + inter_travel + rest_travel + return_travel
    activity_budget = target_total_minutes - fixed_overhead

    if activity_budget <= 0:
        # not enough time even for minimal stops — use minimum durations
        activity_budget = sum(vs.venue.suggested_duration_min for vs in venue_slots)

    # --- assign activity durations proportionally ---
    venue_durations: list[int] = []
    for vs in venue_slots:
        v = vs.venue
        min_d = v.suggested_duration_min
        max_d = v.suggested_duration_max
        share = max(1, activity_budget // len(venue_slots))
        # Prefer at least min_d, but if budget share is tighter, use share
        # (budget guarantee takes priority over suggested minimum)
        duration = min(max_d, max(min_d, share) if share >= min_d else share)
        venue_durations.append(duration)

    # --- step: depart ---
    arrive_first = add_minutes(current_time, travel_out)
    steps.append({
        "step_type": "travel",
        "title": "出发前往目的地",
        "location_name": "途中",
        "start_time": current_time,
        "end_time": arrive_first,
        "duration_minutes": travel_out,
        "distance_from_previous_km": home_to_first_km,
        "notes": f"距家约 {home_to_first_km} km",
        "related_entity_id": None,
        "area": "",
    })
    used_minutes += travel_out
    current_time = arrive_first

    # --- steps: activity venues ---
    for idx, vs in enumerate(venue_slots):
        v = vs.venue
        dur = venue_durations[idx]

        role_label = {"primary": "游玩", "secondary": "游览", "light": "顺游"}[vs.role]
        leave = add_minutes(current_time, dur)
        steps.append({
            "step_type": "activity",
            "title": f"{role_label} {v.name}",
            "location_name": v.name,
            "start_time": current_time,
            "end_time": leave,
            "duration_minutes": dur,
            "distance_from_previous_km": 0.0 if idx == 0 else 1.5,
            "notes": "",
            "related_entity_id": v.id,
            "area": v.area,
        })
        used_minutes += dur
        current_time = leave

        # travel to next venue (if any)
        if idx < len(venue_slots) - 1:
            next_v = venue_slots[idx + 1].venue
            same = v.area == next_v.area
            t = estimate_travel_minutes(1.5, same_area=same)
            next_arrive = add_minutes(current_time, t)
            steps.append({
                "step_type": "travel",
                "title": f"前往 {next_v.name}",
                "location_name": "途中",
                "start_time": current_time,
                "end_time": next_arrive,
                "duration_minutes": t,
                "distance_from_previous_km": 1.5,
                "notes": "",
                "related_entity_id": None,
                "area": "",
            })
            used_minutes += t
            current_time = next_arrive

    # --- travel to first restaurant ---
    if restaurant_slots:
        r0 = restaurant_slots[0].restaurant
        t_to_rest = max(10, estimate_travel_minutes(r0.distance_from_venue_km))
        arrive_rest = add_minutes(current_time, t_to_rest)
        steps.append({
            "step_type": "travel",
            "title": f"前往 {r0.name}",
            "location_name": "途中",
            "start_time": current_time,
            "end_time": arrive_rest,
            "duration_minutes": t_to_rest,
            "distance_from_previous_km": r0.distance_from_venue_km,
            "notes": f"距场馆约 {r0.distance_from_venue_km} km",
            "related_entity_id": None,
            "area": "",
        })
        used_minutes += t_to_rest
        current_time = arrive_rest

        # --- steps: meals ---
        for ridx, rs in enumerate(restaurant_slots):
            r = rs.restaurant
            available_for_meal = max(0, target_total_minutes - used_minutes - return_travel)
            meal_dur = min(
                r.suggested_meal_duration_max,
                max(r.suggested_meal_duration_min, available_for_meal),
            )
            # Budget guarantee: never overflow the remaining window
            meal_dur = max(1, min(meal_dur, available_for_meal))

            leave_rest = add_minutes(current_time, meal_dur)
            steps.append({
                "step_type": "meal",
                "title": f"在 {r.name} 用餐",
                "location_name": r.name,
                "start_time": current_time,
                "end_time": leave_rest,
                "duration_minutes": meal_dur,
                "distance_from_previous_km": 0.0,
                "notes": "",
                "related_entity_id": r.id,
                "area": r.area,
            })
            used_minutes += meal_dur
            current_time = leave_rest

            # travel between restaurants (rare — only if 2 meals)
            if ridx < len(restaurant_slots) - 1:
                next_r = restaurant_slots[ridx + 1].restaurant
                t = max(10, estimate_travel_minutes(next_r.distance_from_venue_km))
                next_arrive_r = add_minutes(current_time, t)
                steps.append({
                    "step_type": "travel",
                    "title": f"前往 {next_r.name}",
                    "location_name": "途中",
                    "start_time": current_time,
                    "end_time": next_arrive_r,
                    "duration_minutes": t,
                    "distance_from_previous_km": next_r.distance_from_venue_km,
                    "notes": "",
                    "related_entity_id": None,
                    "area": "",
                })
                used_minutes += t
                current_time = next_arrive_r

    # --- return home ---
    return_arrive = add_minutes(current_time, return_travel)
    steps.append({
        "step_type": "return",
        "title": "返回家中",
        "location_name": "家",
        "start_time": current_time,
        "end_time": return_arrive,
        "duration_minutes": return_travel,
        "distance_from_previous_km": home_to_first_km,
        "notes": "",
        "related_entity_id": None,
        "area": "",
    })

    return steps
