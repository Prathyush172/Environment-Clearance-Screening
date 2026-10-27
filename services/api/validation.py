"""Validation logic and cross-field rules for screening requests."""

import re
import unicodedata
from typing import Optional, List, Dict, Any, Tuple
from libs.common.models.screening_request import (
    Capacity,
    CapacityUnit,
    ProximityFeature,
    FeatureType,
    INDIAN_STATES,
)

# Approximate bounding boxes [min_lat, min_lon, max_lat, max_lon] for major Indian states/UTs
STATE_BOUNDING_BOXES: Dict[str, Tuple[float, float, float, float]] = {
    "Andhra Pradesh": (12.6, 76.7, 19.9, 84.8),
    "Arunachal Pradesh": (26.6, 91.5, 29.5, 97.5),
    "Assam": (24.1, 89.7, 28.0, 96.0),
    "Bihar": (24.2, 83.3, 27.5, 88.3),
    "Chhattisgarh": (17.7, 80.2, 24.1, 84.4),
    "Goa": (14.8, 73.6, 15.8, 74.4),
    "Gujarat": (20.1, 68.1, 24.7, 74.5),
    "Haryana": (27.6, 74.4, 30.9, 77.6),
    "Himachal Pradesh": (30.3, 75.5, 33.3, 79.0),
    "Jharkhand": (21.9, 83.3, 25.3, 87.9),
    "Karnataka": (11.5, 74.0, 18.5, 78.6),
    "Kerala": (8.2, 74.8, 12.8, 77.4),
    "Madhya Pradesh": (21.1, 74.0, 26.9, 82.8),
    "Maharashtra": (15.6, 72.6, 22.0, 80.9),
    "Manipur": (23.8, 93.0, 25.7, 94.8),
    "Meghalaya": (25.0, 89.8, 26.1, 92.8),
    "Mizoram": (21.9, 92.2, 24.5, 93.4),
    "Nagaland": (25.1, 93.3, 27.0, 95.2),
    "Odisha": (17.8, 81.4, 22.6, 87.5),
    "Punjab": (29.5, 73.8, 32.5, 76.9),
    "Rajasthan": (23.0, 69.5, 30.2, 78.3),
    "Sikkim": (27.0, 88.0, 28.1, 88.9),
    "Tamil Nadu": (8.0, 76.2, 13.6, 80.3),
    "Telangana": (15.8, 77.2, 19.9, 81.8),
    "Tripura": (22.9, 91.1, 24.5, 92.4),
    "Uttar Pradesh": (23.8, 77.0, 30.4, 84.6),
    "Uttarakhand": (28.7, 77.5, 31.5, 81.1),
    "West Bengal": (21.5, 85.8, 27.2, 89.9),
    "Delhi": (28.4, 76.8, 28.9, 77.3),
    "Jammu and Kashmir": (32.2, 73.5, 37.1, 80.3),
    "Ladakh": (32.0, 75.5, 36.0, 80.5),
}


def sanitise_description(description: str) -> str:
    """Normalize unicode, strip dangerous non-printable control characters."""
    if not description:
        return ""
    # Normalize unicode to NFKC
    normalized = unicodedata.normalize("NFKC", description)
    # Remove non-printable control characters except newline and tab
    sanitised = "".join(ch for ch in normalized if ch in "\n\r\t" or unicodedata.category(ch)[0] != "C")
    # Collapse excessive whitespace
    sanitised = re.sub(r"[ \t]+", " ", sanitised)
    return sanitised.strip()


def validate_description_not_empty_after_sanitisation(description: str) -> None:
    """Check that description remains meaningful after stripping control chars."""
    clean = sanitise_description(description)
    if len(clean) < 20:
        raise ValueError("Description is too short or empty after sanitisation (min 20 characters required)")


def validate_capacity_unit_sector_compatibility(
    capacity: Optional[Capacity], sector_hint: Optional[str]
) -> None:
    """Validate that capacity units align with the declared sector."""
    if not capacity or not sector_hint:
        return

    sector_lower = sector_hint.lower()
    unit = capacity.unit

    if "power" in sector_lower or "thermal" in sector_lower or "solar" in sector_lower or "wind" in sector_lower:
        if unit not in [CapacityUnit.MW, CapacityUnit.TPD]:
            raise ValueError(f"Power generation sectors require MW or TPD capacity unit, got: {unit.value}")

    if "mining" in sector_lower:
        if unit not in [CapacityUnit.MTPA, CapacityUnit.TPD, CapacityUnit.TONNES_PER_ANNUM, CapacityUnit.HA]:
            raise ValueError(f"Mining sector requires MTPA, TPD, tonnes_per_annum, or ha, got: {unit.value}")

    if "effluent" in sector_lower or "treatment" in sector_lower or "cetp" in sector_lower:
        if unit not in [CapacityUnit.MLD, CapacityUnit.M3_PER_DAY]:
            raise ValueError(f"Effluent/treatment sectors require MLD or m3_per_day, got: {unit.value}")


def validate_lat_lon_state_consistency(
    latitude: Optional[float], longitude: Optional[float], state: str
) -> None:
    """Verify lat/long falls roughly within the declared Indian state bounding box."""
    if latitude is None or longitude is None:
        return

    if state not in INDIAN_STATES:
        raise ValueError(f"Unknown state: {state}")

    bbox = STATE_BOUNDING_BOXES.get(state)
    if bbox:
        min_lat, min_lon, max_lat, max_lon = bbox
        # Allow 0.5 degree buffer for border proximity
        buffer = 0.5
        if not (min_lat - buffer <= latitude <= max_lat + buffer and min_lon - buffer <= longitude <= max_lon + buffer):
            raise ValueError(
                f"Coordinates ({latitude:.4f}, {longitude:.4f}) do not match state boundaries for {state}"
            )


def validate_proximity_no_duplicates(proximity_list: Optional[List[ProximityFeature]]) -> None:
    """Check for duplicate proximity items."""
    if not proximity_list:
        return
    seen = set()
    for item in proximity_list:
        key = (item.feature_type, round(item.distance_km, 2), (item.name or "").lower().strip())
        if key in seen:
            raise ValueError(f"Duplicate proximity entry found: {item.feature_type.value} at {item.distance_km} km")
        seen.add(key)


def validate_proximity_critically_polluted_needs_name_or_district(
    proximity_list: Optional[List[ProximityFeature]], district: Optional[str]
) -> None:
    """Critically polluted area proximity requires either cluster name or district."""
    if not proximity_list:
        return
    for item in proximity_list:
        if item.feature_type == FeatureType.CRITICALLY_POLLUTED_AREA:
            if not item.name and not district:
                raise ValueError("Critically polluted area proximity requires cluster name or location district")


def validate_area_ha_plausible_for_unit(area_ha: Optional[float], capacity: Optional[Capacity]) -> None:
    """Ensure area and capacity are within plausible bounds when both provided."""
    if area_ha is not None and area_ha <= 0:
        raise ValueError("area_ha must be greater than zero")
    if capacity and capacity.unit == CapacityUnit.HA and area_ha is not None:
        # If capacity is specified in ha, it shouldn't radically conflict with area_ha
        ratio = capacity.value / area_ha
        if ratio < 0.01 or ratio > 100:
            raise ValueError(
                f"Discrepancy between capacity value ({capacity.value} ha) and area_ha ({area_ha} ha)"
            )
