"""Restaurant and coupon schemas.

`Restaurant` represents a dining option near a venue. `Coupon` represents a
mock purchasable deal that can target either a venue or a restaurant. Both
are returned by mock tools and consumed by the planner / executor.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.coupon_package import Package, RestaurantCoupon


class Restaurant(BaseModel):
    """A dining option associated with (typically near) a venue.

    `available_seats == 0` triggers the "fully booked" failure case used in
    demo scenarios. `available_slots` lists concrete reservation times that
    can be passed to `reserve_restaurant`.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Stable restaurant identifier, e.g. 'rest_001'.")
    name: str = Field(..., description="Display name of the restaurant.")
    tags: list[str] = Field(
        ...,
        description="Free-form tags, e.g. 'kid_friendly', 'low_calorie', 'photo'.",
    )
    near_location: str = Field(
        ...,
        description="ID of the venue this restaurant is near, or 'home'.",
    )
    distance_from_venue_km: float = Field(
        ...,
        ge=0.0,
        description="Walking/driving distance from the associated venue in km.",
    )
    avg_price_per_person: float = Field(
        ...,
        ge=0.0,
        description="Average per-person spend in CNY.",
    )
    rating: float = Field(
        ...,
        ge=0.0,
        le=5.0,
        description="Average user rating on a 0-5 scale.",
    )
    open_time: str = Field(
        ...,
        description="Opening time in HH:MM 24-hour format.",
    )
    close_time: str = Field(
        ...,
        description="Closing time in HH:MM 24-hour format.",
    )
    queue_minutes: int = Field(
        ...,
        ge=0,
        description="Estimated walk-in queue length in minutes.",
    )
    noise_level: Literal["quiet", "moderate", "loud"] = Field(
        default="moderate",
        description="Ambient noise level: 'quiet', 'moderate', or 'loud'.",
    )
    reservation_available: bool = Field(
        ...,
        description="Whether reservations can be made through the mock API.",
    )
    has_kids_menu: bool = Field(
        ...,
        description="Whether a children's menu is available.",
    )
    has_low_calorie_options: bool = Field(
        ...,
        description="Whether low-calorie / diet-friendly options are available.",
    )
    available_seats: int = Field(
        ...,
        ge=0,
        description="Number of seats currently available; 0 triggers the no-seats failure.",
    )
    available_slots: list[str] = Field(
        ...,
        description="Reservable time slots in HH:MM format, e.g. ['17:00', '17:30'].",
    )

    # --- MVP-4: duration range ---
    suggested_meal_duration_min: int = Field(
        default=60,
        ge=0,
        description="Minimum sensible meal duration in minutes.",
    )
    suggested_meal_duration_max: int = Field(
        default=90,
        ge=0,
        description="Maximum sensible meal duration in minutes.",
    )

    # --- MVP-4: rich review data ---
    review_count: int = Field(
        default=0,
        ge=0,
        description="Number of user reviews on the platform.",
    )
    positive_review_tags: list[str] = Field(
        default_factory=list,
        description="Top positive review tags, e.g. ['出品稳定', '服务好', '环境安静'].",
    )
    negative_review_tags: list[str] = Field(
        default_factory=list,
        description="Top negative review tags, e.g. ['节假日排队长', '停车不便'].",
    )
    recommended_dishes: list[str] = Field(
        default_factory=list,
        description="Signature / frequently-ordered dishes, e.g. ['招牌牛肉面', '秘制红烧肉'].",
    )
    specialty_tags: list[str] = Field(
        default_factory=list,
        description="Marketing highlight tags, e.g. ['网红打卡', '情侣首选'].",
    )

    # --- MVP-4: area / location ---
    area: str = Field(
        default="",
        description="District or landmark area this restaurant belongs to.",
    )
    nearby_areas: list[str] = Field(
        default_factory=list,
        description="Adjacent areas that this restaurant is considered near.",
    )

    # --- MVP-4: promotions ---
    packages: list[Package] = Field(
        default_factory=list,
        description="Bundled meal deals, e.g. double set meal.",
    )
    restaurant_coupons: list[RestaurantCoupon] = Field(
        default_factory=list,
        description="Discount coupons available for this restaurant.",
    )


class Coupon(BaseModel):
    """A mock purchasable coupon for a venue or restaurant.

    Coupons are simple deterministic objects used to demonstrate the
    `purchase_coupon` action in the executor.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Stable coupon identifier, e.g. 'coupon_001'.")
    target_id: str = Field(
        ...,
        description="ID of the venue or restaurant the coupon applies to.",
    )
    target_type: Literal["venue", "restaurant"] = Field(
        ...,
        description="Whether the coupon targets a venue or a restaurant.",
    )
    title: str = Field(..., description="Human-readable coupon title.")
    price: float = Field(
        ...,
        ge=0.0,
        description="Discounted price the user pays in CNY.",
    )
    original_price: float = Field(
        ...,
        ge=0.0,
        description="Original full price in CNY before the coupon.",
    )
    valid_until: str = Field(
        ...,
        description="Expiry date or datetime string, e.g. 'YYYY-MM-DD'.",
    )
    available: bool = Field(
        ...,
        description="Whether the coupon is currently purchasable.",
    )
