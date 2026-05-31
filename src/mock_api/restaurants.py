from src.schemas.restaurant import Coupon, Restaurant

RESTAURANTS: list[Restaurant] = [
    Restaurant(
        id="rest_001",
        name="轻食花园餐厅",
        tags=["healthy", "low_calorie", "kid_friendly", "salad", "light"],
        near_location="venue_001",
        distance_from_venue_km=0.8,
        avg_price_per_person=86.0,
        rating=4.6,
        open_time="11:00",
        close_time="21:00",
        queue_minutes=15,
        reservation_available=True,
        has_kids_menu=True,
        has_low_calorie_options=True,
        available_seats=12,
        available_slots=["17:00", "17:30", "18:00", "18:30"],
    ),
    Restaurant(
        id="rest_002",
        name="樱花日式料理",
        tags=["japanese", "healthy", "photo", "social", "kid_friendly"],
        near_location="venue_001",
        distance_from_venue_km=1.2,
        avg_price_per_person=110.0,
        rating=4.7,
        open_time="11:30",
        close_time="22:00",
        queue_minutes=30,
        reservation_available=True,
        has_kids_menu=True,
        has_low_calorie_options=True,
        available_seats=8,
        available_slots=["17:30", "18:00", "19:00"],
    ),
    Restaurant(
        id="rest_003",
        name="老街麻辣火锅",
        tags=["hotpot", "social", "friends", "spicy"],
        near_location="venue_002",
        distance_from_venue_km=0.5,
        avg_price_per_person=95.0,
        rating=4.5,
        open_time="11:00",
        close_time="23:00",
        queue_minutes=45,
        reservation_available=True,
        has_kids_menu=False,
        has_low_calorie_options=False,
        available_seats=20,
        available_slots=["17:00", "18:00", "19:00", "20:00"],
    ),
    Restaurant(
        id="rest_004",
        name="家常小馆",
        tags=["chinese", "homestyle", "kid_friendly", "affordable"],
        near_location="venue_002",
        distance_from_venue_km=0.3,
        avg_price_per_person=55.0,
        rating=4.3,
        open_time="10:00",
        close_time="21:00",
        queue_minutes=10,
        reservation_available=False,
        has_kids_menu=True,
        has_low_calorie_options=False,
        available_seats=30,
        available_slots=[],
    ),
    Restaurant(
        id="rest_005",
        name="西式简餐咖啡馆",
        tags=["western", "cafe", "photo", "social", "friends", "low_calorie"],
        near_location="venue_005",
        distance_from_venue_km=0.2,
        avg_price_per_person=75.0,
        rating=4.4,
        open_time="08:00",
        close_time="22:00",
        queue_minutes=20,
        reservation_available=True,
        has_kids_menu=False,
        has_low_calorie_options=True,
        available_seats=16,
        available_slots=["17:00", "17:30", "18:00", "18:30", "19:00"],
    ),
    Restaurant(
        id="rest_006",
        name="博物馆旁面馆",
        tags=["noodles", "chinese", "quick", "affordable", "kid_friendly"],
        near_location="venue_003",
        distance_from_venue_km=0.1,
        avg_price_per_person=40.0,
        rating=4.2,
        open_time="09:00",
        close_time="20:00",
        queue_minutes=5,
        reservation_available=False,
        has_kids_menu=True,
        has_low_calorie_options=False,
        available_seats=25,
        available_slots=[],
    ),
]

COUPONS: list[Coupon] = [
    Coupon(
        id="coupon_001",
        target_id="rest_001",
        target_type="restaurant",
        title="轻食三人套餐券",
        price=198.0,
        original_price=258.0,
        valid_until="2026-12-31",
        available=True,
    ),
    Coupon(
        id="coupon_002",
        target_id="venue_001",
        target_type="venue",
        title="亲子乐园3人票套餐",
        price=220.0,
        original_price=264.0,
        valid_until="2026-12-31",
        available=True,
    ),
    Coupon(
        id="coupon_003",
        target_id="rest_002",
        target_type="restaurant",
        title="日料双人套餐",
        price=168.0,
        original_price=220.0,
        valid_until="2026-12-31",
        available=True,
    ),
    Coupon(
        id="coupon_004",
        target_id="rest_005",
        target_type="restaurant",
        title="咖啡馆四人下午茶套餐",
        price=168.0,
        original_price=220.0,
        valid_until="2026-12-31",
        available=True,
    ),
]

_REST_MAP: dict[str, Restaurant] = {r.id: r for r in RESTAURANTS}
_COUPON_MAP: dict[str, Coupon] = {c.id: c for c in COUPONS}


def get_restaurant(restaurant_id: str) -> Restaurant | None:
    return _REST_MAP.get(restaurant_id)


def get_coupon(coupon_id: str) -> Coupon | None:
    return _COUPON_MAP.get(coupon_id)


def search_restaurants(
    near_location: str,
    group_size: int,
    preferences: list[str],
) -> list[Restaurant]:
    results = []
    for r in RESTAURANTS:
        if r.near_location != near_location:
            continue
        if preferences and not any(p in r.tags for p in preferences):
            continue
        results.append(r)
    if not results:
        results = [r for r in RESTAURANTS if r.near_location == near_location]
    return sorted(results, key=lambda r: (-r.rating, r.queue_minutes))


def get_coupons_for(target_id: str) -> list[Coupon]:
    return [c for c in COUPONS if c.target_id == target_id and c.available]
