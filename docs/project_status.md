# Project Status

## 1. Current Phase

Current phase: **Production Deployed — TypeScript Frontend Live**

Live URLs:
- Next.js frontend (Vercel): https://native-planning.vercel.app
- FastAPI backend (HuggingFace Spaces, Docker): https://aisakamai-nativeplanning.hf.space
- Streamlit UI (Streamlit Community Cloud, `main` branch): https://nativeplanning.streamlit.app/
- GitHub: https://github.com/aisakataiga1215/NativePlanning

## 2. Milestones

### MVP-5: TypeScript Frontend + Production Deployment

Status: **Complete** (2026-06-08)

Delivered (branch `feat/ts-frontend`):
- `frontend/`: Next.js 14 App Router + TypeScript + Tailwind CSS SPA
- 8 components covering the full flow: `IntentPanel`, `PlanCard`, `PlanSelector`, `Timeline`, `ToolTrace`, `ExecutionResult`, `ShareMessage`, `RevisionInput`
- State machine: `idle → generating → plan_ready → revising → executing → done`
- `frontend/lib/types.ts`: TypeScript interfaces mirroring all Pydantic schemas
- `frontend/lib/api.ts`: typed `generate` / `revise` / `execute` client; `next.config.mjs` dev proxy to FastAPI:8000
- Brand color `#FF6900` (Meituan orange)
- `Dockerfile` for HuggingFace Spaces (port 7860)
- `render.yaml` alternative deployment recipe
- CORS middleware added to `src/api/app.py`
- E2E verified on production: generate, revise, execute flows all confirmed working
- Streamlit UI on `main` continues to be the in-repo demo path

See: [docs/architecture.md](architecture.md#7-frontend-topology) for the frontend + deployment topology.

### MVP-4.6: Bugfix & Data Consistency Pass

Status: **Complete** (2026-06-03)

Delivered (Bugs A, B, C, D, F, G, I):
- `ItineraryPlan.feasible` / `infeasible_reasons` fields
- Explicit activity guarantee: `generate_plans()` candidate pinning + `rank_plans(pinned_venue_ids)`
- Opening hours hard filter: truncation when `available >= min_duration`; `feasible=False` otherwise
- Destination-type activity: `build_destination_timeline()`, `is_destination` venue field, venue_013/014 updated
- Full-day meal timing: `needs_lunch = start < 11:00 AND end > 12:30`; 14:00-start no longer gets lunch
- `meal_policy` (required/optional/excluded): parser, planner, executor, message_agent, UI
- Tool duration: `perf_counter` + `_fmt_elapsed()` UI helper
- Regression test: `plan.reasons` never contains "多站点"
- 26 new tests; **242/243 total** (1 skipped)

### MVP-4.5: Time-Aware Planning + Opening Hours + Revision Scope + UI Completeness

Status: **Complete** (2026-06-02)

Delivered:
- `src/workflow/datetime_parser.py`: `parse_date_time(text, now=None)` resolves 今天/明天/周X/N号/早上/晚上/待会 to `DateTimeResult(date, weekday, time_period, start_time)`
- `UserIntent` new fields: `weekday`, `time_period`, `revision_scope` (all with defaults)
- `src/services/opening_hours.py`: `is_open_at`, `is_open_during` (midnight-crossing), `opening_hours_warning`
- Opening-hours warning in planner + −0.35 penalty in ranker when venue closed during activity
- `revision_scope` in `apply_revision()`: cleared each call; `restaurant_only` / `venue_only` scope dispatch in API + InProcessClient
- `revise_restaurant_only` / `revise_venue_only` in planner
- `TicketOption` schema + `Venue.ticket_options` field
- Activity-type boost in `generate_plans()` + `_ACTIVITY_TYPE_MAP` in ranker
- New intent_parser rules: 动物园/夜市/烛光晚餐 keywords
- Mock data: 5 new venues (venue_014–018), 4 new restaurants (rest_013–016)
- UI: compact intent panel + debug expander, timeline icons + 营业 status column, venue/restaurant hours + ticket cards, multi-stop display
- 72 new tests; **216/216 total** (1 skipped)

### MVP-4: Rich Data + Multi-stop + Location Anchor

Status: **Complete** (2026-06-02)

Delivered:
- `src/schemas/coupon_package.py`: Package, VenueCoupon, RestaurantCoupon Pydantic schemas
- All 12 venues + 12 restaurants enriched with area, review_count, tags, coupons, packages, duration ranges
- venue_013 (超级主题乐园, theme_park, min 240 min) added for large-venue constraint testing
- `build_dynamic_timeline()` in itinerary_builder: budget-residual driven, guarantees total <= duration_hours × 60
- `generate_plans()` as new main entry point (multi-stop capable); `generate_candidate_plans()` preserved
- `UserIntent.location_anchor` + `_extract_location_anchor()` in intent_parser
- `apply_revision()` updated with anchor update/clear rules (Rule 18)
- 4 new ranking dimensions in plan_ranker (anchor_bonus, promo_bonus, dishes_bonus, negative_review penalty)
- UI shows specialty_tags, coupons, packages, recommended_dishes, review_count, area column, location_anchor badge
- 23 new tests; **136/136 total**

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

### MVP-3.5: Plan Revision Loop + Mock Data Expansion

Status: **Complete** (2026-06-02)

Delivered:
- Plan revision loop: "太远了" / "换个餐厅" / "想吃日料" updates intent and re-runs pipeline before execution
- `src/workflow/revision_parser.py`: 17-rule keyword table; `apply_revision()` returns new UserIntent via `model_copy`
- `POST /api/plans/revise` endpoint; `revise()` on both InProcessClient and HttpClient
- Mock data: 6 → 12 venues (board_game, tea_house, citywalk, escape_room, movie, kids_lab); 6 → 12 restaurants
- New schema fields on Venue (`walk_intensity`, `noise_level`, `queue_minutes`) and Restaurant (`noise_level`)
- `UserIntent.avoid_venue_ids` / `.avoid_restaurant_ids`: planner filters these before candidate generation
- Field-aware ranking penalties (walk intensity, queue time, noise level, indoor constraint)
- Streamlit revision UI: `st.form` input; hidden after execution; radio pre-selection fixed; cost breakdown with item detail
- Bug fix: default plan start time 10:00 (was 00:00 from LLM omission)
- 22 new tests; **113/113 total passing**

See: `docs/handoff_mvp4.md` for design decisions, known limitations, and MVP-4 proposals.

### MVP-4: Rich Local-Life Data + Multi-stop Itinerary + Location Anchor

Status: **Planned**

Tasks:
- Rich local-life data: business hours, rating, `specialty_tags` (网红/情侣/亲子); time-of-day availability
- Multi-stop itinerary: 2–3 activity stops + 1–2 meal stops chained by time; `PlanStep.travel_minutes`; constraint solver validates full chain continuity
- Location anchor: `UserIntent.location_anchor`; mock venues with lat/lon; Haversine distance filter; distance-from-anchor in timeline

### v1: SQLite Persistence (Deferred)

Status: **Deferred**

Tasks:
- Add SQLite via SQLAlchemy (behind feature flag)
- Save plan sessions
- User preference memory

## 3. Current State

- **321 tests passing**, 0 failed (no external API calls required)
- Production deployed on three platforms:
  - Next.js frontend: https://native-planning.vercel.app (Vercel)
  - FastAPI backend: https://aisakamai-nativeplanning.hf.space (HuggingFace Spaces, Docker)
  - Streamlit UI: https://nativeplanning.streamlit.app/ (Streamlit Community Cloud, `main`)
- 8 demo acceptance cases verified end-to-end
- Both in-process and HTTP backend modes functional; Streamlit and Next.js share the same FastAPI endpoints
- Rule-based fallback confirmed working without `OPENAI_API_KEY`

## 4. Known Limitations

- Mock data only — not connected to real Meituan / Amap API
- Distance, queue time, and seat counts are simulated values
- No real payment; booking returns a mock booking ID
- Single session — no user login or persistent history
- CORS is permissive (`allow_origins=["*"]`) — acceptable for the competition demo, not production
- TypeScript schemas in `frontend/lib/types.ts` are hand-maintained against `src/schemas/*.py` (no codegen)

## 5. Next Steps (Post-Submission)

- Real API integration (Meituan / Amap / queue / coupon)
- Schema codegen from Pydantic to TypeScript to remove the manual mirror
- SQLite persistence + user history
- Multi-city expansion
- Tighten CORS to known frontend origins
