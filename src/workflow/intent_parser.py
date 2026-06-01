from __future__ import annotations

import json
import os
import re
from typing import Literal, Optional

from pydantic import BaseModel, ValidationError

from src.schemas.user_intent import Participant, PersonProfile, UserIntent

# ── Participant detection keywords ────────────────────────────────────────────

_CHILD_PRESENCE_KEYWORDS = ("孩子", "宝宝", "小孩", "娃", "儿子", "女儿", "小朋友")
_SENIOR_KEYWORDS = ("爷爷", "奶奶", "外公", "外婆", "爸妈", "父母", "老人", "长辈", "老年人")
_COUPLE_KEYWORDS = ("情侣", "恋人", "约会", "女朋友", "男朋友", "对象", "媳妇", "夫妻二人", "两人世界")
_COUPLE_SPOUSE_KEYWORDS = ("老婆", "老公")   # only match when no child-presence keywords
_FRIENDS_KEYWORDS = ("朋友", "同学", "小伙伴", "闺蜜", "哥们", "战友", "校友",
                     "师生", "老同学", "同班", "聚会", "好友")
_COLLEAGUE_KEYWORDS = ("同事", "团建", "公司", "部门")

# ── Explicit activity/meal request mappings ───────────────────────────────────

_ACTIVITY_REQUEST_MAP: dict[str, str] = {
    "亲子乐园": "kids_playground",
    "儿童乐园": "kids_playground",
    "亲子馆":   "kids_playground",
    "看展":    "exhibition",
    "展览":    "exhibition",
    "美术馆":  "exhibition",
    "博物馆":  "museum",
    "公园":    "park_walk",
    "湖边":    "park_walk",
    "散步":    "park_walk",
    "电影":    "movie",
    "影院":    "movie",
    "看电影":  "movie",
    "密室":    "escape_room",
    "剧本杀":  "escape_room",
    "攀岩":    "climbing",
    "citywalk": "citywalk",
    "小吃街":  "citywalk",
    "逛街":    "citywalk",
    "骑行":    "cycling",
    "骑车":    "cycling",
}

_MEAL_REQUEST_MAP: dict[str, str] = {
    "火锅":    "hotpot",
    "烤肉":    "bbq",
    "日料":    "japanese",
    "日本料理": "japanese",
    "西餐":    "western",
    "咖啡":    "coffee",
    "奶茶":    "bubble_tea",
    "轻食":    "healthy_food",
    "减肥":    "healthy_food",
    "健康饮食": "healthy_food",
}

# ── Distance thresholds ────────────────────────────────────────────────────────
# NEAR must be checked before FAR (some near-phrases contain "远")

_NEAR_KEYWORDS = ("离家近", "附近", "不用太远", "别太远", "就近", "周边", "不远", "近一点", "太远")
_SOMEWHAT_FAR_KEYWORDS = ("稍微远", "远一点", "稍远")
_FAR_KEYWORDS = ("不限", "很远", "尽量远", "无所谓远近", "远点也行")

# ── Duration patterns ─────────────────────────────────────────────────────────

_AGE_PATTERN = re.compile(r"(\d+)\s*岁")
_HOURS_PATTERN = re.compile(r"([一二三四五六七八九十\d]+)\s*个?\s*小时")
_CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
           "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

# ── LLM output schema ────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """你是本地生活活动规划助理。从用户消息中提取活动安排意图。

严格输出以下JSON格式，不添加任何说明文字：
{
  "scenario_type": "solo" | "couple" | "family" | "friends" | "colleagues" | "unknown",
  "group_size": 总人数（含用户，整数），
  "time": "HH:MM"（24小时制出发时间，如"14:00"），
  "duration_hours": 活动时长（小时，如5.0），
  "max_distance_km": 最远距离（千米），
  "activity_preferences": ["标签1", "标签2"],
  "meal_preferences": ["标签1", "标签2"],
  "budget_preference": "low" | "medium" | "high"
}

规则：
- 有孩子/宝宝/儿童 → scenario_type="family"
- 老婆/老公 且无孩子 → scenario_type="couple"
- 朋友/同学/聚会 → scenario_type="friends"
- 同事/团建/公司 → scenario_type="colleagues"
- "下午" → time="14:00"，"傍晚"/"晚上" → time="17:00"，"上午"/"早上" → time="10:00"
- "一整天"/"全天" → duration_hours=8.0，"半天" → duration_hours=4.0
- "离家近"/"附近"/"别太远" → max_distance_km=6.0
- "稍微远"/"远一点" → max_distance_km=10.0
- "不限"/"很远" → max_distance_km=20.0
- 未提及距离 → max_distance_km=6.0
- 未提及时长 → duration_hours=5.0"""


class UserIntentLLM(BaseModel):
    """Lightweight model for LLM output. All fields have defaults for partial responses."""

    scenario_type: Literal["solo", "couple", "family", "friends", "colleagues", "unknown"] = "unknown"
    group_size: int = 2
    time: str = "14:00"
    duration_hours: float = 5.0
    max_distance_km: float = 6.0
    activity_preferences: list[str] = []
    meal_preferences: list[str] = []
    budget_preference: Literal["low", "medium", "high"] = "medium"


def _make_client():
    """Return an OpenAI-compatible client, or None if OPENAI_API_KEY not set."""
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
    return OpenAI(**kwargs)


def _llm_to_intent(llm: UserIntentLLM, raw_input: str) -> UserIntent:
    """Convert UserIntentLLM to UserIntent, adding scenario-specific defaults."""
    prefs = list(llm.activity_preferences)
    soft_prefs: list[str] = []
    if llm.scenario_type == "family":
        if "parent_child" not in prefs:
            prefs.append("parent_child")
        if "kids" not in prefs:
            prefs.append("kids")
    elif llm.scenario_type == "couple":
        for p in ("romantic", "photo", "walk"):
            if p not in prefs:
                prefs.append(p)
    elif llm.scenario_type == "friends":
        if "social" not in prefs:
            prefs.append("social")
    elif llm.scenario_type == "colleagues":
        soft_prefs = ["business_casual", "not_too_private"]
        for p in ("group_friendly", "quiet", "transport_convenient"):
            if p not in prefs:
                prefs.append(p)
    return UserIntent(
        scenario_type=llm.scenario_type,
        group_size=llm.group_size,
        date="today",
        time=llm.time,
        duration_hours=llm.duration_hours,
        max_distance_km=llm.max_distance_km,
        activity_preferences=prefs,
        meal_preferences=list(llm.meal_preferences),
        soft_preferences=soft_prefs,
        budget_preference=llm.budget_preference,
        raw_input=raw_input,
        source="llm",
    )


def _llm_parse(user_input: str, client) -> UserIntent:
    """Try Structured Outputs → json_object → rule-based fallback."""
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]
    _last_exc: Exception | None = None

    # ── 1. Structured Outputs (preferred) ────────────────────────────────────
    try:
        response = client.beta.chat.completions.parse(
            model=model,
            messages=messages,
            response_format=UserIntentLLM,
            temperature=0,
        )
        parsed = response.choices[0].message.parsed
        if parsed is not None:
            return _llm_to_intent(parsed, user_input)
    except Exception as exc:
        _last_exc = exc

    # ── 2. json_object mode ───────────────────────────────────────────────────
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        allowed = set(UserIntentLLM.model_fields)
        llm = UserIntentLLM(**{k: v for k, v in data.items() if k in allowed})
        return _llm_to_intent(llm, user_input)
    except Exception as exc:
        _last_exc = exc

    # ── 3. Rule-based fallback — record why LLM failed ───────────────────────
    result = _rule_fallback(user_input)
    if _last_exc is not None:
        result = result.model_copy(update={
            "warnings": list(result.warnings) + [
                f"LLM 调用失败，已降级到规则解析：{type(_last_exc).__name__}: {_last_exc}"
            ]
        })
    return result


def _classify_age_group(age: int) -> str:
    if age <= 6:  return "young_child"
    if age <= 12: return "child"
    if age <= 17: return "teenager"
    if age <= 25: return "young_adult"
    if age <= 59: return "adult"
    return "senior"


def _parse_duration_hours(text: str) -> float:
    if any(k in text for k in ("一整天", "全天", "整天", "一天")): return 8.0
    if any(k in text for k in ("半天", "半日")): return 4.0
    m = _HOURS_PATTERN.search(text)
    if m:
        raw = m.group(1)
        n = int(raw) if raw.isdigit() else _CN_NUM.get(raw, 5)
        return max(1.0, min(12.0, float(n)))
    if any(k in text for k in ("几个小时", "几小时")): return 4.0
    return 5.0


def _detect_participants(text: str) -> list[Participant]:
    """Extract participant list from natural language text."""
    participants: list[Participant] = [Participant(role="self", age_group="adult")]

    if any(k in text for k in ("老婆", "媳妇", "妻子", "太太")):
        participants.append(Participant(role="spouse", age_group="adult"))
    if any(k in text for k in ("老公", "丈夫", "先生")):
        participants.append(Participant(role="spouse", age_group="adult"))
    if any(k in text for k in ("女朋友",)):
        participants.append(Participant(role="partner", age_group="adult"))
    if any(k in text for k in ("男朋友",)):
        participants.append(Participant(role="partner", age_group="adult"))
    if any(k in text for k in ("对象", "恋人")):
        participants.append(Participant(role="partner", age_group="adult"))

    # Children
    if any(k in text for k in _CHILD_PRESENCE_KEYWORDS):
        child_ages = [int(m.group(1)) for m in _AGE_PATTERN.finditer(text) if int(m.group(1)) < 20]
        if child_ages:
            for ca in child_ages:
                participants.append(Participant(role="child", age=ca, age_group=_classify_age_group(ca)))
        else:
            participants.append(Participant(role="child", age_group="child"))

    # Seniors — each keyword adds one participant
    _SENIOR_SINGLE = ("爷爷", "奶奶", "外公", "外婆", "老人")
    for kw in _SENIOR_SINGLE:
        if kw in text:
            participants.append(Participant(role="elderly", age_group="senior"))
    # 爸妈/父母/爸爸妈妈 → two parents (default adult, senior if age hint ≥60)
    if any(k in text for k in ("爸妈", "父母", "爸爸妈妈")):
        senior_ages = [int(m.group(1)) for m in _AGE_PATTERN.finditer(text) if int(m.group(1)) >= 55]
        grp = _classify_age_group(senior_ages[0]) if senior_ages else "adult"
        participants.append(Participant(role="parent", age_group=grp))
        participants.append(Participant(role="parent", age_group=grp))

    # Friends / colleagues (add a few representative participants for group_size estimation)
    if any(k in text for k in _FRIENDS_KEYWORDS):
        for _ in range(2):
            participants.append(Participant(role="friend", age_group="young_adult"))
    if any(k in text for k in _COLLEAGUE_KEYWORDS):
        for _ in range(2):
            participants.append(Participant(role="colleague", age_group="adult"))

    return participants


def _extract_requests(text: str) -> tuple[list[str], list[str], list[str]]:
    """Extract (requested_activities, requested_meals, requested_places) from text."""
    req_acts: list[str] = []
    req_meals: list[str] = []
    req_places: list[str] = []
    for kw, tag in _ACTIVITY_REQUEST_MAP.items():
        if kw in text and tag not in req_acts:
            req_acts.append(tag)
    for kw, tag in _MEAL_REQUEST_MAP.items():
        if kw in text and tag not in req_meals:
            req_meals.append(tag)
    return req_acts, req_meals, req_places


def _rule_fallback(user_input: str) -> UserIntent:
    """Keyword-based intent extraction when LLM is unavailable or fails."""
    text = user_input

    has_child     = any(k in text for k in _CHILD_PRESENCE_KEYWORDS)
    has_senior    = any(k in text for k in _SENIOR_KEYWORDS)
    has_couple    = any(k in text for k in _COUPLE_KEYWORDS) or (
                    not has_child and any(k in text for k in _COUPLE_SPOUSE_KEYWORDS))
    has_friends   = any(k in text for k in _FRIENDS_KEYWORDS)
    has_colleagues = any(k in text for k in _COLLEAGUE_KEYWORDS)

    participants = _detect_participants(text)
    req_acts, req_meals, req_places = _extract_requests(text)

    # Scenario: child/senior → family; couple; colleagues; friends; unknown
    if has_child or has_senior:
        scenario: Literal["solo", "couple", "family", "friends", "colleagues", "unknown"] = "family"
        act_prefs = ["parent_child", "kids", "family_friendly"] if has_child else ["family_friendly", "walk"]
        meal_prefs = ["kid_friendly", "healthy"] if has_child else ["healthy", "group_friendly"]
    elif has_couple:
        scenario = "couple"
        act_prefs = ["romantic", "photo", "walk"]
        meal_prefs = ["romantic", "affordable"]
    elif has_colleagues:
        scenario = "colleagues"
        act_prefs = ["group_friendly", "transport_convenient", "quiet", "not_too_private"]
        meal_prefs = ["group_friendly", "business_casual"]
    elif has_friends:
        scenario = "friends"
        act_prefs = ["social", "photo"]
        meal_prefs = ["social", "affordable"]
    else:
        scenario = "unknown"
        act_prefs = []
        meal_prefs = []

    hard_constraints: list[str] = []
    soft_prefs: list[str] = []
    warnings: list[str] = []

    if has_senior:
        soft_prefs += ["elderly_friendly", "low_burden"]
        hard_constraints += ["avoid_long_walk", "avoid_long_queue"]
    if has_colleagues:
        soft_prefs += ["business_casual", "not_too_private"]

    if "kids_playground" in req_acts and not has_child:
        warnings.append("该活动通常更适合儿童家庭，已按您的明确要求保留。")

    # Time
    if any(k in text for k in ("上午", "早上")):    start_time = "10:00"
    elif any(k in text for k in ("傍晚", "晚上")):  start_time = "17:00"
    else:                                            start_time = "14:00"

    # Distance (NEAR checked before FAR to avoid "别太远" matching "远")
    if any(k in text for k in _NEAR_KEYWORDS):             max_km = 6.0
    elif any(k in text for k in _SOMEWHAT_FAR_KEYWORDS):   max_km = 10.0
    elif any(k in text for k in _FAR_KEYWORDS):            max_km = 20.0
    else:                                                   max_km = 6.0

    return UserIntent(
        scenario_type=scenario,
        group_size=max(2, len(participants)),
        date="today",
        time=start_time,
        duration_hours=_parse_duration_hours(text),
        max_distance_km=max_km,
        activity_preferences=act_prefs,
        meal_preferences=meal_prefs,
        requested_activities=req_acts,
        requested_meals=req_meals,
        requested_places=req_places,
        place_preferences=[],
        hard_constraints=hard_constraints,
        soft_preferences=soft_prefs,
        warnings=warnings,
        participants=participants,
        budget_preference="medium",
        raw_input=user_input,
        source="rule_based",
    )


# ── Fixture scenarios (MVP-0 backward-compatible) ────────────────────────────

_SCENARIOS: dict[str, UserIntent] = {
    "family": UserIntent(
        scenario_type="family",
        group_size=3,
        people=[
            PersonProfile(role="user", age_group="adult"),
            PersonProfile(role="wife", age_group="adult", diet_goal="weight_loss",
                          preferences=["healthy_food"], constraints=["avoid_high_calorie"]),
            PersonProfile(role="child", age=5, age_group="child"),
        ],
        date="today",
        time="14:00",
        duration_hours=5.0,
        max_distance_km=5.0,
        activity_preferences=["parent_child", "kids", "family_friendly"],
        meal_preferences=["low_calorie", "kid_friendly", "healthy"],
        budget_preference="medium",
        special_constraints=["child_friendly", "avoid_long_queue"],
        raw_input="今天下午想和老婆孩子出去玩几个小时，别离家太远，帮我安排一下",
    ),
    "friends": UserIntent(
        scenario_type="friends",
        group_size=4,
        people=[
            PersonProfile(role="friend", age_group="adult"),
            PersonProfile(role="friend", age_group="adult"),
            PersonProfile(role="friend", age_group="adult"),
            PersonProfile(role="friend", age_group="adult"),
        ],
        date="today",
        time="14:00",
        duration_hours=5.0,
        max_distance_km=8.0,
        activity_preferences=["social", "photo", "friends"],
        meal_preferences=["social", "affordable"],
        budget_preference="medium",
        special_constraints=[],
        raw_input="今天下午四个朋友想出去玩，拍拍照吃个饭，安排一下",
    ),
    "failure-no-seats": UserIntent(
        scenario_type="family",
        group_size=3,
        people=[
            PersonProfile(role="user", age_group="adult"),
            PersonProfile(role="wife", age_group="adult", diet_goal="weight_loss"),
            PersonProfile(role="child", age=5, age_group="child"),
        ],
        date="today",
        time="14:00",
        duration_hours=5.0,
        max_distance_km=5.0,
        activity_preferences=["parent_child", "kids"],
        meal_preferences=["low_calorie", "kid_friendly"],
        budget_preference="medium",
        special_constraints=["child_friendly"],
        raw_input="今天下午亲子出行，但餐厅没有位子的情况",
    ),
    "failure-no-tickets": UserIntent(
        scenario_type="family",
        group_size=3,
        people=[
            PersonProfile(role="user", age_group="adult"),
            PersonProfile(role="wife", age_group="adult"),
            PersonProfile(role="child", age=5, age_group="child"),
        ],
        date="today",
        time="14:00",
        duration_hours=5.0,
        max_distance_km=5.0,
        activity_preferences=["parent_child", "kids"],
        meal_preferences=["kid_friendly"],
        budget_preference="medium",
        special_constraints=["child_friendly"],
        raw_input="今天下午亲子出行，但场馆没有票的情况",
    ),
    "failure-time-conflict": UserIntent(
        scenario_type="family",
        group_size=3,
        people=[
            PersonProfile(role="user", age_group="adult"),
            PersonProfile(role="wife", age_group="adult"),
            PersonProfile(role="child", age=5, age_group="child"),
        ],
        date="today",
        time="16:30",
        duration_hours=3.0,
        max_distance_km=5.0,
        activity_preferences=["parent_child", "kids"],
        meal_preferences=["kid_friendly"],
        budget_preference="medium",
        special_constraints=["child_friendly"],
        raw_input="今天傍晚时间紧，亲子出行时间冲突的情况",
    ),
}


def parse_intent(scenario_key: str, raw_input: str | None = None) -> UserIntent:
    """Return fixture UserIntent by scenario key. Used by tests and failure scenarios."""
    intent = _SCENARIOS.get(scenario_key)
    if intent is None:
        raise ValueError(f"Unknown scenario: {scenario_key!r}. Available: {list(_SCENARIOS)}")
    if raw_input:
        return intent.model_copy(update={"raw_input": raw_input})
    return intent


def parse_free_text(user_input: str) -> UserIntent:
    """Parse free-form Chinese text into UserIntent.

    Priority: fixture lookup → Structured Outputs → json_object → rule-based.
    """
    stripped = user_input.strip()
    if stripped in _SCENARIOS:
        return _SCENARIOS[stripped]

    client = _make_client()
    if client:
        return _llm_parse(user_input, client)

    return _rule_fallback(user_input)
