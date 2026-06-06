"""User intent and person profile schemas.

These models capture the parsed natural language request from the user and the
participants in the planned activity. They are produced by the intent parser
and consumed by the planning pipeline.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class Participant(BaseModel):
    """A participant in the outing, with age/role for audience-aware ranking."""

    model_config = ConfigDict(extra="forbid")

    role: Literal[
        "self", "spouse", "partner", "child", "parent",
        "elderly", "friend", "colleague", "unknown",
    ] = "unknown"
    age: Optional[int] = Field(default=None, description="Exact age in years when known.")
    age_group: Literal[
        "young_child", "child", "teenager", "young_adult",
        "adult", "senior", "unknown",
    ] = "adult"
    notes: list[str] = Field(default_factory=list)


class PersonProfile(BaseModel):
    """A single participant in the planned activity.

    Captures role within the group, age information for child-friendliness
    checks, dietary goals, and free-form preferences/constraints.
    """

    model_config = ConfigDict(extra="forbid")

    role: str = Field(
        ...,
        description="Role in the group: 'user', 'wife', 'child', 'friend', etc.",
    )
    age: Optional[int] = Field(
        default=None,
        description="Exact age in years when known.",
    )
    age_group: Literal["adult", "child", "senior"] = Field(
        default="adult",
        description="Coarse-grained age bucket used by planning rules.",
    )
    diet_goal: Optional[str] = Field(
        default=None,
        description="Dietary goal such as 'weight_loss' or 'none'.",
    )
    preferences: list[str] = Field(
        default_factory=list,
        description="Positive preferences such as 'spicy' or 'outdoor'.",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Hard constraints such as 'no_seafood' or 'no_stairs'.",
    )


class UserIntent(BaseModel):
    """Structured representation of the user's natural language request.

    Produced by the intent parser and used as the input contract for the
    planner agent. All fields have safe defaults so partial parses still
    produce a valid intent object.
    """

    model_config = ConfigDict(extra="forbid")

    scenario_type: Literal["solo", "couple", "family", "friends", "colleagues", "unknown"] = Field(
        default="unknown",
        description="High-level scenario used to select planning heuristics.",
    )
    group_size: int = Field(
        default=2,
        ge=1,
        description="Total number of participants including the user.",
    )
    people: list[PersonProfile] = Field(
        default_factory=list,
        description="Profiles of each participant when known.",
    )
    date: str = Field(
        default="today",
        description="Target date, e.g. 'today' or 'YYYY-MM-DD'.",
    )
    weekday: str = Field(
        default="",
        description="周一…周日，由 datetime_parser 填写",
    )
    time_period: str = Field(
        default="",
        description="morning|noon|afternoon|evening|night|soon|unknown",
    )
    revision_scope: str = Field(
        default="",
        description="restaurant_only|venue_only|''",
    )
    time: str = Field(
        default="14:00",
        description="Target start time in HH:MM 24-hour format.",
    )
    duration_hours: float = Field(
        default=5.0,
        gt=0.0,
        description="Approximate duration of the whole outing in hours.",
    )
    max_distance_km: float = Field(
        default=5.0,
        ge=0.0,
        description="Maximum acceptable distance from home in kilometres.",
    )
    activity_preferences: list[str] = Field(
        default_factory=list,
        description="Preferred activity tags such as 'parent_child' or 'photo'.",
    )
    meal_preferences: list[str] = Field(
        default_factory=list,
        description="Meal preferences such as 'low_calorie' or 'kid_friendly'.",
    )
    requested_activities: list[str] = Field(
        default_factory=list,
        description="Activity types explicitly named by user: 'kids_playground', 'exhibition', etc.",
    )
    requested_meals: list[str] = Field(
        default_factory=list,
        description="Meal types explicitly named: 'hotpot', 'japanese', 'western', etc.",
    )
    requested_places: list[str] = Field(
        default_factory=list,
        description="Specific places explicitly named: '芳华街', '湖边公园', etc.",
    )
    place_preferences: list[str] = Field(
        default_factory=list,
        description="Inferred place preferences from group context.",
    )
    hard_constraints: list[str] = Field(
        default_factory=list,
        description="Must-not-violate constraints: 'avoid_long_walk', 'avoid_long_queue', etc.",
    )
    soft_preferences: list[str] = Field(
        default_factory=list,
        description="Tradeable preferences: 'elderly_friendly', 'business_casual', etc.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Parser-generated notices e.g. 'no children but kids_playground requested'.",
    )
    participants: list[Participant] = Field(
        default_factory=list,
        description="Structured participant list for audience-aware ranking.",
    )
    budget_preference: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="Overall budget tier for the outing.",
    )
    meal_policy: Literal["required", "optional", "excluded"] = Field(
        default="required",
        description="Meal arrangement policy: required=always plan a meal, optional=skip if no good match, excluded=do not arrange any meal.",
    )
    plan_mode: Literal["activity_first", "meal_first", "meal_only"] = Field(
        default="activity_first",
        description="Planning mode: activity_first=normal, meal_first=meal is primary goal, meal_only=only search restaurants.",
    )
    special_constraints: list[str] = Field(
        default_factory=list,
        description="Free-form constraints not covered by structured fields.",
    )
    raw_input: Optional[str] = Field(
        default=None,
        description="Original natural language input from the user.",
    )
    source: Literal["llm", "rule_based", "unknown"] = Field(
        default="unknown",
        description="Which code path produced this intent: 'llm', 'rule_based', or 'unknown'.",
    )
    avoid_venue_ids: list[str] = Field(
        default_factory=list,
        description="Venue IDs to exclude from planning (e.g. after 'change venue' revision).",
    )
    avoid_restaurant_ids: list[str] = Field(
        default_factory=list,
        description="Restaurant IDs to exclude from planning (e.g. after 'change restaurant' revision).",
    )

    # --- MVP-4: location anchor ---
    location_anchor: str = Field(
        default="",
        description="User-specified area anchor for the outing, e.g. '芳华街', '云景', '公司附近'.",
    )
    anchor_place: str = Field(
        default="",
        description="Specific place name within the anchor area, e.g. '芳华街 SOHO'.",
    )
