# Deployment Guide

## Streamlit Community Cloud（推荐）

### 前置条件

- 项目已推送到 GitHub（公开仓库）
- Streamlit Community Cloud 账号：https://share.streamlit.io

### 部署步骤

1. **Fork / Push 仓库**

   将本仓库推送到你的 GitHub 账号。

2. **登录 Streamlit Community Cloud**

   访问 https://share.streamlit.io 并用 GitHub 账号登录。

3. **New App → 填写信息**

   | 字段 | 值 |
   |------|-----|
   | Repository | `your-github-username/NativePlanning` |
   | Branch | `main` |
   | Main file path | `src/ui/app.py` |
   | Python version | 3.11 |

4. **配置 Secrets（可选）**

   若要使用 LLM 意图解析，在 **App settings → Secrets** 中添加：

   ```toml
   OPENAI_API_KEY = "sk-..."
   OPENAI_BASE_URL = "https://api.deepseek.com/"   # 可选
   OPENAI_MODEL = "deepseek-chat"                     # 可选
   ```

   **不配置 Secrets 也能完整运行**：系统自动降级为 rule-based 意图解析 + MockAPI，所有 8 条验收用例均可通过。

5. **点击 Deploy**

   等待约 2-5 分钟，Streamlit Cloud 安装依赖并启动。

6. **获取公网 URL**

   部署成功后 URL 形如：
   ```
   https://your-username-nativeplanning-src-ui-app-xxxxx.streamlit.app
   ```

---

## Hugging Face Spaces（备选）

1. 创建新 Space：https://huggingface.co/new-space
2. SDK 选 **Streamlit**，Python 选 **3.11**
3. 将本仓库内容 push 到 Space 仓库
4. HF Spaces 会自动读取 `requirements.txt` 并安装依赖
5. Entry point 为 `src/ui/app.py`（在 Space 根目录创建 `app.py` 软链或添加 `README.md` 的 `app_file` 字段）

   在 `README.md` YAML front matter 中添加：
   ```yaml
   ---
   title: NativePlanning
   sdk: streamlit
   sdk_version: "1.30"
   app_file: src/ui/app.py
   ---
   ```

6. Secrets 在 Space Settings → Repository secrets 中配置（同上）

---

## 本地运行

```bash
# 1. 安装依赖
pip install -e ".[api,ui]"
# 或直接用 requirements.txt
pip install -r requirements.txt && pip install -e .

# 2. (可选) 配置 LLM
cp .env.example .env
# 编辑 .env，设置 OPENAI_API_KEY

# 3. 启动 Streamlit
streamlit run src/ui/app.py
# → http://localhost:8501

# 4. 启动 FastAPI 后端（可选，分离部署时）
uvicorn src.api.app:app --reload --port 8000
```

---

## 注意事项

- 不需要提交 `.env` 文件；本地路径（`E:/`、`C:/`）不会出现在代码或配置中。
- `requirements.txt` 中所有依赖均可通过 PyPI 安装，无私有包。
- 无 API Key 时系统自动降级为 rule-based 模式，功能完整。
