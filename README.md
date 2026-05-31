# NativePlanning — Local Activity Planning Agent

A local-life planning and execution agent that turns one natural language request into a
complete, confirmed, executable 4–6 hour activity plan.

> 今天下午想和老婆孩子出去玩几个小时，别离家太远，帮我安排一下。

The system searches venues and restaurants via MockAPI, handles seat/ticket failures, ranks
candidates, presents a timeline with scores and risks, and executes bookings after one-click
confirmation.

---

## Quick Start

```bash
# 1. Activate the conda environment
mamba activate E:\miniforge
mamba activate agent

# 2. Install core + optional deps
cd NativePlanning
pip install -e ".[api,ui]"        # FastAPI + Streamlit
# or minimal:
pip install -e ".[dev]"           # tests only

# 3. (Optional) Configure LLM — any OpenAI-compatible provider
cp .env.example .env
# Set OPENAI_API_KEY, OPENAI_BASE_URL (DeepSeek), OPENAI_MODEL
# Without a key the system falls back to rule-based intent parsing automatically
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

The UI shows intent panel, plan card (5-dim score), timeline, collapsible tool traces,
two-step confirm flow, execution results with booking IDs, and a copy-ready share message.

See [`docs/demo_script.md`](docs/demo_script.md) for the full judge demo walkthrough.

---

## Tests

```bash
pytest tests/ -v
# 43 passed in ~1 s — no OPENAI_API_KEY required
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
| MVP-2 | ✓ Complete | Streamlit UI, dual backend mode, 43/43 tests in <1 s |
| v1 | Planned | Optional SQLite persistence |

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
tests/            # 43 tests, no external API calls
docs/             # architecture, changelog, demo_script, project_status
```
