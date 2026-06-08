---
title: NativePlanning
emoji: 🗺️
colorFrom: red
colorTo: yellow
sdk: docker
pinned: false
---

# NativePlanning — Local Activity Planning Agent

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://nativeplanning.streamlit.app/)

**Live Demo:**
- Next.js 前端：https://native-planning.vercel.app
- Streamlit UI：https://nativeplanning.streamlit.app
- FastAPI 后端：https://aisakamai-nativeplanning.hf.space/api/health

A local-life planning and execution agent that turns one natural language request into a
complete, confirmed, executable 4–6 hour activity plan.

> 今天下午想和老婆孩子出去玩几个小时，别离家太远，帮我安排一下。

The system searches venues and restaurants via MockAPI, handles seat/ticket failures, ranks
candidates, presents a timeline with scores and risks, and executes bookings after one-click
confirmation.

---

## Quick Start

### Next.js 前端（推荐）

```bash
# Terminal 1 — FastAPI backend
pip install -r requirements.txt
cp .env.example .env   # fill in OPENAI_API_KEY
uvicorn src.api.app:app --port 8000

# Terminal 2 — Next.js frontend
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

### Streamlit UI

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in OPENAI_API_KEY
streamlit run src/ui/app.py
# → http://localhost:8501
```

### CLI Demo (no extra deps)

```bash
python -m src.cli.main family
python -m src.cli.main friends
python -m src.cli.main failure-no-seats
python -m src.cli.main failure-no-tickets
python -m src.cli.main failure-time-conflict
# free-text (requires OPENAI_API_KEY):
python -m src.cli.main 今天下午想和三个朋友出去玩，拍拍照吃个好的
```

---

## Recommended Inputs

```
今天晚上带孩子去亲子乐园
待会和老婆去吃烛光晚餐
明天去动物园，不吃饭
今晚和朋友吃火锅
明天早上7点带孩子去动物园
明天和老婆去看展，然后吃日料
```

After generating a plan, try: `太远了` / `换个餐厅` / `不吃饭`

---

## Tests

```bash
pytest tests/ -q
# 321 passed — no OPENAI_API_KEY required
```

---

## Architecture

```
User Input
  └─ Intent Parser (LLM → json_object → rule-based fallback)
       └─ Planner → Constraint Solver → Plan Ranker
            └─ Executor (book_venue, reserve_restaurant, …)
                 └─ Message Agent (LLM → template fallback)

MockAPI  ←  Tool Wrappers (ToolTrace / TraceLog)
FastAPI  ←  Next.js (Vercel) / Streamlit UI
```

See [`docs/architecture.md`](docs/architecture.md) for details.

---

## Milestones

| Milestone | Status | Description |
|-----------|--------|-------------|
| MVP-0 | ✓ Complete | Deterministic CLI, 5 scenarios, 18 tests |
| MVP-1 | ✓ Complete | LLM intent parser (OpenAI-compatible) + FastAPI app |
| MVP-2 | ✓ Complete | Streamlit UI, dual backend mode |
| MVP-3 | ✓ Complete | Alternative plans selector, source tracking, UI polish |
| MVP-4 | ✓ Complete | meal_policy, revision, opening-hours gate, 321 tests |
| MVP-5 | ✓ Complete | TypeScript Next.js 14 frontend + production deployment |

---

## Project Structure

```
frontend/                      # Next.js 14 App Router SPA (Vercel)
├── app/page.tsx               # 主页面 — 6 阶段状态机
├── components/                # UI 组件
│   ├── IntentPanel.tsx        # 意图解析结果
│   ├── PlanCard.tsx           # 方案卡片（5 维评分）
│   ├── PlanSelector.tsx       # 备选方案切换
│   ├── Timeline.tsx           # 行程时间轴
│   ├── ToolTrace.tsx          # 工具调用链（可折叠）
│   ├── ExecutionResult.tsx    # 预订结果
│   ├── ShareMessage.tsx       # 分享文案 + 一键复制
│   └── RevisionInput.tsx      # 修改意见输入
└── lib/
    ├── api.ts                 # fetch 客户端（generate / revise / execute）
    └── types.ts               # TypeScript 接口（镜像 Pydantic schemas）

src/
├── api/                       # FastAPI 入口 + HTTP schemas
├── workflow/                  # 核心规划链
│   ├── intent_parser.py       # LLM / rule-based 意图解析
│   ├── planner.py             # 场馆 + 餐厅召回与组合
│   ├── constraint_solver.py   # 营业时间 / 时间冲突修复
│   ├── revision_parser.py     # 局部修改（restaurant / venue / distance）
│   ├── executor.py            # 预订执行
│   └── message_agent.py       # 分享文案生成
├── services/
│   ├── plan_ranker.py         # 5 维评分排序
│   └── itinerary_builder.py   # 时间轴生成
├── tools/                     # Tool wrappers + ToolTrace / TraceLog
├── mock_api/                  # 内存 MockAPI（场馆 18 / 餐厅 16）
├── schemas/                   # Pydantic v2 领域模型
├── ui/                        # Streamlit UI（main 分支）
└── cli/                       # CLI 入口

tests/                         # 321 tests，无需 OPENAI_API_KEY
docs/                          # 架构文档、changelog、设计方案、评委指南
```

---

## Known Limitations

- Mock data only — not connected to real Meituan / Amap API
- Distance, queue time, and seat counts are simulated values
- No real payment; booking returns a mock booking ID
- Single session — no user login or persistent history

---

## Design & Judge Docs

- [Design Proposal](docs/design_proposal.md) — architecture, intent parsing, tool chain, exception handling
- [Design Proposal (PDF)](design_proposal.pdf) — printable version
- [Judge Guide](docs/judge_guide.md) — 8 acceptance cases, recommended inputs, UI walkthrough
- [Meituan Alignment](docs/meituan_alignment.md) — GENE alignment and evaluation metrics
