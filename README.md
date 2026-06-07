# NativePlanning — Local Activity Planning Agent

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://nativeplanning.streamlit.app/)

**Live Demo: https://nativeplanning.streamlit.app/**

A local-life planning and execution agent that turns one natural language request into a
complete, confirmed, executable 4–6 hour activity plan.

> 今天下午想和老婆孩子出去玩几个小时，别离家太远，帮我安排一下。

The system searches venues and restaurants via MockAPI, handles seat/ticket failures, ranks
candidates, presents a timeline with scores and risks, and executes bookings after one-click
confirmation.

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt && pip install -e .
# or with extras:
pip install -e ".[api,ui]"        # FastAPI + Streamlit
pip install -e ".[dev]"           # tests only

# 2. (Optional) Configure LLM — any OpenAI-compatible provider
cp .env.example .env
# Set OPENAI_API_KEY, OPENAI_BASE_URL (DeepSeek), OPENAI_MODEL
# Without a key the system falls back to rule-based intent parsing automatically

# 3. Start Streamlit UI
streamlit run src/ui/app.py
# → http://localhost:8501
```

---

## CLI Demo (no extra deps)

```bash
python -m src.cli.main family              # family scenario
python -m src.cli.main friends             # friends scenario
python -m src.cli.main failure-no-seats    # restaurant unavailable → auto-repair
python -m src.cli.main failure-no-tickets  # venue tickets sold out → auto-repair
python -m src.cli.main failure-time-conflict  # time crunch → plan compressed
```

Free-text input (requires `OPENAI_API_KEY`):
```bash
python -m src.cli.main 今天下午想和三个朋友出去玩，拍拍照吃个好的
```

---

## Streamlit UI

> Full judge walkthrough: **[docs/demo_script.md](docs/demo_script.md)**

**In-process mode (default):**
```bash
streamlit run src/ui/app.py
# → http://localhost:8501
```

**HTTP mode (FastAPI backend):**
```bash
# Terminal 1
uvicorn src.api.app:app --reload --port 8000

# Terminal 2 — Windows
set NATIVE_PLANNING_API_URL=http://localhost:8000
streamlit run src/ui/app.py

# Terminal 2 — macOS / Linux
export NATIVE_PLANNING_API_URL=http://localhost:8000
streamlit run src/ui/app.py
```

The UI shows intent panel (with `[LLM]` / `[rule-based]` source badge), plan card
(5-dim score), alternative plan selector (up to 3 candidates), timeline, collapsible
tool traces, two-step confirm flow, execution results with booking IDs, copy-ready
share message, and a 🔄 reset button.

See [`docs/demo_script.md`](docs/demo_script.md) for the full judge demo walkthrough.

---

## Tests

```bash
pytest tests/ -q
# 321 passed — no OPENAI_API_KEY required
```

---

## Architecture

```
User Input
  └─ Intent Parser (LLM → json_object → rule-based fallback)
       └─ Planner → Constraint Solver → Plan Ranker
            └─ Executor (book_venue, reserve_restaurant, …)
                 └─ Message Agent (LLM → template fallback)

MockAPI  ←  Tool Wrappers (ToolTrace / TraceLog)
FastAPI  ←  InProcessClient / HttpClient  ← Streamlit UI
```

Runtime code lives in `src/workflow/` and `src/tools/`.
See [`docs/architecture.md`](docs/architecture.md) for details.

---

## Milestones

| Milestone | Status | Description |
|-----------|--------|-------------|
| MVP-0 | ✓ Complete | Deterministic CLI, 5 scenarios, 18 tests |
| MVP-1 | ✓ Complete | LLM intent parser (OpenAI-compatible) + FastAPI app |
| MVP-2 | ✓ Complete | Streamlit UI, dual backend mode |
| MVP-3 | ✓ Complete | Alternative plans selector, source tracking, UI polish |
| MVP-4 | ✓ Complete | meal_policy, revision, opening-hours gate, 321 tests |

---

## Project Structure

```
src/
├── api/          # FastAPI app + HTTP schemas
├── cli/          # CLI entry point
├── mock_api/     # In-memory MockAPI (venues, restaurants, coupons)
├── schemas/      # Pydantic v2 domain schemas
├── services/     # plan_ranker, itinerary_builder
├── tools/        # Tool wrappers + TraceLog
├── ui/           # Streamlit app + PlanningClient
└── workflow/     # intent_parser, planner, constraint_solver,
                  # executor, message_agent
tests/            # 91 tests, no external API calls
docs/             # architecture, changelog, demo_script, project_status
```
