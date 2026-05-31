# MVP-2 Handoff Document

> Read this file first when starting a new Claude Code session for MVP-2 work.
> It captures every design decision and constraint already approved by the user.

---

## 1. Current Project State

- **MVP-0 complete** (2026-05-28): deterministic CLI demo, 5 fixture scenarios, in-memory mock API. 18 tests.
- **MVP-1 complete** (2026-05-29): OpenAI/DeepSeek intent parsing, LLM message agent, FastAPI app. +15 tests.
- **Tests: 33/33 passing** — `pytest tests/ -v`.

### Runnable Commands

```bash
# Activate env first
mamba activate E:\miniforge\envs\agent

# CLI fixture path (no LLM)
python -m src.cli.main family
python -m src.cli.main friends
python -m src.cli.main failure-no-seats
python -m src.cli.main failure-no-tickets
python -m src.cli.main failure-time-conflict

# CLI free-text path (needs .env with OPENAI_API_KEY)
python -m src.cli.main "今天下午带孩子去公园"

# FastAPI server
uvicorn src.api.app:app --reload --port 8000
# Endpoints: POST /api/plans/generate, POST /api/plans/execute, GET /api/health
```

### `.env` Keys

| Key | Required | Notes |
|-----|----------|-------|
| `OPENAI_API_KEY` | for LLM path | Without it, both CLI and API fall back to rule-based / template. |
| `OPENAI_BASE_URL` | optional | DeepSeek: `https://api.deepseek.com/v1`. Omit for OpenAI. |
| `OPENAI_MODEL` | optional | Default lives in `src/workflow/intent_parser.py`. Override for DeepSeek (e.g. `deepseek-chat`). |

---

## 2. Architecture Conventions (DO NOT VIOLATE)

- Runtime workflow lives in **`src/workflow/`** — never `src/agents/`.
- Claude Code subagents in `.claude/agents/` are **dev assistants only**, not runtime components.
- Schemas centralized in **`src/schemas/`**. HTTP-only request/response models in `src/api/schemas.py`.
- Mock data stays **in-memory** in `src/mock_api/` — no JSON files, no network calls.
- Tools always invoked through `traced_call()` in `src/tools/wrappers.py` so traces are captured.
- **MVP-0 commands (5 fixture scenarios) must keep working unchanged.** Backwards compatibility is non-negotiable.
- LLM is **optional everywhere**. Intent parser and message agent must fall back to deterministic paths when `OPENAI_API_KEY` is missing or any LLM call fails. The chain is:
  1. OpenAI Structured Outputs (`client.beta.chat.completions.parse`)
  2. json_object mode + Pydantic validation
  3. Rule-based (intent parser) / template (message agent)
- Field naming is unified: `scenario_type`, `group_size`, `max_distance_km`, `near_location`, `date`, `time`. Do not reintroduce old names (`group_type`, `people_count`, `radius_km`, `near_poi_id`, `start_time`).
- **Always call `load_dotenv()` at every entry point** (CLI, FastAPI app, Streamlit app). The `[LLM]` badge broke previously because of a missing `load_dotenv()` call.
- **Pydantic v2 only.** Use `model_dump()` not `.dict()`. Use `ConfigDict` not class-based `Config`.

---

## 3. MVP-2 Goals (Approved Design Decisions)

Streamlit UI at `src/ui/app.py` with four locked design decisions:

### 3.1 Dual Backend Mode

A single env var switches mode:

| `NATIVE_PLANNING_API_URL` | Mode | Behavior |
|---------------------------|------|----------|
| unset | **In-process** | UI imports workflow modules directly, same as CLI. |
| e.g. `http://localhost:8000` | **HTTP** | UI calls FastAPI endpoints via httpx. |

Both modes hide behind a `PlanningClient` abstraction so UI code is mode-agnostic.

### 3.2 Two-Step Confirm Flow

1. User enters Chinese text → clicks **生成计划** → backend returns a plan.
2. UI shows plan card + timeline + trace expander + warnings.
3. User clicks **确认并执行** → backend executes (stateless: UI sends the plan back).
4. UI shows execution results + share message.

The plan is held in `st.session_state["plan"]` between steps.

### 3.3 Tool Trace Display

- `st.expander("工具调用追踪 (N 步)", expanded=False)` containing
- `st.dataframe` (or `st.table`) with columns: **工具 / 状态 / 摘要 / 耗时(ms)**.
- Status uses ✓ / ✗ glyphs (same as CLI).
- Default collapsed — keep the plan card the visual focus.

### 3.4 Share Message Copy

- Render with `st.code(msg.message, language=None)`.
- Streamlit's built-in copy icon handles clipboard. **No custom JS, no `streamlit_clipboard` package.**

### 3.5 Intent Source Badge

- `[LLM]` if `OPENAI_API_KEY` is set in the environment, otherwise `[rule-based]`.
- Same heuristic as the CLI — do not over-engineer (see known risk in Section 8).

---

## 4. NOT in Scope for MVP-2

- ❌ No SQLite / SQLAlchemy / any database (defer to v1).
- ❌ No user login / accounts / cross-refresh sessions.
- ❌ No user preference memory beyond a single page load.
- ❌ No real payment integration (mock execution results stay mock).
- ❌ No multi-turn conversation or chat history.
- ❌ No breaking changes to existing CLI commands or FastAPI endpoints.
- ❌ No changes to `src/workflow/`, `src/services/`, `src/mock_api/`, `src/tools/`, `src/schemas/` unless a bug is discovered while building the UI.
- ❌ No new LLM features. Intent parser and message agent are done.

---

## 5. Recommended File Structure

```
src/ui/
├── __init__.py
├── app.py                  # Streamlit entry: streamlit run src/ui/app.py
└── planning_client.py      # PlanningClient: in-process vs HTTP behind one interface

tests/
└── test_ui_client.py       # Unit tests for PlanningClient (mock httpx + in-process)
```

If `app.py` grows past ~400 lines, extract render helpers into:
```
src/ui/components.py        # render_intent_panel, render_plan_card,
                            # render_trace_expander, render_execution_panel
```

### `PlanningClient` Interface Sketch

```python
from typing import Protocol
from src.schemas.user_intent import UserIntent
from src.schemas.plan import ItineraryPlan
from src.api.schemas import GenerateResponse, ExecuteResponse

class PlanningClient(Protocol):
    def generate(self, user_input: str) -> GenerateResponse: ...
    def execute(self, plan: ItineraryPlan, intent: UserIntent) -> ExecuteResponse: ...

class InProcessClient:
    """Imports workflow modules directly; same code path as CLI."""

class HttpClient:
    """Uses httpx with a 30s timeout; hits /api/plans/generate and /execute."""

def make_client() -> PlanningClient:
    url = os.getenv("NATIVE_PLANNING_API_URL")
    return HttpClient(url) if url else InProcessClient()
```

### `pyproject.toml`

Add Streamlit to optional deps:

```toml
[project.optional-dependencies]
ui = ["streamlit>=1.30"]
```

Install: `pip install -e ".[ui]"` (or `pip install -e ".[api,ui,dev]"` for full dev setup).

---

## 6. MVP-2 Feature Checklist

- [ ] `PlanningClient` abstraction with in-process + HTTP implementations
- [ ] Streamlit page: text input + 生成计划 button
- [ ] Intent panel with `[LLM]` / `[rule-based]` badge
- [ ] Plan card: title, summary, score breakdown, reasons, risks, warnings, estimated cost
- [ ] Timeline: ordered steps with 时间 / 步骤 / 地点 / 时长
- [ ] Tool trace expander (collapsed by default) with status icons and elapsed ms
- [ ] 确认并执行 button (disabled until a plan exists in `st.session_state`)
- [ ] Execution result panel: per-action status + booking/order IDs
- [ ] Share message via `st.code` (built-in copy icon)
- [ ] Warnings rendered with `st.warning` above the plan card
- [ ] Graceful empty / error states (no plans found, LLM unavailable, etc.)
- [ ] Tests for `PlanningClient` (both modes mocked); existing 33 tests still pass

---

## 7. Verification

### Tests

```bash
pytest tests/ -v   # expect 33 existing + new test_ui_client.py all passing
```

### Manual E2E — In-process Mode

```bash
mamba activate E:\miniforge\envs\agent
streamlit run src/ui/app.py
# Open http://localhost:8501
```

### Manual E2E — HTTP Mode

```bash
# Terminal 1
uvicorn src.api.app:app --reload --port 8000

# Terminal 2
set NATIVE_PLANNING_API_URL=http://localhost:8000   # Windows
# or: export NATIVE_PLANNING_API_URL=http://localhost:8000   # bash
streamlit run src/ui/app.py
```

Both modes must produce identical plans + execution + share messages for the `family` fixture key.

### Smoke Checklist

1. Free-text input → plan card appears within ~5s (LLM) or <1s (rule).
2. Trace expander shows ≥4 rows (search_venues, search_restaurants, check_*, etc.).
3. 确认并执行 produces non-empty execution results + share message.
4. `st.code` block shows clipboard icon on hover.
5. Refresh page → state clears (acceptable for MVP-2).
6. Set `OPENAI_API_KEY` to an invalid value → page still works via rule/template fallback (badge may mislabel — known limitation, see Section 8).

---

## 8. Known Risks & Notes

- **`[LLM]` badge accuracy.** The badge currently reflects only env var presence, not whether the LLM call actually succeeded. If the LLM fails and falls back to rule-based, the badge still says `[LLM]`. Real fix: thread a `source` value out of `parse_free_text()` (return `(intent, source)` tuple). Defer to MVP-2 polish or later.
- **Streamlit rerun semantics.** Every widget interaction reruns the whole script top-to-bottom. Keep heavy work (plan generation, execution) behind explicit button clicks, and cache results in `st.session_state`. Do **not** call `generate()` on every rerun.
- **`httpx` timeout in `HttpClient`.** LLM calls can take 5–10s. Set timeout to 30s.
- **Streamlit dataframe column widths.** Tool trace `inputs` can be long dicts — truncate to ~60 chars for the summary column, or render full input via `st.json` inside a per-row nested expander.
- **Stateless API + `session_state`.** The plan lives only in `st.session_state["plan"]`. Browser refresh wipes it. Acceptable for demo, but mention it in the UI ("刷新页面会清空当前计划").
- **Python 3.14 + Streamlit.** Confirm `streamlit>=1.30` works on Python 3.14.4 (user's env). If not, fall back to a Python 3.12 conda env for UI work only.
- **Conda env reminder.** User works in `agent` at `E:\miniforge\envs\agent`. Run `mamba activate E:\miniforge\envs\agent` first.
- **Trace serialization in HTTP mode.** `/api/plans/generate` already serializes traces to plain dicts via `_trace_to_dict`. The UI must **not** assume traces are `ToolTrace` dataclasses. The in-process client should also normalize traces to dicts so both modes have identical shapes.
- **Memory files.** `MEMORY.md` already notes: OpenAI (not Anthropic), conda env `agent`, Python 3.14.4. Do not contradict these.
- **`CLAUDE.md` priorities still apply.** Keep code modular, mock API separate from agent logic, schemas centralized, planning logic testable. MVP-2 is the UI step — proceed.

---

## Quick Start for the Next Session

1. `mamba activate E:\miniforge\envs\agent`
2. `pytest tests/ -v` → confirm 33/33 still pass before touching anything.
3. Read **Section 3** (approved design decisions) and **Section 5** (file structure).
4. Build `src/ui/planning_client.py` first (no Streamlit dependency yet — just the abstraction + tests).
5. Then build `src/ui/app.py` calling the client.
6. Verify both backend modes per **Section 7**.
