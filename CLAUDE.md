# CLAUDE.md

## 0. Environment

- Python: `E:\miniforge\envs\common\python.exe`
- Run tests: `E:\miniforge\envs\common\python.exe -m pytest tests/ -q`
- Run Streamlit: `E:\miniforge\envs\common\Scripts\streamlit.exe run src/ui/app.py`

## 1. Project Goal

This project is a competition demo for a local life planning and execution agent.

The system accepts a natural language request such as:

> 今天下午空的，想和老婆孩子/朋友出去玩几个小时，别离家太远，帮我安排一下。

It should generate an executable 4-6 hour local activity plan, check availability through MockAPI tools, handle exceptions, and execute key booking or ordering actions after user confirmation.

The goal is not to build a generic recommendation list, but to build an agent that helps the user complete the full local-life task.

## 2. Architecture Overview

The system follows a hybrid Agent + Tool architecture.

Main layers:

1. UI Layer
   - CLI or Web UI
   - Receives user input
   - Shows plan cards, timeline, tool traces, and execution result

2. Agent Layer
   - Intent Parser
   - Planner
   - Constraint Solver
   - Executor
   - Message Agent

3. Tool Layer
   - Venue tools
   - Restaurant tools
   - Booking tools
   - Order tools

4. MockAPI Layer
   - Simulates local life data and actions
   - Provides venue, restaurant, availability, and booking APIs

5. Trace Layer
   - Records each tool call and decision
   - Supports observability and demo explanation

For detailed system design, see [docs/architecture.md](docs/architecture.md).

## 3. Design Style Guide

The product should feel like a local-life assistant that has already done the work for the user.

Preferred UX style:

- Clear timeline
- Simple plan summary
- Visible reasons for each recommendation
- Explicit availability status
- Clear confirmation step
- One-click execution after confirmation
- Shareable final message

Avoid:

- Long recommendation lists
- Unexplained ranking
- Overly technical wording in user-facing output
- Asking too many follow-up questions
- Returning plans that are not executable

## 4. User Experience Rules

Every generated plan should include:

- Departure time
- Activity timeline
- Restaurant arrangement
- Travel or buffer time
- Availability status
- Booking or reservation action
- Reason why the plan fits the group
- Risk or fallback notes if applicable

For family scenarios, prioritize:

- Child friendliness
- Safety
- Short travel distance
- Healthy food options
- Lower physical burden

For friend scenarios, prioritize:

- Social interaction
- Balanced appeal to the group
- Photo-friendly or conversation-friendly places
- Smooth dinner arrangement
- Flexible optional activities

## 5. Planning Constraints

Hard constraints:

- The total plan should fit within 4-6 hours.
- Activities and meals must not overlap.
- Restaurants must have available seats before being selected.
- Ticket-based venues must have availability before booking.
- Travel distance should respect the user's "not too far" constraint.

Soft constraints:

- Healthy food preference
- Child-friendly environment
- Group atmosphere
- Price reasonableness
- Novelty and fun
- Low waiting time

## 6. Tool Usage Rules

The agent must not invent availability, seats, tickets, or booking results.

Before presenting a final executable plan, the agent should call tools for:

- Venue search
- Venue availability
- Restaurant search
- Restaurant availability

Before marking the plan as executed, the agent should call tools for:

- Ticket booking
- Restaurant reservation
- Optional order creation
- Share message generation

All tool calls should be logged.

## 7. Exception Handling Rules

The system must support at least three failure cases:

1. Restaurant has no seats
2. Venue has no tickets
3. Time or distance conflict

The system should repair the plan automatically when possible.

Fallback should preserve the user's main goal. For example:

- If the restaurant is unavailable, do not regenerate the entire plan.
- If the activity is unavailable, replace only the activity section.
- If there is a time conflict, first remove optional items before changing core items.

## 8. Repository Etiquette

When modifying the project:

1. Keep code modular.
2. Keep MockAPI separate from Agent logic.
3. Keep schemas centralized under `src/schemas`.
4. Keep planning logic testable.
5. Update [docs/architecture.md](docs/architecture.md) when adding major components.
6. Update [docs/changelog.md](docs/changelog.md) after meaningful changes.
7. Update [docs/project_status.md](docs/project_status.md) after completing milestones.
8. Do not duplicate long documentation across files. Use links instead.
9. Add or update tests when changing planner, tools, schemas, or exception handling.
10. Keep demo scenarios stable and easy to run.

## 9. Development Priority

Build in this order:

1. MockAPI data and endpoints
2. Core schemas
3. Intent parser
4. Planner
5. Tool wrappers
6. Exception handler
7. Executor
8. CLI demo
9. Web UI
10. Observability and polish

Do not optimize UI before the end-to-end flow works.

## Claude Code Subagent Workflow

This repository uses Claude Code subagents only as development assistants.

They are not part of the runtime product architecture.

Runtime product workflow lives under:

- `src/workflow/`
- `src/tools/`
- `src/services/`
- `src/mock_api/`

Claude Code development subagents live under:

- `.claude/agents/`

Available development subagents:

1. `architect`
   - Reviews architecture, project structure, and milestone scope.

2. `backend-engineer`
   - Implements backend APIs, schemas, MockAPI, tool wrappers, and persistence.

3. `frontend-engineer`
   - Implements CLI, Streamlit UI, timeline cards, confirmation flow, and trace display.

4. `planning-agent-engineer`
   - Implements intent parsing, planning, constraint solving, time allocation, ranking, and fallback repair.

5. `qa-observability-engineer`
   - Implements tests, E2E checks, trace validation, and demo stability checks.

6. `docs-maintainer`
   - Maintains project documentation and cross-links.

Subagent usage rules:

- Use `architect` before major structure changes.
- Use `planning-agent-engineer` for planning logic changes.
- Use `backend-engineer` for API, MockAPI, schema, and tool implementation.
- Use `frontend-engineer` only after the core flow is working.
- Use `qa-observability-engineer` after each milestone.
- Use `docs-maintainer` after meaningful architecture, API, or milestone changes.

Do not use Claude Code subagents as a reason to introduce unnecessary runtime multi-agent orchestration.
