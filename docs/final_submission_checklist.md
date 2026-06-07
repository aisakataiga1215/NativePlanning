# Final Submission Checklist

## 测试

- [ ] `pytest tests/ -q` → 321+ passed，0 failed
- [ ] 8 条 demo 验收用例手动通过（见 `docs/judge_guide.md`）

## 环境 & 配置

- [ ] `requirements.txt` 存在，无本地绝对路径
- [ ] `.streamlit/config.toml` 存在（headless + enableXsrfProtection=false）
- [ ] `.gitignore` 包含 `.env`、`.env.*`、`.streamlit/secrets.toml`
- [ ] `.env` 未提交到 git（`.env.example` 已提交）

## 文档

- [ ] `README.md` — 含公网 URL、推荐输入、已知限制、设计文档链接
- [ ] `docs/design_proposal.md` — 12 节正式评委版（含 intent/plan/tool chain/exception 表格）
- [ ] `docs/judge_guide.md` — 含实际 URL、8 条验收用例、revision 操作指引
- [ ] `docs/deployment.md` — Streamlit Cloud + HF Spaces 部署步骤
- [ ] `docs/final_submission_checklist.md` — 本文件
- [ ] `docs/architecture.md` — 系统架构（已存在）
- [ ] `docs/changelog.md` — 含 Final Submission 条目
- [ ] `docs/project_status.md` — 阶段改为 Final Submission / Deployment Ready

## 部署

- [ ] 代码已 push 到 GitHub `main` 分支
- [ ] Streamlit Community Cloud 部署成功，公网可访问
- [ ] 无 API key 时 demo 可完整运行（rule-based 模式）
- [ ] 公网 URL 已填入 README、judge_guide、提交表单

## GitHub 仓库

- [ ] 无 `E:/`、`C:/` 等本地绝对路径（CLAUDE.md 除外）
- [ ] 无 API key / token 泄露
- [ ] README 顶部含 Streamlit 徽章和公网链接

## 提交材料

- [ ] 部署链接：https://nativeplanning.streamlit.app/
- [ ] GitHub 链接：https://github.com/aisakataiga1215/NativePlanning
- [ ] 设计方案：`docs/design_proposal.md`
- [ ] 已准备备用截图 / 录屏（防止演示环境出问题）
