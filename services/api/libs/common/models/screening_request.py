"""Data contracts and validation for screening requests."""

from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator


class CapacityUnit(str, Enum):
    MW = "MW"
    MTPA = "MTPA"
    TPD = "TPD"
    MLD = "MLD"
    M3_PER_DAY = "m3_per_day"
    HA = "ha"
    KM = "km"
    TONNES_PER_ANNUM = "tonnes_per_annum"


class FeatureType(str, Enum):
    NATIONAL_PARK = "national_park"
    WILDLIFE_SANCTUARY = "wildlife_sanctuary"
    ECO_SENSITIVE_ZONE = "eco_sensitive_zone"
    CRITICALLY_POLLUTED_AREA = "critically_polluted_area"
    INTER_STATE_BOUNDARY = "inter_state_boundary"
    INTERNATIONAL_BOUNDARY = "international_boundary"
    OTHER_PROTECTED_AREA = "other_protected_area"


INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
    "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry"
]


class Capacity(BaseModel):
    value: float = Field(gt=0, lt=1_000_000_000)
    unit: CapacityUnit


class Location(BaseModel):
    state: str = Field(..., description="Indian state or UT name")
    district: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=6.0, le=38.0)  # India bounding box
    longitude: Optional[float] = Field(None, ge=68.0, le=98.0)

    @model_validator(mode="after")
    def lat_lon_both_or_neither(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must both be provided or both omitted")
        if self.state not in INDIAN_STATES:
            raise ValueError(f"state must be a valid Indian state or UT: {self.state}")
        return self


class ProximityFeature(BaseModel):
    feature_type: FeatureType
    distance_km: float = Field(ge=0, le=500)
    name: Optional[str] = None


class ScreeningRequest(BaseModel):
    client_id: str = Field(..., min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    project_name: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=20, max_length=5000)
    sector_hint: Optional[str] = None  # derived from corpus
    capacity: Optional[Capacity] = None
    area_ha: Optional[float] = Field(None, gt=0, lt=10_000_000)
    location: Location
    proximity: Optional[List[ProximityFeature]] = None
    callback_url: Optional[str] = None

    @model_validator(mode="after")
    def no_duplicate_proximity_features(self):
        if self.proximity:
            seen = set()
            for p in self.proximity:
                key = (p.feature_type, p.distance_km, p.name)
                if key in seen:
                    raise ValueError(f"Duplicate proximity entry: {key}")
                seen.add(key)
        return self

    @model_validator(mode="after")
    def critically_polluted_area_check(self):
        if self.proximity:
            for p in self.proximity:
                if p.feature_type == FeatureType.CRITICALLY_POLLUTED_AREA:
                    if not p.name and not self.location.district:
                        raise ValueError(
                            "Critically polluted area proximity requires cluster name or location district"
                        )
        return self
