# Changelog

All meaningful project changes should be recorded in this file.

## [TypeScript Frontend + Production Deployment] — 2026-06-08

### Added

- **`frontend/` (branch `feat/ts-frontend`)**: Next.js 14 App Router + TypeScript + Tailwind CSS single-page client
  - 8 components: `IntentPanel`, `PlanCard`, `PlanSelector`, `Timeline`, `ToolTrace`, `ExecutionResult`, `ShareMessage`, `RevisionInput`
  - State machine in `frontend/app/page.tsx`: `idle → generating → plan_ready → revising → executing → done`
  - `frontend/lib/types.ts`: TypeScript interfaces mirroring all Pydantic schemas (`UserIntent`, `ItineraryPlan`, `PlanStep`, `ScoreBreakdown`, `ExecutionResult`, `ShareMessage`, `TraceEntry`, `GenerateResponse`, `ExecuteResponse`)
  - `frontend/lib/api.ts`: thin `generate` / `revise` / `execute` HTTP client with typed responses
  - `frontend/next.config.mjs`: dev proxy `/api/:path*` → `http://localhost:8000` (or `NEXT_PUBLIC_API_URL` in production)
  - Brand color `#FF6900` (Meituan orange) via Tailwind theme extension
  - Sample inputs (4 Chinese prompts) surfaced in the idle state
- **Deployment artifacts**
  - `Dockerfile` (Python 3.11-slim, exposes 7860, `uvicorn src.api.app:app`) for HuggingFace Spaces
  - `render.yaml`: alternative Render web service config with `OPENAI_API_KEY` / `OPENAI_BASE_URL` env vars
  - HuggingFace Spaces README config commit (`b8db6f1`, `2def55e`) and CORS middleware (`0d8de5d`)
- **CORS middleware in `src/api/app.py`**: `allow_origins=["*"]`, `allow_methods=["*"]` so the Vercel-hosted frontend can call the HF Spaces backend
- **Live URLs**
  - Backend: https://aisakamai-nativeplanning.hf.space (HuggingFace Spaces, Docker)
  - Frontend: https://native-planning.vercel.app (Vercel)

### Verified

- End-to-end generate / revise / execute flows confirmed working on the live URLs (production)
- Streamlit UI remains deployed at https://nativeplanning.streamlit.app/ from `main`

### Architecture

- Both Streamlit and Next.js UIs share the same FastAPI backend and the same three endpoints. See [docs/architecture.md](architecture.md#7-frontend-topology) for the topology diagram.
- TypeScript schemas are hand-maintained against `src/schemas/*.py` — no codegen yet.

---

## [Final Submission] — 2026-06-07

### Added

- `requirements.txt`: flat dependency file for Streamlit Cloud deployment
- `.streamlit/config.toml`: Meituan orange theme + headless server config
- `docs/deployment.md`: Streamlit Community Cloud + HF Spaces deployment guide
- `docs/judge_guide.md`: judge walkthrough with 8 acceptance cases, recommended inputs, revision guide
- `docs/design_proposal.md`: 12-section formal design proposal (intent parsing table, plan generation table, tool call chain, exception handling table, feature modules, Meituan alignment, evaluation metrics)
- `docs/final_submission_checklist.md`: pre-submission verification checklist
- Public deployment: https://nativeplanning.streamlit.app/

### Changed

- `README.md`: added recommended inputs, known limitations, design doc links; test count updated to 321
- `docs/demo_script.md`: removed all local absolute paths (`E:\`)
- `.gitignore`: added `.env.*` and `.streamlit/secrets.toml`
- `.streamlit/config.toml`: added `enableXsrfProtection=false`, `gatherUsageStats=false`

---

## [MVP-4.6] - 2026-06-03 (Bugfix & Data Consistency Pass)

### Fixed

- **Bug A — Explicit activity guarantee** (`src/workflow/planner.py`, `src/services/plan_ranker.py`): `generate_plans()` now separates explicit candidates from others; feasible explicit plans are returned at index 0. `rank_plans()` gains `pinned_venue_ids` to prevent scoring from undoing the placement. `explicit_bonus` raised to 0.30 with 0.50 distance floor.
- **Bug B — Opening hours hard filter** (`src/workflow/planner.py`): When activity step overruns `close_time`: if `available_min >= suggested_duration_min`, timeline is truncated via `_recalculate_steps_after_truncation()` (shifts all subsequent steps by delta); otherwise `plan.feasible=False`. `generate_plans()` non-explicit path returns only feasible plans when available.
- **Bug C — Destination activity** (`src/services/itinerary_builder.py`, `src/workflow/planner.py`, `src/schemas/venue.py`, `src/mock_api/venues.py`): `is_destination` venues (zoo/theme_park) use `build_destination_timeline()` — single venue multi-segment (morning activity → optional lunch → afternoon activity) — instead of inserting secondary activity stops. venue_013 and venue_014 updated with `is_destination=True`.
- **Bug D — Full-day meal timing** (`src/workflow/planner.py`): Lunch slot inserted only when `start_min < 11*60 AND end_min > 12*60+30` (`needs_lunch`). 14:00-start plans no longer incorrectly receive a lunch restaurant slot.
- **Bug F — Regression test** (`tests/test_bugfix_mvp46.py`): `test_plan_reasons_no_multistop_label` verifies `plan.reasons` never contains "多站点".
- **Bug G — Tool duration format** (`src/tools/wrappers.py`, `src/ui/app.py`): `traced_call` now uses `time.perf_counter()` instead of `time.monotonic()`. `_fmt_elapsed(ms)` helper added to UI; trace table column shows "<1ms" for sub-millisecond calls.
- **Bug I — meal_policy** (`src/schemas/user_intent.py`, `src/workflow/intent_parser.py`, `src/workflow/planner.py`, `src/workflow/executor.py`, `src/workflow/message_agent.py`, `src/ui/app.py`): New `meal_policy: Literal["required","optional","excluded"] = "required"` field. Parser extracts keywords ("不吃饭"→excluded, "随便吃点"→optional). Excluded policy skips restaurant search, removes meal steps, skips `reserve_restaurant` action, suppresses restaurant info in share message and UI.

### Added

- `ItineraryPlan.feasible: bool = True` and `infeasible_reasons: list[str]` fields (`src/schemas/plan.py`)
- `Venue.is_destination`, `onsite_meal_available`, `nearby_meal_area` fields (`src/schemas/venue.py`)
- `build_destination_timeline()` in `src/services/itinerary_builder.py`
- `_recalculate_steps_after_truncation()` in `src/workflow/planner.py`
- `get_explicit_venue_ids()` in `src/services/plan_ranker.py`
- `_fmt_elapsed()` in `src/ui/app.py`
- 26 new tests across `tests/test_bugfix_mvp46.py` and `tests/test_meal_policy.py`; **242/243 total** (1 skipped)

---

## [MVP-4.5] - 2026-06-02

### Added

- **Date/Time Parsing** (`src/workflow/datetime_parser.py`, new): `parse_date_time(text, now=None) → DateTimeResult` resolves natural-language date/time expressions — 今天/明天/后天/大后天, 周X/周末, N号, 早上/中午/下午/傍晚/晚上/待会 — to a concrete `date` (YYYY-MM-DD), `weekday` (周一…周日), `time_period`, and `start_time` (HH:MM). Injectable `now` for test determinism. 26 unit tests.
- **UserIntent new fields** (all with defaults, `extra="forbid"` preserved): `weekday: str = ""`, `time_period: str = ""`, `revision_scope: str = ""`. `parse_free_text()` gains `_now` injection; all paths end with a `parse_date_time` post-processing step that overwrites `date`/`weekday`/`time_period`/`time`.
- **Opening Hours Service** (`src/services/opening_hours.py`, new): `is_open_at`, `is_open_during` (full step containment, midnight-crossing via ±1440 offset), `opening_hours_warning`. 25 unit + integration tests.
- **Opening Hours in Planner**: `_build_one_plan` checks primary-venue activity step against `venue.open_time/close_time`; out-of-hours venues get a `plan.warnings` entry (plan still generated so ranker can deprioritize).
- **Opening Hours Penalty in Ranker**: `score_plan` / `rank_plans` gain optional `activity_start_time` / `activity_end_time` params; −0.35 `constraint_penalty` when venue is closed during the activity.
- **Revision Scope** (`revision_scope` in `UserIntent`): `apply_revision()` clears scope at the start of every call (prevents cross-revision pollution), then sets `"restaurant_only"` for meal-related rules and `"venue_only"` for activity-related rules. Global constraint rules (距离/预算/排队/天气) leave scope empty.
- **Partial Re-plan functions**: `revise_restaurant_only(intent, current_plan, log)` preserves `venue_ids`, re-searches only restaurant; `revise_venue_only(intent, current_plan, log)` preserves `restaurant_id`, re-searches only venues. Both fall back to `generate_plans` when mock data yields no results.
- **Scope Dispatch** in `POST /api/plans/revise` and `InProcessClient.revise()`: `restaurant_only` → `revise_restaurant_only`; `venue_only` → `revise_venue_only`; else → `generate_plans`.
- **TicketOption schema** (`src/schemas/coupon_package.py`): `type: Literal["adult","student","senior","child","family"]`, `price`, `note`, `available`.
- **Venue ticket_options field**: `Venue.ticket_options: list[TicketOption] = []`.
- **Activity-type boost in Planner**: `generate_plans()` reorders venues so those whose `type` matches `intent.requested_activities` (via `_ACTIVITY_TYPE_MAP`) move to the front — ensuring e.g. "动物园" request surfaces a zoo-type venue even if its raw rating ranks it lower.
- **Activity-type map in Ranker** (`_ACTIVITY_TYPE_MAP`): maps requested activity keywords (zoo, theme_park, mall, exhibition, movie, board_game, …) to venue `type` values for `explicit_bonus`.
- **New keyword rules in `intent_parser.py`**: "动物园"→zoo, "主题乐园"→theme_park, "夜市"→night_market, "商场"→mall in `requested_activities`; "烛光晚餐"/"浪漫晚餐"→western in `requested_meals` + romantic/candlelight in `soft_preferences`.
- **Mock data expansion** (Phase 6): 5 new venues (venue_014 城郊动物园 zoo 09:00–17:30, venue_015 夜市美食集市, venue_016 星河购物中心, venue_017 城市音乐现场, venue_018 商场亲子乐园 10:00–22:00); 4 new restaurants (rest_013 烛光西餐厅, rest_014 清晨面包坊, rest_015 深夜拉面馆 18:00–02:00 midnight-crossing, rest_016 动物园亲子餐厅).
- **UI improvements** (`src/ui/app.py`):
  - Intent panel: compact 4-metric layout + `📅 date weekday · time_period` + `💰 budget label`; `st.expander("🔍 调试信息")` shows full `intent.model_dump()`.
  - Timeline: step-type icons (🚗/🎯/🍽/🏠), `营业` column (🟢/🔴 via `is_open_during`), `step.notes` displayed inline.
  - Venue card: `🕐 open_time – close_time`, `⏱ min–max 分钟`, ticket_options list with notes.
  - Restaurant card: `🕐 open_time – close_time`, `⏳ 排队约 N 分钟`.
  - Multi-stop: extra venues in `plan.venue_ids` shown with name + rating + hours + specialty_tags.
- **Test expansion**: 18 `test_revision_scope.py`, 25 `test_opening_hours.py`, 26 `test_datetime_parser.py`, 4 new tests in `test_intent_parser_rules.py`; **216/216 total** (1 skipped).

### Changed

- `parse_free_text()` signature: optional `_now: datetime | None = None` (production path uses `datetime.now()`; only tests inject a fixed value).
- `score_plan()` / `rank_plans()` signature: new optional `activity_start_time: str = ""`, `activity_end_time: str = ""`.
- `generate_plans()` now reorders venue candidates to prioritize `requested_activities` type matches before taking top 3.



### Added

- **Dynamic Multi-stop Itinerary**: `generate_plans()` replaces `generate_candidate_plans()` as the main API/UI entry point. Plans are driven by a time-budget residual (`remaining_minutes`), not a hard half-day/full-day template. Light stops (tea/citywalk) are inserted when remaining >= 40 min; secondary activities when remaining >= 90 min and `duration_type == "full_day"` (>= 7 h).
- `build_dynamic_timeline()` in `src/services/itinerary_builder.py`: dynamic timeline builder that guarantees `total_duration_minutes <= intent.duration_hours × 60` via budget-priority duration clamping (activity durations and meal duration are compressed below their suggested minimums when the budget requires it).
- `get_duration_type(duration_hours) -> Literal["half_day", "full_day"]` pure helper in `src/workflow/planner.py`.
- **Location Anchor**: `UserIntent.location_anchor` and `anchor_place` fields; `_extract_location_anchor()` in `src/workflow/intent_parser.py` detects patterns like "先去芳华街", "云景附近", "离公司近"; `UserIntentLLM.location_anchor` field + system prompt rule; `apply_revision()` updated with anchor update/clear rules.
- **Rich Mock Data**: all 12 venues and 12 restaurants enriched with `area`, `nearby_areas`, `review_count`, `positive_review_tags`, `negative_review_tags`, `specialty_tags`, `packages`, `venue_coupons`/`restaurant_coupons`, `suggested_duration_min/max`, `duration_flexibility`, `suggested_meal_duration_min/max`, `recommended_dishes`. New venue_013 (超级主题乐园, theme_park, min 240 min, flexibility="low") for testing large-venue scenarios.
- `src/schemas/coupon_package.py` (new): `Package`, `VenueCoupon`, `RestaurantCoupon` Pydantic models with `extra="forbid"`.
- **New Ranking Dimensions** in `src/services/plan_ranker.py` (all with default args for backward compatibility):
  - `anchor_bonus`: +0.15 (venue in anchor area), +0.10 (restaurant in anchor area)
  - `promo_bonus`: +0.05 per entity with coupons or packages
  - `dishes_bonus`: +0.10 via `MEAL_TAG_TO_DISH_KEYWORDS` (English tag → Chinese dish keyword mapping)
  - `negative_review_tags × hard_constraints` penalty: −0.05 when "avoid_long_queue" and restaurant negative tags contain "排队"
  - Score clamped to [0.0, 1.0] to prevent bonus stacking from exceeding 1.
- **UI Enhancements** in `src/ui/app.py`: venue specialty_tags + venue_coupons, restaurant rating with review_count, recommended_dishes, positive/negative_review_tags, restaurant_coupons, packages; intent panel shows `location_anchor` badge; timeline table adds "区域" column from `step.area`.
- 23 new tests (`test_multistop_planner.py` × 12, `test_location_anchor.py` × 11); **136/136 total**.

### Changed

- `src/api/app.py` and `src/ui/planning_client.py`: both `generate` and `revise` endpoints now call `generate_plans()` (multi-stop capable) and forward `location_anchor` + `requested_meals` to `rank_plans()`.
- `estimate_travel_minutes()`: minimum raised from 10 min to 15 min (fixes unrealistic 1–2 min travel estimates); cross-area trips use ×1.3 congestion factor.
- `build_family_timeline()` and `generate_candidate_plans()` preserved unchanged for backward compatibility with existing tests.



### Added

- **Plan Revision Loop**: user types "太远了" / "换个餐厅" / "想吃日料" (etc.) after seeing a plan and clicks "调整方案" — `apply_revision()` updates the intent and re-runs the full pipeline before execution
- `src/workflow/revision_parser.py` (new): 17-rule keyword table covering distance, budget, queue, fatigue, indoor/outdoor, 6 activity types, 6 meal types, "换个场地/餐厅" with avoid-ID tracking
- `POST /api/plans/revise` FastAPI endpoint + `ReviseRequest` schema; wired into both `InProcessClient.revise()` and `HttpClient.revise()`
- Streamlit revision UI: `st.form` input + "调整方案" button shown between trace expander and execute button; hidden once execution is confirmed
- Mock data expanded 6 → 12 venues (board_game, tea_house, citywalk, escape_room, movie, kids_lab) and 6 → 12 restaurants; all entries now include `walk_intensity`, `noise_level`, `queue_minutes`
- New schema fields: `Venue.walk_intensity`, `Venue.noise_level`, `Venue.queue_minutes`; `Restaurant.noise_level`; `UserIntent.avoid_venue_ids`, `UserIntent.avoid_restaurant_ids`
- Field-aware ranking penalties: `walk_intensity=="high"` → −0.20; `restaurant.queue_minutes>20` → −0.15; senior+loud → −0.15/−0.10; `"indoor"` constraint+outdoor venue → −0.30; colleagues+loud → −0.10
- Planner filters `avoid_venue_ids` / `avoid_restaurant_ids` from search results before candidate generation
- 22 new tests (`test_revision_parser.py` × 19 unit, `test_revision_integration.py` × 3 integration); **113/113 total**

### Fixed

- Default plan start time was `00:00` when LLM did not mention time — added "未提及时间 → time='10:00'" to system prompt; changed `UserIntentLLM.time` default to `"10:00"`; rule-based fallback also defaults to `"10:00"` instead of `"14:00"`
- Streamlit revision form: `clear_on_submit=True` caused `text_input` to return `""` in the same rerun as `form_submit_button` returned `True`, silently skipping the revision call — removed `clear_on_submit`
- Radio plan selector not pre-selected after revision: changed `st.session_state.pop("selected_plan_idx")` to explicit `st.session_state["selected_plan_idx"] = 0`
- Plan card cost section now shows itemized breakdown (🎟 门票, 🍽 餐饮, 💰 合计) with hover tooltips; distance metric shows actual km instead of distance score

## [MVP-3] - 2026-06-01

### Added

- `docs/data_simulation.md`: judge-facing Chinese document explaining the mock data strategy — why MockAPI is used (no real APIs from the competition), data coverage (12 venues / 12 restaurants / 4 coupons), scenario matrix (family / couple / friends / colleagues / elderly), exception fixtures (no-seats / no-tickets / time-conflict), and the value MockAPI brings to demo stability, reproducibility, tool trace, and fallback演示. Cross-links to `mock_api_design.md`, `architecture.md`, and `planning_strategy.md` to avoid duplication
- `UserIntent.source` field (`Literal["llm", "rule_based", "unknown"]`): `_rule_fallback()` sets `"rule_based"`, `_llm_to_intent()` sets `"llm"`; intent panel badge in `_render_intent_panel` now reflects actual runtime path, not just env-var presence
- `GenerateResponse.alternatives: list[ItineraryPlan]`: up to 2 runner-up plans returned by both `InProcessClient` and `HttpClient`; `src/api/app.py` also returns `alternatives=ranked[1:3]`
- Plan selector `st.radio` in `src/ui/app.py`: shown when 2+ candidates; `_run_execute` receives the selected plan, not always the best plan
- Header env diagnostics: `openai=✓/✗`, `key=✓/✗`, Python name always visible in caption; `st.warning` with exact launch command shown when LLM unavailable
- 🔄 reset button at true page right edge via `st.columns([20, 1])` + `use_container_width=True`; clears `last_generate`, `last_execute`, `selected_plan_idx`
- 48 new tests (intent parser source field, UI client alternatives, API alternatives shape, trust_env flag); **91/91 total**

### Fixed

- `_llm_parse` now captures the last exception into `UserIntent.warnings` on fallback, so `_render_warnings` surfaces the actual API error in the UI instead of silently showing `[rule-based]`
- `load_dotenv(_PROJECT_ROOT / ".env")` in all three entry points (`src/ui/app.py`, `src/api/app.py`, `src/cli/main.py`) — `.env` is found regardless of working directory; fixes HTTP mode where uvicorn launched from a different directory failed to pick up `OPENAI_API_KEY`
- `httpx.Client(trust_env=False)` in `HttpClient.generate()` and `.execute()` — bypasses system HTTP proxy (was causing 502 errors)
- `ShareMessage.receiver_type` Literal extended with `"partner"` and `"colleague_group"` — was causing 500 errors for couple / colleague scenarios
- `build_family_timeline` accepts `target_total_minutes` — inflates venue duration to match requested `duration_hours`; fixes 8h request producing 3.5h timeline

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
