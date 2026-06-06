# Demo Script — NativePlanning

## 演示前检查清单（重要）

```bash
# 确认 NATIVE_PLANNING_API_URL 未设置（否则 UI 会尝试连接不存在的后端）
echo %NATIVE_PLANNING_API_URL%   # Windows — 应为空
echo $NATIVE_PLANNING_API_URL    # macOS/Linux — 应为空

# 如已设置，清除它（Windows：设置为空字符串，UI 的 if url: 判断等价于未设置）
set NATIVE_PLANNING_API_URL=     # Windows
unset NATIVE_PLANNING_API_URL    # macOS/Linux
```

---

## 环境准备

```bash
cd E:\git-clone\NativePlanning
```

如需 LLM 意图解析（可选），在 `.env` 中设置：
```
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.deepseek.com/   # 兼容 DeepSeek
OPENAI_MODEL=deepseek-chat
```
不设置时自动退回规则解析，全部功能仍可演示。

---

## 1. CLI Demo

每条命令独立可运行，无需额外配置：

```bash
E:\miniforge\envs\agent\python.exe -m src.cli.main family
E:\miniforge\envs\agent\python.exe -m src.cli.main friends
E:\miniforge\envs\agent\python.exe -m src.cli.main failure-no-seats
E:\miniforge\envs\agent\python.exe -m src.cli.main failure-no-tickets
E:\miniforge\envs\agent\python.exe -m src.cli.main failure-time-conflict
```

**自由文本（规则解析，无需 API Key）：**
```bash
E:\miniforge\envs\agent\python.exe -m src.cli.main 明天早上带孩子去动物园
E:\miniforge\envs\agent\python.exe -m src.cli.main 今天晚上带孩子出去玩
E:\miniforge\envs\agent\python.exe -m src.cli.main 待会和老婆去吃烛光晚餐
```

---

## 2. Streamlit UI — In-Process 模式（默认）

```bash
E:\miniforge\envs\agent\Scripts\streamlit.exe run src/ui/app.py
# 浏览器打开 http://localhost:8501
```

演示流程：
1. 输入框已预填"今天下午想和老婆孩子出去玩几个小时，别离家太远"
2. 点击 **生成计划** → 等待 1-2 秒
3. 看：意图解析面板 — 场景/人数/时长/最远距离、`📅 日期 周X · 时段 出发 HH:MM`、`💰 预算偏好`；`[rule-based]`/`[LLM]` 徽章
4. 点击 **🔍 调试信息** expander 查看完整 intent JSON（revision_scope 等内部字段在此可见）
5. 看：**方案选择器**（若有备选方案）— 最多 3 个候选，可点击切换
6. 看：推荐计划卡片（综合评分、理由、风险、预估费用）
7. 看：场馆卡片 — `🕐 营业时间`、`⏱ 建议时长`、票种列表（成人票/学生票/老年票…）
8. 看：餐厅卡片 — `🕐 营业时间`、`⏳ 排队约 N 分钟`
9. 看：时间线表格 — `🚗/🎯/🍽/🏠` 步骤图标、`营业` 列（🟢/🔴）
10. 展开 **工具调用追踪**：查看每个 tool 的状态、摘要、耗时
11. 在调整意见框输入"换个餐厅"，点击 **调整方案** — 观察 venue 不变、只换了餐厅
12. 点击 **确认并执行**
13. 看：执行结果（已购票 / 已预约，含 booking_id）
14. 看：分享消息（点击右上角图标一键复制）
15. 点击 **🔄**（右上角）重新开始

也可输入：
- `family` / `friends` → 直接走 fixture 场景
- `failure-no-seats` → 演示餐厅无位自动替换
- `failure-no-tickets` → 演示场馆无票自动替换
- `failure-time-conflict` → 演示时间冲突自动修复

---

## 3. Streamlit UI — HTTP 模式（FastAPI 后端）

**终端 1**（启动 API 服务器）：
```bash
cd E:\git-clone\NativePlanning
E:\miniforge\envs\agent\python.exe -m uvicorn src.api.app:app --reload --port 8000
# 等待出现：Uvicorn running on http://127.0.0.1:8000
```

**终端 2**（启动 UI，指向 HTTP 后端）：
```bash
cd E:\git-clone\NativePlanning
set NATIVE_PLANNING_API_URL=http://localhost:8000   # Windows
E:\miniforge\envs\agent\Scripts\streamlit.exe run src/ui/app.py
```

UI 标题下方会显示"后端：HTTP → http://localhost:8000"，行为与 in-process 模式完全一致。

---

## 4. FastAPI 裸接口（可选）

```bash
# 生成计划
curl -X POST http://localhost:8000/api/plans/generate \
  -H "Content-Type: application/json" \
  -d '{"user_input": "family"}' | python -m json.tool

# 健康检查
curl http://localhost:8000/api/health
```

---

## 5. 测试套件

```bash
E:\miniforge\envs\agent\python.exe -m pytest tests/ -q
# 期望：216 passed, 1 skipped in ~1s（无 OPENAI_API_KEY 亦可通过）
```

---

## 6. 评委重点关注

### 日期/时间自然语言解析（MVP-4.5 亮点）

意图解析面板中的 `📅` 行显示解析后的日期、星期、时段和出发时间。

演示方法：
```
明天早上带孩子去动物园
```
应看到：`📅 2026-06-03 周三 · 上午 出发 09:00`，意图面板 `[rule-based]` 模式下依然正确。

时段优先于活动名称：
```
待会和老婆去吃烛光晚餐
```
应看到：`📅 ... · 待会 出发 HH:30`（出发时间 = now+30 min）。"烛光晚餐"只影响餐厅偏好，不影响时段。

### 营业时间过滤（MVP-4.5 亮点）

出发时间与场馆营业时间冲突时，时间线的 `营业` 列显示 🔴；ranker 施加 −0.35 惩罚，开门的场馆优先排名。

演示方法：
```
今天晚上带孩子出去玩
```
动物园（城郊动物园，17:30 关）应被 商场亲子乐园（22:00 关）替代或降权；
时间线中应看到 🟢（在营业时间内的场馆/餐厅）。

如果动物园出现在计划中，场馆卡片上方会显示 ⚠️ warning："城郊动物园在游玩时段 XX:XX–XX:XX 内未营业"。

### 修订范围调度（MVP-4.5 亮点）

"换个餐厅" / "想吃日料" 等以餐饮为主的调整只重搜餐厅，不改变场馆；
"换个场地" / "想看展览" 等以活动为主的调整只重搜场馆，不改变餐厅。

演示方法：
1. 生成一个计划，记录场馆名称和餐厅名称
2. 在调整意见框输入 **"换个餐厅"**，点击调整方案
3. 验证：场馆名称不变，餐厅名称变了
4. 再输入 **"换个场地"**，点击调整方案
5. 验证：餐厅名称不变，场馆名称变了

全局约束（太远了/太贵了/不想排队）不设置 scope，走全量重排。

### 票种与证件提醒（MVP-4.5 亮点）

场馆卡片中显示票种列表（成人票 / 学生票 / 老年票 / 儿童票）及对应备注。

演示方法：
```
明天早上带孩子去动物园，不限距离
```
动物园（venue_014）场馆卡片应显示：
- 成人票: ¥80 — 需出示有效证件
- 学生票: ¥40 — 需出示学生证
- 老年票: ¥40 — 60岁以上，需出示身份证
- 儿童票: ¥0 — 1.2m以下免票

### 备选方案选择器（MVP-3 亮点）

生成计划后，若 Planner 产出 2-3 个候选，页面会显示 **方案选择器**（横排 radio）。
切换到方案 2 / 方案 3 后点击"确认并执行"，执行的是所选方案，而非默认方案。

### 动态多站点行程（MVP-4 亮点）

全天模式（时长 ≥ 7h）下，Planner 会根据剩余时间预算自动插入 light stop（茶馆/citywalk），
或在时间宽裕时增加第二活动站点。

演示方法：
```
今天带家人逛一整天，上午下午各玩一个地方
```
时间线中应出现 3–4 个非交通站点，且 `total_duration_minutes` ≤ `duration_hours × 60`。

### 位置锚点（MVP-4 亮点）

演示方法：
```
先去芳华街逛逛，然后找个好餐厅
```
意图面板中应出现 **📍 位置锚点：芳华街**，推荐场馆 area 应为芳华街或相邻区域。

### 丰富本地数据展示（MVP-4 亮点）

计划卡片中应显示：
- **推荐菜**：如"龙虾拼盘 · 黑椒牛柳 · 招牌焦糖蛋糕"
- **好评标签**：绿色 chip，如 `` `服务热情` `` `` `出品稳定` ``
- **差评风险**：如"⚠️ 风险：周末排队 / 上菜慢"
- **优惠券**：绿色 success box，如"🎫 立减20元"
- **营业时间 + 排队时间**：如"🕐 10:30 – 21:00" + "⏳ 排队约 15 分钟"

### LLM vs 规则解析徽章

- 意图解析面板标题右侧显示 `` `[LLM]` `` 或 `` `[rule-based]` ``，反映实际运行路径
- 页眉 caption 同步显示 `openai=✓/✗` 和 `key=✓/✗`
- **🔍 调试信息** expander 展示完整 intent JSON（含 `weekday`/`time_period`/`revision_scope`）

### 工具调用 Trace

展开 **工具调用追踪** 后，应能看到：

| 工具 | 说明 |
|---|---|
| `search_venues` | 按场景偏好搜索场馆 |
| `check_venue_availability` | 检查场馆余票 |
| `search_restaurants` | 搜索餐厅 |
| `check_restaurant_availability` | 检查餐厅座位 |
| `book_venue` | 购票（执行阶段） |
| `reserve_restaurant` | 预约餐厅（执行阶段） |

失败场景中还会出现 `fallback_venue` / `fallback_restaurant`，说明系统已自动修复。

### 执行结果与分享消息

- 执行结果表应包含 `booking_id` / `rsv_XXXXXX` 确认号
- 分享消息应为完整中文短句（≥ 20 字），可直接复制发给家人/朋友

### 异常处理

运行 `failure-*` 场景时，计划卡片上方会出现黄色警告条，
说明"原餐厅/场馆已不可用，已替换为 XX"，时间线仍然完整可执行。

---

## 附：手动 LLM 验证（不进入自动测试）

以下命令需要 `OPENAI_API_KEY`（`.env` 已配置时自动生效）：

```bash
# LLM 意图解析路径（应看到 [LLM] 徽章）
E:\miniforge\envs\agent\python.exe -m src.cli.main 今天下午想和三个朋友出去玩，拍拍照顺便吃个好的
```


## 演示前检查清单（重要）

```bash
# 确认 NATIVE_PLANNING_API_URL 未设置（否则 UI 会尝试连接不存在的后端）
echo %NATIVE_PLANNING_API_URL%   # Windows — 应为空
echo $NATIVE_PLANNING_API_URL    # macOS/Linux — 应为空

# 如已设置，清除它（Windows：设置为空字符串，UI 的 if url: 判断等价于未设置）
set NATIVE_PLANNING_API_URL=     # Windows
unset NATIVE_PLANNING_API_URL    # macOS/Linux
```

---

## 环境准备

```bash
# 激活 conda 环境（每个终端都需要）
mamba activate E:\miniforge
mamba activate agent

cd E:\git-clone\NativePlanning
```

如需 LLM 意图解析（可选），在 `.env` 中设置：
```
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.deepseek.com/v1   # 兼容 DeepSeek
OPENAI_MODEL=deepseek-chat
```
不设置时自动退回规则解析，全部功能仍可演示。

---

## 1. CLI Demo

每条命令独立可运行，无需额外配置：

```bash
# 家庭场景（主力演示）
python -m src.cli.main family

# 朋友聚会
python -m src.cli.main friends

# 异常：餐厅无位，自动换一家
python -m src.cli.main failure-no-seats

# 异常：场馆无票，自动换场馆
python -m src.cli.main failure-no-tickets

# 异常：时间冲突，自动压缩行程
python -m src.cli.main failure-time-conflict
```

**自由文本（需要 OPENAI_API_KEY）：**
```bash
python -m src.cli.main 今天下午想和老婆孩子出去玩几个小时，别离家太远
```

---

## 2. Streamlit UI — In-Process 模式（默认）

```bash
streamlit run src/ui/app.py
# 浏览器打开 http://localhost:8501
```

演示流程：
1. 输入框已预填"今天下午想和老婆孩子出去玩几个小时，别离家太远"
2. 点击 **生成计划** → 等待 1-2 秒
3. 看：意图解析面板（场景 / 人数 / 出发 / 时长 / 最远距离），注意右上角 `[rule-based]` 或 `[LLM]` 徽章
4. 看：**方案选择器**（若有备选方案）— 最多显示 3 个候选，可点击切换
5. 看：推荐计划卡片（综合评分、理由、风险、预估费用）
6. 看：时间线表格（时间 / 步骤 / 地点 / 时长）
7. 展开 **工具调用追踪**：查看每个 tool 的状态、摘要、耗时
8. 点击 **确认并执行**
9. 看：执行结果（已购票 / 已预约，含 booking_id）
10. 看：分享消息（点击右上角图标一键复制）
11. 点击 **🔄**（右上角）重新开始，确认状态已清空

也可输入：
- `family` / `friends` → 直接走 fixture 场景
- `failure-no-seats` → 演示餐厅无位自动替换
- `failure-no-tickets` → 演示场馆无票自动替换
- `failure-time-conflict` → 演示时间冲突自动修复

---

## 3. Streamlit UI — HTTP 模式（FastAPI 后端）

**终端 1**（启动 API 服务器）：
```bash
mamba activate E:\miniforge && mamba activate agent
cd E:\git-clone\NativePlanning
uvicorn src.api.app:app --reload --port 8000
# 等待出现：Uvicorn running on http://127.0.0.1:8000
```

> **重要：** uvicorn 必须用 conda env 启动，否则 OPENAI_API_KEY 无法加载，
> 意图解析会显示 `[rule-based]`。

**终端 2**（启动 UI，指向 HTTP 后端）：
```bash
mamba activate E:\miniforge && mamba activate agent
cd E:\git-clone\NativePlanning

# Windows
set NATIVE_PLANNING_API_URL=http://localhost:8000
streamlit run src/ui/app.py

# macOS / Linux
export NATIVE_PLANNING_API_URL=http://localhost:8000
streamlit run src/ui/app.py
```

UI 标题下方会显示"后端：HTTP → http://localhost:8000"，行为与 in-process 模式完全一致，
计划输出应逐字相同（同一代码路径）。

---

## 4. FastAPI 裸接口（可选）

```bash
# 生成计划
curl -X POST http://localhost:8000/api/plans/generate \
  -H "Content-Type: application/json" \
  -d '{"user_input": "family"}' | python -m json.tool

# 健康检查
curl http://localhost:8000/api/health
```

---

## 5. 测试套件

```bash
pytest tests/ -v
# 期望：144 passed in ~1s（无 OPENAI_API_KEY 亦可通过）
```

---

## 6. 评委重点关注

### 备选方案选择器（MVP-3 亮点）

生成计划后，若 Planner 产出 2-3 个候选，页面会显示 **方案选择器**（横排 radio）。
切换到方案 2 / 方案 3 后点击"确认并执行"，执行的是所选方案，而非默认方案。

### 动态多站点行程（MVP-4 亮点）

全天模式（时长 ≥ 7h）下，Planner 会根据剩余时间预算自动插入 light stop（茶馆/citywalk/咖啡），
或在时间宽裕时增加第二活动站点。时间紧时自动跳过 light stop，核心步骤不压缩。

演示方法：
```
今天带家人逛一整天，上午下午各玩一个地方
```
时间线中应出现 3–4 个非交通站点，且 `total_duration_minutes` 严格 ≤ `duration_hours × 60`。

### 位置锚点（MVP-4 亮点）

用户指定出发区域或活动集中地，Planner 优先推荐同区域场馆/餐厅，ranker 给同区域加分。

演示方法：
```
先去芳华街逛逛，然后找个好餐厅
```
意图面板中应出现 **📍 位置锚点：芳华街**，推荐场馆 area 应为芳华街或相邻区域。

调整时也可更新锚点：
```
去云景附近吧
```

### 丰富本地数据展示（MVP-4 亮点）

计划卡片中应显示：
- **推荐菜**（餐厅）：如"龙虾拼盘 · 黑椒牛柳 · 招牌焦糖蛋糕"
- **好评标签**：绿色 chip，如 `` `服务热情` `` `` `出品稳定` ``
- **差评风险**：黄色 caption，如"⚠️ 风险：周末排队 / 上菜慢"
- **优惠券**：绿色 success box，如"🎫 立减20元"
- **场馆亮点**：如 `` `家庭首选` `` `` `适合拍照` ``

### 自然修改输入（MVP-4 亮点）

调整方案输入框支持更广泛的中文自然表达：

| 用户输入 | 效果 |
|---|---|
| `太近了` | max_distance_km × 1.5 |
| `有点远` | max_distance_km × 0.6 |
| `太贵了` / `贵了点` | budget_preference → low |
| `贵一点没关系` / `不差钱` | budget_preference → high |
| `人太多了不想等` | hard_constraints += avoid_long_queue |
| `今天太晒了，怕晒` | hard_constraints += indoor |

### LLM vs 规则解析徽章

- 意图解析面板标题右侧显示 `` `[LLM]` `` 或 `` `[rule-based]` ``，反映实际运行路径
- 页眉 caption 同步显示 `openai=✓/✗` 和 `key=✓/✗`，便于评委验证环境

### 工具调用 Trace（第 6 步）

展开 **工具调用追踪** 后，应能看到：

| 工具 | 说明 |
|---|---|
| `search_venues` | 按场景偏好搜索场馆 |
| `check_venue_availability` | 检查场馆余票 |
| `search_restaurants` | 搜索餐厅 |
| `check_restaurant_availability` | 检查餐厅座位 |
| `book_venue` | 购票（执行阶段） |
| `reserve_restaurant` | 预约餐厅（执行阶段） |

失败场景中还会出现 `fallback_venue` / `fallback_restaurant`，说明系统已自动修复。

### 执行结果与分享消息

- 执行结果表应包含 `booking_id` / `rsv_XXXXXX` 确认号
- 分享消息应为完整中文短句（≥ 20 字），可直接复制发给家人/朋友
- 刷新页面会清空当前计划（无持久化，MVP 行为）

### 异常处理

运行 `failure-*` 场景时，计划卡片上方会出现黄色警告条，
内容说明"原餐厅/场馆已不可用，已替换为 XX"，
时间线仍然完整可执行，分享消息包含相应备注。

---

## 附：手动 LLM 验证（不进入自动测试）

以下命令需要 `OPENAI_API_KEY`（`.env` 已配置时自动生效）：

```bash
# LLM 意图解析路径（应看到 [LLM] 徽章）
python -m src.cli.main 今天下午想和三个朋友出去玩，拍拍照顺便吃个好的

# Streamlit 中也可直接输入中文自由文本，徽章为 [LLM]
```
