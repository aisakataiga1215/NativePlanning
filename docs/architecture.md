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
src/ui/            # Demo UI
```

Claude Code subagents are not part of the runtime architecture.

The runtime architecture is:

```txt
User Interface
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
