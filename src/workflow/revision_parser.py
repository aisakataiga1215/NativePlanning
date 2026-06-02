"""Intent revision parser.

`apply_revision` takes an existing UserIntent, a short free-text revision
(e.g. "太远了", "想吃日料"), and optionally the current plan, and returns
a new UserIntent with the relevant fields updated.

Only one turn of revision is supported. The caller decides whether to persist
the result and re-run the planning pipeline.
"""
from __future__ import annotations

import re
from typing import Callable

from src.schemas.plan import ItineraryPlan
from src.schemas.user_intent import UserIntent


def _contains(text: str, keywords: list[str]) -> bool:
    return any(kw in text for kw in keywords)


def apply_revision(
    intent: UserIntent,
    revision_text: str,
    current_plan: ItineraryPlan | None = None,
) -> UserIntent:
    """Return a new UserIntent with fields updated per `revision_text`.

    Rules are applied in a single pass; all matching rules contribute to the
    final merged update dict. Unmentioned fields are preserved unchanged.
    """
    updates: dict = {}
    text = revision_text.strip()
    updates["revision_scope"] = ""  # always clear scope first to prevent cross-revision pollution

    # --- distance ---
    if _contains(text, ["太远", "近一点", "近点", "近一些", "远了", "有点远",
                        "不要太远", "别太远", "离近点"]):
        updates["max_distance_km"] = max(2.0, round(intent.max_distance_km * 0.6, 1))

    if _contains(text, ["太近了", "太近", "近了", "有点近", "再远一点", "稍微远",
                        "远一点", "远点", "范围大一点", "扩大范围", "不用那么近",
                        "去远点", "走远点", "能远点"]):
        updates["max_distance_km"] = min(15.0, round(intent.max_distance_km * 1.5, 1))

    # --- budget ---
    if _contains(text, ["便宜", "省钱", "实惠", "预算少", "花钱少",
                        "太贵了", "贵了", "有点贵", "不要太贵", "别太贵"]):
        updates["budget_preference"] = "low"

    if _contains(text, ["贵一点没关系", "不差钱", "预算充足", "价格不限", "可以贵", "钱不是问题"]):
        updates["budget_preference"] = "high"

    # --- no queue ---
    if _contains(text, ["不想排队", "排队", "人少", "不排队", "避免排队",
                        "人太多", "太多人", "等太久", "不想等", "人挤人"]):
        new_hc = list(intent.hard_constraints)
        if "avoid_long_queue" not in new_hc:
            new_hc.append("avoid_long_queue")
        updates["hard_constraints"] = new_hc

    # --- avoid walk ---
    if _contains(text, ["太累", "走路少", "轻松", "不想走", "少走", "走路累",
                        "有点累", "腿酸", "走不动", "腿疼"]):
        new_hc = list(updates.get("hard_constraints", intent.hard_constraints))
        if "avoid_long_walk" not in new_hc:
            new_hc.append("avoid_long_walk")
        updates["hard_constraints"] = new_hc
        new_sp = list(intent.soft_preferences)
        if "low_burden" not in new_sp:
            new_sp.append("low_burden")
        updates["soft_preferences"] = new_sp

    # --- indoor ---
    if _contains(text, ["室内", "不想晒", "天热", "下雨", "避暑",
                        "太晒了", "热死了", "怕热", "怕晒"]):
        new_hc = list(updates.get("hard_constraints", intent.hard_constraints))
        if "indoor" not in new_hc:
            new_hc.append("indoor")
        updates["hard_constraints"] = new_hc

    # --- outdoor ---
    if _contains(text, ["想去公园", "户外", "散步", "公园"]):
        updates["requested_activities"] = ["park_walk"]
        new_hc = list(updates.get("hard_constraints", intent.hard_constraints))
        if "indoor" in new_hc:
            new_hc.remove("indoor")
        updates["hard_constraints"] = new_hc

    # --- specific activities (only set when not already overridden) ---
    if "requested_activities" not in updates:
        if _contains(text, ["看展", "展览", "美术馆", "博物馆", "艺术"]):
            updates["requested_activities"] = ["exhibition"]
            updates["revision_scope"] = "venue_only"
        elif _contains(text, ["电影", "看电影", "影院", "影城"]):
            updates["requested_activities"] = ["movie"]
            updates["revision_scope"] = "venue_only"
        elif _contains(text, ["桌游"]):
            updates["requested_activities"] = ["board_game"]
            updates["revision_scope"] = "venue_only"
        elif _contains(text, ["茶馆", "喝茶", "品茶"]):
            updates["requested_activities"] = ["tea_house"]
            updates["revision_scope"] = "venue_only"
        elif _contains(text, ["密室", "逃脱"]):
            updates["requested_activities"] = ["escape_room"]
            updates["revision_scope"] = "venue_only"

    # --- change venue ("换个场地") ---
    if _contains(text, ["换个场地", "不想去这个", "换个地方", "换地方"]):
        updates["requested_activities"] = []
        updates["activity_preferences"] = []
        updates["location_anchor"] = ""
        updates["revision_scope"] = "venue_only"
        if current_plan and current_plan.venue_id:
            new_av = list(intent.avoid_venue_ids)
            if current_plan.venue_id not in new_av:
                new_av.append(current_plan.venue_id)
            updates["avoid_venue_ids"] = new_av

    # --- specific meals ---
    if "requested_meals" not in updates:
        if _contains(text, ["日料", "日式", "寿司", "刺身", "拉面"]):
            updates["requested_meals"] = ["japanese"]
            updates["revision_scope"] = "restaurant_only"
        elif _contains(text, ["火锅"]):
            updates["requested_meals"] = ["hotpot"]
            updates["revision_scope"] = "restaurant_only"
        elif _contains(text, ["烤肉", "烧烤", "BBQ", "bbq"]):
            updates["requested_meals"] = ["bbq"]
            updates["revision_scope"] = "restaurant_only"
        elif _contains(text, ["咖啡", "下午茶", "奶茶", "茶饮"]):
            updates["requested_meals"] = ["coffee"]
            updates["revision_scope"] = "restaurant_only"
        elif _contains(text, ["西餐", "西式", "披萨", "意面", "牛排"]):
            updates["requested_meals"] = ["western"]
            updates["revision_scope"] = "restaurant_only"
        elif _contains(text, ["中餐", "家常", "中式"]):
            updates["requested_meals"] = ["chinese"]
            updates["revision_scope"] = "restaurant_only"

    # --- change restaurant ("换个餐厅") ---
    if _contains(text, ["换个餐厅", "不想吃这家", "换家餐厅", "换餐厅"]):
        updates["requested_meals"] = []
        updates["meal_preferences"] = []
        updates["revision_scope"] = "restaurant_only"
        if current_plan and current_plan.restaurant_id:
            new_ar = list(intent.avoid_restaurant_ids)
            if current_plan.restaurant_id not in new_ar:
                new_ar.append(current_plan.restaurant_id)
            updates["avoid_restaurant_ids"] = new_ar

    # --- location anchor ---
    # "去XX附近" / "先去XX" in revision text → update anchor
    _ANCHOR_RE = re.compile(r"先去(\S{2,4})|去(\S{2,4})附近|在(\S{2,4})附近")
    m = _ANCHOR_RE.search(text)
    if m:
        new_anchor = next(g for g in m.groups() if g is not None)
        updates["location_anchor"] = new_anchor.rstrip("的地")

    # "换个区域" / "换个方向" → clear anchor without implying venue change
    if _contains(text, ["换个区域", "换个方向", "不用在那边"]):
        updates["location_anchor"] = ""

    return intent.model_copy(update=updates)
