"""Unit tests for screening request validation and cross-field rules."""

import pytest
from pydantic import ValidationError
from libs.common.models.screening_request import (
    ScreeningRequest,
    Capacity,
    CapacityUnit,
    Location,
    ProximityFeature,
    FeatureType,
)
from services.api.validation import (
    sanitise_description,
    validate_description_not_empty_after_sanitisation,
    validate_capacity_unit_sector_compatibility,
    validate_lat_lon_state_consistency,
    validate_proximity_no_duplicates,
    validate_proximity_critically_polluted_needs_name_or_district,
    validate_area_ha_plausible_for_unit,
)


def test_sanitise_description():
    raw = "Project proposal \x00\x08 with bad \u200b characters and   multiple    spaces."
    cleaned = sanitise_description(raw)
    assert "\x00" not in cleaned
    assert "\x08" not in cleaned
    assert "  " not in cleaned
    assert "Project proposal with bad characters and multiple spaces." in cleaned


def test_validate_description_not_empty_after_sanitisation():
    # Less than 20 chars should raise
    with pytest.raises(ValueError):
        validate_description_not_empty_after_sanitisation("Short desc")

    # Sufficient chars passes
    validate_description_not_empty_after_sanitisation("This is a valid long description with more than twenty characters.")


def test_validate_capacity_unit_sector_compatibility():
    # Power sector with MW should pass
    cap = Capacity(value=100.0, unit=CapacityUnit.MW)
    validate_capacity_unit_sector_compatibility(cap, "Thermal Power Plants")

    # Power sector with MLD should fail
    cap_invalid = Capacity(value=10.0, unit=CapacityUnit.MLD)
    with pytest.raises(ValueError):
        validate_capacity_unit_sector_compatibility(cap_invalid, "Thermal Power Plants")

    # Mining sector with MTPA passes
    cap_mining = Capacity(value=2.5, unit=CapacityUnit.MTPA)
    validate_capacity_unit_sector_compatibility(cap_mining, "Mining of minerals")


def test_validate_lat_lon_state_consistency():
    # Karnataka coordinates pass
    validate_lat_lon_state_consistency(13.21, 75.25, "Karnataka")

    # Out of state bounds should raise
    with pytest.raises(ValueError):
        validate_lat_lon_state_consistency(28.61, 77.20, "Karnataka")  # Delhi coords for Karnataka


def test_validate_proximity_no_duplicates():
    prox = [
        ProximityFeature(feature_type=FeatureType.NATIONAL_PARK, distance_km=2.0, name="Kudremukh"),
        ProximityFeature(feature_type=FeatureType.NATIONAL_PARK, distance_km=2.0, name="Kudremukh"),
    ]
    with pytest.raises(ValueError):
        validate_proximity_no_duplicates(prox)


def test_validate_proximity_critically_polluted_needs_name_or_district():
    prox = [
        ProximityFeature(feature_type=FeatureType.CRITICALLY_POLLUTED_AREA, distance_km=3.0, name=None)
    ]
    with pytest.raises(ValueError):
        validate_proximity_critically_polluted_needs_name_or_district(prox, district=None)

    # With district provided, it passes
    validate_proximity_critically_polluted_needs_name_or_district(prox, district="Vapi")


def test_valid_screening_request_model():
    req = ScreeningRequest(
        client_id="test-client",
        project_name="Test Iron Ore Mine",
        description="Establishment of non-coal open cast iron ore mine with production capacity of 1 MTPA over 45 ha lease.",
        sector_hint="Mining of minerals",
        capacity=Capacity(value=1.0, unit=CapacityUnit.MTPA),
        area_ha=45.0,
        location=Location(state="Karnataka", district="Ballari", latitude=15.1, longitude=76.9),
        proximity=[
            ProximityFeature(feature_type=FeatureType.NATIONAL_PARK, distance_km=2.0, name="Kudremukh")
        ]
    )
    assert req.client_id == "test-client"
    assert req.location.state == "Karnataka"


def test_invalid_state_fails_pydantic():
    with pytest.raises(ValidationError):
        Location(state="Atlantis")
