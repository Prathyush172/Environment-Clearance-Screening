"""Integration tests for API endpoints and quarantine workflow."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from services.api.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "api"}


@patch("services.api.routers.screenings.celery_app.send_task")
@patch("services.api.routers.screenings.get_db_session")
def test_malformed_request_returns_422_and_quarantines(mock_get_db, mock_send_task):
    mock_session = MagicMock()
    mock_get_db.return_value.__aenter__.return_value = mock_session

    # Missing required fields like description, project_name, etc.
    malformed_payload = {
        "client_id": "test_client",
        "description": "too short"
    }

    response = client.post("/v1/screenings", json=malformed_payload)
    assert response.status_code == 422
    data = response.json()
    assert "errors" in data or "detail" in data

    # Assert Celery task was NOT enqueued
    mock_send_task.assert_not_called()

    # Assert quarantine session added an entry
    assert mock_session.add.called


@patch("services.api.routers.screenings.celery_app.send_task")
@patch("services.api.routers.screenings.get_db_session")
def test_valid_submission_returns_202_accepted(mock_get_db, mock_send_task):
    mock_session = MagicMock()
    mock_get_db.return_value.__aenter__.return_value = mock_session

    valid_payload = {
        "client_id": "valid-client-01",
        "project_name": "Commercial Bauxite Mine",
        "description": "Mining operations over an area of 45 hectares with extraction capacity of 0.5 MTPA.",
        "sector_hint": "Mining of minerals",
        "capacity": {
            "value": 0.5,
            "unit": "MTPA"
        },
        "area_ha": 45.0,
        "location": {
            "state": "Karnataka",
            "district": "Ballari",
            "latitude": 15.08,
            "longitude": 76.54
        },
        "proximity": [
            {
                "feature_type": "national_park",
                "distance_km": 2.0,
                "name": "Kudremukh"
            }
        ]
    }

    response = client.post("/v1/screenings", json=valid_payload)
    assert response.status_code == 202
    data = response.json()
    assert "run_id" in data
    assert "status_url" in data
    assert data["status"] == "QUEUED"

    # Verify Celery send_task was called with run_id
    mock_send_task.assert_called_once()
    assert mock_send_task.call_args[1]["task_id"] == data["run_id"]
