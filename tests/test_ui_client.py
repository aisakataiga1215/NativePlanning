"""Tests for src/ui/planning_client.py.

Covers:
* `make_client()` env switch
* `InProcessClient.generate()` / `.execute()` (real workflow, fixture key)
* Trace dict shape parity with the FastAPI serialiser
* `HttpClient.generate()` / `.execute()` (mocked httpx)
* `HttpClient` timeout configuration
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.api.schemas import ExecuteResponse, GenerateResponse
from src.ui.planning_client import (
    HttpClient,
    InProcessClient,
    make_client,
)


# ── make_client() env switch ────────────────────────────────────────────────


def test_make_client_returns_in_process_when_env_unset(monkeypatch):
    monkeypatch.delenv("NATIVE_PLANNING_API_URL", raising=False)
    client = make_client()
    assert isinstance(client, InProcessClient)


def test_make_client_returns_http_when_env_set(monkeypatch):
    monkeypatch.setenv("NATIVE_PLANNING_API_URL", "http://localhost:8000")
    client = make_client()
    assert isinstance(client, HttpClient)
    assert client.base_url == "http://localhost:8000"


def test_make_client_strips_trailing_slash(monkeypatch):
    monkeypatch.setenv("NATIVE_PLANNING_API_URL", "http://localhost:8000/")
    client = make_client()
    assert isinstance(client, HttpClient)
    assert client.base_url == "http://localhost:8000"


# ── InProcessClient (real workflow, fixture path, no LLM) ───────────────────


def test_in_process_generate_family_returns_plan():
    client = InProcessClient()
    response = client.generate("family")
    assert isinstance(response, GenerateResponse)
    assert response.intent.scenario_type == "family"
    assert len(response.plan.steps) >= 4
    assert isinstance(response.traces, list)
    assert isinstance(response.warnings, list)


def test_in_process_execute_returns_share_message():
    client = InProcessClient()
    gen = client.generate("family")
    result = client.execute(gen.plan, gen.intent)
    assert isinstance(result, ExecuteResponse)
    assert len(result.share_message.message) > 20
    assert len(result.results) >= 1


def test_in_process_traces_have_dict_shape():
    client = InProcessClient()
    response = client.generate("family")
    assert response.traces, "expected at least one trace"
    for trace in response.traces:
        assert isinstance(trace, dict)
        assert {"tool_name", "status", "elapsed_ms", "inputs", "output"} <= set(
            trace.keys()
        )


# ── HttpClient (mocked httpx) ───────────────────────────────────────────────


def _generate_response_payload() -> dict:
    """Build a minimal GenerateResponse payload using real fixture data."""
    real = InProcessClient().generate("family")
    return real.model_dump()


def _execute_response_payload() -> dict:
    real = InProcessClient()
    gen = real.generate("family")
    exe = real.execute(gen.plan, gen.intent)
    return exe.model_dump()


@patch("src.ui.planning_client.httpx.Client")
def test_http_client_generate_calls_correct_endpoint(mock_client_cls):
    payload = _generate_response_payload()
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_response = MagicMock()
    mock_response.json.return_value = payload
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response

    client = HttpClient("http://localhost:8000")
    result = client.generate("family")

    assert isinstance(result, GenerateResponse)
    mock_client.post.assert_called_once()
    args, kwargs = mock_client.post.call_args
    assert args[0] == "http://localhost:8000/api/plans/generate"
    assert kwargs["json"] == {"user_input": "family"}


@patch("src.ui.planning_client.httpx.Client")
def test_http_client_execute_calls_correct_endpoint(mock_client_cls):
    exec_payload = _execute_response_payload()
    real = InProcessClient().generate("family")

    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_response = MagicMock()
    mock_response.json.return_value = exec_payload
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response

    client = HttpClient("http://localhost:8000")
    result = client.execute(real.plan, real.intent)

    assert isinstance(result, ExecuteResponse)
    mock_client.post.assert_called_once()
    args, kwargs = mock_client.post.call_args
    assert args[0] == "http://localhost:8000/api/plans/execute"
    assert "plan" in kwargs["json"]
    assert "intent" in kwargs["json"]
    assert kwargs["json"]["intent"]["scenario_type"] == "family"


@patch("src.ui.planning_client.httpx.Client")
def test_http_client_uses_30s_timeout_by_default(mock_client_cls):
    payload = _generate_response_payload()
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_response = MagicMock()
    mock_response.json.return_value = payload
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response

    client = HttpClient("http://localhost:8000")
    client.generate("family")

    mock_client_cls.assert_called_once_with(timeout=30.0, trust_env=False)


@patch("src.ui.planning_client.httpx.Client")
def test_http_client_raises_on_http_error(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = Exception("boom")
    mock_client.post.return_value = mock_response

    client = HttpClient("http://localhost:8000")
    with pytest.raises(Exception, match="boom"):
        client.generate("family")
