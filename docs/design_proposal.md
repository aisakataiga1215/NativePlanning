# 设计思路 — NativePlanning

## 1. 问题定义

用户发出一条自然语言请求（如"今天下午带孩子出去玩几个小时"），系统需要：

1. 理解用户意图（人群、时长、餐饮偏好、距离要求）
2. 从 Mock 数据中搜索、过滤、排序候选场馆和餐厅
3. 生成一个 4-6 小时可执行方案（含时间轴、预订操作）
4. 处理异常（无票/满座/时间冲突）并自动修复

难点不是推荐列表，而是**从搜索到可执行计划**的完整链路。

---

## 2. 整体架构

```
用户输入
  ↓
意图解析（LLM → json_object → rule-based fallback）
  ↓
规划器（Planner）
  ├─ 场馆候选召回
  ├─ 餐厅候选召回
  ├─ 可行性过滤（营业时间 / 库存 / 距离）
  └─ 多维排序（PlanRanker）
  ↓
约束修复（ConstraintSolver）
  ↓
方案展示 + 用户确认
  ↓
执行（Executor）—— 预订 / 下单 / 分享文案
```

所有 MockAPI 调用均通过 ToolWrapper 记录，支持追踪展示。

---

## 3. 关键设计决策

### 3.1 双路径意图解析

- **LLM 路径**：调用 OpenAI-compatible API，输出结构化 JSON（group_type、duration、meal_policy、location_hint 等）
- **Rule-based 路径**：基于关键词匹配，无 API Key 时自动降级
- **价值**：Demo 在无网络/无 Key 环境下依然可完整运行

### 3.2 Planning 不是搜索

规划器不返回推荐列表，而是：

1. 按用户约束（人群类型、时段、距离）召回候选
2. 实时检查营业时间和库存（hard gate）
3. 将活动 + 餐饮组合成时间轴（含缓冲时间）
4. PlanRanker 按 5 个维度打分（亲子/氛围/距离/价格/新颖度）并选出最优

这种设计使方案"开箱即执行"，无需用户二次筛选。

### 3.3 多场景支持

| 场景 | 处理方式 |
|------|---------|
| no-meal（不吃饭） | `meal_policy=excluded`，跳过餐厅搜索，分享消息剔除餐饮词汇 |
| meal-only（只吃饭） | `plan_mode=meal_only`，仅生成餐厅方案 |
| 开园等待 | ConstraintSolver 检测 venue open_time，推迟活动入场时间 |
| revision（太远了/换餐厅） | 保留未变更段，只替换有问题的部分 |

### 3.4 异常自动修复

三类异常各有独立 fallback 策略：

- **餐厅满座** → 在同类型中换一家，保留活动段
- **场馆无票** → 在同类型中换场馆，保留餐厅段
- **时间冲突** → 先删可选项，再压缩缓冲时间

修复后方案需重新通过 feasibility check，确保可执行性。

### 3.5 可观测性

每个 MockAPI 调用通过 `ToolTrace` 记录（工具名、参数、响应、耗时），在 UI 中可折叠展示。这使 Demo 的规划过程透明，适合评委审阅。

---

## 4. 与美团本地生活的对齐

| 美团能力 | 本项目映射 |
|---------|-----------|
| GENE 意图理解 | IntentParser（group/environment/need/emotion） |
| 场景化召回 | Planner 候选召回 + 语义 fallback |
| 实时可用性 | MockAPI availability check |
| 一站式预订 | Executor（book_venue + reserve_restaurant） |
| 分享传播 | MessageAgent 生成中文分享文案 |

---

## 5. 技术栈选择

| 层 | 技术 | 理由 |
|----|------|------|
| UI | Streamlit | 快速原型，评委友好 |
| 后端 | FastAPI | 可选分离部署，支持 HTTP 模式 |
| 数据层 | 纯内存 MockAPI | 无外部依赖，演示稳定 |
| LLM | OpenAI-compatible | 兼容 DeepSeek 等国内 API |
| 数据验证 | Pydantic v2 | 类型安全，schema 集中管理 |

---

## 6. 局限与展望

**当前局限：**
- MockAPI 数据固定，无真实地图/位置计算
- 仅支持单用户 session，无持久化

**下一步（P1）：**
- 真实高德/百度地图 API 接入（距离计算）
- SQLite 持久化历史方案
- Next.js + TypeScript 前端（更好的移动端体验）
