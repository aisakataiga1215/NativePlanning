"""Lightweight coupon and package schemas for venues and restaurants.

These are display/metadata objects used to show available deals in the UI
and to apply a small promo bonus in the plan ranker. They are distinct from
the executor-facing `Coupon` in restaurant.py, which represents a mock
purchasable deal used during the execution phase.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Package(BaseModel):
    """A bundled deal (e.g. family ticket, couple combo) for a venue or restaurant."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Stable package identifier.")
    title: str = Field(..., description="Human-readable title, e.g. '家庭套票（2大1小）'.")
    price: float = Field(..., ge=0.0, description="Package price in CNY.")
    original_price: float = Field(..., ge=0.0, description="Original full price in CNY.")
    includes: list[str] = Field(
        default_factory=list,
        description="What the package includes, e.g. ['门票×3', '餐饮券×1'].",
    )


class VenueCoupon(BaseModel):
    """A discount coupon applicable to a venue entry fee."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Stable coupon identifier.")
    title: str = Field(..., description="Human-readable title, e.g. '立减20元'.")
    discount_type: Literal["fixed", "percent"] = Field(
        default="fixed",
        description="'fixed' = CNY amount off; 'percent' = multiplier (e.g. 0.85 for 85折).",
    )
    value: float = Field(..., ge=0.0, description="Discount value (CNY or multiplier).")
    min_spend: float = Field(default=0.0, ge=0.0, description="Minimum spend to activate.")
    available: bool = Field(default=True, description="Whether the coupon is currently active.")


class RestaurantCoupon(BaseModel):
    """A discount coupon applicable to a restaurant bill."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Stable coupon identifier.")
    title: str = Field(..., description="Human-readable title, e.g. '满100减20'.")
    discount_type: Literal["fixed", "percent"] = Field(
        default="fixed",
        description="'fixed' = CNY amount off; 'percent' = multiplier.",
    )
    value: float = Field(..., ge=0.0, description="Discount value (CNY or multiplier).")
    min_spend: float = Field(default=0.0, ge=0.0, description="Minimum spend to activate.")
    available: bool = Field(default=True, description="Whether the coupon is currently active.")


class TicketOption(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["adult", "student", "senior", "child", "family"]
    price: float = Field(ge=0.0)
    note: str = ""
    available: bool = True
