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
        if action == "book_venue":
            if not plan.venue_id:
                results.append(ExecutionResult(
                    action_type=action, status="skipped",
                    message="无场馆 ID，已跳过门票预订",
                ))
                continue
            result = traced_call(
                "book_venue", mock.book_venue, log,
                venue_id=plan.venue_id,
                date=intent.date,
                time=intent.time,
                group_size=intent.group_size,
            )
            results.append(result)

        elif action == "reserve_restaurant":
            if not plan.restaurant_id:
                results.append(ExecutionResult(
                    action_type=action, status="skipped",
                    message="无餐厅 ID，已跳过餐厅预约",
                ))
                continue
            result = traced_call(
                "reserve_restaurant", mock.reserve_restaurant, log,
                restaurant_id=plan.restaurant_id,
                date=intent.date,
                time=meal_time,
                group_size=intent.group_size,
            )
            results.append(result)

        else:
            results.append(ExecutionResult(
                action_type=action, status="skipped",
                message=f"未知操作类型 {action!r}，已跳过",
            ))

    return results
