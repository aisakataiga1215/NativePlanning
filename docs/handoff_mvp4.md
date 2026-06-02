# MVP-4 完成文档：丰富本地数据 + 动态多站点 + 位置锚点

## 1. MVP-3.5 Summary

MVP-3.5 added the plan revision loop and expanded mock data coverage.

**Plan Revision Loop**
- User types a short correction ("太远了" / "换个餐厅" / "想吃日料") after seeing a plan and clicks "调整方案"
- `apply_revision(intent, text, current_plan?) -> UserIntent` applies 17 keyword rules in a single pass
- Returns a new `UserIntent` via `model_copy(update={...})` — immutable, no in-place mutation
- Full generate pipeline re-runs from the updated intent; result replaces `st.session_state["last_generate"]`
- Revision UI is hidden once the user clicks "确认并执行" — enforces revision-before-execution ordering
- One-turn only; no revision history accumulated

**Mock Data Expansion**
- Venues: 6 → 12 (added board_game, tea_house, citywalk, escape_room, movie, kids_lab)
- Restaurants: 6 → 12 (added bbq/loud, quiet-chinese/elderly, business-casual, coffee/couple, kids-theme, ramen/japanese)
- New schema fields: `Venue.walk_intensity`, `Venue.noise_level`, `Venue.queue_minutes`; `Restaurant.noise_level`
- New intent fields: `UserIntent.avoid_venue_ids`, `UserIntent.avoid_restaurant_ids`

**Field-Aware Ranking**
- `walk_intensity == "high"` + `avoid_long_walk` constraint → −0.20 penalty
- `restaurant.queue_minutes > 20` + `avoid_long_queue` constraint → −0.15 penalty
- Senior participant + `noise_level == "loud"` → −0.15 (venue) / −0.10 (restaurant)
- `"indoor"` constraint + outdoor venue → −0.30 penalty
- Colleagues scenario + loud venue → −0.10 penalty

**Tests**: 22 new (`test_revision_parser.py` × 19, `test_revision_integration.py` × 3); **113/113 total** (MVP-3.5 基线)

---

## 2. Architecture Delta

### New file
- `src/workflow/revision_parser.py` — `apply_revision()`, single public function

### New API endpoint
- `POST /api/plans/revise` in `src/api/app.py`
- Request schema: `ReviseRequest` in `src/api/schemas.py` (`revision_text`, `intent`, `current_plan?`)
- Response: `GenerateResponse` (same shape as `/generate`)

### Extended protocol
- `PlanningClient.revise(revision_text, intent, current_plan?) -> GenerateResponse` added to Protocol
- `InProcessClient.revise()` — calls `apply_revision` then full generate pipeline
- `HttpClient.revise()` — POSTs to `/api/plans/revise` with `trust_env=False`

### Planner filter
- `src/workflow/planner.py`: after `search_venues`, filter `[v for v in venues if v.id not in intent.avoid_venue_ids]`; same for restaurants

### UI flow
```
text input → 生成计划 → [revision loop: 0-N times] → 确认并执行 → (revision hidden)
```

---

## 3. Key Design Decisions

**One-turn stateless revision**  
`apply_revision` merges updates into the most-recently-generated intent, not an accumulating history. Simple to reason about, testable in isolation, sufficient for competition demo. Each "调整方案" click re-runs from a clean delta.

**`st.form` for revision input, no `clear_on_submit`**  
`st.form` avoids the Enter-to-submit UX problem (important for mobile compatibility). `clear_on_submit=True` was removed — Streamlit clears `text_input` return value in the same rerun as `form_submit_button` returns `True`, causing `revision_text.strip()` to be empty and the call to be silently skipped.

**`selected_plan_idx = 0` not `.pop()`**  
After revision, the radio widget must pre-select option 0 (the recommended plan). Popping the key leaves the radio unselected on the next render. Explicit assignment ensures deterministic state.

**Filter in planner, not ranker**  
`avoid_venue_ids` / `avoid_restaurant_ids` are applied after `search_venues` / `search_restaurants`, before candidate generation. This is simpler and cheaper than generating then discarding: avoids wasting planner work on explicitly excluded items.

**Field-aware penalties over pure tag matching**  
Adding `walk_intensity`, `noise_level`, `queue_minutes` to schemas enables precise, auditable scoring. Tag-based matching (checking string lists) gives binary pass/fail; numeric fields allow graduated penalties. Both patterns coexist in `plan_ranker.py`.

**Default start time 10:00**  
LLM output was `"00:00"` when no time was mentioned (model returned midnight for unspecified time). Fixed by adding "未提及时间 → time='10:00'" to the system prompt and changing `UserIntentLLM.time` default. Rule-based fallback now also defaults to `"10:00"` instead of `"14:00"`.

---

## 4. Known Limitations / Tech Debt

- **Revision is keyword-only**: ambiguous inputs ("不好", "换一个") are silently ignored; no feedback to user that the input was unrecognized
- **No multi-turn accumulation**: "太远" + "换个餐厅" in separate turns both work, but each revision starts fresh from the previous intent — the second revision cannot reference changes made by the first
- **"再远一点" caps at 15 km** with no user-visible feedback if the cap is hit
- **`st.form` cannot conditionally disable the button** based on empty input in current Streamlit — button is always enabled; empty submission is caught by `if revision_text.strip()` guard in `_run_revise`
- **`docs/data_simulation.md` states "no real API available from competition"** — if real APIs are added, only tool wrappers (`src/tools/wrappers.py`) and mock API modules need updating; planner and ranker are API-agnostic
- **No pagination in mock API search** — all 12 venues / 12 restaurants returned on every search; acceptable for current dataset size
- **`PersonProfile` vs `Participant`**: fixture scenarios use `PersonProfile` (legacy); free-text parsing uses `Participant` (new). Both coexist in `UserIntent.people` and `UserIntent.participants`. Should be unified in a future cleanup

---

## 5. MVP-4 已交付功能

Core theme: **Rich Local-Life Data + Dynamic Multi-stop Itinerary + Location Anchor**

### A. 丰富本地生活数据（已完成）

- 13 个场馆 / 12 个餐厅均新增：`area`、`nearby_areas`、`review_count`、
  `positive_review_tags`、`negative_review_tags`、`specialty_tags`
- 餐厅新增：`recommended_dishes`、`restaurant_coupons`、`packages`
- 场馆新增：`venue_coupons`、`packages`、`suggested_duration_min/max`、`duration_flexibility`
- `src/schemas/coupon_package.py`：`Package`、`VenueCoupon`、`RestaurantCoupon` Pydantic schema
- UI 计划卡片展示：推荐菜 / 好评标签 / 差评风险 / 优惠券 / 套餐 / 亮点标签

### B. 动态多站点行程（已完成）

- `build_dynamic_timeline()` in `itinerary_builder.py`：时间预算残差驱动，非硬模板
- `generate_plans()` in `planner.py`：新主入口，根据 `duration_hours` 决定单站或多站
- `estimate_travel_minutes(km, same_area)` 替代 10min 魔法固定值
- `ItineraryPlan.venue_ids: list[str]`、`stop_count: int` 新增字段
- `PlanStep.travel_minutes`、`PlanStep.area` 新增字段
- `duration_flexibility == "low"` 的场馆（密室/电影/主题乐园）不触发多站扩展

### C. 位置锚点（已完成）

- `UserIntent.location_anchor: str`（默认空字符串）
- `intent_parser.py`：`_extract_location_anchor()` 函数，虚构地名映射表 `_ANCHOR_AREA_MAP`
- `revision_parser.py`：正则提取 "先去X"/"X附近"，"换个区域" 清空锚点
- `plan_ranker.py`：`location_anchor` 加分（venue 同区 +0.15，restaurant 同区 +0.10）
- UI 意图面板：`location_anchor` 非空时显示"📍 位置锚点：..."

### D. 扩展修改关键词（已完成）

revision_parser 规则数量从 17 条扩展，新增覆盖：
- 距离增大："太近了"、"有点近"、"扩大范围"、"去远点" 等
- 预算降低："太贵了"、"贵了点"、"有点贵" 等
- 预算升高（新规则）："贵一点没关系"、"不差钱"、"预算充足" 等
- 排队回避："人太多了"、"等太久"、"不想等" 等
- 室内需求："太晒了"、"怕晒"、"热死了" 等

### E. 虚构地名（已完成）

所有真实北京地名替换为虚构地名，避免误导用户：

| 原地名 | 虚构替换 |
|--------|----------|
| 三里屯 | 芳华街 |
| 望京 | 云景 |
| 海淀区 / 中关村 / 五道口 | 明湖区 / 学海村 |
| 朝阳区 | 晨阳区 |
| 西城 | 古城区 |
| 前门 / 大栅栏 | 古门 / 旧市 |

**Tests**: 30 new in MVP-4 (`test_multistop_planner.py` × 9, `test_location_anchor.py` × 8,
`test_revision_parser.py` 新增 × 8, `test_revision_integration.py` 新增 × 5); **144/144 total**

---

## 6. Verification Commands

```bash
# Full test suite — must all pass
E:/miniforge/envs/agent/python.exe -m pytest tests/ -q
# Expected: 144 passed, 0 failed

# CLI smoke tests
E:/miniforge/envs/agent/python.exe -m src.cli.main family
E:/miniforge/envs/agent/python.exe -m src.cli.main failure-no-seats
E:/miniforge/envs/agent/python.exe -m src.cli.main friends
E:/miniforge/envs/agent/python.exe -m src.cli.main failure-no-tickets
E:/miniforge/envs/agent/python.exe -m src.cli.main failure-time-conflict

# Streamlit in-process mode
E:/miniforge/envs/agent/Scripts/streamlit.exe run src/ui/app.py

# Revision loop checks:
# 1. Generate plan → type "太近了" → click "调整方案"
#    → intent panel max_distance_km should increase (×1.5)
# 2. Generate plan → type "有点远" → click "调整方案"
#    → intent panel max_distance_km should decrease (×0.6)
# 3. Generate plan → type "太贵了" → click "调整方案"
#    → budget_preference should change to "low"
# 4. Generate plan → type "贵一点没关系" → click "调整方案"
#    → budget_preference should change to "high"
# 5. Generate plan → type "换个餐厅" → click "调整方案"
#    → different restaurant_id in plan card
# 6. Generate plan → click "确认并执行"
#    → "想调整方案" section should be hidden

# Location anchor checks:
# 1. Input "先去芳华街逛逛，然后找个好餐厅"
#    → intent panel shows "📍 位置锚点：芳华街"
#    → recommended venue area is "芳华街" or adjacent
# 2. After plan, type "去云景附近吧" in revision
#    → location_anchor changes to "云景"

# HTTP mode
E:/miniforge/envs/agent/python.exe -m uvicorn src.api.app:app --reload
curl -X POST http://localhost:8000/api/plans/revise \
  -H "Content-Type: application/json" \
  -d "{\"revision_text\":\"太远了\",\"intent\":{\"scenario_type\":\"family\",\"group_size\":3,\"max_distance_km\":8.0,\"duration_hours\":4.0}}"

curl http://localhost:8000/api/health
```

---

## 7. File Map (MVP-3.5 Changes)

| File | Change | Key Detail |
|------|--------|-----------|
| `src/schemas/venue.py` | Modified | +`walk_intensity`, `noise_level`, `queue_minutes` |
| `src/schemas/restaurant.py` | Modified | +`noise_level` |
| `src/schemas/user_intent.py` | Modified | +`avoid_venue_ids`, `avoid_restaurant_ids` |
| `src/mock_api/venues.py` | Modified | 6 → 12 venues; all entries have new fields |
| `src/mock_api/restaurants.py` | Modified | 6 → 12 restaurants; all entries have `noise_level` |
| `src/workflow/planner.py` | Modified | Filter `avoid_venue_ids` / `avoid_restaurant_ids` after each search |
| `src/workflow/revision_parser.py` | **NEW** | `apply_revision()` — 17-rule keyword table |
| `src/workflow/intent_parser.py` | Modified | Default time 10:00; LLM prompt "未提及时间" rule added |
| `src/services/plan_ranker.py` | Modified | Field-aware penalties (walk/queue/noise/indoor) |
| `src/api/schemas.py` | Modified | +`ReviseRequest` |
| `src/api/app.py` | Modified | +`POST /api/plans/revise` endpoint |
| `src/ui/planning_client.py` | Modified | +`revise()` to Protocol, InProcessClient, HttpClient |
| `src/ui/app.py` | Modified | +revision UI (`st.form`); cost breakdown (🎟/🍽/💰); distance label shows km |
| `tests/test_revision_parser.py` | **NEW** | 19 unit tests covering all 17 rules + edge cases |
| `tests/test_revision_integration.py` | **NEW** | 3 integration tests (pipeline shape, avoid_restaurant, distance) |
| `docs/data_simulation.md` | **NEW** | Judge-facing Chinese doc explaining mock data strategy |

---

## 8. Test Coverage

**Total: 144/144 passing** (no `OPENAI_API_KEY` required)

| Test File | Count | What It Covers |
|-----------|-------|----------------|
| `test_intent_parser.py` | ~12 | Rule-based keyword parsing, participant detection, scenario classification |
| `test_intent_parser_llm.py` | 8 | LLM path (mocked), Structured Outputs → json_object → rule-based fallback chain |
| `test_planner.py` | ~12 | Candidate generation, `avoid_ids` filter, multi-scenario coverage |
| `test_constraint_solver.py` | ~8 | 3 failure cases (no-seats, no-tickets, time-conflict) + repair logic |
| `test_ranker.py` | ~8 | 5-dim scoring, field-aware penalties, anchor/coupon/dishes bonuses |
| `test_executor.py` | ~8 | Ticket booking, restaurant reservation, order creation |
| `test_api.py` | 7 | `/generate`, `/execute`, `/revise`, `/health` endpoints |
| `test_ui_client.py` | 10 | `InProcessClient`, `HttpClient`, env-switch, `trust_env=False` |
| `test_revision_parser.py` | ~28 | All `apply_revision` rules incl. expanded distance/budget/indoor keywords |
| `test_revision_integration.py` | ~5 | Full pipeline after revision, `avoid_restaurant_id` propagation, distance reduction |
| `test_multistop_planner.py` | ~9 | Dynamic timeline: theme park no-secondary, light-stop insert, full-day multi-stop, budget conformance |
| `test_location_anchor.py` | ~8 | Anchor extraction (rule + LLM), ranker area match boost, revision anchor update |
| Other (message_agent, itinerary_builder, schemas) | ~20 | Share message generation, timeline building, Pydantic schema validation |

Run with:
```bash
E:/miniforge/envs/agent/python.exe -m pytest tests/ -v --tb=short
```
