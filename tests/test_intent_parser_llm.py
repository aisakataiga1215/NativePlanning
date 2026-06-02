"""Tests for parse_free_text(): fixture lookup, LLM paths, and fallback."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from src.schemas.user_intent import UserIntent
from src.workflow.intent_parser import UserIntentLLM, parse_free_text


def test_fixture_key_bypasses_llm():
    result = parse_free_text("family")
    assert result.scenario_type == "family"
    assert result.group_size == 3


def test_fixture_key_with_leading_space():
    result = parse_free_text("  friends  ")
    assert result.scenario_type == "friends"


def test_fallback_when_no_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    result = parse_free_text("今天下午带孩子去公园")
    assert isinstance(result, UserIntent)
    assert result.scenario_type == "family"


def test_rule_fallback_friends_keyword(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = parse_free_text("今天和朋友一起出去玩")
    assert result.scenario_type == "friends"


def test_rule_fallback_morning_time(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = parse_free_text("上午想出去逛逛")
    assert result.time == "09:00"  # datetime_parser: 上午 → morning → 09:00


@patch("src.workflow.intent_parser._make_client")
def test_structured_outputs_path(mock_make_client):
    mock_client = MagicMock()
    mock_make_client.return_value = mock_client

    parsed_model = UserIntentLLM(scenario_type="family", group_size=3, time="14:00")
    mock_response = MagicMock()
    mock_response.choices[0].message.parsed = parsed_model
    mock_client.beta.chat.completions.parse.return_value = mock_response

    result = parse_free_text("今天下午带孩子出去玩几个小时")
    assert result.scenario_type == "family"
    assert result.group_size == 3
    mock_client.beta.chat.completions.parse.assert_called_once()


@patch("src.workflow.intent_parser._make_client")
def test_json_object_fallback_when_structured_outputs_fails(mock_make_client):
    mock_client = MagicMock()
    mock_make_client.return_value = mock_client

    mock_client.beta.chat.completions.parse.side_effect = Exception("not supported")

    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps({
        "scenario_type": "friends",
        "group_size": 4,
        "time": "15:00",
    })
    mock_client.chat.completions.create.return_value = mock_response

    result = parse_free_text("今天和四个朋友一起出去玩")
    assert result.scenario_type == "friends"
    assert result.group_size == 4


@patch("src.workflow.intent_parser._make_client")
def test_rule_fallback_when_both_llm_paths_fail(mock_make_client):
    mock_client = MagicMock()
    mock_make_client.return_value = mock_client

    mock_client.beta.chat.completions.parse.side_effect = Exception("error")
    mock_client.chat.completions.create.side_effect = Exception("error")

    result = parse_free_text("今天带孩子出去玩")
    assert isinstance(result, UserIntent)
    assert result.scenario_type == "family"
