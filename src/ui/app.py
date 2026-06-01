"""Streamlit UI for NativePlanning MVP-3.

Run with:
    streamlit run src/ui/app.py

Backend mode is controlled by `NATIVE_PLANNING_API_URL`:

* unset   → in-process (imports workflow modules directly, same as CLI)
* set     → HTTP (calls the FastAPI app at the given base URL)

A two-step confirm flow stores the generated plan in `st.session_state`:

1. User enters Chinese text → 生成计划 → plan + traces displayed.
2. User clicks 确认并执行 → execution results + share message displayed.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv()

import streamlit as st

from src.api.schemas import ExecuteResponse, GenerateResponse
from src.schemas.plan import ItineraryPlan
from src.ui.planning_client import make_client

_SUMMARY_TRUNCATE = 60

st.set_page_config(
    page_title="NativePlanning",
    page_icon="🗺️",
    layout="wide",
)


def _intent_source_badge() -> str:
    """Header badge: shows configured method (env-based, before any generation)."""
    return "[LLM]" if os.getenv("OPENAI_API_KEY") else "[rule-based]"


def _source_label(source: str) -> str:
    """Convert intent.source value to display label."""
    return {"llm": "[LLM]", "rule_based": "[rule-based]"}.get(source, "[?]")


def _backend_mode_label() -> str:
    url = os.getenv("NATIVE_PLANNING_API_URL")
    return f"HTTP → {url}" if url else "in-process"


def _truncate(value: object, limit: int = _SUMMARY_TRUNCATE) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _trace_summary(trace: dict) -> str:
    status = trace.get("status")
    if status == "error":
        return _truncate(f"error: {trace.get('error') or ''}")
    output = trace.get("output")
    if isinstance(output, list):
        return f"{len(output)} 项"
    if isinstance(output, dict):
        if "available" in output:
            return f"available={output['available']}"
        return _truncate(output)
    if output is None:
        return ""
    return _truncate(output)


def _status_icon(status: str) -> str:
    if status == "ok":
        return "✓"
    if status == "error":
        return "✗"
    return status


def _render_header() -> None:
    st.title("🗺️ NativePlanning")
    st.caption(
        "本地生活活动规划助理 · 输入需求 → 生成计划 → 确认执行 · "
        "点击「重新开始」清空当前计划"
    )
    try:
        import openai as _oa  # noqa: F401
        _openai_ok = True
    except ImportError:
        _openai_ok = False
    _key_ok = bool(os.getenv("OPENAI_API_KEY"))
    st.caption(f"后端：{_backend_mode_label()}  ·  意图解析：{_intent_source_badge()}")
    if not _openai_ok or not _key_ok:
        st.caption(
            f"⚠ LLM 不可用 — openai={'已安装' if _openai_ok else '未安装'}，"
            f"OPENAI_API_KEY={'已设置' if _key_ok else '未设置'}，"
            f"Python: `{sys.executable}`"
        )


def _render_intent_panel(generate: GenerateResponse) -> None:
    intent = generate.intent
    source_lbl = _source_label(intent.source)
    with st.container(border=True):
        st.markdown(f"### 1. 意图解析  `{source_lbl}`")
        cols = st.columns(5)
        cols[0].metric("场景", intent.scenario_type)
        cols[1].metric("人数", intent.group_size)
        cols[2].metric("出发", f"{intent.date} {intent.time}")
        cols[3].metric("时长", f"{intent.duration_hours} h")
        cols[4].metric("最远距离", f"{intent.max_distance_km} km")
        if intent.raw_input:
            st.caption(f"原始输入：{intent.raw_input}")


def _render_warnings(warnings: list[str]) -> None:
    for warning in warnings:
        st.warning(warning)


def _render_plan_card(plan: ItineraryPlan) -> None:
    with st.container(border=True):
        st.markdown(f"### 2. 推荐计划 — {plan.title}")
        st.write(plan.summary)

        sb = plan.score_breakdown
        score_cols = st.columns(6)
        score_cols[0].metric("综合", f"{plan.score:.2f}")
        score_cols[1].metric("距离", f"{sb.distance_score:.2f}")
        score_cols[2].metric("时间", f"{sb.time_score:.2f}")
        score_cols[3].metric("适配", f"{sb.group_fit_score:.2f}")
        score_cols[4].metric("餐厅", f"{sb.restaurant_score:.2f}")
        score_cols[5].metric("可执行", f"{sb.execution_score:.2f}")

        reasons_col, risks_col = st.columns(2)
        with reasons_col:
            st.markdown("**理由**")
            if plan.reasons:
                for reason in plan.reasons:
                    st.markdown(f"- ✓ {reason}")
            else:
                st.caption("（无）")
        with risks_col:
            st.markdown("**风险**")
            if plan.risks:
                for risk in plan.risks:
                    st.markdown(f"- ⚠ {risk}")
            else:
                st.caption("（无风险）")

        st.markdown(f"**预估费用：¥{plan.estimated_total_cost:.0f}**")


def _render_timeline(plan: ItineraryPlan) -> None:
    with st.container(border=True):
        st.markdown("### 3. 时间线")
        rows = [
            {
                "时间": f"{step.start_time} – {step.end_time}",
                "步骤": step.title,
                "地点": step.location_name,
                "时长": f"{step.duration_minutes} min",
            }
            for step in plan.steps
        ]
        st.dataframe(rows, hide_index=True, use_container_width=True)


def _render_trace_expander(traces: list[dict]) -> None:
    with st.expander(f"工具调用追踪 ({len(traces)} 步)", expanded=False):
        if not traces:
            st.caption("（无追踪记录）")
            return
        rows = [
            {
                "工具": trace.get("tool_name", ""),
                "状态": _status_icon(trace.get("status", "")),
                "摘要": _trace_summary(trace),
                "耗时(ms)": trace.get("elapsed_ms", 0),
            }
            for trace in traces
        ]
        st.dataframe(rows, hide_index=True, use_container_width=True)


def _render_execution(execute: ExecuteResponse) -> None:
    with st.container(border=True):
        st.markdown("### 4. 执行结果")
        if not execute.results:
            st.caption("（无需执行操作）")
        else:
            rows = []
            for result in execute.results:
                ref = result.booking_id or result.order_id or ""
                detail = (
                    f"{result.message}  ({ref})" if ref else result.message
                )
                rows.append(
                    {
                        "操作": result.action_type,
                        "状态": "✓ 成功"
                        if result.status == "success"
                        else "✗ 失败",
                        "详情": detail,
                    }
                )
            st.dataframe(rows, hide_index=True, use_container_width=True)

        st.markdown("**分享消息**（点击右上角图标复制）")
        st.code(execute.share_message.message, language=None)


def _run_generate(user_input: str) -> None:
    client = make_client()
    try:
        with st.spinner("生成计划中..."):
            response = client.generate(user_input)
        st.session_state["last_generate"] = response
        st.session_state.pop("last_execute", None)
        st.session_state.pop("selected_plan_idx", None)
    except Exception as exc:
        st.error(f"生成计划失败：{exc}")


def _run_execute(plan: ItineraryPlan) -> None:
    generate: GenerateResponse | None = st.session_state.get("last_generate")
    if generate is None:
        st.error("请先生成计划。")
        return
    client = make_client()
    try:
        with st.spinner("执行中..."):
            response = client.execute(plan, generate.intent)
        st.session_state["last_execute"] = response
    except Exception as exc:
        st.error(f"执行失败：{exc}")


def main() -> None:
    _render_header()

    default_input = "今天下午想和老婆孩子出去玩几个小时，别离家太远"
    user_input = st.text_area(
        "请输入你的需求",
        value=st.session_state.get("user_input", default_input),
        placeholder="例如：今天下午想带孩子去公园…  或输入 family / friends / failure-no-seats",
        height=100,
        key="user_input_box",
    )
    st.session_state["user_input"] = user_input

    col_gen, col_rst = st.columns([20, 1])
    with col_gen:
        generate_clicked = st.button(
            "生成计划",
            type="primary",
            disabled=not user_input.strip(),
        )
    with col_rst:
        if st.button("🔄", help="重新开始", use_container_width=True):
            for key in ("last_generate", "last_execute", "selected_plan_idx"):
                st.session_state.pop(key, None)
            st.rerun()

    if generate_clicked:
        _run_generate(user_input.strip())

    generate: GenerateResponse | None = st.session_state.get("last_generate")
    if generate is None:
        st.info("输入需求并点击「生成计划」开始。")
        return

    _render_intent_panel(generate)
    _render_warnings(generate.warnings)

    # Plan selector — only shown when there are alternatives
    all_plans = [generate.plan] + list(generate.alternatives)
    if len(all_plans) > 1:
        options = [
            f"方案{i + 1}{'（推荐）' if i == 0 else ''}：{p.title}  ·  综合 {p.score:.2f}"
            for i, p in enumerate(all_plans)
        ]
        idx: int = st.radio(
            "选择方案",
            range(len(options)),
            format_func=lambda i: options[i],
            horizontal=True,
            key="selected_plan_idx",
        )
    else:
        idx = 0

    selected_plan = all_plans[idx]

    _render_plan_card(selected_plan)
    _render_timeline(selected_plan)
    _render_trace_expander(generate.traces)

    execute_clicked = st.button(
        "确认并执行",
        type="primary",
        disabled=st.session_state.get("last_execute") is not None,
    )
    if execute_clicked:
        _run_execute(selected_plan)

    execute: ExecuteResponse | None = st.session_state.get("last_execute")
    if execute is not None:
        _render_execution(execute)
        _render_trace_expander(execute.traces)


main()
