# Handoff: MVP-4.6 Bugfix & Data Consistency Pass

> 本文档供新的 Claude Code 会话接手使用。请先完整阅读，再输出实现计划，等人确认后再写代码。

---

## 1. 当前项目状态

### 已完成里程碑

| 里程碑 | 完成时间 | 核心内容 |
|--------|---------|---------|
| MVP-0 | 2026-05-28 | 项目脚手架、Pydantic v2 schemas、mock API、工具包装、规则解析、规划管道、CLI demo |
| MVP-1 | 2026-05-29 | OpenAI LLM 解析（结构化输出→json→规则回退）、FastAPI app |
| MVP-2 | 2026-05-29 | Streamlit UI（双后端 in-process/HTTP）、plan card、timeline、执行确认 |
| MVP-3 | 2026-06-01 | 备选方案、LLM source 追踪、UI 美化、环境诊断 |
| MVP-3.5 | 2026-06-02 | Plan revision loop（太远/换餐厅/换场地）、mock 数据扩展（12 venues/12 restaurants） |
| MVP-4 | 2026-06-02 | 多站点行程、位置锚点、丰富本地生活数据（优惠券/推荐菜/评价标签/营业时间/区域） |
| MVP-4.5 | 2026-06-02 | 日期时间解析、营业时间服务、票种 schema、revision scope、UI 完善、数据继续扩充（18 venues/15 restaurants） |

### 当前测试

**216 个测试通过（1 个 skipped）**

```bash
E:/miniforge/envs/agent/python.exe -m pytest tests/ -q
```

### 当前可运行命令

```bash
# CLI demo（fixture 场景）
E:/miniforge/envs/common/python.exe -m src.cli.main family
E:/miniforge/envs/common/python.exe -m src.cli.main friends
E:/miniforge/envs/common/python.exe -m src.cli.main "今天下午和老婆孩子出去玩"

# Streamlit UI（in-process 模式）
E:\miniforge\envs\common\Scripts\streamlit.exe run src/ui/app.py

# FastAPI 后端（HTTP 模式需同时启动）
E:/miniforge/envs/common/python.exe -m uvicorn src.api.app:app --reload

# 全量测试
E:/miniforge/envs/common/python.exe -m pytest tests/ -q
```

### 当前主要能力

- **意图解析**：LLM（OpenAI Structured Outputs → json_object）+ 规则 fallback；日期时间解析（明天/周X/N号/早上/晚上/待会→具体日期+时刻）；位置锚点提取
- **动态多站点行程**：最多 3 个活动站点（primary + light + secondary）+ 1-2 餐厅；时间预算驱动；保证 total_minutes ≤ 用户时长
- **营业时间**：`is_open_during`（支持跨午夜）；planner 生成 warning；ranker 施加 -0.35 惩罚
- **票种提醒**：`TicketOption` schema 含学生票/老年票/儿童票；venue card 展示
- **revision loop**：revision_scope（restaurant_only / venue_only / global）；partial re-plan 仅换餐厅或仅换场地
- **丰富本地数据**：18 个场馆、15 家餐厅；每个含 area/rating/review_count/specialty_tags/coupons/packages/营业时间/recommended_dishes
- **Streamlit UI**：意图面板（日期/时刻/时段/预算）、plan card（评分/理由/风险/费用/票种/营业时间）、timeline（图标/营业状态）、revision 表单、执行面板、分享消息
- **FastAPI**：`POST /api/plans/generate` / `POST /api/plans/revise` / `POST /api/plans/execute` / `GET /api/health`；两种后端模式（in-process / HTTP）

---

## 2. 硬约束

以下约束在 MVP-4.6 内必须遵守：

- 不切换 TypeScript / Next.js — 项目保持 Python only
- 不引入 SQLite / 数据库 — 所有数据保持 mock in-memory
- 不做登录/用户记忆 — 每次会话独立
- 不接真实地图 API — 使用 mock 距离数据
- 不做真实支付/预约 — MockAPI 仿真
- 不做执行后取消/改约 — 执行一次确认即终止
- 不破坏现有 216 个测试 — 所有新字段必须有默认值
- 自动测试不能依赖真实时间 — 使用 `_now` 注入
- Streamlit in-process 和 HTTP mode 都必须保留 — 两种后端同步更新
- 不做真正的 LLM 推理测试（不调 OpenAI API）— 使用 fixture 或 rule-based mock

---

## 3. 当前暴露的核心 Bug

### Bug A：明确要求的活动/地点不出现在 top 方案

**现象**："明天带孩子去动物园" → top 方案不是动物园（venue_014），可能是科学馆、亲子乐园。

**根因**：
1. LLM 路径（`_llm_to_intent`）从不调用 `_extract_requests()`，`requested_activities` 永远为空（只有 `activity_preferences`）
2. `explicit_bonus = +0.15` 不足以弥补距离惩罚：venue_014 距离 12km，max_km=6 → `distance_score = max(0, 1-(12/6-0.5)) = 0.0`；即使加 +0.15，总分仍远低于附近场馆

**预期行为**：用户点名的活动是目标不是偏好 → 动物园 feasible 时必须 top1；不可行时明确 warning 说明，不能静默换成其他

**关键文件**：`src/workflow/intent_parser.py:162-197`（`_llm_to_intent`）、`src/services/plan_ranker.py:130-141`（`explicit_bonus`）

---

### Bug B：营业时间冲突仍出现在 top 方案

**现象**："今天晚上带孩子玩" → 动物园（17:30 关）可能仍出现；top1 有红色营业状态

**根因**：
- 当前只有 -0.35 软惩罚，不是硬过滤
- `ItineraryPlan` 无 `feasible` 字段，无法在 API 层过滤
- top1 不允许有 opening hours 冲突（除非所有方案都不可行）

**期望修复**：
- 若活动时段与 venue open/close 有冲突，尝试将活动结束时间截断到 `close_time`
- 若截断后剩余可玩时间 < `venue.suggested_duration_min`，则该 venue 标为不可行
- 不可行的 venue 不进入最终推荐，换下一候选；仅当所有候选均不可行时才降级展示并附 warning
- `ItineraryPlan` 新增 `feasible: bool = True` 和 `infeasible_reasons: list[str] = []`

**关键文件**：`src/schemas/plan.py`、`src/workflow/planner.py:308-336`（开放时间检查块）、`src/workflow/planner.py:176-182`（generate_plans 返回）

---

### Bug C：目的地型活动（zoo/theme_park/大型景区）逻辑缺失

**现象**："去动物园" 被处理成普通半天活动，强行在旁边插入第二个娱乐场馆（board_game/茶馆）

**期望行为**：
- `zoo` / `theme_park` / 大型景区应作为目的地型（destination）活动，全程在园内
- 园内活动时间可跨多个 segment（游玩→园内午餐→继续游玩）
- 不强插第二个娱乐场所；优先使用园内/附近餐厅
- 如果是全天行程，园内/附近午餐 + 园外晚餐

**实现方向**：在 `venue.type` 中判断是否为目的地型（可用 flag `destination_type: bool = False`）；planner 对目的地型 venue 跳过 light stop / secondary venue 插入

**关键文件**：`src/schemas/venue.py`（新增 `is_destination: bool = False`）、`src/workflow/planner.py`（`_build_one_plan` 的 light/secondary 插入逻辑）

---

### Bug D：全天计划的用餐时间不合理

**现象**：14:00 出发的 8h 计划生成"午餐 XX"（在 16:xx 时间段吃"午餐"）；10:00 出发的计划有时不安排午餐

**根因**：`planner.py:248-252` 中 `if duration_type == "full_day"` 是纯结构判断，不检查 `intent.time`

**修复逻辑**：
```python
start_min = time_to_minutes(intent.time)
end_min = start_min + target_minutes
needs_lunch = start_min < 11 * 60  # 早于 11:00 出发才需要午餐
insert_meal_after_first = needs_lunch and len(restaurants) >= 2
```
- 出发 < 11:00 → 插入午餐 + 晚餐（两餐）
- 出发 11:00–14:00 → 只有午餐或晚餐（一餐）
- 出发 ≥ 17:00 → 只有晚餐（一餐）

**关键文件**：`src/workflow/planner.py:248-252`、`src/services/itinerary_builder.py`（`time_to_minutes` 已有）

---

### Bug E：预算偏好未真正影响方案排名

**现象**："便宜点" 后，top 方案可能仍是高价场馆；"贵点没事" 也没有匹配规则

**根因**：
- `plan_ranker.py` 无任何 `budget_preference` 引用
- `revision_parser.py:52` 高预算列表缺少 "贵点没事"、"贵点也行"、"贵一些没事"

**修复方向**：
- `revision_parser.py`：增加"贵点没事"等关键词 → `budget_preference = "high"`
- `plan_ranker.py`：`score_plan` 新增 `budget_preference: str = "medium"` 参数；低预算对便宜场馆/餐厅加分，对贵的扣分；高预算对高评分/体验感加分
- `rank_plans` 透传 `budget_preference`；planner + API + client 调用处同步更新
- UI：intent panel 显示预算偏好；alternatives 差异标签包含"更省钱"

**关键文件**：`src/workflow/revision_parser.py:52`、`src/services/plan_ranker.py:70-81`

---

### Bug F：plan.reasons 可能包含"多站点行程"

**现象**：多站点计划的 `reasons` 列表写入"多站点行程：XX → YY"，这是系统能力描述而非用户价值

**修复**：已在上一轮实现中删除，但缺少回归测试

**预期 reasons 来源**：用户需求匹配（评分/适合群体）、时间可行性、距离合理性、人群适配、预算/优惠、营业状态、风险规避

**关键文件**：`tests/test_planner.py`（新增断言 `"多站点" not in reason for reason in plan.reasons`）

---

### Bug G：tool duration 全为 0ms

**现象**：工具调用追踪中，所有 `elapsed_ms` 显示 0；UI 显示"0"而非"<1ms"

**根因**：`wrappers.py:33,46` 使用 `time.monotonic()`，Windows 下分辨率约 15ms；mock 调用 <1ms → 四舍五入后为 0

**修复**：
- `wrappers.py`：`time.monotonic()` → `time.perf_counter()`（分辨率 <100ns）
- `ui/app.py`：工具调用耗时列格式化为 `"<1ms"` 当 `elapsed_ms < 1`

**关键文件**：`src/tools/wrappers.py:33,46`、`src/ui/app.py`（trace 表格列）

---

### Bug H：缺少场馆/餐厅数据目录文档

**现象**：无法快速查阅所有 18 个场馆和 15 家餐厅的完整属性

**修复**：新建 `docs/local_life_catalog.md`，全中文，列出所有场馆和餐厅，字段统一，没有的写"无"或"[]"，不要英文 schema dump

---

### Bug I：用户说"不吃饭"时系统仍强制安排餐厅

**现象**："明天去动物园，不吃饭" → 方案仍包含餐厅预约、meal step、restaurant_id

**根因**：planner 始终搜索餐厅并插入 meal step；无 `meal_policy` 概念

**期望行为**：
- `meal_policy = "excluded"` → 不搜索餐厅、不插入 meal step、不执行餐厅预约、分享消息不写餐厅
- `meal_policy = "optional"` → 时间够才插入 light meal（如咖啡）
- `meal_policy = "required"` → 保持现有餐厅规划逻辑（默认）

---

## 4. MVP-4.6 推荐实现顺序

### Phase 1：数据目录文档（Bug H）

新建 `docs/local_life_catalog.md`：
- 全中文
- 列出全部 18 个场馆（id/名称/类型/区域/距离/营业时间/门票价格/评分/标签/室内/亮点）
- 列出全部 15 家餐厅（id/名称/区域/营业时间/人均/评分/标签/推荐菜/特色）
- 字段统一，没有的写"无"或"[]"

### Phase 2：meal_policy schema + intent_parser + planner 支持（Bug I）

`UserIntent` 新增：
```python
meal_policy: Literal["required", "optional", "excluded"] = "required"
```

intent_parser 解析规则（rule_based 路径 + `_extract_requests`）：
- 不吃饭 / 不用吃饭 / 不安排吃的 / 不要餐厅 / 饭我自己解决 / 不需要餐厅 → `excluded`
- 随便吃点 / 可吃可不吃 / 有合适的再吃 → `optional`
- 想吃日料 / 火锅 / 烛光晚餐 / 找家餐厅 / 吃顿饭（明确餐厅诉求）→ `required`（已有 requested_meals，保持默认 required）

planner 处理：
- `excluded`：跳过 restaurant 搜索，不插入 meal step；`restaurant_id = None`；`required_actions` 不含 `reserve_restaurant`
- `optional`：时间有余才尝试插入 light meal（咖啡/轻食）；没有余量则不插
- `required`：保持现有逻辑

执行层（executor/message_agent）：
- `excluded`：不调用 `reserve_restaurant` / `order_food`；share message 不写餐厅预约

UI：intent panel 显示餐饮策略标签（按需安排/可吃可不吃/不安排餐饮）

测试：
```python
def test_no_meal_policy_excludes_meal_steps():
    intent = parse_free_text("明天带孩子去动物园，不吃饭")
    assert intent.meal_policy == "excluded"
    plans = generate_plans(intent, TraceLog())
    for p in plans:
        assert all(s.step_type != "meal" for s in p.steps)
        assert p.restaurant_id is None
```

### Phase 3：明确目标活动保证（Bug A）

LLM 路径 fix（`intent_parser.py`，`_llm_to_intent`）：
```python
req_acts, req_meals, _ = _extract_requests(raw_input)
```
在返回前 merge 到 intent（`requested_activities` 合并而非覆盖）

Ranker fix（`plan_ranker.py`，`explicit_bonus` 块）：
- explicit match 时：`explicit_bonus = 0.30`（从 0.15 升至 0.30）
- 同时：`distance_score = max(distance_score, 0.50)`（防止 12km 场馆距离分为 0）

测试：
```python
def test_zoo_requested_top1_feasible():
    intent = parse_free_text("明天早上带孩子去动物园")  # 9:00 出发，动物园营业
    plans = generate_plans(intent, TraceLog())
    ranked = rank_plans(plans, intent.max_distance_km, intent.duration_hours, ...)
    assert ranked[0].venue_id == "venue_014"
```

### Phase 4：目的地型活动 + 就近餐饮处理（Bug C）

`src/schemas/venue.py` 新增 `is_destination: bool = False`；venue_014/013 设为 True

`planner.py`：对 `is_destination=True` 的 venue 跳过 light stop / secondary venue 插入逻辑；优先查找 `near_location=venue_id` 的餐厅（如 rest_016 动物园亲子餐厅）

### Phase 5：营业时间截断 + 硬不可行过滤（Bug B）

`src/schemas/plan.py`：新增 `feasible: bool = True`、`infeasible_reasons: list[str] = []`

`planner.py` `_build_one_plan`：
1. 计算 activity step 的 start/end
2. 若 end_time > venue.close_time：尝试截断到 close_time
3. 若截断后时长 < `venue.suggested_duration_min`：`plan.feasible = False`，记录 `infeasible_reasons`
4. `generate_plans` 返回前：优先返回 feasible 方案；全不可行时返回所有并附 warning

### Phase 6：全天计划用餐时间修复（Bug D）

`planner.py:248-252`（lunch 插入块）：替换为时间感知逻辑（见 Bug D 修复逻辑）

新增测试：
- 14:00 出发全天 → 无午餐 step
- 09:00 出发全天 → 有午餐 step（标题含"午餐"），有晚餐 step（标题含"晚餐"）

### Phase 7：预算偏好影响排名/理由/UI（Bug E）

按 Bug E 修复方向实现；UI alternatives 差异标签增加"更省钱"

### Phase 8：工具耗时格式化（Bug G）

`wrappers.py`：`time.monotonic()` → `time.perf_counter()`
`ui/app.py`：format `"<1ms"` when `elapsed_ms < 1`

### Phase 9：测试 + 文档更新（Bug F、回归测试）

- `tests/test_planner.py`：回归测试 `"多站点" not in reason`
- 更新 `docs/changelog.md`、`docs/project_status.md`
- 所有 Phase 1-8 新增测试，目标 >= 240 个测试通过

---

## 5. meal_policy 完整设计

### Schema（`src/schemas/user_intent.py`）

```python
meal_policy: Literal["required", "optional", "excluded"] = "required"
```

`UserIntent.extra="forbid"` → 字段必须写进类定义。

### 解析规则

**排除餐饮** → `excluded`：
- 关键词：不吃饭、不用吃饭、不安排吃的、不要餐厅、饭我自己解决、不需要餐厅、不用管吃、自己解决吃饭、不要安排餐厅

**随意餐饮** → `optional`：
- 关键词：随便吃点、可吃可不吃、有合适的再吃、吃不吃无所谓、不一定要吃、顺便吃点

**明确需要餐饮** → `required`（默认值）：
- 有 `requested_meals`（火锅/日料/烛光晚餐）→ required
- "找家餐厅"、"吃顿饭"、"去吃" → required

### Planner 处理

```python
if intent.meal_policy == "excluded":
    # 不搜索餐厅
    restaurant_slots = []
    # 不插入 meal step
    # restaurant_id = None
elif intent.meal_policy == "optional":
    # 尝试搜索，搜不到或时间不够则跳过
    ...
else:  # required
    # 保持现有逻辑（必须有餐厅，没有则跳过该 venue）
    ...
```

### 执行层

`excluded` 时，`required_actions` 不含 `reserve_restaurant` / `order_food`；share message 模板跳过餐厅信息段。

### UI

intent panel 新增一行：
- `🍽 餐饮：按需安排` / `可吃可不吃` / `不安排餐饮`

plan card：若 `meal_policy == "excluded"`，餐饮费用行显示"已按要求不安排餐饮"。

---

## 6. 新会话第一条 Prompt（可直接复制）

---

```
请先阅读 docs/handoff_mvp46_bugfix.md，了解项目当前状态和需要修复的 bug 列表（Bug A–I）。

然后完成以下工作：
1. 输出 MVP-4.6 实现计划（按 Phase 1–9 顺序），覆盖所有 9 个 bug
2. 每个 Phase 列出：要改的文件路径 + 函数名 + 具体改动说明 + 新增测试断言
3. 等我确认后，再按 Phase 顺序逐步实现，每个 Phase 完成后运行测试，通过后继续下一 Phase

约束：
- 不破坏现有 216 个测试
- 所有新字段必须有默认值
- 不引入 SQLite/数据库
- 不切换语言/框架
- 不接真实 API
- 自动测试不依赖真实时间（使用 _now 注入）

环境：
- Python: E:/miniforge/envs/common/python.exe
- 测试命令: E:/miniforge/envs/common/python.exe -m pytest tests/ -q
- Streamlit: E:/miniforge/envs/common/Scripts/streamlit.exe run src/ui/app.py
```

---
