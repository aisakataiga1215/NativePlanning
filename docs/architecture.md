# Architecture

## 1. Overview

LocalLife Agent is a local activity planning and execution system. It transforms a user's natural language request into a structured, executable local-life plan.

The system uses a hybrid architecture:

- LLM for natural language understanding and high-level planning
- Deterministic rules for constraints, time allocation, and fallback
- MockAPI tools for venue, restaurant, availability, and booking simulation
- Trace logging for observability

## 2. Main Flow

```txt
User Message
  ↓
Intent Parser
  ↓
Structured Intent
  ↓
Planner
  ↓
Tool Calls
  ↓
Constraint Solver
  ↓
Candidate Plan
  ↓
Availability Check
  ↓
Exception Handler
  ↓
Final Plan
  ↓
User Confirmation
  ↓
Executor
  ↓
Bookings / Orders / Share Message
```

## 3. Main Components

### 3.1 UI Layer

The UI layer can be CLI or Web UI.

Responsibilities:

* Accept user request
* Display generated plan
* Display tool traces
* Ask for user confirmation
* Display execution result

### 3.2 Intent Parser

Converts natural language into structured constraints.

Extracted information includes:

* Scenario type
* Group size
* Group profile
* Time window
* Distance constraint
* Diet preference
* Activity preference

### 3.3 Planner

Generates a multi-step itinerary.

Responsibilities:

* Allocate time blocks
* Select activity categories
* Select restaurant timing
* Call search tools
* Compose executable plan

### 3.4 Constraint Solver

Checks whether the plan satisfies hard and soft constraints.

Hard constraints include:

* Time window
* Availability
* Group size
* Travel distance

Soft constraints include:

* Healthy food
* Child friendliness
* Social atmosphere
* Novelty

### 3.5 Tool Layer

Tool wrappers hide MockAPI details from the Agent layer.

Tools include:

* Venue search
* Venue availability check
* Restaurant search
* Restaurant availability check
* Booking
* Order creation
* Share message generation

### 3.6 MockAPI Layer

The MockAPI simulates local life platform capabilities.

It stores:

* Venues
* Restaurants
* Availability
* Ticket inventory
* Seat inventory
* Booking records

### 3.7 Executor

The executor runs confirmed actions.

Execution actions include:

* Book venue tickets
* Reserve restaurant seats
* Create optional orders
* Generate final share message

### 3.8 Trace Logger

The trace logger records:

* Tool name
* Tool input
* Tool output
* Latency
* Failure reason
* Fallback result

## 4. Data Flow

### 4.1 Plan Creation

```txt
POST /api/plan/create
  → parse intent
  → search venues
  → search restaurants
  → check availability
  → generate plan
  → return plan
```

### 4.2 Plan Execution

```txt
POST /api/plan/{plan_id}/execute
  → check user confirmation
  → book venue
  → reserve restaurant
  → create optional order
  → generate share message
  → return execution result
```

## 5. Failure Recovery

The exception handler should attempt automatic repair before asking the user.

Failure types:

1. No restaurant seats
2. No venue tickets
3. Time conflict
4. Distance too far
5. Tool timeout

## 6. Design Principles

* Keep Agent decisions observable.
* Do not invent tool results.
* Prefer local repair over full replanning.
* Keep demo scenarios deterministic.
* Use schemas to validate every important object.

## 7. Frontend Topology

The project ships two interchangeable UI clients on top of the same FastAPI backend:

1. **Streamlit UI** (`src/ui/app.py`) — the default in-repo demo. Runs in-process or via HTTP against the FastAPI app. Lives on `main`.
2. **Next.js 14 SPA** (`frontend/`) — TypeScript App Router build delivered on branch `feat/ts-frontend`. Talks to the FastAPI backend over HTTP only.

Both UIs consume the same three endpoints: `POST /api/plans/generate`, `POST /api/plans/revise`, `POST /api/plans/execute`. Schemas are mirrored on the TypeScript side in `frontend/lib/types.ts`.

### 7.1 Next.js Client Layout

```txt
frontend/
  app/
    layout.tsx          # root layout
    page.tsx            # single-page state machine
    globals.css
  components/
    IntentPanel.tsx     # parsed intent display
    PlanCard.tsx        # plan summary + score breakdown
    PlanSelector.tsx    # radio between primary + alternatives
    Timeline.tsx        # step-by-step itinerary
    ToolTrace.tsx       # collapsible tool call log
    ExecutionResult.tsx # booking / reservation results
    ShareMessage.tsx    # final share text
    RevisionInput.tsx   # natural-language revision form
  lib/
    types.ts            # mirrors Pydantic schemas
    api.ts              # generate / revise / execute HTTP client
  next.config.mjs       # dev proxy /api/:path* → FastAPI :8000
```

The page state machine drives the UI:

```txt
idle → generating → plan_ready → revising → plan_ready → executing → done
                          ↑__________________|
```

Tailwind CSS with brand color `#FF6900` powers the styling. No client-side state library is used; React `useState` plus a single page component is sufficient for the demo flow.

### 7.2 Deployment Topology

```txt
Browser
  ↓
Vercel (Next.js SPA)
  https://native-planning.vercel.app
  ↓ HTTPS
HuggingFace Spaces (Docker, FastAPI)
  https://aisakamai-nativeplanning.hf.space
  ↓
In-process MockAPI + Workflow Layer
```

- The Streamlit UI continues to be deployed to Streamlit Community Cloud at `https://nativeplanning.streamlit.app/` from `main`.
- The Next.js client points at `NEXT_PUBLIC_API_URL=https://aisakamai-nativeplanning.hf.space` in production and at `http://localhost:8000` in dev via `next.config.mjs` rewrites.
- The FastAPI app enables permissive CORS (`allow_origins=["*"]`) so any Vercel preview URL can call it; this is acceptable for the competition demo only.
- `Dockerfile` builds the backend for HuggingFace Spaces (port 7860). `render.yaml` is preserved as an alternative Render deployment recipe.

For deployment verification, see [docs/changelog.md](changelog.md) and [docs/project_status.md](project_status.md).

## Repository Structure

The repository separates runtime product code from Claude Code development assistants.

```txt
.claude/agents/    # Claude Code development subagents
src/workflow/      # Runtime planning workflow
src/tools/         # Tool wrappers
src/mock_api/      # Mock local-life APIs
src/services/      # Shared services
src/schemas/       # Pydantic schemas
src/api/           # FastAPI app APIs
src/ui/            # Streamlit demo UI (main branch)
frontend/          # Next.js 14 TypeScript SPA (feat/ts-frontend branch)
Dockerfile         # HuggingFace Spaces backend image
render.yaml        # Render alternative deployment recipe
```

Claude Code subagents are not part of the runtime architecture.

The runtime architecture is:

```txt
User Interface (Streamlit or Next.js)
  ↓
API / CLI
  ↓
Workflow Layer
  ↓
Tools
  ↓
MockAPI
  ↓
Trace / Persistence
```

For Claude Code subagent usage, see [docs/claude_code_workflow.md](claude_code_workflow.md).
