# Claude Code Workflow

## 1. Purpose

This document defines how Claude Code subagents should be used during development.

Claude Code subagents are development assistants. They are not part of the runtime product architecture.

Runtime product code lives in:

- `src/workflow/`
- `src/tools/`
- `src/services/`
- `src/mock_api/`

Claude Code subagents live in:

- `.claude/agents/`

## 2. Subagent List

### 2.1 architect

Use for:

- Architecture review
- Project structure review
- MVP/v1/v2/future scope decisions
- Refactoring review

Do not use for:

- Writing large implementation code
- UI details
- Mock data editing

### 2.2 backend-engineer

Use for:

- FastAPI routes
- MockAPI endpoints
- Pydantic schemas
- Tool wrappers
- SQLite or persistence
- Execution APIs

Do not use for:

- Product strategy
- UI design
- Long documentation writing

### 2.3 frontend-engineer

Use for:

- CLI demo
- Streamlit or web UI
- Timeline display
- Plan cards
- Confirmation flow
- Trace display

Do not use for:

- Planner internals
- MockAPI design
- Backend schema changes without coordination

### 2.4 planning-agent-engineer

Use for:

- Intent parsing
- Planner
- Time allocation
- Constraint solving
- Ranking
- Tool calling chain
- Exception repair

Do not use for:

- UI polish
- Documentation-only changes
- MockAPI endpoint redesign unless necessary

### 2.5 qa-observability-engineer

Use for:

- Unit tests
- Integration tests
- E2E tests
- Trace validation
- Latency checks
- Demo stability

Do not use for:

- Major feature design
- Large rewrites without approval

### 2.6 docs-maintainer

Use for:

- Updating specs
- Updating architecture docs
- Updating changelog
- Updating project status
- Removing duplicated docs
- Adding cross-links

Do not use for:

- Code implementation
- Runtime logic design

## 3. Recommended Development Flow

### Phase 1: Documentation and Structure

Use:

- `architect`
- `docs-maintainer`

Goal:

- Create base docs
- Confirm architecture
- Confirm project structure

### Phase 2: MockAPI

Use:

- `backend-engineer`
- `qa-observability-engineer`

Goal:

- Implement deterministic MockAPI
- Add test data for happy paths and failure paths

### Phase 3: Runtime Workflow

Use:

- `planning-agent-engineer`
- `backend-engineer`
- `qa-observability-engineer`

Goal:

- Implement intent parsing
- Implement planner
- Implement constraint solving
- Implement fallback repair

### Phase 4: Demo Interface

Use:

- `frontend-engineer`
- `qa-observability-engineer`

Goal:

- Implement CLI or Streamlit UI
- Show timeline, trace, confirmation, and execution result

### Phase 5: Demo Polish

Use:

- `architect`
- `qa-observability-engineer`
- `docs-maintainer`

Goal:

- Verify end-to-end stability
- Check docs
- Prepare demo script

## 4. Coordination Rules

1. The main Claude Code session should remain the coordinator.
2. Subagents should be used for focused tasks.
3. Do not let multiple subagents edit the same file at the same time.
4. After a subagent changes architecture, API, schema, or milestone status, run `docs-maintainer`.
5. After a subagent changes planning logic, run `qa-observability-engineer`.
6. After backend API changes, notify frontend work explicitly.
7. Keep runtime workflow and Claude Code subagents conceptually separate.

## 5. Anti-patterns

Avoid:

- Creating too many subagents.
- Treating Claude Code subagents as runtime product agents.
- Letting every subagent rewrite documentation.
- Letting UI work start before the end-to-end flow works.
- Adding real API integrations before MockAPI is stable.
- Overengineering multi-agent orchestration inside the product.
