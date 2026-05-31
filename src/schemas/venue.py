"""Venue (POI / activity location) schema.

Represents a place the user can visit: kids playgrounds, lake parks, museums,
gardens, and similar local-life points of interest. Returned by the mock POI
search tool and consumed by the planner.
"""

from pydantic import BaseModel, ConfigDict, Field


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
