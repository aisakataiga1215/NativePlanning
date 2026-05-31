"""Restaurant and coupon schemas.

`Restaurant` represents a dining option near a venue. `Coupon` represents a
mock purchasable deal that can target either a venue or a restaurant. Both
are returned by mock tools and consumed by the planner / executor.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
