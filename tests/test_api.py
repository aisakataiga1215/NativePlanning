"""FastAPI endpoint tests using TestClient (no LLM calls — fixture keys only)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.app import app

client = TestClient(app)


def test_health_endpoint():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_generate_family_scenario():
    r = client.post("/api/plans/generate", json={"user_input": "family"})
    assert r.status_code == 200
    data = r.json()
    assert data["intent"]["scenario_type"] == "family"
    assert data["plan"] is not None
    assert isinstance(data["traces"], list)
    assert isinstance(data["warnings"], list)


def test_generate_friends_scenario():
    r = client.post("/api/plans/generate", json={"user_input": "friends"})
    assert r.status_code == 200
    assert r.json()["intent"]["scenario_type"] == "friends"


def test_generate_response_has_plan_steps():
    r = client.post("/api/plans/generate", json={"user_input": "family"})
    assert r.status_code == 200
    plan = r.json()["plan"]
    assert len(plan["steps"]) >= 4


def test_execute_endpoint_returns_share_message():
    gen_r = client.post("/api/plans/generate", json={"user_input": "family"})
    assert gen_r.status_code == 200
    gen_data = gen_r.json()

    exec_r = client.post("/api/plans/execute", json={
        "plan": gen_data["plan"],
        "intent": gen_data["intent"],
    })
    assert exec_r.status_code == 200
    exec_data = exec_r.json()
    assert "share_message" in exec_data
    assert len(exec_data["share_message"]["message"]) > 20


def test_execute_endpoint_returns_results():
    gen_r = client.post("/api/plans/generate", json={"user_input": "family"})
    gen_data = gen_r.json()

    exec_r = client.post("/api/plans/execute", json={
        "plan": gen_data["plan"],
        "intent": gen_data["intent"],
    })
    assert exec_r.status_code == 200
    data = exec_r.json()
    assert isinstance(data["results"], list)
    assert len(data["results"]) >= 1


def test_generate_endpoint_has_traces():
    r = client.post("/api/plans/generate", json={"user_input": "family"})
    assert r.status_code == 200
    traces = r.json()["traces"]
    tool_names = [t["tool_name"] for t in traces]
    assert "search_venues" in tool_names
    assert "search_restaurants" in tool_names
