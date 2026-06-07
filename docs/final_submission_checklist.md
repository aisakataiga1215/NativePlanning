# Final Submission Checklist

## 代码 & 环境

- [ ] `requirements.txt` 存在，无本地绝对路径（`E:/`、`C:/`）
- [ ] `.streamlit/config.toml` 存在，无本地路径
- [ ] `pyproject.toml` 版本号正确（当前 0.1.0）
- [ ] `.env.example` 存在（`.env` 未提交到 git）
- [ ] `.gitignore` 包含 `.env`、`__pycache__`、`*.egg-info`

## 测试

- [ ] `pytest tests/ -q` → 321+ passed，0 failed
- [ ] 8 条验收用例手动通过（见 `docs/judge_guide.md` 第 3 节）

## 文档

- [ ] `README.md` — 项目介绍 + 快速启动（无本地路径）
- [ ] `docs/deployment.md` — Streamlit Cloud / HF Spaces 部署步骤
- [ ] `docs/judge_guide.md` — 评委操作指引 + 8 条验收用例
- [ ] `docs/design_proposal.md` — 设计思路（1-2 页）
- [ ] `docs/architecture.md` — 系统架构（已存在）
- [ ] `docs/evaluation.md` — 评测指标（已存在）
- [ ] `docs/meituan_alignment.md` — 美团对齐（已存在）

## 部署

- [ ] 代码已 push 到 GitHub（`main` 分支）
- [ ] Streamlit Community Cloud 或 HF Spaces 部署成功
- [ ] 公网 URL 可访问，无 API Key 时也能完整演示
- [ ] 公网 URL 已填写到提交表单

## GitHub 仓库整洁

- [ ] 无调试垃圾文件（`test_*.py` 临时文件、`debug_*.py` 等）
- [ ] 无 `E:/`、`C:/` 等本地路径在任何提交文件中
- [ ] README 顶部包含公网 URL 或徽章

## 最终确认

- [ ] 所有 P0 项已完成
- [ ] 提交材料（URL + 文档链接）已整理完毕
