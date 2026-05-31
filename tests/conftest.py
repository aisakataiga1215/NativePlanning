"""Pytest session configuration.

Two things this file ensures:

1. LangSmith tracing is OFF (belt+suspenders alongside the addopts entry in
   pyproject.toml).  The langsmith_plugin makes one HTTPS trace request per test
   when LANGCHAIN_API_KEY is set, adding ~10-15 s per test.

2. OPENAI_API_KEY is absent for every test.  src/api/app.py calls load_dotenv()
   at import time, which can restore the key from .env after a session-level
   pop.  The autouse fixture below removes the key before each test function,
   preventing accidental real API calls in _llm_message / _make_client.

Tests that exercise LLM code paths mock _make_client (intent_parser) directly
via @patch — they don't need a real key.
"""
from __future__ import annotations

import os

import pytest

os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"


@pytest.fixture(autouse=True)
def _no_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
