"""Unit tests for Milestone 2 Research Loop, Tools, and Reference Case."""

import pytest
import asyncio
from services.worker.tools.registry import (
    tool_get_clause,
    tool_find_modifiers,
    tool_list_amendments,
    tool_compare_threshold,
)
from services.worker.graph_agent import ScreeningAgentGraph


@pytest.mark.asyncio
async def test_tool_get_clause_general_condition():
    """Verify get_clause retrieves exact General Condition text and 5 km threshold."""
    res = await tool_get_clause("General Condition")
    assert res["status"] == "EXACT_MATCH"
    assert res["threshold_primary_km"] == 5.0
    assert "within 5 km" in res["text"]
    assert "1(c)" in res["enhanced_items"]


@pytest.mark.asyncio
async def test_tool_find_modifiers_discovers_gc():
    """Verify find_modifiers inspects retrieved passage text and returns GC."""
    retrieved_text = "Schedule Item 1(a) Mining of minerals. Category B projects appraised by SEAC."
    mods = await tool_find_modifiers(passage_text=retrieved_text)
    assert len(mods) >= 1
    gc_mod = next((m for m in mods if m["modifier_type"] == "GENERAL_CONDITION"), None)
    assert gc_mod is not None
    assert gc_mod["threshold_primary_km"] == 5.0


def test_tool_compare_threshold_numeric():
    """Verify compare_threshold accurately tests distance thresholds without LLM arithmetic."""
    # 2 km is within 5 km threshold
    res_2km = tool_compare_threshold(2.0, "km", "within 5 km")
    assert res_2km["triggers_modifier"] is True
    assert res_2km["comparison"] == "LESS_THAN"

    # 12 km is outside 5 km threshold
    res_12km = tool_compare_threshold(12.0, "km", "within 5 km")
    assert res_12km["triggers_modifier"] is False
    assert res_12km["comparison"] == "GREATER_THAN"

    # 5.0 km boundary test
    res_5km = tool_compare_threshold(5.0, "km", "within 5 km")
    assert res_5km["exact_boundary"] is True


@pytest.mark.asyncio
async def test_reference_case_primary_2km():
    """Reference Case 4.1: Industrial/mining Category B project, 2 km from national park.
    MUST route to CATEGORY_A_CENTRAL, citing BOTH Schedule Item and General Condition.
    """
    graph = ScreeningAgentGraph()
    req = {
        "client_id": "client-ref-2km",
        "project_name": "Granite Quarry Project",
        "description": "Open-cast mining of granite over 10 ha.",
        "sector_hint": "Mining of minerals",
        "area_ha": 10.0,
        "location": {"state": "Rajasthan", "district": "Jodhpur"},
        "proximity": [
            {"feature_type": "national_park", "distance_km": 2.0, "name": "Keoladeo National Park"}
        ]
    }

    result = await graph.run("run-ref-2km", req, "corr-ref-2km")

    assert result["route"] == "CATEGORY_A_CENTRAL"
    assert len(result["citations"]) >= 2
    
    # Assert Schedule row is cited
    has_schedule_cite = any("Schedule" in c["clause_ref"] for c in result["citations"])
    assert has_schedule_cite, "Schedule row citation is mandatory"

    # Assert General Condition is cited
    has_gc_cite = any("General Condition" in c["clause_ref"] for c in result["citations"])
    assert has_gc_cite, "General Condition citation is mandatory"

    # Assert GC quote contains 5 km
    gc_cite = next(c for c in result["citations"] if "General Condition" in c["clause_ref"])
    assert "5 km" in gc_cite["quote"]


@pytest.mark.asyncio
async def test_reference_case_negative_control_12km():
    """Negative Control: Category B project 12 km from national park stays Category B State."""
    graph = ScreeningAgentGraph()
    req = {
        "client_id": "client-ref-12km",
        "project_name": "Granite Quarry Project",
        "description": "Open-cast mining of granite over 10 ha.",
        "sector_hint": "Mining of minerals",
        "area_ha": 10.0,
        "location": {"state": "Rajasthan", "district": "Jodhpur"},
        "proximity": [
            {"feature_type": "national_park", "distance_km": 12.0, "name": "Keoladeo National Park"}
        ]
    }

    result = await graph.run("run-ref-12km", req, "corr-ref-12km")

    # Stays Category B State authority
    assert result["route"] == "CATEGORY_B_STATE"
    assert result["verification"]["passed"] is True


@pytest.mark.asyncio
async def test_ambiguous_proximity_escalates():
    """Ambiguous proximity ('near a forest') MUST escalate with PROXIMITY_UNCERTAIN."""
    graph = ScreeningAgentGraph()
    req = {
        "client_id": "client-ambig",
        "project_name": "Granite Quarry Project",
        "description": "Open-cast mining of granite over 10 ha near a forest area.",
        "sector_hint": "Mining of minerals",
        "location": {"state": "Rajasthan", "district": "Jodhpur"},
        "proximity": []
    }

    result = await graph.run("run-ambig", req, "corr-ambig")

    assert result["route"] == "ESCALATED_TO_HUMAN"
    assert result["escalation"]["reason_code"] == "PROXIMITY_UNCERTAIN"


@pytest.mark.asyncio
async def test_out_of_corpus_escalates():
    """Out-of-corpus sector MUST escalate with OUT_OF_CORPUS_SECTOR."""
    graph = ScreeningAgentGraph()
    req = {
        "client_id": "client-ooc",
        "project_name": "Software Tech Park",
        "description": "A cloud software development hub with data centers.",
        "sector_hint": "Software development",
        "location": {"state": "Karnataka", "district": "Bengaluru"},
        "proximity": []
    }

    result = await graph.run("run-ooc", req, "corr-ooc")

    assert result["route"] == "ESCALATED_TO_HUMAN"
    assert result["escalation"]["reason_code"] == "OUT_OF_CORPUS_SECTOR"
