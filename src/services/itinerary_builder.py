from __future__ import annotations

from datetime import datetime, timedelta


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
    """Build a family scenario step list."""
    TRAVEL_SPEED_KMH = 30.0
    depart = start_time

    travel1_min = max(10, int(venue_distance_km / TRAVEL_SPEED_KMH * 60))
    travel2_min = max(5, int(restaurant_distance_km / TRAVEL_SPEED_KMH * 60))
    travel3_min = max(10, int((venue_distance_km + restaurant_distance_km) / TRAVEL_SPEED_KMH * 60))
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
