# Engineering Spec: LocalLife Agent

## 1. Tech Stack

### Recommended MVP Stack

- Language: Python 3.11+
- Backend: FastAPI
- CLI: Typer or Click
- Web UI: Streamlit or simple React frontend
- Database: SQLite for MVP
- MockAPI: FastAPI mock server
- LLM Provider: Claude API or OpenAI-compatible API
- Schema Validation: Pydantic
- Testing: Pytest

### Alternative Stack

If prioritizing frontend demo:

- Frontend: Next.js + Tailwind CSS
- Backend: FastAPI
- Database: SQLite
- MockAPI: FastAPI

## 2. System Overview

The system consists of five major layers:

1. User Interface Layer
   - CLI or Web UI
   - Receives natural language requests
   - Displays plans, tool traces, and execution status

2. Agent Layer
   - Intent Parser
   - Planner
   - Constraint Solver
   - Executor
   - Message Agent

3. Tool Layer
   - Venue search tool
   - Restaurant search tool
   - Availability check tool
   - Booking tool
   - Order tool

4. MockAPI Layer
   - Simulates local life services
   - Provides venues, restaurants, ticket inventory, seats, and booking results

5. Persistence and Trace Layer
   - Stores generated plans
   - Stores booking records
   - Stores tool call traces
   - Supports demo observability

## 3. Core Modules

### 3.1 Intent Parser

Responsible for converting natural language into structured intent.

Input:

```json
{
  "message": "今天下午空的，想和老婆孩子出去玩几个小时，别离家太远，帮我安排一下"
}
````

Output:

```json
{
  "scenario_type": "family",
  "group": {
    "adults": 2,
    "children": 1,
    "child_age": 5
  },
  "time_window": {
    "date": "today",
    "start": "14:00",
    "duration_hours": 5
  },
  "constraints": {
    "distance": "near_home",
    "diet": ["healthy", "low_calorie"],
    "activity": ["child_friendly"]
  }
}
```

### 3.2 Planner

Responsible for generating a candidate itinerary.

Responsibilities:

* Allocate time dynamically
* Choose activity categories
* Select restaurant timing
* Add travel buffer
* Call tools when required
* Produce a structured plan

### 3.3 Constraint Solver

Responsible for checking hard and soft constraints.

Hard constraints:

* Time window
* Group size
* Seat availability
* Ticket availability
* Distance limit

Soft constraints:

* Health preference
* Child friendliness
* Photo-friendly
* Social atmosphere
* Budget

### 3.4 Executor

Responsible for executing confirmed actions.

Execution actions:

* Book tickets
* Reserve restaurant
* Place optional order
* Generate final confirmation message

### 3.5 Exception Handler

Responsible for automatic fallback.

Failure cases:

1. Restaurant has no seats
2. Venue has no tickets
3. Plan has time conflict
4. Distance too far
5. Tool timeout

## 4. Data Models

### 4.1 UserIntent

```python
class UserIntent(BaseModel):
    scenario_type: Literal["family", "friends"]
    group_size: int
    group_profile: dict
    time_window: TimeWindow
    location_constraint: str
    preferences: list[str]
    restrictions: list[str]
```

### 4.2 Plan

```python
class Plan(BaseModel):
    plan_id: str
    title: str
    total_duration_minutes: int
    items: list[PlanItem]
    estimated_cost: int
    risk_notes: list[str]
    execution_actions: list[ExecutionAction]
```

### 4.3 PlanItem

```python
class PlanItem(BaseModel):
    item_type: Literal["activity", "meal", "transport", "buffer", "optional"]
    start_time: str
    end_time: str
    name: str
    location: str
    reason: str
    booking_required: bool
    availability_status: str
```

### 4.4 ToolCallTrace

```python
class ToolCallTrace(BaseModel):
    tool_name: str
    input: dict
    output: dict
    latency_ms: int
    status: Literal["success", "failed", "fallback"]
```

## 5. MockAPI Design

### 5.1 Venue APIs

```txt
GET /mock/venues/search
GET /mock/venues/{venue_id}/availability
POST /mock/venues/{venue_id}/book
```

### 5.2 Restaurant APIs

```txt
GET /mock/restaurants/search
GET /mock/restaurants/{restaurant_id}/availability
POST /mock/restaurants/{restaurant_id}/reserve
```

### 5.3 Order APIs

```txt
POST /mock/orders/create
POST /mock/messages/share
```

## 6. API Structure

### 6.1 App APIs

```txt
POST /api/plan/create
POST /api/plan/{plan_id}/confirm
POST /api/plan/{plan_id}/execute
GET  /api/plan/{plan_id}
GET  /api/traces/{plan_id}
```

### 6.2 Example: Create Plan

Request:

```json
{
  "message": "今天下午空的，想和老婆孩子出去玩几个小时，别离家太远，帮我安排一下",
  "home_location": "望京",
  "scenario_hint": "family"
}
```

Response:

```json
{
  "plan_id": "plan_001",
  "status": "ready_for_confirmation",
  "summary": "下午2点出发，先去亲子乐园，再吃健康轻食晚餐。",
  "items": [],
  "tool_traces": []
}
```

## 7. Planning Strategy

The planner uses a hybrid strategy:

1. Parse user intent with LLM
2. Convert intent into structured constraints
3. Retrieve candidate venues and restaurants through tools
4. Filter candidates with hard constraints
5. Rank candidates with soft constraints
6. Compose itinerary with dynamic time allocation
7. Check availability
8. Repair plan if conflicts occur
9. Return final executable plan

## 8. Exception Handling Strategy

### Case 1: Restaurant unavailable

Fallback order:

1. Try adjacent time slots
2. Try similar restaurants nearby
3. Change meal order while preserving activity plan

### Case 2: Venue unavailable

Fallback order:

1. Try same category venue nearby
2. Try different child-friendly or social activity
3. Shorten activity and add optional stop

### Case 3: Time conflict

Fallback order:

1. Increase buffer
2. Remove optional activity
3. Replace far destination
4. Ask user to confirm shortened plan

### Case 4: Tool timeout

Fallback order:

1. Retry once
2. Use cached mock data
3. Mark risk and continue with safer option

## 9. Observability

Each plan should store:

* Parsed intent
* Tool calls
* Tool latency
* Candidate filtering results
* Fallback decisions
* Final execution result

This is important for demo explanation and judging criteria.

## 10. Testing Strategy

### Unit Tests

* Intent parsing
* Time allocation
* Constraint filtering
* Restaurant fallback
* Venue fallback

### Integration Tests

* Family scenario full flow
* Friend scenario full flow
* No-seat fallback
* No-ticket fallback
* Time-conflict fallback

### Demo Tests

* Pass@1 end-to-end test
* Tool latency simulation
* Failure recovery demonstration

## Project Structure

The project uses separate directories for runtime workflow code, development subagents, tools, MockAPI, and documentation.

```txt
NativePlanning/
├── README.md
├── CLAUDE.md
├── product_spec.md
├── engineering_spec.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── .claude/
│   └── agents/
│       ├── architect.md
│       ├── backend-engineer.md
│       ├── frontend-engineer.md
│       ├── planning-agent-engineer.md
│       ├── qa-observability-engineer.md
│       └── docs-maintainer.md
├── docs/
│   ├── architecture.md
│   ├── changelog.md
│   ├── project_status.md
│   └── schema_design.md
├── src/
│   ├── cli/
│   │   └── main.py          # CLI entry: python -m src.cli.main <scenario>
│   ├── workflow/             # planning pipeline (intent→plan→execute→message)
│   │   ├── intent_parser.py
│   │   ├── planner.py
│   │   ├── constraint_solver.py
│   │   ├── executor.py
│   │   └── message_agent.py
│   ├── services/
│   │   ├── itinerary_builder.py
│   │   └── plan_ranker.py
│   ├── tools/
│   │   └── wrappers.py      # ToolTrace / TraceLog
│   ├── mock_api/             # in-memory mock data + API functions
│   │   ├── venues.py
│   │   ├── restaurants.py
│   │   ├── booking.py
│   │   └── orders.py
│   └── schemas/
│       ├── user_intent.py
│       ├── venue.py
│       ├── restaurant.py
│       ├── plan.py
│       └── order.py
└── tests/
    ├── test_happy_path.py
    └── test_failures.py
```

## Runtime Workflow Modules

Runtime workflow code lives in `src/workflow/`.

It includes:

* `intent_parser.py`
* `planner.py`
* `constraint_solver.py`
* `executor.py`
* `message_generator.py`

Do not confuse these runtime modules with Claude Code development subagents under `.claude/agents/`.

## Detailed Planning Strategy

See [docs/planning_strategy.md](docs/planning_strategy.md).

## Detailed MockAPI Design

See [docs/mock_api_design.md](docs/mock_api_design.md).

## Claude Code Development Workflow

See [docs/claude_code_workflow.md](docs/claude_code_workflow.md).
