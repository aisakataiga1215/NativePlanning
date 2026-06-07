from __future__ import annotations

import os
import re

from src.schemas.order import ExecutionResult, ShareMessage
from src.schemas.plan import ItineraryPlan
from src.schemas.user_intent import UserIntent

_FAMILY_TEMPLATE = (
    "搞定了！{date}{time}出发，我们先去{venue_name}，"
    "{meal_time}去{restaurant_name}吃饭。"
    "{booking_note}"
    "估计{return_time}左右到家。"
)
_FRIENDS_TEMPLATE = (
    "安排好了！{date}{time}出发，先去{venue_name}，"
    "然后{meal_time}在{restaurant_name}吃饭。"
    "{booking_note}"
)
_COUPLE_TEMPLATE = (
    "安排好了！{date}{time}出发，先去{venue_name}，"
    "{meal_time}再去{restaurant_name}共进晚餐。"
    "{booking_note}"
)
_SENIOR_TEMPLATE = (
    "帮您安排好了：{date}{time}出发，先去{venue_name}，"
    "{meal_time}在{restaurant_name}用餐，行程轻松舒适。"
    "{booking_note}"
)
_FALLBACK_TEMPLATE = (
    "计划已安排：{date}{time}出发，前往{venue_name}，之后在{restaurant_name}用餐。"
    "{booking_note}"
)

_FAMILY_NO_MEAL_TEMPLATE = (
    "搞定了！{date}{time}出发，我们去{venue_name}玩。"
    "{booking_note}"
    "估计{return_time}左右到家。"
)
_FRIENDS_NO_MEAL_TEMPLATE = (
    "安排好了！{date}{time}出发，去{venue_name}玩。"
    "{booking_note}"
)
_COUPLE_NO_MEAL_TEMPLATE = (
    "安排好了！{date}{time}出发，去{venue_name}约会。"
    "{booking_note}"
)
_FALLBACK_NO_MEAL_TEMPLATE = (
    "计划已安排：{date}{time}出发，前往{venue_name}。{booking_note}"
)


def _booking_note(results: list[ExecutionResult]) -> str:
    notes = []
    for r in results:
        if r.status == "success":
            if r.booking_id:
                notes.append(r.message)
            elif r.order_id:
                notes.append(r.message)
        else:
            notes.append(f"⚠ {r.message}")
    if notes:
        return "（" + "；".join(notes) + "）"
    return ""


def _venue_name(plan: ItineraryPlan) -> str:
    step = next((s for s in plan.steps if s.step_type == "activity"), None)
    return step.location_name if step else "目的地"


def _restaurant_name(plan: ItineraryPlan) -> str:
    step = next((s for s in plan.steps if s.step_type == "meal"), None)
    return step.location_name if step else "餐厅"


def _llm_message(
    plan: ItineraryPlan,
    results: list[ExecutionResult],
    intent: UserIntent,
) -> str | None:
    """Generate share message via LLM. Returns None on any failure."""
    try:
        from openai import OpenAI
    except ImportError:
        return None

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    kwargs: dict = {"api_key": api_key}
    base_url = os.getenv("OPENAI_BASE_URL")
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    venue = _venue_name(plan)
    restaurant = _restaurant_name(plan)
    meal_step = next((s for s in plan.steps if s.step_type == "meal"), None)
    meal_time = meal_step.start_time if meal_step else ""
    booking = _booking_note(results)
    date_str = "今天" if intent.date == "today" else intent.date

    meal_part = f"餐厅：{meal_time}去{restaurant}。" if meal_step else "不安排正餐。"
    summary = (
        f"场景：{intent.scenario_type}，{intent.group_size}人，"
        f"{date_str}{intent.time}出发。"
        f"活动地点：{venue}。"
        f"{meal_part}"
        f"{booking}"
    )
    if plan.warnings:
        summary += " 注意：" + "；".join(plan.warnings)

    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=0.3,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是家庭活动助理，用温暖自然的中文写一条给家人或朋友的分享消息，"
                        "语气活泼，不超过100字，不要包含英文。"
                    ),
                },
                {"role": "user", "content": summary},
            ],
        )
        text = resp.choices[0].message.content
        if text:
            return text.strip()
    except Exception:
        pass
    return None


def _filter_warnings(
    warnings: list[str],
    current_restaurant_id: str | None,
    current_venue_id: str | None,
) -> list[str]:
    """Keep fallback-explanation warnings; drop only stale entity-specific ones."""
    import src.mock_api as mock
    rest = mock.get_restaurant(current_restaurant_id) if current_restaurant_id else None
    venue = mock.get_venue(current_venue_id) if current_venue_id else None
    current_names = {
        n for n in [getattr(rest, "name", None), getattr(venue, "name", None)] if n
    }
    kept = []
    for w in warnings:
        if "已切换至" in w:
            kept.append(w)
            continue
        named = re.findall(r"「([^」]+)」", w)
        if not named:
            kept.append(w)
            continue
        if any(n in current_names for n in named):
            kept.append(w)
    return kept


def _exec_context_note(results: list[ExecutionResult], has_meal: bool) -> str:
    if not has_meal or not results:
        return ""
    rest_result = next(
        (r for r in results if r.action_type == "reserve_restaurant"), None
    )
    if rest_result and rest_result.status in ("failed", "skipped"):
        return "\n⚠ 餐厅预约未完成，请提前联系餐厅确认"
    return ""


def _template_message(
    plan: ItineraryPlan,
    results: list[ExecutionResult],
    intent: UserIntent,
) -> tuple[str, str]:
    """Return (message, receiver_type) using templates."""
    venue_name = _venue_name(plan)
    restaurant_name = _restaurant_name(plan)
    return_step = next((s for s in plan.steps if s.step_type == "return"), None)
    meal_step = next((s for s in plan.steps if s.step_type == "meal"), None)

    date_str = "今天" if intent.date == "today" else intent.date
    meal_time = meal_step.start_time if meal_step else ""
    return_time = return_step.end_time if return_step else ""
    note = _booking_note(results)
    has_meal = bool(plan.restaurant_id)

    if intent.scenario_type == "family":
        has_senior = any(p.age_group == "senior" for p in (intent.participants or []))
        if has_senior:
            if has_meal:
                msg = _SENIOR_TEMPLATE.format(
                    date=date_str, time=intent.time,
                    venue_name=venue_name, meal_time=meal_time,
                    restaurant_name=restaurant_name, booking_note=note,
                )
            else:
                msg = _FAMILY_NO_MEAL_TEMPLATE.format(
                    date=date_str, time=intent.time,
                    venue_name=venue_name, booking_note=note,
                    return_time=return_time,
                )
        else:
            if has_meal:
                msg = _FAMILY_TEMPLATE.format(
                    date=date_str, time=intent.time,
                    venue_name=venue_name, meal_time=meal_time,
                    restaurant_name=restaurant_name, booking_note=note,
                    return_time=return_time,
                )
            else:
                msg = _FAMILY_NO_MEAL_TEMPLATE.format(
                    date=date_str, time=intent.time,
                    venue_name=venue_name, booking_note=note,
                    return_time=return_time,
                )
        receiver = "wife"
    elif intent.scenario_type == "couple":
        if has_meal:
            msg = _COUPLE_TEMPLATE.format(
                date=date_str, time=intent.time,
                venue_name=venue_name, meal_time=meal_time,
                restaurant_name=restaurant_name, booking_note=note,
            )
        else:
            msg = _COUPLE_NO_MEAL_TEMPLATE.format(
                date=date_str, time=intent.time,
                venue_name=venue_name, booking_note=note,
            )
        receiver = "partner"
    elif intent.scenario_type == "friends":
        if has_meal:
            msg = _FRIENDS_TEMPLATE.format(
                date=date_str, time=intent.time,
                venue_name=venue_name, meal_time=meal_time,
                restaurant_name=restaurant_name, booking_note=note,
            )
        else:
            msg = _FRIENDS_NO_MEAL_TEMPLATE.format(
                date=date_str, time=intent.time,
                venue_name=venue_name, booking_note=note,
            )
        receiver = "friend_group"
    else:
        if has_meal:
            msg = _FALLBACK_TEMPLATE.format(
                date=date_str, time=intent.time,
                venue_name=venue_name,
                restaurant_name=restaurant_name, booking_note=note,
            )
        else:
            msg = _FALLBACK_NO_MEAL_TEMPLATE.format(
                date=date_str, time=intent.time,
                venue_name=venue_name, booking_note=note,
            )
        receiver = "unknown"

    msg += _exec_context_note(results, has_meal)
    filtered = _filter_warnings(plan.warnings or [], plan.restaurant_id, plan.venue_id)
    if filtered:
        msg += "\n备注：" + "；".join(filtered)

    return msg, receiver


def generate_share_message(
    plan: ItineraryPlan,
    results: list[ExecutionResult],
    intent: UserIntent,
) -> ShareMessage:
    receiver = (
        "wife" if intent.scenario_type == "family"
        else "partner" if intent.scenario_type == "couple"
        else "friend_group" if intent.scenario_type == "friends"
        else "unknown"
    )

    llm_text = _llm_message(plan, results, intent)
    if llm_text:
        return ShareMessage(
            receiver_type=receiver,
            included_plan_id=plan.id,
            message=llm_text,
        )

    msg, receiver = _template_message(plan, results, intent)
    return ShareMessage(
        receiver_type=receiver,
        included_plan_id=plan.id,
        message=msg,
    )
