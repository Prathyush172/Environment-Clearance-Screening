"""End-to-end integration tests for Scenario A (Thermal) and Scenario B (Unsupported Sector)."""

import pytest
import asyncio
from fastapi.testclient import TestClient
from services.api.main import app
from services.worker.graph_agent import ScreeningAgentGraph
from libs.common.models.screening_request import ScreeningRequest
from libs.common.db.models import ScreeningRoute, User
from services.api.auth import get_current_user

client = TestClient(app)


@pytest.fixture(autouse=True)
def override_auth():
    app.dependency_overrides[get_current_user] = lambda: User(
        id="test-e2e-user",
        username="officer",
        email="officer@eia.gov.in",
        role="user",
        client_id="test-client-thermal",
        is_active=True,
    )
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_e2e_scenario_a_thermal_power_plant_api_boundary():
    """End-to-end test A through the API boundary:
    300 MW Thermal Power Plant located 7.0 km from a National Park.
    - Ordinarily Category B under Item 1(d) (< 500 MW coal-based)
    - Enhanced General Condition applies (10 km threshold for Item 1(d))
    - Distance 7.0 km <= 10.0 km -> Upgraded to CATEGORY_A_CENTRAL
    """
    payload = {
        "client_id": "test-client-thermal",
        "project_name": "Thermal Power Plant 7km from Park",
        "description": "Establishment of a 300 MW coal-based thermal power plant situated 7.0 km from the boundary of a notified National Park in Madhya Pradesh.",
        "sector_hint": "Thermal Power Plants",
        "capacity": {
            "value": 300.0,
            "unit": "MW"
        },
        "location": {
            "state": "Madhya Pradesh"
        },
        "proximity": [
            {
                "feature_type": "national_park",
                "distance_km": 7.0,
                "name": "Bandhavgarh National Park"
            }
        ]
    }

    # 1. API submission boundary
    resp = client.post("/v1/screenings", json=payload, headers={"X-Correlation-ID": "test-corr-thermal"})
    assert resp.status_code == 202
    data = resp.json()
    assert "run_id" in data
    assert data["status"] == "QUEUED"

    # 2. Worker pipeline execution
    graph = ScreeningAgentGraph()
    result = asyncio.run(graph.run(run_id=data["run_id"], request_data=payload, correlation_id="test-corr-thermal"))

    # 3. Assertions on final route and regulatory basis
    assert result["route"] in (ScreeningRoute.CATEGORY_A_CENTRAL, "CATEGORY_A_CENTRAL")
    assert result["schedule_entry"] is not None
    assert result["schedule_entry"]["item_no"] == "1(d)"
    assert result["schedule_entry"]["sector"] == "Thermal Power Plants"

    # Check that General Condition was triggered and recorded
    assert len(result["conditions_applied"]) > 0
    gc_applied = any(
        "General Condition" in cond.get("text_summary", "") and "10.0 km" in cond.get("text_summary", "")
        for cond in result["conditions_applied"]
    )
    assert gc_applied, f"Expected 10km enhanced General Condition in conditions_applied: {result['conditions_applied']}"

    # Check traceable citations and verifier execution
    assert len(result["citations"]) >= 1
    assert result["verification"] is not None
    assert result["verification"]["passed"] is True

    # Check non-official screening disclaimer
    assert "SCREENING OPINION ONLY" in result["disclaimer"]
    assert "MoEFCC" in result["disclaimer"]


def test_e2e_scenario_b_unsupported_sector_api_boundary():
    """End-to-end test B through the API boundary:
    Fintech Software Office in an unsupported sector ('Software development').
    - Must escalate to human review with OUT_OF_CORPUS_SECTOR
    - Must NOT invent a Category A or B determination
    - Must include clear explanation and non-official disclaimer
    """
    payload = {
        "client_id": "test-client-software",
        "project_name": "Fintech Software Office",
        "description": "Development of enterprise SaaS platform with server room in tech park.",
        "sector_hint": "Software development",
        "location": {
            "state": "Karnataka"
        }
    }

    # 1. API submission boundary
    resp = client.post("/v1/screenings", json=payload, headers={"X-Correlation-ID": "test-corr-software"})
    assert resp.status_code == 202
    data = resp.json()
    assert "run_id" in data

    # 2. Worker pipeline execution
    graph = ScreeningAgentGraph()
    result = asyncio.run(graph.run(run_id=data["run_id"], request_data=payload, correlation_id="test-corr-software"))

    # 3. Assertions on escalation
    assert result["route"] in (ScreeningRoute.ESCALATED_TO_HUMAN, "ESCALATED_TO_HUMAN")
    assert result["schedule_entry"] is None
    assert result["escalation"] is not None
    assert result["escalation"]["reason_code"] == "OUT_OF_CORPUS_SECTOR"
    assert "Software development" in result["escalation"]["detail"]
    assert len(result["escalation"]["human_checklist"]) > 0

    # Check non-official screening disclaimer
    assert "SCREENING OPINION ONLY" in result["disclaimer"]
