"""Pydantic v2 schemas for the NativePlanning MVP.

Re-exports all data models so callers can simply do:

    from src.schemas import UserIntent, Venue, Restaurant, ...

Schemas are grouped into themed modules:

* ``user_intent`` - parsed user request and participant profiles
* ``venue`` - POI / activity venues returned by the mock POI tool
* ``restaurant`` - dining options and coupons
* ``plan`` - itinerary plans, plan steps, and score breakdown
* ``order`` - execution actions, results, and the final share message
"""

from src.schemas.order import ExecutionAction, ExecutionResult, ShareMessage
from src.schemas.plan import ItineraryPlan, PlanStep, ScoreBreakdown
from src.schemas.restaurant import Coupon, Restaurant
from src.schemas.user_intent import PersonProfile, UserIntent
from src.schemas.venue import Venue

__all__ = [
    "Coupon",
    "ExecutionAction",
    "ExecutionResult",
    "ItineraryPlan",
    "PersonProfile",
    "PlanStep",
    "Restaurant",
    "ScoreBreakdown",
    "ShareMessage",
    "UserIntent",
    "Venue",
]
