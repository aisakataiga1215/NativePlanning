"""FastAPI application for NativePlanning MVP-1.

Endpoints:
    POST /api/plans/generate  — parse intent + build best plan
    POST /api/plans/execute   — execute a confirmed plan (stateless)
    GET  /api/health          — liveness check
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.api.schemas import (
    ExecuteRequest,
    ExecuteResponse,
    GenerateRequest,
    GenerateResponse,
    ReviseRequest,
)
from src.services.plan_ranker import rank_plans, get_explicit_venue_ids
from src.tools.wrappers import ToolTrace, TraceLog
from src.workflow.constraint_solver import validate_and_repair
from src.workflow.executor import execute_plan
from src.workflow.intent_parser import parse_free_text
from src.workflow.message_agent import generate_share_message
from src.workflow.planner import generate_plans, revise_meal_policy_only, revise_restaurant_only, revise_venue_only
from src.workflow.revision_parser import apply_revision

load_dotenv(_PROJECT_ROOT / ".env")

app = FastAPI(title="NativePlanning API", version="0.1.0")


def _serialize_output(output: Any) -> Any:
    """Convert ToolTrace.output to a JSON-serializable value."""
    if output is None:
        return None
    if hasattr(output, "model_dump"):
        return output.model_dump()
    if isinstance(output, list):
        return [
            item.model_dump() if hasattr(item, "model_dump") else item
            for item in output
        ]
    if isinstance(output, dict):
        return output
    return str(output)


def _trace_to_dict(trace: ToolTrace) -> dict:
    return {
        "tool_name": trace.tool_name,
        "inputs": trace.inputs,
        "output": _serialize_output(trace.output),
        "status": trace.status,
        "elapsed_ms": trace.elapsed_ms,
        "error": trace.error,
    }


@app.post("/api/plans/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest) -> GenerateResponse:
    log = TraceLog()
    intent = parse_free_text(request.user_input)
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


@app.post("/api/plans/execute", response_model=ExecuteResponse)
async def execute(request: ExecuteRequest) -> ExecuteResponse:
    log = TraceLog()
    results = execute_plan(request.plan, request.intent, log)
    msg = generate_share_message(request.plan, results, request.intent)
    return ExecuteResponse(
        results=results,
        share_message=msg,
        traces=[_trace_to_dict(t) for t in log.traces],
    )


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/api/plans/revise", response_model=GenerateResponse)
async def revise(request: ReviseRequest) -> GenerateResponse:
    log = TraceLog()
    updated_intent = apply_revision(request.intent, request.revision_text, request.current_plan)
    scope = updated_intent.revision_scope
    venue_pin: list[str] = []
    if scope == "restaurant_only" and request.current_plan:
        plans = revise_restaurant_only(updated_intent, request.current_plan, log)
    elif scope == "venue_only" and request.current_plan:
        plans = revise_venue_only(updated_intent, request.current_plan, log)
    elif scope == "meal_policy_only" and request.current_plan:
        venue_pin = [request.current_plan.venue_id] if request.current_plan.venue_id else []
        plans = revise_meal_policy_only(updated_intent, request.current_plan, log)
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
