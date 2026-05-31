from src.schemas.venue import Venue

VENUES: list[Venue] = [
    Venue(
        id="venue_001",
        name="森林亲子乐园",
        type="kids_playground",
        tags=["parent_child", "kids", "indoor", "family_friendly"],
        distance_km=3.2,
        suggested_duration_minutes=120,
        suitable_age_min=3,
        suitable_age_max=12,
        open_time="09:00",
        close_time="20:00",
        price_per_person=88.0,
        rating=4.7,
        indoor=True,
        requires_ticket=True,
        available_tickets=30,
    ),
    Venue(
        id="venue_002",
        name="城市湖边公园",
        type="lake_park",
        tags=["outdoor", "walk", "photo", "family_friendly", "free"],
        distance_km=2.1,
        suggested_duration_minutes=90,
        suitable_age_min=0,
        suitable_age_max=99,
        open_time="06:00",
        close_time="21:00",
        price_per_person=0.0,
        rating=4.5,
        indoor=False,
        requires_ticket=False,
        available_tickets=999,
    ),
    Venue(
        id="venue_003",
        name="科技探索博物馆",
        type="museum",
        tags=["educational", "indoor", "kids", "family_friendly", "parent_child"],
        distance_km=4.8,
        suggested_duration_minutes=150,
        suitable_age_min=5,
        suitable_age_max=99,
        open_time="09:30",
        close_time="17:30",
        price_per_person=60.0,
        rating=4.6,
        indoor=True,
        requires_ticket=True,
        available_tickets=50,
    ),
    Venue(
        id="venue_004",
        name="植物园温室",
        type="garden",
        tags=["outdoor", "indoor", "photo", "walk", "family_friendly", "romantic"],
        distance_km=5.5,
        suggested_duration_minutes=120,
        suitable_age_min=0,
        suitable_age_max=99,
        open_time="08:00",
        close_time="18:00",
        price_per_person=40.0,
        rating=4.4,
        indoor=False,
        requires_ticket=True,
        available_tickets=20,
    ),
    Venue(
        id="venue_005",
        name="创意艺术中心",
        type="art_center",
        tags=["indoor", "art", "photo", "friends", "social"],
        distance_km=3.9,
        suggested_duration_minutes=100,
        suitable_age_min=8,
        suitable_age_max=99,
        open_time="10:00",
        close_time="21:00",
        price_per_person=55.0,
        rating=4.3,
        indoor=True,
        requires_ticket=True,
        available_tickets=15,
    ),
    Venue(
        id="venue_006",
        name="室内攀岩体验馆",
        type="climbing",
        tags=["sports", "indoor", "adventure", "friends", "active"],
        distance_km=6.2,
        suggested_duration_minutes=90,
        suitable_age_min=10,
        suitable_age_max=50,
        open_time="10:00",
        close_time="22:00",
        price_per_person=120.0,
        rating=4.5,
        indoor=True,
        requires_ticket=True,
        available_tickets=10,
    ),
]

_VENUE_MAP: dict[str, Venue] = {v.id: v for v in VENUES}


def get_venue(venue_id: str) -> Venue | None:
    return _VENUE_MAP.get(venue_id)


def search_venues(
    scenario_type: str,
    max_distance_km: float,
    tags: list[str],
) -> list[Venue]:
    results = []
    for venue in VENUES:
        if venue.distance_km > max_distance_km:
            continue
        if tags and not any(t in venue.tags for t in tags):
            continue
        results.append(venue)
    return sorted(results, key=lambda v: (-v.rating, v.distance_km))
