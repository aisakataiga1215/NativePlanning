"""Execution action, execution result, and share message schemas.

These models describe the mock execution layer: the actions the executor
runs against the mock tools (booking, reservation, coupon purchase, add-on
orders), the structured result of each action, and the final shareable
message produced for family or friends.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ExecutionAction(BaseModel):
    """A single mock execution action requested by a plan.

    The executor consumes a list of these and dispatches them to the
    corresponding mock tool. `payload` is intentionally a free-form dict so
    each action type can carry its own parameters.
    """

    model_config = ConfigDict(extra="forbid")

    action_type: Literal[
        "book_venue",
        "reserve_restaurant",
        "purchase_coupon",
        "order_addon",
    ] = Field(
        ...,
        description="Which mock tool the executor should invoke.",
    )
    target_id: str = Field(
        ...,
        description="ID of the venue, restaurant, or coupon this action targets.",
    )
    payload: dict = Field(
        ...,
        description="Tool-specific parameters such as time slot, party size, or add-on items.",
    )
    required: bool = Field(
        default=True,
        description="If False, plan execution can succeed even when this action fails.",
    )
    status: Literal["pending", "success", "failed"] = Field(
        default="pending",
        description="Current execution status; updated by the executor.",
    )


class ExecutionResult(BaseModel):
    """Structured outcome of a single executed action.

    `order_id` and `booking_id` are populated on success depending on the
    action type. `error_reason` is populated on failure and surfaced to the
    user as part of the final summary.
    """

    model_config = ConfigDict(extra="forbid")

    action_type: str = Field(
        ...,
        description="The action_type from the originating ExecutionAction.",
    )
    status: Literal["success", "failed", "skipped"] = Field(
        ...,
        description="Terminal status of the executed action.",
    )
    order_id: Optional[str] = Field(
        default=None,
        description="Mock order identifier returned on successful coupon / add-on orders.",
    )
    booking_id: Optional[str] = Field(
        default=None,
        description="Mock booking identifier returned on successful venue / restaurant bookings.",
    )
    message: str = Field(
        ...,
        description="Human-readable result message shown in the demo.",
    )
    error_reason: Optional[str] = Field(
        default=None,
        description="Machine-readable failure reason such as 'no_seats' or 'venue_closed'.",
    )


class ShareMessage(BaseModel):
    """Final shareable plan message generated for family or friends.

    The message agent assembles this from the confirmed plan. The receiver
    type drives the tone and content of the message body.
    """

    model_config = ConfigDict(extra="forbid")

    receiver_type: Literal["wife", "partner", "friend_group", "family", "colleague_group", "unknown"] = Field(
        ...,
        description="Who the message is addressed to; drives tone and content.",
    )
    included_plan_id: str = Field(
        ...,
        description="ID of the ItineraryPlan summarised by this message.",
    )
    message: str = Field(
        ...,
        description="The natural language message body ready to be copied / shared.",
    )
