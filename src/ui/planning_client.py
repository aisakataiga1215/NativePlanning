"""Backend client abstraction for the Streamlit UI.

The UI calls `generate()` and `execute()` through a single `PlanningClient`
protocol. Two implementations are provided:

* `InProcessClient` — imports the workflow modules directly (same code path
  as the CLI). Used by default.
* `HttpClient` — calls the FastAPI endpoints via httpx. Used when
  `NATIVE_PLANNING_API_URL` is set in the environment.

Both clients return `GenerateResponse` / `ExecuteResponse` from
`src/api/schemas.py`, so the UI layer is mode-agnostic and the trace list
shape is identical (`list[dict]`) in either mode.
"""
from __future__ import annotations

import os
from typing import Protocol

import httpx

from src.api.app import _trace_to_dict
from src.api.schemas import ExecuteResponse, GenerateResponse
from src.schemas.plan import ItineraryPlan
from src.schemas.user_intent import UserIntent
from src.services.plan_ranker import rank_plans, get_explicit_venue_ids
from src.tools.wrappers import TraceLog
from src.workflow.constraint_solver import validate_and_repair
from src.workflow.executor import execute_plan
from src.workflow.intent_parser import parse_free_text
from src.workflow.message_agent import generate_share_message
from src.workflow.planner import generate_plans, revise_meal_policy_only, revise_restaurant_only, revise_venue_only
from src.workflow.revision_parser import apply_revision

_DEFAULT_HTTP_TIMEOUT_SECONDS = 30.0


class PlanningClient(Protocol):
    """Protocol shared by in-process and HTTP backends."""

    def generate(self, user_input: str) -> GenerateResponse: ...

    def execute(
        self, plan: ItineraryPlan, intent: UserIntent
    ) -> ExecuteResponse: ...

    def revise(
        self, revision_text: str, intent: UserIntent,
        current_plan: ItineraryPlan | None = None,
    ) -> GenerateResponse: ...


class InProcessClient:
    """Run the workflow in-process (same modules the CLI imports)."""

    def generate(self, user_input: str) -> GenerateResponse:
        log = TraceLog()
        intent = parse_free_text(user_input)
        plans = generate_plans(intent, log)
        repaired = [validate_and_repair(p, intent, log) for p in plans]
        _pinned = get_explicit_venue_ids(intent.requested_activities) if intent.requested_activities else None
        ranked = rank_plans(
            repaired, intent.max_distance_km, intent.duration_hours,
            participants=intent.participants or None,
            requested_activities=intent.requested_activities or None,
            hard_constraints=intent.hard_constraints or None,
            location_anchor=intent.location_anchor,
            requested_meals=intent.requested_meals or None,
            pinned_venue_ids=_pinned or None,
        )
        best = ranked[0]
        return GenerateResponse(
            plan=best,
            alternatives=ranked[1:3],
            intent=intent,
            traces=[_trace_to_dict(t) for t in log.traces],
            warnings=best.warnings,
        )

    def execute(
        self, plan: ItineraryPlan, intent: UserIntent
    ) -> ExecuteResponse:
        log = TraceLog()
        results = execute_plan(plan, intent, log)
        msg = generate_share_message(plan, results, intent)
        return ExecuteResponse(
            results=results,
            share_message=msg,
            traces=[_trace_to_dict(t) for t in log.traces],
        )

    def revise(
        self, revision_text: str, intent: UserIntent,
        current_plan: ItineraryPlan | None = None,
    ) -> GenerateResponse:
        log = TraceLog()
        updated_intent = apply_revision(intent, revision_text, current_plan)
        scope = updated_intent.revision_scope
        venue_pin: list[str] = []
        if scope == "restaurant_only" and current_plan:
            plans = revise_restaurant_only(updated_intent, current_plan, log)
        elif scope == "venue_only" and current_plan:
            plans = revise_venue_only(updated_intent, current_plan, log)
        elif scope == "meal_policy_only" and current_plan:
            venue_pin = [current_plan.venue_id] if current_plan.venue_id else []
            plans = revise_meal_policy_only(updated_intent, current_plan, log)
        else:
            plans = generate_plans(updated_intent, log)
        repaired = [validate_and_repair(p, updated_intent, log) for p in plans]
        _explicit = get_explicit_venue_ids(updated_intent.requested_activities) if updated_intent.requested_activities else []
        _pinned_r = list(dict.fromkeys(_explicit + venue_pin)) or None
        ranked = rank_plans(
            repaired, updated_intent.max_distance_km, updated_intent.duration_hours,
            participants=updated_intent.participants or None,
            requested_activities=updated_intent.requested_activities or None,
            hard_constraints=updated_intent.hard_constraints or None,
            location_anchor=updated_intent.location_anchor,
            requested_meals=updated_intent.requested_meals or None,
            pinned_venue_ids=_pinned_r or None,
        )
        best = ranked[0]
        return GenerateResponse(
            plan=best,
            alternatives=ranked[1:3],
            intent=updated_intent,
            traces=[_trace_to_dict(t) for t in log.traces],
            warnings=best.warnings,
        )


class HttpClient:
    """Hit the FastAPI endpoints over HTTP."""

    def __init__(
        self, base_url: str, timeout: float = _DEFAULT_HTTP_TIMEOUT_SECONDS
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def generate(self, user_input: str) -> GenerateResponse:
        with httpx.Client(timeout=self.timeout, trust_env=False) as client:
            response = client.post(
                f"{self.base_url}/api/plans/generate",
                json={"user_input": user_input},
            )
            response.raise_for_status()
            return GenerateResponse.model_validate(response.json())

    def execute(
        self, plan: ItineraryPlan, intent: UserIntent
    ) -> ExecuteResponse:
        payload = {
            "plan": plan.model_dump(),
            "intent": intent.model_dump(),
        }
        with httpx.Client(timeout=self.timeout, trust_env=False) as client:
            response = client.post(
                f"{self.base_url}/api/plans/execute",
                json=payload,
            )
            response.raise_for_status()
            return ExecuteResponse.model_validate(response.json())

    def revise(
        self, revision_text: str, intent: UserIntent,
        current_plan: ItineraryPlan | None = None,
    ) -> GenerateResponse:
        payload = {
            "revision_text": revision_text,
            "intent": intent.model_dump(),
            "current_plan": current_plan.model_dump() if current_plan else None,
        }
        with httpx.Client(timeout=self.timeout, trust_env=False) as client:
            response = client.post(
                f"{self.base_url}/api/plans/revise",
                json=payload,
            )
            response.raise_for_status()
            return GenerateResponse.model_validate(response.json())


def make_client() -> PlanningClient:
    """Return an `HttpClient` when `NATIVE_PLANNING_API_URL` is set, else an `InProcessClient`."""
    url = os.getenv("NATIVE_PLANNING_API_URL")
    if url:
        return HttpClient(url)
    return InProcessClient()
