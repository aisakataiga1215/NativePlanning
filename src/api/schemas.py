"""HTTP request/response Pydantic models for the FastAPI layer."""
from __future__ import annotations

from pydantic import BaseModel, Field

from src.schemas.order import ExecutionResult, ShareMessage
from src.schemas.plan import ItineraryPlan
from src.schemas.user_intent import UserIntent


class GenerateRequest(BaseModel):
    user_input: str


class GenerateResponse(BaseModel):
    plan: ItineraryPlan
    alternatives: list[ItineraryPlan] = Field(default_factory=list)
    intent: UserIntent
    traces: list[dict]
    warnings: list[str]


class ExecuteRequest(BaseModel):
    plan: ItineraryPlan
    intent: UserIntent


class ExecuteResponse(BaseModel):
    results: list[ExecutionResult]
    share_message: ShareMessage
    traces: list[dict]


class ReviseRequest(BaseModel):
    revision_text: str
    intent: UserIntent
    current_plan: ItineraryPlan | None = None
