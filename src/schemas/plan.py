"""Itinerary plan schemas.

These models describe a fully-formed plan: the ordered list of steps, the
score breakdown used by the ranker, and surrounding metadata such as reasons,
risks, warnings, and required execution actions.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class PlanStep(BaseModel):
    """A single step in an itinerary, such as travel, activity, or meal.

    Steps are ordered and form a contiguous timeline. `related_entity_id`
    points back to the source venue / restaurant / coupon when applicable.
    """

    model_config = ConfigDict(extra="forbid")

    step_type: Literal["travel", "activity", "meal", "addon", "return"] = Field(
        ...,
        description="Type of step; drives downstream rendering and execution.",
    )
    title: str = Field(..., description="Short human-readable title for the step.")
    location_name: str = Field(
        ...,
        description="Display name of the location, e.g. venue or restaurant name.",
    )
    start_time: str = Field(
        ...,
        description="Start time in HH:MM 24-hour format, e.g. '14:00'.",
    )
    end_time: str = Field(
        ...,
        description="End time in HH:MM 24-hour format, e.g. '16:00'.",
    )
    duration_minutes: int = Field(
        ...,
        ge=0,
        description="Duration of this step in minutes.",
    )
    distance_from_previous_km: float = Field(
        default=0.0,
        ge=0.0,
        description="Distance from the previous step in kilometres.",
    )
    notes: str = Field(
        default="",
        description="Optional planner notes shown to the user, e.g. why this step fits.",
    )
    related_entity_id: Optional[str] = Field(
        default=None,
        description="ID of the venue, restaurant, or coupon backing this step.",
    )


class ScoreBreakdown(BaseModel):
    """Per-dimension scores used by the plan ranker.

    Higher is better. The aggregate plan score is derived from these
    components in the ranker service.
    """

    model_config = ConfigDict(extra="forbid")

    distance_score: float = Field(
        ...,
        description="How well the plan fits the user's distance budget.",
    )
    time_score: float = Field(
        ...,
        description="How well the plan fits the available time window.",
    )
    group_fit_score: float = Field(
        ...,
        description="How well the plan fits the group composition (e.g. child-friendliness).",
    )
    restaurant_score: float = Field(
        ...,
        description="Quality / suitability of the chosen restaurant.",
    )
    execution_score: float = Field(
        ...,
        description="Likelihood the plan can actually be executed (reservations, tickets).",
    )


class ItineraryPlan(BaseModel):
    """A complete, executable plan ready to be shown to the user.

    `required_actions` lists the action types the executor must run before
    the plan is fully confirmed. `warnings` carries repair / fallback notes
    surfaced by the constraint validator and ranker.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Stable plan identifier, e.g. 'plan_001'.")
    title: str = Field(..., description="Short human-readable plan title.")
    scenario_type: Literal["solo", "couple", "family", "friends", "colleagues", "unknown"] = Field(
        ...,
        description="Scenario this plan targets; should match the user intent.",
    )
    summary: str = Field(
        ...,
        description="One-paragraph natural language summary of the plan.",
    )
    steps: list[PlanStep] = Field(
        ...,
        description="Ordered list of plan steps forming the timeline.",
    )
    estimated_total_cost: float = Field(
        ...,
        ge=0.0,
        description="Estimated total cost for the group in CNY.",
    )
    total_duration_minutes: int = Field(
        ...,
        ge=0,
        description="Total duration of the plan in minutes.",
    )
    score: float = Field(
        ...,
        description="Aggregate score produced by the plan ranker.",
    )
    score_breakdown: ScoreBreakdown = Field(
        ...,
        description="Per-dimension scores used to compute the aggregate score.",
    )
    reasons: list[str] = Field(
        ...,
        description="Natural language reasons why this plan fits the user's intent.",
    )
    risks: list[str] = Field(
        ...,
        description="Known risks such as queue time or weather sensitivity.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Repair / fallback notes added by the constraint validator.",
    )
    required_actions: list[str] = Field(
        ...,
        description="ExecutionAction.action_type strings required before the plan is confirmed.",
    )
    backup_plan_id: Optional[str] = Field(
        default=None,
        description="ID of an alternative plan to show as a backup.",
    )
    venue_id: Optional[str] = Field(
        default=None,
        description="Primary venue for this plan, when applicable.",
    )
    restaurant_id: Optional[str] = Field(
        default=None,
        description="Primary restaurant for this plan, when applicable.",
    )
