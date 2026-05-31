from __future__ import annotations

from src.schemas.plan import ItineraryPlan
from src.schemas.user_intent import UserIntent
from src.tools.wrappers import TraceLog, traced_call
from src.services.itinerary_builder import add_minutes, time_to_minutes
import src.mock_api as mock


def validate_and_repair(
    plan: ItineraryPlan,
    intent: UserIntent,
    log: TraceLog,
    force_no_tickets: bool = False,
    force_no_seats: bool = False,
    force_time_conflict: bool = False,
) -> ItineraryPlan:
    plan, repaired = _check_venue_tickets(plan, intent, log, force_no_tickets)
    plan, repaired2 = _check_restaurant_seats(plan, intent, log, force_no_seats)
    plan, repaired3 = _check_time_conflict(plan, intent, log, force_time_conflict)
    return plan


def _check_venue_tickets(
    plan: ItineraryPlan,
    intent: UserIntent,
    log: TraceLog,
    force: bool,
) -> tuple[ItineraryPlan, bool]:
    if not plan.venue_id:
        return plan, False

    avail = traced_call(
        "check_venue_availability", mock.check_venue_availability, log,
        venue_id=plan.venue_id,
        date=intent.date,
        time=intent.time,
        group_size=intent.group_size,
    )
    if force:
        avail = {"available": False, "reason": "no_tickets", "available_tickets": 0}

    if avail.get("available"):
        return plan, False

    reason = avail.get("reason", "unknown")
    warning = f"⚠ 场馆 {plan.venue_id} 无票（{reason}），尝试切换备选场馆"

    # find alternative venue
    all_venues = traced_call(
        "search_venues_alt", mock.search_venues, log,
        scenario_type=intent.scenario_type,
        max_distance_km=intent.max_distance_km * 1.5,
        tags=intent.activity_preferences or [],
    )
    alt_venues = [v for v in all_venues if v.id != plan.venue_id and v.available_tickets >= intent.group_size]

    if not alt_venues:
        # fallback to free outdoor venue
        free_venues = [v for v in all_venues if v.price_per_person == 0 and v.id != plan.venue_id]
        alt_venues = free_venues

    if alt_venues:
        alt = alt_venues[0]
        warning += f"，已切换至「{alt.name}」"
        updated_steps = [
            s.model_copy(update={
                "title": s.title.replace(plan.steps[1].location_name, alt.name),
                "location_name": alt.name if s.step_type == "activity" else s.location_name,
                "related_entity_id": alt.id if s.step_type == "activity" else s.related_entity_id,
            }) for s in plan.steps
        ]
        plan = plan.model_copy(update={
            "venue_id": alt.id,
            "steps": updated_steps,
            "warnings": plan.warnings + [warning],
            "required_actions": [a for a in plan.required_actions if a != "book_venue"]
                + (["book_venue"] if alt.requires_ticket else []),
        })
    else:
        plan = plan.model_copy(update={
            "warnings": plan.warnings + [warning + "，未找到备选，保留原计划但标注风险"],
        })

    return plan, True


def _check_restaurant_seats(
    plan: ItineraryPlan,
    intent: UserIntent,
    log: TraceLog,
    force: bool,
) -> tuple[ItineraryPlan, bool]:
    if not plan.restaurant_id:
        return plan, False

    meal_step = next((s for s in plan.steps if s.step_type == "meal"), None)
    meal_time = meal_step.start_time if meal_step else "17:00"

    avail = traced_call(
        "check_restaurant_availability", mock.check_restaurant_availability, log,
        restaurant_id=plan.restaurant_id,
        date=intent.date,
        time=meal_time,
        group_size=intent.group_size,
    )
    if force:
        avail = {"available": False, "reason": "no_seats", "available_seats": 0}

    if avail.get("available"):
        return plan, False

    warning = f"⚠ 餐厅 {plan.restaurant_id} 无空位，尝试切换备选餐厅"

    # find alternative restaurant near same venue
    alt_rests = traced_call(
        "search_restaurants_alt", mock.search_restaurants, log,
        near_location=plan.venue_id or "venue_001",
        group_size=intent.group_size,
        preferences=[],
    )
    alt_rests = [r for r in alt_rests if r.id != plan.restaurant_id and r.available_seats >= intent.group_size]

    if alt_rests:
        alt = alt_rests[0]
        warning += f"，已切换至「{alt.name}」"
        updated_steps = [
            s.model_copy(update={
                "title": f"在 {alt.name} 用餐" if s.step_type == "meal" else s.title,
                "location_name": alt.name if s.step_type == "meal" else s.location_name,
                "related_entity_id": alt.id if s.step_type == "meal" else s.related_entity_id,
            }) for s in plan.steps
        ]
        plan = plan.model_copy(update={
            "restaurant_id": alt.id,
            "steps": updated_steps,
            "warnings": plan.warnings + [warning],
        })
    else:
        plan = plan.model_copy(update={
            "warnings": plan.warnings + [warning + "，暂无备选，建议自行安排用餐"],
            "required_actions": [a for a in plan.required_actions if a != "reserve_restaurant"],
        })

    return plan, True


def _check_time_conflict(
    plan: ItineraryPlan,
    intent: UserIntent,
    log: TraceLog,
    force: bool,
) -> tuple[ItineraryPlan, bool]:
    end_step = plan.steps[-1] if plan.steps else None
    if not end_step:
        return plan, False

    end_min = time_to_minutes(end_step.end_time)
    limit_min = time_to_minutes(intent.time) + int(intent.duration_hours * 60)

    if not force and end_min <= limit_min:
        return plan, False

    warning = f"⚠ 当前计划结束时间 {end_step.end_time} 超出时间窗口，尝试压缩行程"

    # try shortening activity by 30 min
    activity_step = next((s for s in plan.steps if s.step_type == "activity"), None)
    if activity_step and activity_step.duration_minutes > 60:
        new_duration = activity_step.duration_minutes - 30
        new_end = add_minutes(activity_step.start_time, new_duration)
        updated_steps = []
        prev_end = activity_step.start_time
        for s in plan.steps:
            if s.step_type == "activity":
                s = s.model_copy(update={"duration_minutes": new_duration, "end_time": new_end})
                prev_end = new_end
            elif s.step_type in ("travel", "meal", "return") and updated_steps:
                s = s.model_copy(update={"start_time": prev_end, "end_time": add_minutes(prev_end, s.duration_minutes)})
                prev_end = s.end_time
            updated_steps.append(s)
        warning += "，已将活动时长缩短 30 分钟"
        plan = plan.model_copy(update={
            "steps": updated_steps,
            "warnings": plan.warnings + [warning],
            "total_duration_minutes": plan.total_duration_minutes - 30,
        })
    else:
        plan = plan.model_copy(update={
            "warnings": plan.warnings + [warning + "，行程较紧，建议选择更近的目的地"],
        })

    return plan, True
