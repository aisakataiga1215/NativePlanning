from __future__ import annotations

from src.schemas.order import ExecutionResult
from src.schemas.plan import ItineraryPlan
from src.schemas.user_intent import UserIntent
from src.tools.wrappers import TraceLog, traced_call
import src.mock_api as mock


def execute_plan(
    plan: ItineraryPlan,
    intent: UserIntent,
    log: TraceLog,
) -> list[ExecutionResult]:
    results: list[ExecutionResult] = []
    meal_step = next((s for s in plan.steps if s.step_type == "meal"), None)
    meal_time = meal_step.start_time if meal_step else "17:00"

    for action in plan.required_actions:
        if action == "book_venue" and plan.venue_id:
            result = traced_call(
                "book_venue", mock.book_venue, log,
                venue_id=plan.venue_id,
                date=intent.date,
                time=intent.time,
                group_size=intent.group_size,
            )
            results.append(result)

        elif action == "reserve_restaurant" and plan.restaurant_id:
            result = traced_call(
                "reserve_restaurant", mock.reserve_restaurant, log,
                restaurant_id=plan.restaurant_id,
                date=intent.date,
                time=meal_time,
                group_size=intent.group_size,
            )
            results.append(result)

    return results
