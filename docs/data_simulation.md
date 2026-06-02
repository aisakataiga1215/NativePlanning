# 数据模拟说明（Data Simulation）

> 本文档面向赛事评审，说明 NativePlanning（本地生活规划与执行 Agent）的模拟数据策略。
>
> 相关文档：[mock_api_design.md](mock_api_design.md)（接口规格） · [architecture.md](architecture.md)（系统结构） · [planning_strategy.md](planning_strategy.md)（规划逻辑）

---

## 1. 为什么使用 MockAPI（数据说明）

本赛题未提供真实的本地生活业务接口（场馆库存、餐厅座位、票务、预订与下单等），也未授权接入真实平台数据。为了保证 Agent 能在评审环境中完整跑通"规划 → 校验 → 确认 → 执行"全链路，团队构建了一套 MockAPI 与配套数据 fixture。

使用 MockAPI 的核心原因：

1. **赛题边界**：赛题未提供真实业务 API 和真实数据，团队必须自行模拟才能验证 Agent 决策与工具调用的完整闭环。
2. **链路完整性**：模拟数据让 Agent 的意图解析、计划生成、可用性校验、异常修复、确认与执行的每个环节都能被真实触发，而不是停留在 prompt 演示。
3. **可离线、可复现**：Demo 在评审现场必须稳定运行，不依赖外部网络与第三方 API，多次运行结果一致。
4. **可观测**：每一次工具调用都会被 TraceLog 完整记录，便于评审环节中讲解 Agent 的实际行为。

---

## 2. Mock 数据覆盖范围

Mock 数据位于 `src/mock_api/`，由 `venues.py`、`restaurants.py`、`booking.py`、`orders.py` 模块提供，数据 fixture 当前正从 6/6/4 扩展到 12/12/4。

### 2.1 场馆（Venue）：12 条

覆盖的场馆类型：

```text
kids_playground   亲子游乐
lake_park         湖边公园
museum            博物馆
garden            植物园 / 主题花园
art_center        艺术中心
climbing          攀岩 / 运动馆
board_game        桌游吧
tea_house         茶馆 / 茶空间
citywalk          城市漫步路线
escape_room       密室
movie             影院
kids_lab          儿童科学实验室
```

关键字段：

| 字段 | 含义 |
|------|------|
| `name` / `type` / `tags` | 场馆名称、类型与画像标签 |
| `distance_km` | 距离用户家的公里数 |
| `duration_minutes` | 建议游玩时长 |
| `suitable_age_min` / `suitable_age_max` | 适合年龄区间 |
| `price_per_person` | 人均价格 |
| `indoor` | 是否室内（影响天气与体力维度） |
| `walk_intensity` | 步行强度（low / medium / high） |
| `noise_level` | 噪音水平 |
| `queue_minutes` | 预计排队时长 |
| `available_tickets` | 可售票数（**0 = 售罄**） |

### 2.2 餐厅（Restaurant）：12 条

覆盖的菜系：

```text
healthy   轻食 / 健康
japanese  日料
hotpot    火锅
chinese   中餐
western   西餐
cafe      咖啡
bbq       烧烤
noodles   面食
```

关键字段：

| 字段 | 含义 |
|------|------|
| `name` / `tags` | 餐厅名称与画像标签 |
| `avg_price_per_person` | 人均消费 |
| `queue_minutes` | 排队时长 |
| `noise_level` | 噪音水平（影响场景适配） |
| `has_kids_menu` | 是否有儿童餐 |
| `reservation_available` | 是否支持预约 |
| `available_seats` | 可用座位数（**0 = 无座**） |

### 2.3 优惠券（Coupon）：4 条

覆盖 venue 与 restaurant 两类目标对象，用于在执行阶段拼接到分享文案与订单中。

### 2.4 可用性控制

可用性完全由数据字段控制，无任何随机性：

- `available_tickets = 0` → 触发"无票"异常分支
- `available_seats = 0` → 触发"无座"异常分支

这一设计保证了 Demo 的失败路径可在评审现场稳定复现。

---

## 3. 场景覆盖矩阵

Mock 数据围绕真实本地生活场景设计，覆盖五类典型人群与对应的硬约束、软约束。

| 场景 | 典型场馆类型 | 典型餐厅类型 | 测试的约束维度 |
|------|-------------|-------------|----------------|
| **family / parent_child**（家庭带娃） | kids_playground · kids_lab · lake_park · garden | healthy · chinese（带儿童餐） | 儿童友好 · 距离近 · 步行强度低 · 噪音低 · 健康饮食 |
| **couple**（情侣 / 夫妻） | garden · art_center · museum · tea_house · movie | japanese · western · cafe | 氛围 · 摄影友好 · 安静 · 预算适中 |
| **friends**（朋友聚会） | board_game · escape_room · climbing · citywalk | hotpot · bbq · noodles | 社交互动 · 群体氛围 · 弹性活动 · 排队时长 |
| **colleagues**（同事团建） | citywalk · climbing · board_game · museum | hotpot · chinese · western | 体力均衡 · 群体口味平衡 · 价格合理 |
| **elderly**（带长辈） | lake_park · garden · museum · tea_house | chinese · healthy · noodles | 步行强度低 · 噪音低 · 健康饮食 · 短距离 |

每个场景都至少覆盖一条"快乐路径"（happy path）与一条异常分支，用于演示 Agent 在不同人群下的差异化决策。

---

## 4. 异常数据设计

异常场景由 fixture 中的特定字段触发，Planner 与 ExceptionHandler 会自动识别并执行修复策略。

### 4.1 无座（no-seats）

**触发数据：**

```json
{
  "id": "rest_003",
  "name": "老街麻辣火锅",
  "available_seats": 0
}
```

**触发机制：** 工具 `check_restaurant_availability` 返回 `available_seats = 0`。

**自动修复路径：**

1. ExceptionHandler 标记当前餐厅不可用
2. Planner 在同标签集合内重选餐厅（保持菜系、价格、噪音维度的画像匹配）
3. 仅替换餐厅节点，活动主线不重新规划
4. TraceLog 记录原餐厅与替换餐厅，供评审讲解

### 4.2 无票（no-tickets）

**触发数据：**

```json
{
  "id": "venue_001",
  "name": "森林亲子乐园",
  "available_tickets": 0
}
```

**触发机制：** 工具 `check_venue_availability` 返回 `available_tickets = 0`。

**自动修复路径：**

1. ExceptionHandler 标记该场馆当前时段不可用
2. Planner 先尝试相邻时段，再尝试同类型替代场馆
3. 替换后重新计算 timeline（出发时间 · 通勤 · buffer）
4. 餐厅与执行节点根据新的活动时间二次校准

### 4.3 时间冲突（time-conflict）

**触发数据：** fixture 注入相邻步骤之间存在时间重叠，例如活动结束时间晚于餐厅预约时间。

**触发机制：** Planner 在生成 timeline 后做一致性校验时检测到 overlap。

**自动修复路径：**

1. 优先压缩可选活动（optional step）
2. 必要时减少 venue duration 或后移餐厅时间
3. 仅在不得已时替换核心活动
4. 始终保证总时长在 4–6 小时窗口内

---

## 5. MockAPI 的价值

MockAPI 不只是"占位数据"，它直接支撑了本项目的四项工程价值：

### 5.1 稳定 demo

所有数据本地化，无任何外部依赖。多次运行结果完全一致，评审现场不会因为网络或第三方服务波动而出现意外。

### 5.2 可复现测试

项目已构建 **91 个自动化测试**（unit · integration · e2e），全部基于 MockAPI 跑通，**无需 API KEY、无需外部网络**。每一次修改都可以快速回归整条链路。

### 5.3 支撑 tool trace

每一次工具调用都会生成结构化 trace 记录：

```json
{
  "tool_name": "check_restaurant_availability",
  "status": "success",
  "output": { "available_seats": 0, "status": "full" },
  "elapsed_ms": 118
}
```

trace 字段包含：`tool_name` · `status` · `output` · `elapsed_ms`，可在 UI 或 CLI 中实时展示，便于评审环节解释 Agent 的每一步决策依据。

### 5.4 支撑 fallback 演示

异常 fixture（无座 / 无票 / 时间冲突）让"规划异常自动修复"这一核心能力可以被现场稳定演示。评审看到的不仅是一个"happy path 一次跑通"，而是 Agent 真正在面对真实业务异常时的应对路径。

---

详细接口与数据模型见 [docs/mock_api_design.md](mock_api_design.md)；规划与异常修复策略见 [docs/planning_strategy.md](planning_strategy.md)。
