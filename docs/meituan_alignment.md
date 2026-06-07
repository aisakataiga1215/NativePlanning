# Meituan 本地生活技术对齐

本文记录 NativePlanning 与美团本地生活搜索推荐核心技术思路的对齐关系。

---

## 1. GENE 本地生活需求图谱对齐

GENE（Goals, Environment, Needs, Expectations）是美团本地生活需求理解的核心框架，将用户需求拆解为 8 个维度。

| GENE 维度 | UserIntent 字段 | Pipeline 阶段 | UI 展示 |
|-----------|----------------|--------------|---------|
| 场景需求 | `scenario_type`, `plan_mode` | 意图解析 | 家庭 · 活动优先 |
| 人物要素 | `group_size`, `participants[].age_group` | 意图解析 | 3人 · 成人×2 老人×1 |
| 时间要素 | `date`, `weekday`, `time`, `time_period`, `duration_hours` | 意图解析 + 排序 | 今天 周日 下午 · 14:00出发 · 4h |
| 空间要素 | `location_anchor`, `max_distance_km` | 候选召回过滤 | 当前位置 ≤5km |
| 具象需求 | `requested_activities`, `activity_preferences`, `requested_places` | 候选召回权重 | 公园 · 散步 |
| 餐饮策略 | `meal_policy`, `requested_meals`, `meal_preferences` | 规划策略选择 | 需要餐饮 · 火锅 |
| 硬约束 | `hard_constraints`, `avoid_venue_ids`, `avoid_restaurant_ids` | 候选过滤 | 不要太远 · 避开2家场馆 |
| 软偏好 | `soft_preferences`, `budget_preference` | 排序加分 | 亲子 · 适中预算 |

**解析路径：**
- `source == "llm"` → LLM 解析（`src/workflow/intent_parser.py:parse_intent_llm`）
- `source == "rule_based"` → 规则解析（`src/workflow/intent_parser.py:parse_intent_rule`）

---

## 2. 美团搜索推荐链路对齐

美团本地生活推荐遵循「召回 → 粗排 → 精排 → 重排」的五阶段链路。本项目实现了等价的五阶段规划链路：

| 美团链路阶段 | 本项目等价实现 | 关键工具/函数 | 代码位置 |
|------------|--------------|-------------|---------|
| 需求理解 | 意图解析 | `parse_intent_llm` / `parse_intent_rule` | `src/workflow/intent_parser.py` |
| 候选召回 | 场馆/餐厅搜索 | `search_venues`, `search_restaurants`, `*_fallback`, `*_wide` | `src/mock_api/venues.py`, `src/mock_api/restaurants.py` |
| 可行性过滤 | 营业时间 + 库存检查 | `check_venue_availability`, `check_restaurant_availability` | `src/mock_api/venues.py`, `src/workflow/constraint_solver.py` |
| 多维排序 | 综合打分 | `rank_plans(plans, intent)` → `ScoreBreakdown` | `src/services/plan_ranker.py` |
| 生成执行计划 | 方案构建 + 步骤分配 | `generate_plans`, `build_itinerary_timeline` | `src/workflow/planner.py`, `src/services/itinerary_builder.py` |

**Fallback 机制：** 当召回结果为空或可行性检查失败时，系统自动触发：
- `search_venues_alt` / `search_restaurants_alt_base` — 扩大范围重搜
- `validate_and_repair` — 约束修复（切换餐厅/扩大半径）

---

## 3. 商品知识图谱推荐理由/特色标签对齐

美团商品知识图谱为每个 POI 提供结构化标签，驱动推荐理由生成。本项目 Mock 数据包含等价字段：

### 场馆字段 → 推荐理由

| Mock 字段 | 类型 | 推荐理由示例 |
|----------|------|------------|
| `rating` + `review_count` | float + int | `⭐ 城市湖边公园 4.6分 (1243评)` |
| `distance_km` + `open_time/close_time` | float + str | `📍 距离 2.3km · 营业 08:00–21:00` |
| `queue_minutes` | int | `⏳ 预计排队 15 分钟，建议提前` |
| `positive_review_tags` | list[str] | `👍 亲子友好 · 风景优美 · 设施完善` |
| `specialty_tags` | list[str] | 排序权重 + 标签展示 |
| `ticket_options[].price` | float | 成本估算 |
| `requires_ticket` | bool | 决定是否触发 `book_venue` |

### 餐厅字段 → 推荐理由

| Mock 字段 | 类型 | 推荐理由示例 |
|----------|------|------------|
| `rating` + `review_count` | float + int | `⭐ 老街麻辣火锅 4.7分 (2891评)` |
| `avg_price_per_person` + `open_time/close_time` | float + str | `💰 人均约 ¥68 · 营业 11:00–22:00` |
| `queue_minutes` | int | `⏳ 排队约 20 分钟` |
| `positive_review_tags` | list[str] | `👍 锅底鲜美 · 食材新鲜 · 服务热情` |
| `recommended_dishes` | list[str] | `🥢 推荐：毛肚 · 鸭肠` |
| `reservation_available` | bool | 决定是否触发 `reserve_restaurant` |

**实现位置：** `src/workflow/planner.py:_build_venue_reasons`, `_build_meal_only_reasons`

---

## 4. Badcase@3 评测思路

美团质量评测使用 Badcase 分析识别系统性缺陷。本项目定义 3 类关键 Badcase：

### Badcase 1：餐厅切换后分享消息仍提旧名

**描述：** 火锅无位触发切换后，分享消息正文仍提及被替换的餐厅名称，导致用户收到错误的行程信息。

**检测方法：** `tests/test_execution_polish.py::test_fallback_share_consistent_with_current_plan`

**覆盖：** 断言 `main_body = msg.split("\n备注：")[0]` 中不含旧餐厅名，且 `"已切换至" in msg`。

### Badcase 2：营业时间冲突方案仍为 Top-1

**描述：** 规划返回的首选方案包含活动/餐厅在用户出发时段未开门的步骤，导致方案不可执行。

**检测方法：** `tests/test_opening_hours.py` — 断言 `plan.feasible == True` 且 `score_breakdown.time_score == 1.0`。

**覆盖：** `src/workflow/constraint_solver.py:validate_and_repair` + `src/services/plan_ranker.py:opening_fit`。

### Badcase 3：no-meal 方案分享消息含餐饮词汇

**描述：** 用户明确选择不安排餐饮，但分享消息仍出现"餐厅"、"吃饭"等词汇，误导用户和家人。

**检测方法：** `tests/test_execution_polish.py::test_no_meal_share_excludes_restaurant_keywords`

**覆盖：** 断言消息不含 `{"餐厅", "用餐", "预约餐厅", "吃饭"}`，通过 no-meal 分支模板实现。

---

## 5. VitaBench 生活场景 Agent 对齐

VitaBench 定义了 5 类生活场景 Agent 任务类型。本项目演示场景覆盖对应类型：

| VitaBench 任务类型 | 描述 | 本项目对应演示场景 |
|------------------|------|----------------|
| 活动规划 | 用户给出时间/人员，Agent 自主安排行程 | 家庭下午公园+火锅（happy path） |
| 餐饮预约 | 搜索餐厅 → 检查可用性 → 完成预约 | 仅餐饮（meal_only）场景 |
| 异常处理 | 遇到约束冲突，Agent 自动修复方案 | 朋友火锅无位→切换（fallback） |
| 多轮修改 | 用户在已有方案基础上提出修改意见 | 修改方案：换餐厅 / 太远了 |
| 执行确认 | 方案确认后执行预订并生成分享消息 | 所有场景的执行阶段 |

**关键对齐点：** VitaBench 强调 Agent 的「工具调用链可追踪性」，本项目通过 `TraceLog` + UI 工具调用追踪面板实现全程可见。
