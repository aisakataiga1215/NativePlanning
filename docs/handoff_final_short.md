# NativePlanning 交接文档

## 1. 当前状态

- **项目**：NativePlanning — 美团本地生活活动规划 Agent（竞赛 Demo）
- **UI**：Streamlit (`src/ui/app.py`)
- **后端**：FastAPI (`src/api/app.py`) + Python planner / ranker / mock tools
- **测试**：321 passed（`tests/` 目录）
- **核心 Demo**：已稳定，8 条验收用例全部可跑

---

## 2. 已完成功能

| 功能 | 文件 |
|------|------|
| 意图解析（LLM + 规则双路径） | `src/workflow/intent_parser.py` |
| 时间解析（今天/明天/上午/傍晚/now 等） | `src/workflow/datetime_parser.py` |
| 活动 + 餐饮规划（family/couple/friends/solo） | `src/workflow/planner.py` |
| 营业时间 hard gate（开园前不排 activity） | `src/workflow/constraint_solver.py` |
| no-meal（`meal_policy=excluded`） | planner + message_agent |
| meal-only（`plan_mode=meal_only`） | planner |
| revision：太远了 / 换餐厅 / 不吃饭 | `src/workflow/planner.py:revise_*` |
| 动物园开园等待（早上时段推迟） | constraint_solver |
| 火锅 fallback consistency（切换餐厅后消息一致） | message_agent + `_filter_warnings` |
| Execution result polish（中文标签 + 下一步提醒） | `src/ui/app.py`, `src/workflow/executor.py` |
| Meituan alignment（GENE 意图面板 + 规划链路摘要 + 推荐理由） | `src/ui/app.py`, planner |
| 评测文档 | `docs/meituan_alignment.md`, `docs/evaluation.md` |

---

## 3. 最终提交还差什么

### P0（必须完成，不提交就会扣分）

- [ ] 跑全量 pytest，确认 321+ passed，0 failed
- [ ] 手动过 8 条验收用例（见第 4 节）
- [ ] **Streamlit 部署到公网**（评委需要通过 URL 访问）
  - 推荐：Streamlit Community Cloud 或 Hugging Face Spaces
  - 无 API key 也必须能跑（rule-based + mock mode）
  - 不提交 `.env`，不含 `E:/`、`C:/` 本地路径
  - 补 `requirements.txt`、`.streamlit/config.toml`、`docs/deployment.md`
- [ ] 整理 GitHub repo（README 完整、无调试垃圾文件）
- [ ] 补/写以下文档：
  - `README.md`（项目介绍 + 快速启动）
  - `docs/design_proposal.md`（设计思路，1~2 页）
  - `docs/judge_guide.md`（评委操作指引，含截图步骤）
  - `docs/deployment.md`（部署说明）
  - `docs/final_submission_checklist.md`（提交清单）

### P1（有余力再做）

- [ ] 备用截图 / 录屏（防止 Demo 环境出问题）
- [ ] Next.js + TypeScript + Vercel 前端（**不要优先做，不要删 Streamlit**）

---

## 4. 8 条验收用例

| # | 输入 | 预期关键点 |
|---|------|-----------|
| 1 | 今天晚上带孩子去亲子乐园 | family，activity，开园时间匹配 |
| 2 | 待会和老婆去吃烛光晚餐 | couple，meal_only，romantic 餐厅 |
| 3 | 明天去动物园，不吃饭 | no-meal，动物园 venue，share 无餐饮词 |
| 4 | 今晚和朋友吃火锅 | friends，火锅餐厅，reservation |
| 5 | 明天早上7点带孩子去动物园 | 开园约束，activity 时间 ≥ open_time |
| 6 | 明天和老婆去看展，然后吃日料 | couple，展览 venue，日料餐厅 |
| 7 | 用例 6 方案 → 换个餐厅 | revision，保留场馆，换餐厅 |
| 8 | 明天带孩子去动物园 → 太远了 | revision，距离缩小，feasible |

---

## 5. 运行命令

```bash
# 测试
E:/miniforge/envs/common/python.exe -m pytest tests/ -q

# Streamlit（in-process 模式，推荐演示用）
E:/miniforge/envs/common/Scripts/streamlit.exe run src/ui/app.py

# FastAPI 后端
E:/miniforge/envs/common/python.exe -m uvicorn src.api.app:app --port 8000

# HTTP 模式（分离部署时）
NATIVE_PLANNING_API_URL=http://localhost:8000 streamlit run src/ui/app.py
```

---

## 6. 不要做

- 不要加新功能或 API
- 不要改 planner / ranker 核心逻辑
- 不要现在做 Next.js / Vercel（P1，有余力再说）
- 不要加 SQLite、登录、真实地图 API、真实支付
- 不要删除 Streamlit
- 不要破坏现有测试（321 passed 是底线）

---

## 7. 关键文件速查

```
src/
  workflow/intent_parser.py     # 意图解析
  workflow/planner.py           # 规划主逻辑
  workflow/constraint_solver.py # 约束修复 / fallback
  workflow/executor.py          # 执行操作
  workflow/message_agent.py     # 分享消息生成
  services/plan_ranker.py       # 方案打分排序
  ui/app.py                     # Streamlit UI
  api/app.py                    # FastAPI 后端
  mock_api/                     # Mock 数据和工具

docs/
  architecture.md               # 系统架构
  evaluation.md                 # 评测指标 + 验收用例
  meituan_alignment.md          # 美团技术对齐
  demo_script.md                # Demo 演示脚本

tests/                          # 321 个测试用例
```
