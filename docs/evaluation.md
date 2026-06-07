# NativePlanning 评测框架

本文定义 NativePlanning 系统的 7 项质量指标和 8 个验收用例，用于评估规划 Agent 的可靠性和产品完整性。

---

## 评测指标

| # | 指标名称 | 定义 | 测量方式 | 目标 |
|---|---------|------|---------|------|
| 1 | Intent Accuracy（意图准确率） | 意图解析后，`scenario_type`、`group_size`、`time`、`meal_policy` 等关键字段正确率 | 单元测试断言字段值 | ≥ 90% |
| 2 | Top-1 Relevance（首选相关性） | 返回的第一个方案与用户核心诉求匹配（场景类型、距离、餐饮策略） | 人工抽查 + 测试断言 `plan.score > 0` | ≥ 85% |
| 3 | Feasibility（可行性 100%） | 最终方案不含营业时间冲突、座位不足等硬性约束违反 | `opening_fit == 1.0`，`plan.feasible == True` | 100% |
| 4 | Constraint Satisfaction（约束满足） | 硬约束（`hard_constraints`, `avoid_*`）全部被尊重 | `tests/test_robustness.py` | 100% |
| 5 | Revision Correctness（修改正确率） | 用户修改请求后，新方案正确反映修改意图（换餐厅/换场馆/调整距离） | `tests/test_revision.py` | ≥ 90% |
| 6 | Execution Completion（执行完成率） | `required_actions` 中每个动作都产生 ExecutionResult（success/failed/skipped 均计） | `tests/test_execution_polish.py` | 100% |
| 7 | Badcase@3（零 Badcase） | 3 个命名演示场景无系统性错误输出（餐厅错名/时间冲突/分享内容矛盾） | 见下方验收用例 | 0 |

---

## 验收用例

以下 8 个用例为系统验收的最低标准。每个用例对应一条确定性输入，预期行为如下。

### 用例 1：家庭下午公园+火锅（Happy Path）

**输入：** 今天下午，家庭场景，3人，含儿童，出发14:00，4小时，≤5km

**预期：**
- `scenario_type == "family"`，`plan_mode == "activity_first"`
- Top-1 方案包含 activity 步骤 + meal 步骤
- `plan.feasible == True`
- 执行后 share message 包含场馆名和餐厅名
- 不含营业时间冲突（`time_score > 0`）

**测试覆盖：** `tests/test_planner.py::test_family_afternoon_park_hotpot`

---

### 用例 2：情侣烛光西餐（浪漫场景）

**输入：** 今天晚上，情侣场景，2人，出发18:00，3小时，≤8km，偏好西餐

**预期：**
- `scenario_type == "couple"`
- Top-1 餐厅有 `specialty_tags` 含"浪漫"或"西餐"
- 分享消息使用情侣语气模板（`_COUPLE_TEMPLATE`）

**测试覆盖：** `tests/test_planner.py` couple 相关用例

---

### 用例 3：动物园早起+午餐（开园时间限制）

**输入：** 家庭场景，4人，含儿童，出发09:00，5小时，请求动物园

**预期：**
- 方案中动物园步骤的 `start_time` ≥ 动物园 `open_time`
- 若开园冲突，约束修复器扩大时间窗口或切换场馆
- `plan.feasible == True`

**测试覆盖：** `tests/test_opening_hours.py`

---

### 用例 4：看展+日料（博物馆/展览 + 特定菜系）

**输入：** 朋友场景，4人，出发13:00，4小时，请求展览，偏好日料

**预期：**
- Top-1 方案 venue 含博物馆/展览类场馆
- restaurant `cuisine_type` 或 `specialty_tags` 含日料关键词
- `meal_policy == "required"`

**测试覆盖：** `tests/test_planner.py` cuisine_type 相关用例

---

### 用例 5：朋友火锅无位→切换（Fallback 一致性）

**输入：** 朋友场景，6人，点名火锅，但目标餐厅无座（`available_seats < 6`）

**预期：**
- 约束修复触发，切换至另一家有座位的餐厅
- share message 正文（备注前）不含旧餐厅名
- share message 含 `"已切换至"` 说明
- `plan.warnings` 含切换说明

**测试覆盖：** `tests/test_execution_polish.py::test_fallback_share_consistent_with_current_plan`

---

### 用例 6：不吃饭家庭游（no-meal）

**输入：** 家庭场景，3人，`meal_policy == "excluded"`，出发14:00，3小时

**预期：**
- 方案不含 meal 步骤
- `plan.restaurant_id is None`
- share message 不含 `{"餐厅", "用餐", "预约餐厅", "吃饭"}`
- `required_actions` 不含 `"reserve_restaurant"`
- 执行结果为空列表

**测试覆盖：** `tests/test_execution_polish.py::test_no_meal_share_excludes_restaurant_keywords`

---

### 用例 7：修改方案——换餐厅

**输入：** 已生成方案后，用户输入"想换家餐厅"或"想吃日料"

**预期：**
- 修改后方案保留原场馆
- 餐厅更换为符合新需求的餐厅
- 新方案 `plan.restaurant_id` 不同于原方案
- share message 引用新餐厅名称

**测试覆盖：** `tests/test_revision.py::test_revise_restaurant`

---

### 用例 8：修改方案——太远了

**输入：** 已生成方案后，用户输入"太远了"或"近一点"

**预期：**
- 修改后方案 `max_distance_km` 缩小（或等效地选择距离更近的场馆）
- 新方案 `venue.distance_km` < 原方案场馆距离
- 不破坏餐饮策略和时间安排

**测试覆盖：** `tests/test_revision.py::test_revise_too_far`

---

## 运行验收用例

```bash
# 全量测试（必须保持 321+ 通过）
E:/miniforge/envs/common/python.exe -m pytest tests/ -q

# 仅执行相关分组
E:/miniforge/envs/common/python.exe -m pytest tests/test_execution_polish.py tests/test_opening_hours.py tests/test_revision.py -v
```

## 与代码的对应关系

| 评测组件 | 代码位置 |
|---------|---------|
| 意图解析 | `src/workflow/intent_parser.py` |
| 规划 + 排序 | `src/workflow/planner.py`, `src/services/plan_ranker.py` |
| 约束修复 | `src/workflow/constraint_solver.py` |
| 执行器 | `src/workflow/executor.py` |
| 分享消息 | `src/workflow/message_agent.py` |
| 评测测试 | `tests/` |
