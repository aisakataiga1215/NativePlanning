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
)
from src.services.plan_ranker import rank_plans
from src.tools.wrappers import ToolTrace, TraceLog
from src.workflow.constraint_solver import validate_and_repair
from src.workflow.executor import execute_plan
from src.workflow.intent_parser import parse_free_text
from src.workflow.message_agent import generate_share_message
from src.workflow.planner import generate_candidate_plans

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
    plans = generate_candidate_plans(intent, log)
    repaired = [validate_and_repair(p, intent, log) for p in plans]
    ranked = rank_plans(
        repaired, intent.max_distance_km, intent.duration_hours,
        participants=intent.participants or None,
        requested_activities=intent.requested_activities or None,
        hard_constraints=intent.hard_constraints or None,
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
