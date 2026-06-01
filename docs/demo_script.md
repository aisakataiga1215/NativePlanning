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
# 期望：91 passed in ~1s（无 OPENAI_API_KEY 亦可通过）
```

---

## 6. 评委重点关注

### 备选方案选择器（MVP-3 亮点）

生成计划后，若 Planner 产出 2-3 个候选，页面会显示 **方案选择器**（横排 radio）。
切换到方案 2 / 方案 3 后点击"确认并执行"，执行的是所选方案，而非默认方案。

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
