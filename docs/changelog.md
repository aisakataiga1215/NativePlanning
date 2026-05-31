# Changelog

All meaningful project changes should be recorded in this file.

## [MVP-2 patch] - 2026-05-31

### Fixed

- `tests/conftest.py` (new): autouse fixture removes `OPENAI_API_KEY` / `OPENAI_BASE_URL` before every test.
  `src/api/app.py` calls `load_dotenv()` at module import time, which was restoring the key from `.env`
  and causing `message_agent._llm_message` to make real API calls in integration tests — adding 4-10 s per test.
- `pyproject.toml`: `addopts = "-p no:langsmith_plugin"` disables the LangSmith pytest plugin, which was
  making one HTTPS trace request per test when `LANGCHAIN_API_KEY` was set (≈15 s/test × 43 = 10 min total).
- `src/ui/app.py`: `sys.path.insert(0, project_root)` added so `streamlit run src/ui/app.py` works from any
  working directory, not only from the project root.

### Added

- `docs/demo_script.md`: step-by-step guide for CLI, Streamlit in-process, Streamlit HTTP, and manual LLM
  verification; includes judge focus points (tool traces, execution results, share message, failure repair).

### Result

`pytest tests/ -v` now passes 43/43 in ≈ 1 s with no `OPENAI_API_KEY` required.

## [MVP-2] - 2026-05-29

### Added

- `src/ui/planning_client.py`: `PlanningClient` Protocol + `InProcessClient` + `HttpClient` + `make_client()` factory
- `src/ui/app.py`: Streamlit single-page UI with two-step confirm flow (生成计划 → 确认并执行)
- Dual backend mode via `NATIVE_PLANNING_API_URL`: unset → in-process (CLI code path), set → HTTP (FastAPI endpoints)
- Trace serialization parity: `InProcessClient` imports `_trace_to_dict` from `src/api/app.py` so both modes emit identical `list[dict]` shape
- Intent panel with `[LLM]` / `[rule-based]` badge driven by `bool(os.getenv("OPENAI_API_KEY"))`
- Plan card with 6-dim score breakdown, reasons, risks, estimated cost
- Timeline as `st.dataframe` (时间 / 步骤 / 地点 / 时长)
- Collapsible tool trace expander with 工具 / 状态 / 摘要 / 耗时(ms) columns; long inputs truncated to 60 chars
- Execution result table + share message via `st.code(..., language=None)` (Streamlit built-in copy icon)
- `[ui]` optional dependency group: `streamlit>=1.30`
- `httpx>=0.27` promoted from `dev` to core `dependencies` (required by `HttpClient`)
- 10 new tests in `tests/test_ui_client.py`: env switch (3), `InProcessClient` happy path + trace shape (3), `HttpClient` endpoint / timeout / error (4)
- `docs/handoff_mvp2.md`: design decisions and verification commands that seeded this milestone

### Architecture

- UI is mode-agnostic: both clients return `GenerateResponse` / `ExecuteResponse` from `src/api/schemas.py`
- Streamlit state lives in `st.session_state["last_generate"]` / `st.session_state["last_execute"]`; page refresh clears the plan
- `try / except` around every client call → `st.error(...)`; missing `OPENAI_API_KEY` never crashes the UI
- No edits to `src/workflow/`, `src/services/`, `src/mock_api/`, `src/tools/`, `src/schemas/`, `src/api/`, `src/cli/`, or existing tests

## [MVP-1] - 2026-05-29

### Added

- `parse_free_text()` in `intent_parser.py`: Structured Outputs → json_object → rule-based chain
- `UserIntentLLM` lightweight schema for LLM output validation
- `_make_client()` helper: reads `OPENAI_API_KEY` + optional `OPENAI_BASE_URL` / `OPENAI_MODEL`
- LLM message agent path in `message_agent.py` (template fallback preserved)
- FastAPI app at `src/api/app.py`: `/api/plans/generate`, `/api/plans/execute`, `/api/health`
- HTTP schemas in `src/api/schemas.py`
- CLI free-form text support (`" ".join(sys.argv[1:])`) with source badge
- `.env.example` extended with `OPENAI_BASE_URL` and `OPENAI_MODEL`
- 15 new tests: `test_intent_parser_llm.py` (8), `test_api.py` (7)

### Architecture

- DeepSeek-compatible: any OpenAI-compatible provider works via env vars
- FastAPI is stateless: client passes plan back in `/execute` request



### Added

- Project scaffold: `pyproject.toml`, `.env.example`, `.gitignore`, `README.md`
- Pydantic v2 schemas: `UserIntent`, `Venue`, `Restaurant`, `Coupon`, `PlanStep`, `ItineraryPlan`, `ExecutionAction`, `ExecutionResult`, `ShareMessage`
- In-memory mock API: 6 venues, 6 restaurants, 4 coupons, booking/order functions
- Tool wrappers with `ToolTrace` / `TraceLog` for observability
- Rule-based intent parser with 5 fixture scenarios
- Planning pipeline: planner, constraint solver (3 failure cases), executor, message agent (template-based)
- Plan ranker with 5-dimension scoring
- CLI demo: `python -m src.cli.main <scenario>` (5 scenarios)
- 18 tests covering happy path + 3 failure paths

### Architecture

- Runtime workflow lives in `src/workflow/` (not `src/agents/`)
- Mock data is in-memory Python objects in `src/mock_api/`
- Uses OpenAI API key for MVP-1+ LLM features (not Anthropic)

## [Unreleased]

### Added

- Initial project planning.
- Added product specification.
- Added engineering specification.
- Added architecture documentation.
- Added project status tracking.

### Changed

- N/A

### Fixed

- N/A
