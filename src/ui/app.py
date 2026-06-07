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

load_dotenv(_PROJECT_ROOT / ".env")

import streamlit as st

from src.api.schemas import ExecuteResponse, GenerateResponse
from src.schemas.plan import ItineraryPlan
from src.ui.planning_client import make_client

_SUMMARY_TRUNCATE = 60

_ACTION_LABELS: dict[str, str] = {
    "book_venue": "门票预订",
    "reserve_restaurant": "餐厅预约",
    "order_food": "点餐/套餐",
    "queue_restaurant": "排队取号",
}
_STATUS_LABELS: dict[str, str] = {
    "success": "✅ 成功",
    "failed":  "❌ 失败",
    "skipped": "⏭ 跳过",
}

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


def _fmt_elapsed(ms: float) -> str:
    return "<1ms" if ms < 1 else f"{ms:.1f}ms"


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
        "点击 🔄 清空当前计划"
    )
    try:
        import openai as _oa  # noqa: F401

        _openai_ok = True
    except ImportError:
        _openai_ok = False
    _key_ok = bool(os.getenv("OPENAI_API_KEY"))
    st.caption(
        f"后端：{_backend_mode_label()}  ·  意图解析：{_intent_source_badge()}  ·  "
        f"openai={'✓' if _openai_ok else '✗'}  ·  "
        f"key={'✓' if _key_ok else '✗'}  ·  "
        f"Python: `{Path(sys.executable).name}`"
    )
    if not _openai_ok or not _key_ok:
        st.warning(
            f"LLM 不可用 — openai={'已安装' if _openai_ok else '**未安装**'}，"
            f"OPENAI_API_KEY={'已设置' if _key_ok else '**未设置**'}。  \n"
            f"请用 conda env 启动：`E:/miniforge/envs/common/Scripts/streamlit.exe run src/ui/app.py`  \n"
            f"完整路径：`{sys.executable}`"
        )


_PLAN_MODE_LABEL: dict[str, str] = {
    "activity_first": "活动优先", "meal_first": "餐饮优先", "meal_only": "仅餐饮",
}
_SCENARIO_LABEL: dict[str, str] = {
    "family": "家庭", "couple": "情侣", "friends": "朋友",
    "solo": "独行", "colleagues": "同事", "unknown": "—",
}
_MEAL_POLICY_LABEL: dict[str, str] = {
    "required": "需要餐饮", "optional": "按需安排", "excluded": "不安排餐饮",
}
_BUDGET_LABEL: dict[str, str] = {"low": "省钱", "medium": "适中", "high": "不限"}
_TIME_PERIOD_LABEL: dict[str, str] = {
    "morning": "上午", "noon": "中午", "afternoon": "下午",
    "evening": "傍晚", "night": "晚上", "soon": "待会", "unknown": "",
}


def _gene_row(label: str, value: str) -> None:
    st.markdown(f"**{label}**  {value or '—'}")


def _fmt_participants(intent) -> str:
    n = intent.group_size
    parts = getattr(intent, "participants", None) or []
    if not parts:
        return f"{n}人"
    from collections import Counter
    cnt = Counter(getattr(p, "age_group", "") for p in parts)
    chips = " ".join(f"{v}{k}" for k, v in cnt.items() if k)
    return f"{n}人 · {chips}" if chips else f"{n}人"


def _fmt_time(intent) -> str:
    date = "今天" if intent.date == "today" else intent.date
    weekday = getattr(intent, "weekday", None) or ""
    period = _TIME_PERIOD_LABEL.get(getattr(intent, "time_period", ""), "")
    parts = [p for p in [date, weekday, period] if p]
    return " ".join(parts) + f" · {intent.time}出发 · {intent.duration_hours}h"


def _fmt_concrete(intent) -> str:
    items = (
        (getattr(intent, "requested_activities", None) or [])
        + (getattr(intent, "activity_preferences", None) or [])
        + (getattr(intent, "requested_places", None) or [])
    )
    return " · ".join(items[:5]) if items else "—"


def _fmt_meal(intent) -> str:
    policy = _MEAL_POLICY_LABEL.get(getattr(intent, "meal_policy", "required"), "")
    meals = (getattr(intent, "requested_meals", None) or []) + (
        getattr(intent, "meal_preferences", None) or []
    )
    return policy + (f" · {' / '.join(meals[:3])}" if meals else "")


def _fmt_hard(intent) -> str:
    hc = getattr(intent, "hard_constraints", None) or []
    av = len(getattr(intent, "avoid_venue_ids", None) or [])
    ar = len(getattr(intent, "avoid_restaurant_ids", None) or [])
    parts = list(hc[:3])
    if av:
        parts.append(f"避开{av}场馆")
    if ar:
        parts.append(f"避开{ar}餐厅")
    return " · ".join(parts) if parts else "—"


def _fmt_soft(intent) -> str:
    sp = getattr(intent, "soft_preferences", None) or []
    budget = _BUDGET_LABEL.get(getattr(intent, "budget_preference", "medium"), "")
    parts = list(sp[:3])
    if budget:
        parts.append(f"{budget}预算")
    return " · ".join(parts) if parts else budget or "—"


def _render_intent_panel(generate: GenerateResponse) -> None:
    intent = generate.intent
    source_lbl = _source_label(intent.source)
    with st.container(border=True):
        st.markdown(f"### 1. 需求理解  `{source_lbl}`")
        if intent.raw_input:
            st.caption(f"原始输入：{intent.raw_input}")
        left, right = st.columns(2)
        with left:
            _gene_row(
                "场景需求",
                f"{_SCENARIO_LABEL.get(intent.scenario_type, '—')} · "
                f"{_PLAN_MODE_LABEL.get(getattr(intent, 'plan_mode', ''), '—')}",
            )
            _gene_row("人物要素", _fmt_participants(intent))
            _gene_row("时间要素", _fmt_time(intent))
            _gene_row(
                "空间要素",
                f"{intent.location_anchor or '当前位置'} ≤{intent.max_distance_km}km",
            )
        with right:
            _gene_row("具象需求", _fmt_concrete(intent))
            _gene_row("餐饮策略", _fmt_meal(intent))
            _gene_row("硬约束", _fmt_hard(intent))
            _gene_row("软偏好", _fmt_soft(intent))


def _render_warnings(warnings: list[str]) -> None:
    for warning in warnings:
        st.warning(warning)


def _render_right_column(
    col,
    positive_tags: list[str],
    negative_tags: list[str],
    specialty_tags: list[str],
    coupons: list,
    packages: list,
    suitable_for: str = "",
) -> None:
    with col:
        if positive_tags:
            st.caption("✅ " + "  ".join(f"`{t}`" for t in positive_tags[:3]))
        if negative_tags:
            st.caption("⚠️ " + "  ".join(f"`{t}`" for t in negative_tags[:2]))
        if specialty_tags:
            st.caption("⭐ " + "  ".join(f"`{t}`" for t in specialty_tags[:2]))
        for c in coupons[:1]:
            if c.available:
                st.caption(f"🎟 {c.title}")
        for p in packages[:1]:
            st.caption(f"📦 {p.title}")
        if suitable_for:
            st.caption(f"👥 适合：{suitable_for}")


def _render_plan_card(plan: ItineraryPlan, group_size: int = 1) -> None:
    from src.mock_api.restaurants import get_restaurant as _get_restaurant
    from src.mock_api.venues import get_venue as _get_venue
    venue = _get_venue(plan.venue_id) if plan.venue_id else None
    restaurant = _get_restaurant(plan.restaurant_id) if plan.restaurant_id else None

    with st.container(border=True):
        st.markdown(f"### 2. 推荐计划 — {plan.title}")
        st.write(plan.summary)

        sb = plan.score_breakdown
        score_cols = st.columns(6)
        score_cols[0].metric("综合", f"{plan.score:.2f}")
        dist_label = f"{venue.distance_km} km" if venue else f"{sb.distance_score:.2f}"
        score_cols[1].metric("距离", dist_label)
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

        st.markdown(f"**预估费用 （共 {group_size} 人）**")
        cost_cols = st.columns(3)
        all_venue_data = [_get_venue(vid) for vid in plan.venue_ids if _get_venue(vid)]
        if all_venue_data:
            ticket_price_sum = sum(v.price_per_person for v in all_venue_data) * group_size
            ticket_label = "免费" if ticket_price_sum == 0 else f"¥{ticket_price_sum:.0f}"
            if len(all_venue_data) > 1:
                help_str = " + ".join(f"{v.name} ¥{v.price_per_person:.0f}/人" for v in all_venue_data)
            elif all_venue_data[0].price_per_person:
                help_str = f"¥{all_venue_data[0].price_per_person:.0f}/人 × {group_size}人"
            else:
                help_str = "无需购票"
            cost_cols[0].metric("🎟 门票", ticket_label, help=help_str)
        else:
            cost_cols[0].metric("🎟 门票", "—")
        if restaurant:
            food_total = restaurant.avg_price_per_person * group_size
            cost_cols[1].metric("🍽 餐饮", f"¥{food_total:.0f}",
                                help=f"人均约 ¥{restaurant.avg_price_per_person:.0f} × {group_size}人")
        else:
            cost_cols[1].metric("🍽 餐饮", "—")
        per_person = plan.estimated_total_cost / group_size if group_size else plan.estimated_total_cost
        cost_cols[2].metric("💰 合计", f"¥{plan.estimated_total_cost:.0f}",
                            help=f"人均约 ¥{per_person:.0f}")

        # venue details
        if venue:
            st.markdown("---")
            vcols = st.columns(2)
            with vcols[0]:
                st.markdown(f"**{venue.name}**  ·  {venue.rating}⭐ ({venue.review_count} 评)")
                st.caption(f"🕐 {venue.open_time} – {venue.close_time}")
                st.caption(f"⏱ {venue.suggested_duration_min}–{venue.suggested_duration_max} 分钟")
                if venue.price_per_person:
                    st.caption(f"💰 ¥{venue.price_per_person:.0f}/人")
                if venue.queue_minutes > 0:
                    st.caption(f"⏳ 排队约 {venue.queue_minutes} 分钟")
                if venue.ticket_options:
                    st.markdown("**票种：**")
                    for t in venue.ticket_options:
                        if t.available:
                            note_str = f" — {t.note}" if t.note else ""
                            st.markdown(f"- {t.type}: ¥{t.price:.0f}{note_str}")
            _render_right_column(
                vcols[1],
                positive_tags=venue.positive_review_tags,
                negative_tags=venue.negative_review_tags,
                specialty_tags=venue.specialty_tags,
                coupons=venue.venue_coupons,
                packages=venue.packages,
            )

        # multi-stop: extra venues
        if len(plan.venue_ids) > 1:
            extra_ids = [vid for vid in plan.venue_ids if vid != plan.venue_id]
            for vid in extra_ids:
                extra = _get_venue(vid)
                if extra:
                    st.markdown("---")
                    st.markdown(
                        f"**{extra.name}**  ·  {extra.rating}⭐ ({extra.review_count} 评)  ·  "
                        f"🕐 {extra.open_time} – {extra.close_time}"
                    )
                    st.caption(f"⏱ {extra.suggested_duration_min}–{extra.suggested_duration_max} 分钟")
                    if extra.specialty_tags:
                        st.caption("  ".join(f"`{t}`" for t in extra.specialty_tags[:3]))

        # restaurant details
        if restaurant:
            st.markdown("---")
            rcols = st.columns(2)
            with rcols[0]:
                st.markdown(f"**{restaurant.name}**  ·  {restaurant.rating}⭐ ({restaurant.review_count} 评)")
                st.caption(f"🕐 {restaurant.open_time} – {restaurant.close_time}")
                if getattr(restaurant, "suggested_meal_duration_min", 0):
                    st.caption(f"⏱ 约 {restaurant.suggested_meal_duration_min} 分钟")
                if restaurant.avg_price_per_person:
                    st.caption(f"💰 人均约 ¥{restaurant.avg_price_per_person:.0f}")
                if restaurant.queue_minutes > 0:
                    st.caption(f"⏳ 排队约 {restaurant.queue_minutes} 分钟")
                if restaurant.recommended_dishes:
                    st.markdown(f"**推荐菜：** {' · '.join(restaurant.recommended_dishes[:3])}")
            _render_right_column(
                rcols[1],
                positive_tags=restaurant.positive_review_tags,
                negative_tags=restaurant.negative_review_tags,
                specialty_tags=restaurant.specialty_tags,
                coupons=restaurant.restaurant_coupons,
                packages=restaurant.packages,
            )


def _render_timeline(plan: ItineraryPlan) -> None:
    from src.mock_api.restaurants import get_restaurant as _get_restaurant
    from src.mock_api.venues import get_venue as _get_venue
    from src.services.opening_hours import is_open_during

    _STEP_ICON = {"travel": "🚗", "activity": "🎯", "meal": "🍽", "return": "🏠", "addon": "➕"}

    def _opening_status(step) -> str:
        if step.step_type == "activity" and step.related_entity_id:
            venue = _get_venue(step.related_entity_id)
            if venue and hasattr(venue, "open_time") and venue.open_time:
                ok = is_open_during(venue.open_time, venue.close_time, step.start_time, step.end_time)
                return "🟢" if ok else "🔴"
        if step.step_type == "meal" and step.related_entity_id:
            rest = _get_restaurant(step.related_entity_id)
            if rest and hasattr(rest, "open_time") and rest.open_time:
                ok = is_open_during(rest.open_time, rest.close_time, step.start_time, step.end_time)
                return "🟢" if ok else "🔴"
        return ""

    with st.container(border=True):
        st.markdown("### 3. 时间线")
        rows = []
        for step in plan.steps:
            icon = _STEP_ICON.get(step.step_type, "")
            title_str = f"{icon} {step.title}".strip()
            if step.notes:
                title_str += f" ({step.notes})"
            rows.append({
                "时间": f"{step.start_time} – {step.end_time}",
                "步骤": title_str,
                "地点": step.location_name,
                "区域": step.area or "—",
                "时长": f"{step.duration_minutes} min",
                "营业": _opening_status(step),
            })
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
                "耗时": _fmt_elapsed(trace.get("elapsed_ms", 0)),
            }
            for trace in traces
        ]
        st.dataframe(rows, hide_index=True, use_container_width=True)


_SEARCH_TOOLS = {
    "search_venues", "search_venues_fallback", "search_restaurants",
    "search_restaurants_meal_only", "search_venues_tooFar_wide",
    "search_venues_evening_wide", "search_restaurants_cuisine_wider",
}
_CHECK_TOOLS = {
    "check_venue_availability", "check_restaurant_availability",
    "search_venues_alt", "search_restaurants_alt_base",
}


def _count_results(output) -> int:
    if isinstance(output, list):
        return len(output)
    if isinstance(output, dict):
        for key in ("count", "results", "items"):
            v = output.get(key)
            if isinstance(v, list):
                return len(v)
            if isinstance(v, int):
                return v
    return 0


def _render_planning_chain(traces: list[dict], intent, plan) -> None:
    with st.container(border=True):
        st.markdown("#### 规划链路摘要")
        rows = []

        src_lbl = "LLM" if getattr(intent, "source", "") == "llm" else "规则"
        scenario = _SCENARIO_LABEL.get(intent.scenario_type, intent.scenario_type)
        rows.append({"阶段": "需求理解", "状态": "✅",
                     "摘要": f"{scenario} {intent.group_size}人 · {src_lbl}"})

        search_ts = [t for t in traces if t.get("tool_name") in _SEARCH_TOOLS]
        venue_cnt = sum(
            _count_results(t.get("output"))
            for t in search_ts if "venue" in t.get("tool_name", "")
        )
        rest_cnt = sum(
            _count_results(t.get("output"))
            for t in search_ts if "restaurant" in t.get("tool_name", "")
        )
        ms_s = sum(t.get("elapsed_ms", 0) for t in search_ts)
        rows.append({"阶段": "候选召回", "状态": "✅" if search_ts else "—",
                     "摘要": f"{venue_cnt}家场馆  {rest_cnt}家餐厅  ({ms_s:.0f}ms)"})

        check_ts = [t for t in traces if t.get("tool_name") in _CHECK_TOOLS]
        adjusted = any("alt" in t.get("tool_name", "") for t in check_ts)
        ms_c = sum(t.get("elapsed_ms", 0) for t in check_ts)
        status_c = "⚠" if adjusted else ("✅" if check_ts else "—")
        note_c = "有调整" if adjusted else ("通过" if check_ts else "跳过")
        rows.append({"阶段": "可行性过滤", "状态": status_c,
                     "摘要": f"{note_c}  ({ms_c:.0f}ms)"})

        sb = plan.score_breakdown
        rows.append({"阶段": "多维排序", "状态": "✅",
                     "摘要": (
                         f"综合{plan.score:.2f}  距离{sb.distance_score:.2f}  "
                         f"适配{sb.group_fit_score:.2f}  餐厅{sb.restaurant_score:.2f}"
                     )})

        rows.append({"阶段": "生成执行计划", "状态": "✅",
                     "摘要": f"{plan.title}  ·  {plan.stop_count}站"})

        st.dataframe(rows, hide_index=True, use_container_width=True)


def _build_exec_detail(result, plan, intent) -> str:
    import src.mock_api as mock
    ref = result.booking_id or result.order_id or ""
    ref_str = f" 确认号：{ref}" if ref else ""
    if result.action_type == "book_venue" and plan.venue_id:
        v = mock.get_venue(plan.venue_id)
        name = getattr(v, "name", plan.venue_id)
        step = next((s for s in plan.steps if s.step_type == "activity"), None)
        t = step.start_time if step else ""
        n = getattr(intent, "group_size", 1)
        return f"{name} · {n}张 · 入场 {t}{ref_str}" if t else f"{name} · {n}张{ref_str}"
    if result.action_type == "reserve_restaurant" and plan.restaurant_id:
        res = mock.get_restaurant(plan.restaurant_id)
        name = getattr(res, "name", plan.restaurant_id)
        step = next((s for s in plan.steps if s.step_type == "meal"), None)
        t = step.start_time if step else ""
        n = getattr(intent, "group_size", 1)
        return f"{name} · {n}人 · {t}{ref_str}" if t else f"{name} · {n}人{ref_str}"
    return result.message or ref_str.strip()


def _render_execution(execute, plan, intent) -> None:
    with st.container(border=True):
        st.markdown("### 4. 执行结果")
        if not execute.results:
            st.caption("（无需执行操作）")
        else:
            rows = []
            for result in execute.results:
                label = _ACTION_LABELS.get(result.action_type, result.action_type)
                status = _STATUS_LABELS.get(result.status, result.status)
                detail = _build_exec_detail(result, plan, intent)
                rows.append({"操作": label, "状态": status, "详情": detail})
            st.dataframe(rows, hide_index=True, use_container_width=True)

        st.markdown("**分享消息**（点击右上角图标复制）")
        st.code(execute.share_message.message, language=None)

        st.subheader("下一步提醒")
        reminders = []
        if any(r.action_type == "book_venue" and r.status == "success" for r in execute.results):
            reminders.append("📋 查看门票确认信息，按时到场")
        if any(r.action_type == "reserve_restaurant" and r.status == "success" for r in execute.results):
            reminders.append("🍽 餐厅预约已确认，注意保留时间")
        reminders.append("🪪 出行请携带证件")
        if plan.warnings:
            reminders.append("⚠ 查看行程备注，注意风险提示")
        for rem in reminders:
            st.write(rem)


def _run_generate(user_input: str) -> None:
    client = make_client()
    try:
        with st.spinner("生成计划中..."):
            response = client.generate(user_input)
        st.session_state["last_generate"] = response
        st.session_state.pop("last_execute", None)
        st.session_state["selected_plan_idx"] = 0
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


def _run_revise(revision_text: str, current_plan: ItineraryPlan) -> None:
    generate: GenerateResponse | None = st.session_state.get("last_generate")
    if generate is None:
        st.error("请先生成计划。")
        return
    client = make_client()
    try:
        with st.spinner("调整方案中..."):
            response = client.revise(revision_text, generate.intent, current_plan)
        st.session_state["last_generate"] = response
        st.session_state.pop("last_execute", None)
        st.session_state["selected_plan_idx"] = 0
    except Exception as exc:
        st.error(f"调整失败：{exc}")


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

    if not generate.plan.feasible or generate.plan.score <= 0.05:
        st.warning("⚠️ 当前未找到完全匹配的方案，以下为最接近推荐")

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

    if not selected_plan.feasible:
        st.caption("🔴 此方案存在约束冲突（如营业时间），仅供参考")

    _render_plan_card(selected_plan, group_size=generate.intent.group_size)
    _render_timeline(selected_plan)
    _render_planning_chain(generate.traces, generate.intent, selected_plan)
    _render_trace_expander(generate.traces)

    # Revision UI — only shown before execution
    if st.session_state.get("last_execute") is None:
        with st.container(border=True):
            st.markdown("#### 想调整方案？")
            with st.form("revision_form"):
                rev_col, btn_col = st.columns([5, 1])
                with rev_col:
                    revision_text = st.text_input(
                        "调整意见",
                        placeholder="太远了 / 便宜点 / 不想排队 / 想吃日料 / 室内一点 / 换个餐厅",
                        label_visibility="collapsed",
                    )
                with btn_col:
                    revise_clicked = st.form_submit_button(
                        "调整方案",
                        use_container_width=True,
                    )
        if revise_clicked and revision_text.strip():
            _run_revise(revision_text.strip(), selected_plan)
            st.rerun()

    execute_clicked = st.button(
        "确认并执行",
        type="primary",
        disabled=st.session_state.get("last_execute") is not None,
    )
    if execute_clicked:
        _run_execute(selected_plan)

    execute: ExecuteResponse | None = st.session_state.get("last_execute")
    if execute is not None:
        _render_execution(execute, selected_plan, generate.intent)
        _render_trace_expander(execute.traces)


main()
