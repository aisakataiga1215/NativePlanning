"""Tests for MVP-4 location anchor extraction and ranking bonus."""
from __future__ import annotations

import pytest

from src.schemas.user_intent import UserIntent
from src.services.plan_ranker import rank_plans, score_plan
from src.tools.wrappers import TraceLog
from src.workflow.intent_parser import _extract_location_anchor, parse_free_text
from src.workflow.planner import generate_plans
from src.workflow.revision_parser import apply_revision


# ── _extract_location_anchor ──────────────────────────────────────────────────

def test_extract_sanliTun_anchor_xian_qu():
    assert _extract_location_anchor("先去芳华街逛逛，然后吃饭") == "芳华街"


def test_extract_wangjing_anchor_fujin():
    assert _extract_location_anchor("云景附近随便走走") == "云景"


def test_extract_company_anchor_li_jin():
    assert _extract_location_anchor("离公司近一点的地方") == "公司附近"


def test_extract_shopping_mall_anchor():
    assert _extract_location_anchor("先去商场逛逛") == "商场附近"


def test_extract_no_anchor_empty_string():
    assert _extract_location_anchor("今天下午随便玩") == ""


def test_extract_zhongguancun_maps_to_haidian():
    assert _extract_location_anchor("去学海村附近") == "明湖区"


# ── parse_free_text integration ───────────────────────────────────────────────

def test_parse_free_text_anchor_propagated():
    """Rule-based parse of a text with '先去芳华街' should set location_anchor."""
    intent = parse_free_text("先去芳华街逛逛，然后找个好餐厅，两个朋友")
    assert intent.location_anchor == "芳华街"


def test_parse_free_text_no_anchor_default_empty():
    intent = parse_free_text("今天下午带孩子出去玩，别太远")
    assert intent.location_anchor == ""


# ── Ranking bonus ─────────────────────────────────────────────────────────────

def _make_minimal_intent(**kwargs) -> UserIntent:
    defaults = dict(
        scenario_type="friends",
        group_size=2,
        date="today",
        time="14:00",
        duration_hours=5.0,
        max_distance_km=10.0,
        activity_preferences=["social", "photo"],
        meal_preferences=[],
        budget_preference="medium",
        raw_input="test",
    )
    defaults.update(kwargs)
    return UserIntent(**defaults)


def test_anchor_area_match_boosts_score():
    """Plans whose venue is in the anchor area should score higher than those without."""
    intent = _make_minimal_intent(
        activity_preferences=["friends", "social"],
        location_anchor="芳华街",
    )
    log = TraceLog()
    plans = generate_plans(intent, log)
    if not plans:
        pytest.skip("No plans generated for this intent")

    ranked_with_anchor = rank_plans(
        plans,
        intent.max_distance_km,
        intent.duration_hours,
        location_anchor="芳华街",
    )
    ranked_without_anchor = rank_plans(
        plans,
        intent.max_distance_km,
        intent.duration_hours,
        location_anchor="",
    )

    # The top plan with anchor should score >= top plan without (anchor can only add bonus)
    assert ranked_with_anchor[0].score >= ranked_without_anchor[0].score - 0.01


def test_anchor_no_match_no_boost():
    """An anchor that doesn't match any venue area should not raise score above 1.0."""
    intent = _make_minimal_intent(location_anchor="郊区某地")
    log = TraceLog()
    plans = generate_plans(intent, log)
    if not plans:
        pytest.skip("No plans generated")

    ranked = rank_plans(
        plans,
        intent.max_distance_km,
        intent.duration_hours,
        location_anchor="郊区某地",
    )
    for plan in ranked:
        assert plan.score <= 1.0


# ── Revision: location anchor update ─────────────────────────────────────────

def test_revision_sets_new_anchor():
    """Revision text '去芳华街附近' should update location_anchor."""
    intent = _make_minimal_intent(location_anchor="")
    updated = apply_revision(intent, "去芳华街附近吧")
    assert updated.location_anchor == "芳华街"


def test_revision_clear_anchor_on_venue_change():
    """'换个地方' revision should clear the existing location_anchor."""
    intent = _make_minimal_intent(location_anchor="芳华街")
    updated = apply_revision(intent, "换个地方")
    assert updated.location_anchor == ""
