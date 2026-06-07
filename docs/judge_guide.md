# NativePlanning — 评委操作指引

本文档帮助评委快速验证 NativePlanning Demo 的核心功能。

---

## 1. 访问 Demo

**在线访问（推荐）：**

> 公网 URL 见提交表单或 README 顶部徽章。

**本地运行：**

```bash
pip install -r requirements.txt && pip install -e .
streamlit run src/ui/app.py
# → http://localhost:8501
```

无需配置 API Key，系统自动使用 rule-based 模式 + MockAPI。

---

## 2. UI 界面说明

| 区域 | 说明 |
|------|------|
| 顶部输入框 | 输入自然语言请求（中文或英文） |
| 意图解析面板 | 展示 group_type、duration、meal_policy 等结构化意图 |
| 方案卡片 | 含 5 维评分（亲子/氛围/距离/价格/新颖度）和推荐理由 |
| 时间轴 | 活动 + 餐饮的时间安排（含出行缓冲） |
| 工具调用追踪 | 可折叠，展示 MockAPI 调用链 |
| 确认 → 执行 | 两步确认后显示预订 ID 和分享文案 |

---

## 3. 8 条验收用例

### 用例 1 — 亲子乐园（family + activity）

**输入：**
```
今天晚上带孩子去亲子乐园
```
**预期验证点：**
- group_type = family
- 包含 activity（亲子乐园类 venue）
- 开园时间匹配（如晚上时段无开园问题则直接排入）
- 包含餐饮安排

---

### 用例 2 — 烛光晚餐（couple + meal_only）

**输入：**
```
待会和老婆去吃烛光晚餐
```
**预期验证点：**
- group_type = couple
- plan_mode = meal_only（无 activity 段）
- 餐厅标签含 romantic / 烛光

---

### 用例 3 — 动物园 + no-meal（no-meal + venue）

**输入：**
```
明天去动物园，不吃饭
```
**预期验证点：**
- meal_policy = excluded
- venue 为动物园类
- 分享消息中无餐饮相关词汇

---

### 用例 4 — 朋友火锅（friends + 火锅餐厅）

**输入：**
```
今晚和朋友吃火锅
```
**预期验证点：**
- group_type = friends
- 餐厅 cuisine 含 hotpot / 火锅
- 生成预订确认 / reservation

---

### 用例 5 — 早晨动物园开园约束

**输入：**
```
明天早上7点带孩子去动物园
```
**预期验证点：**
- 活动开始时间 ≥ 动物园 open_time（通常 09:00）
- 若用户指定 7:00 到，系统应调整/延迟排入时间，而非强行安排 7:00 入园

---

### 用例 6 — 展览 + 日料（couple + venue + restaurant）

**输入：**
```
明天和老婆去看展，然后吃日料
```
**预期验证点：**
- venue 类型含 exhibition / 展览
- 餐厅 cuisine 含 japanese / 日料
- group_type = couple

---

### 用例 7 — Revision：换餐厅（保留场馆）

**前提：** 先完成用例 6，获得一个包含展览 + 日料的方案。

**输入（在 revision 输入框）：**
```
换个餐厅
```
**预期验证点：**
- 展览场馆保持不变
- 餐厅更换为不同选项
- 方案时间轴更新

---

### 用例 8 — Revision：太远了（距离缩小）

**前提：** 先完成用例1（动物园/亲子场景），获得一个方案。

**输入（在 revision 输入框）：**
```
太远了
```
**预期验证点：**
- 新方案 venue 距离更小
- 方案可行（通过 feasibility check）

---

## 4. 执行流程（用例 1 完整示例）

1. 在输入框输入：`今天晚上带孩子去亲子乐园`
2. 点击 **生成方案**
3. 查看意图面板（group_type = family，meal_policy 等）
4. 查看方案卡片（评分、推荐理由）
5. 点击 **查看时间轴** 确认时间安排
6. 展开 **工具调用追踪** 查看 MockAPI 调用链
7. 点击 **确认方案**
8. 点击 **执行预订**
9. 查看执行结果（预订 ID、分享文案）

---

## 5. 常见问题

**Q: 出现"LLM 不可用"提示？**
A: 无需处理，系统自动切换为 rule-based 模式，所有功能完整。

**Q: revision 入口在哪里？**
A: 执行完用例 6 获得方案后，页面下方会出现 "修改方案" 输入框。

**Q: 测试如何跑？**
```bash
python -m pytest tests/ -q
# 预期：321 passed
```
