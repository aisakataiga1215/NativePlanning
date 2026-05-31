# Project Status

## 1. Current Phase

Current phase: **MVP-2 Complete**

MVP-2 adds a Streamlit UI on top of MVP-1, supporting both in-process and HTTP backend modes via the `NATIVE_PLANNING_API_URL` env var.

Next milestone after MVP-2: **v1** — optional SQLite persistence.

## 2. Milestones

### MVP-0: Minimum Runnable Closed Loop

Status: **Complete** (2026-05-28)

Delivered:
- Project scaffold: `pyproject.toml`, `.env.example`, `.gitignore`, `README.md`
- Pydantic v2 schemas in `src/schemas/` (UserIntent, Venue, Restaurant, Plan, Order)
- In-memory mock API in `src/mock_api/` (6 venues, 6 restaurants, 4 coupons)
- Tool wrappers with `ToolTrace` / `TraceLog` in `src/tools/wrappers.py`
- Rule-based intent parser (`src/workflow/intent_parser.py`)
- Planning pipeline: planner → constraint_solver → executor → message_agent
- Services: `plan_ranker.py`, `itinerary_builder.py`
- CLI demo: `python -m src.cli.main <scenario>` (5 scenarios)
- 18 passing tests (8 happy path + 10 failure path)

### MVP-1: OpenAI API + FastAPI App

Status: **Complete** (2026-05-29)

Delivered:
- `parse_free_text()` in `src/workflow/intent_parser.py`: Structured Outputs → json_object → rule-based fallback
- DeepSeek-compatible via `OPENAI_BASE_URL` + `OPENAI_MODEL` env vars
- LLM message agent in `src/workflow/message_agent.py` (template fallback preserved)
- FastAPI app at `src/api/app.py`: `POST /api/plans/generate`, `POST /api/plans/execute`, `GET /api/health`
- CLI upgrades: free-form text with spaces, `[LLM]`/`[rule-based]` badge
- 15 new tests (7 intent-parser LLM + 7 API); 33/33 total passing

### MVP-2: Streamlit UI

Status: **Complete** (2026-05-29)

Delivered:
- `PlanningClient` Protocol + `InProcessClient` + `HttpClient` + `make_client()` in `src/ui/planning_client.py`
- Streamlit page at `src/ui/app.py`: text input, intent panel with `[LLM]`/`[rule-based]` badge, plan card with 6-dim score breakdown, timeline, trace expander, two-step confirm flow, execution panel, share message via `st.code`
- Dual backend mode via `NATIVE_PLANNING_API_URL`: unset → in-process (CLI code path), set → HTTP (FastAPI endpoints)
- Trace serialization parity: `InProcessClient` imports `_trace_to_dict` from `src/api/app.py` so both modes emit identical `list[dict]` shape
- `httpx>=0.27` promoted to core deps; `[ui]` optional dep group with `streamlit>=1.30`
- 10 new tests in `tests/test_ui_client.py`; 43/43 total passing
- All 5 CLI fixture scenarios remain bit-for-bit compatible

See: `docs/handoff_mvp2.md` for the original design decisions and verification commands.

### v1: Persistence (Optional)

Status: **Planned**

Tasks:
- Add SQLite via SQLAlchemy (behind feature flag)
- Save plan sessions
- User preference memory

## 3. Current Progress

MVP-0 complete. MVP-1 complete. MVP-2 complete. All 43 tests passing (33 existing + 10 new). All 5 CLI fixture scenarios still produce valid plans bit-for-bit.

## 4. Next Steps

1. Optional MVP-3 polish: real-time tool-trace streaming, `[LLM]` badge that reflects actual code path taken (not just env var), persistent share message clipboard feedback
2. v1 SQLite persistence (behind feature flag)
