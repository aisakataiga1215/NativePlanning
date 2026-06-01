# Project Status

## 1. Current Phase

Current phase: **MVP-3 Complete**

MVP-3 adds alternative plan selection, runtime source tracking (`[LLM]`/`[rule-based]` from actual execution path), LLM error surfacing, UI polish (reset button, env diagnostics), and load-dotenv robustness across all entry points.

Next milestone after MVP-3: **v1** — optional SQLite persistence.

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

### MVP-3: Alternative Plans + Source Tracking + UI Polish

Status: **Complete** (2026-06-01)

Delivered:
- `UserIntent.source` field (`"llm"` / `"rule_based"` / `"unknown"`): set by `_rule_fallback()` and `_llm_to_intent()`; intent panel badge now reflects actual execution path
- `GenerateResponse.alternatives`: up to 2 runner-up plans returned by API and in-process client
- Streamlit plan selector: `st.radio` shown when 2+ candidates; `_run_execute` uses the selected plan
- `_llm_parse` error surfacing: captures last exception into `UserIntent.warnings` on fallback so UI shows why LLM failed
- `load_dotenv(_PROJECT_ROOT / ".env")` in all entry points (ui/app.py, api/app.py, cli/main.py) — key loads regardless of launch directory
- Header env diagnostics: always shows `openai=✓/✗`, `key=✓/✗`, Python name; `st.warning` with launch command when LLM unavailable
- 🔄 reset button (`st.columns([20, 1])`, `use_container_width=True`) at true right edge; clears all session state
- `httpx.Client(trust_env=False)` in `HttpClient` — bypasses system proxy
- 48 new tests; **91/91 total passing** (no external API calls required)

### v1: Persistence (Optional)

Status: **Planned**

Tasks:
- Add SQLite via SQLAlchemy (behind feature flag)
- Save plan sessions
- User preference memory

## 3. Current Progress

MVP-0 complete. MVP-1 complete. MVP-2 complete. MVP-3 complete. All 91 tests passing. All 5 CLI fixture scenarios still produce valid plans. Both in-process and HTTP backend modes verified.

## 4. Next Steps

1. v1 SQLite persistence (behind feature flag)
