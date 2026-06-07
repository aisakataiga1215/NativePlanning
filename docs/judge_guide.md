# 评委体验指南 — NativePlanning

**Live Demo:** https://nativeplanning.streamlit.app/
**GitHub:** https://github.com/aisakataiga1215/NativePlanning

---

## 1. 访问方式

**在线访问（推荐，无需配置）：**
直接打开 https://nativeplanning.streamlit.app/

系统在无 API key 时自动使用 rule-based 模式，所有功能完整可用。

**本地运行：**
```bash
pip install -r requirements.txt && pip install -e .
streamlit run src/ui/app.py
# → http://localhost:8501
```

---

## 2. 推荐体验输入

以下 6 条输入可覆盖系统主要能力：

| # | 输入 | 覆盖能力 |
|---|------|---------|
| 1 | 今天晚上带孩子去亲子乐园 | 亲子场景、营业时间过滤、活动+餐饮计划 |
| 2 | 待会和老婆去吃烛光晚餐 | meal_only 模式、romantic 餐厅召回 |
| 3 | 明天去动物园，不吃饭 | no_meal 模式、餐饮链路完全关闭 |
| 4 | 今晚和朋友吃火锅 | friends 场景、cuisine 精确匹配 |
| 5 | 明天早上7点带孩子去动物园 | 开园约束自动修复、时间调整说明 |
| 6 | 明天和老婆去看展，然后吃日料 | 展览场馆 + 日料餐厅精确召回 |

---

## 3. 推荐交互操作（Revision）

在用例 6 或用例 8 生成方案后，在下方「修改方案」框继续输入：

| 输入 | 效果 |
|------|------|
| `换个餐厅` | 仅替换餐厅，场馆和时间轴不变 |
| `太远了` | 更新距离约束，输出替代说明 |
| `不吃饭` | 删除餐饮段，重新生成 no_meal 方案 |

---

## 4. UI 界面重点看点

| 区域 | 重点观察 |
|------|---------|
| **意图解析面板** | `[LLM]` / `[rule-based]` 来源徽章；group_type、meal_policy、time_period、duration 等字段 |
| **方案卡片** | 5 维评分（适配/距离/氛围/价格/新颖度）+ 推荐理由 + feasibility 状态 |
| **多方案选择器** | 最多 3 个候选，可点击切换查看不同方案 |
| **时间轴** | 活动→出行→餐饮→返程全链路；营业状态列（🟢/🔴） |
| **工具调用追踪** | 可折叠展示完整 MockAPI 调用链（工具名/参数/响应/耗时） |
| **确认执行** | 两步确认 → 显示预订 ID + 下一步提醒 |
| **分享消息** | 中文分享文案，no_meal 场景下无餐饮词汇 |

---

## 5. 8 条验收用例

| # | 输入 | 预期关键点 |
|---|------|-----------|
| 1 | 今天晚上带孩子去亲子乐园 | group=family，夜间可行场馆，top1 feasible=True，含餐饮 |
| 2 | 待会和老婆去吃烛光晚餐 | plan_mode=meal_only，romantic 餐厅，无 activity 段 |
| 3 | 明天去动物园，不吃饭 | meal_policy=excluded，无餐厅，share 消息无餐饮词 |
| 4 | 今晚和朋友吃火锅 | group=friends，hotpot 餐厅，生成 reservation |
| 5 | 明天早上7点带孩子去动物园 | activity start ≥ open_time，warning 说明调整入场时间 |
| 6 | 明天和老婆去看展，然后吃日料 | exhibition venue，japanese 餐厅，group=couple |
| 7 | 用例 6 → 换个餐厅 | venue 不变，只换餐厅 |
| 8 | 动物园方案 → 太远了 | 新方案距离更小，warning 说明替代原因 |

---

## 6. 完整执行示例（用例 1）

1. 输入：`今天晚上带孩子去亲子乐园`
2. 点击 **生成方案**
3. 查看意图面板 — `group_type=family`，`meal_policy=required`，时段解析
4. 查看方案卡片 — 评分、推荐理由、feasibility 状态
5. 展开 **工具调用追踪** — 查看 Venue Search / Opening Hours Gate / Ranker 调用链
6. 点击 **确认方案** → 点击 **执行预订**
7. 查看预订 ID + 中文分享文案

---

## 7. 测试套件

```bash
python -m pytest tests/ -q
# 预期：321 passed，0 failed，无需 OPENAI_API_KEY
```

---

## 8. 已知限制

- 使用 mock 数据演示，未连接真实美团 / 高德 API
- 距离、排队时长、座位数为模拟值
- 无真实支付；预订结果为 mock booking ID
- 单 session，无用户登录和历史偏好记忆
