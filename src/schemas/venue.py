"""Venue (POI / activity location) schema.

Represents a place the user can visit: kids playgrounds, lake parks, museums,
gardens, and similar local-life points of interest. Returned by the mock POI
search tool and consumed by the planner.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.coupon_package import Package, TicketOption, VenueCoupon


class Venue(BaseModel):
    """A point-of-interest / activity venue returned by the mock POI tool.

    Fields are intentionally flat so the planner can score venues without
    additional joins. `available_tickets == 0` is used to trigger the
    "no tickets" failure case in the demo.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Stable venue identifier, e.g. 'venue_001'.")
    name: str = Field(..., description="Display name of the venue.")
    type: str = Field(
        ...,
        description="Category tag such as 'kids_playground', 'lake_park', 'museum', 'garden'.",
    )
    tags: list[str] = Field(
        ...,
        description="Free-form tags used for matching, e.g. 'parent_child', 'photo'.",
    )
    distance_km: float = Field(
        ...,
        ge=0.0,
        description="Distance from the user's home in kilometres.",
    )
    suggested_duration_minutes: int = Field(
        ...,
        gt=0,
        description="Typical visit duration in minutes.",
    )
    suitable_age_min: int = Field(
        default=0,
        ge=0,
        description="Minimum suitable age in years.",
    )
    suitable_age_max: int = Field(
        default=99,
        ge=0,
        description="Maximum suitable age in years.",
    )
    open_time: str = Field(
        ...,
        description="Opening time in HH:MM 24-hour format.",
    )
    close_time: str = Field(
        ...,
        description="Closing time in HH:MM 24-hour format.",
    )
    price_per_person: float = Field(
        ...,
        ge=0.0,
        description="Per-person ticket / entry price in CNY.",
    )
    rating: float = Field(
        ...,
        ge=0.0,
        le=5.0,
        description="Average user rating on a 0-5 scale.",
    )
    indoor: bool = Field(
        ...,
        description="True if the venue is primarily indoors (used for weather fallback).",
    )
    requires_ticket: bool = Field(
        ...,
        description="True if a ticket / reservation is required before entry.",
    )
    available_tickets: int = Field(
        ...,
        ge=0,
        description="Number of tickets currently available; 0 triggers the no-tickets failure.",
    )
    walk_intensity: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="Physical walking demand: 'low' (seated/indoor), 'medium', 'high' (heavy hiking).",
    )
    noise_level: Literal["quiet", "moderate", "loud"] = Field(
        default="moderate",
        description="Ambient noise level: 'quiet', 'moderate', or 'loud'.",
    )
    queue_minutes: int = Field(
        default=0,
        ge=0,
        description="Estimated entry queue length in minutes.",
    )

    # --- MVP-4: duration range ---
    suggested_duration_min: int = Field(
        default=60,
        ge=0,
        description="Minimum sensible visit duration in minutes.",
    )
    suggested_duration_max: int = Field(
        default=120,
        ge=0,
        description="Maximum sensible visit duration in minutes.",
    )
    duration_flexibility: Literal["low", "medium", "high"] = Field(
        default="medium",
        description=(
            "'low' = fixed-duration (movie/escape_room/theme_park); "
            "'medium' = adjustable ±30 min; 'high' = very flexible (park/citywalk)."
        ),
    )

    # --- MVP-4: rich review data ---
    review_count: int = Field(
        default=0,
        ge=0,
        description="Number of user reviews on the platform.",
    )
    positive_review_tags: list[str] = Field(
        default_factory=list,
        description="Top positive review tags, e.g. ['环境好', '适合亲子', '性价比高'].",
    )
    negative_review_tags: list[str] = Field(
        default_factory=list,
        description="Top negative review tags, e.g. ['节假日排队长', '停车困难'].",
    )
    specialty_tags: list[str] = Field(
        default_factory=list,
        description="Marketing highlight tags, e.g. ['网红打卡', '亲子推荐', '情侣首选'].",
    )

    # --- MVP-4: area / location ---
    area: str = Field(
        default="",
        description="District or landmark area this venue belongs to, e.g. '芳华街', '云景'.",
    )
    nearby_areas: list[str] = Field(
        default_factory=list,
        description="Adjacent areas that this venue is considered part of.",
    )

    # --- MVP-4: promotions ---
    packages: list[Package] = Field(
        default_factory=list,
        description="Bundled deals available for this venue (e.g. family ticket).",
    )
    venue_coupons: list[VenueCoupon] = Field(
        default_factory=list,
        description="Discount coupons available for this venue.",
    )
    ticket_options: list[TicketOption] = Field(default_factory=list)
