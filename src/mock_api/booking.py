import uuid
from src.schemas.order import ExecutionResult
from src.mock_api.venues import get_venue, search_venues
from src.mock_api.restaurants import get_restaurant, search_restaurants


def check_venue_availability(
    venue_id: str,
    date: str,
    time: str,
    group_size: int,
) -> dict:
    venue = get_venue(venue_id)
    if not venue:
        return {"available": False, "reason": "venue_not_found"}
    if venue.available_tickets < group_size:
        return {
            "available": False,
            "reason": "no_tickets",
            "available_tickets": venue.available_tickets,
        }
    return {
        "available": True,
        "available_tickets": venue.available_tickets,
        "open_time": venue.open_time,
        "close_time": venue.close_time,
    }


def book_venue(
    venue_id: str,
    date: str,
    time: str,
    group_size: int,
) -> ExecutionResult:
    venue = get_venue(venue_id)
    if not venue:
        return ExecutionResult(
            action_type="book_venue",
            status="failed",
            message="场馆不存在",
            error_reason="venue_not_found",
        )
    if venue.available_tickets < group_size:
        return ExecutionResult(
            action_type="book_venue",
            status="failed",
            message=f"{venue.name} 当前余票不足（剩余 {venue.available_tickets} 张）",
            error_reason="no_tickets",
        )
    booking_id = f"booking_{uuid.uuid4().hex[:8]}"
    return ExecutionResult(
        action_type="book_venue",
        status="success",
        booking_id=booking_id,
        message=f"已购票 {venue.name} × {group_size} 张，{date} {time} 入场",
    )


def check_restaurant_availability(
    restaurant_id: str,
    date: str,
    time: str,
    group_size: int,
) -> dict:
    restaurant = get_restaurant(restaurant_id)
    if not restaurant:
        return {"available": False, "reason": "restaurant_not_found"}
    if restaurant.available_seats < group_size:
        return {
            "available": False,
            "reason": "no_seats",
            "available_seats": restaurant.available_seats,
        }
    matching_slots = [s for s in restaurant.available_slots if s >= time]
    return {
        "available": True,
        "available_seats": restaurant.available_seats,
        "queue_minutes": restaurant.queue_minutes,
        "reservation_available": restaurant.reservation_available,
        "available_slots": matching_slots,
    }


def reserve_restaurant(
    restaurant_id: str,
    date: str,
    time: str,
    group_size: int,
) -> ExecutionResult:
    restaurant = get_restaurant(restaurant_id)
    if not restaurant:
        return ExecutionResult(
            action_type="reserve_restaurant",
            status="failed",
            message="餐厅不存在",
            error_reason="restaurant_not_found",
        )
    if restaurant.available_seats < group_size:
        return ExecutionResult(
            action_type="reserve_restaurant",
            status="failed",
            message=f"{restaurant.name} 当前无空位（剩余 {restaurant.available_seats} 座）",
            error_reason="no_seats",
        )
    booking_id = f"rsv_{uuid.uuid4().hex[:8]}"
    return ExecutionResult(
        action_type="reserve_restaurant",
        status="success",
        booking_id=booking_id,
        message=f"已预约 {restaurant.name} {time} {group_size} 人位",
    )
