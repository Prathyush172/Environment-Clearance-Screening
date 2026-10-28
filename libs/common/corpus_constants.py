"""
Corpus ground-truth constants extracted verbatim from the EIA Notification 2006 corpus.
These values are READ FROM THE CORPUS, never hardcoded from memory.
This file is updated by the ingest pipeline after each successful extraction.

Source: EIA_Notification_2006_including_all_amendments_till_March_2025 (1).pdf
"""

from __future__ import annotations

# =============================================================================
# GENERAL CONDITION (GC) — VERBATIM FROM CORPUS
# Source file: EIA_Notification_2006_including_all_amendments_till_March_2025 (1).pdf
# Approximate page: 29
# Footnote: 93
# Stream position: ~350,000–352,500
# =============================================================================

GENERAL_CONDITION_VERBATIM = """General Condition (GC): Any project or activity specified in \
Category 'B' will be appraised at the Central Level as Category 'A', if located in whole or in \
part within 5 km from the boundary of: (i) Protected Areas notified under the Wild Life \
(Protection) Act, 1972 (53 of 1972); (ii) Critically Polluted areas as identified by the Central \
Pollution Control Board constituted under the Water (Prevention and Control of Pollution) Act, \
1974 (6 of 1974) from time to time; (iii) Eco-sensitive areas as notified under sub-section (2) \
of section 3 of the Environment (Protection) Act, 1986, and (iv) inter-State boundaries and \
international boundaries; provided that for River Valley Projects specified in item 1(c), Thermal \
Power Plants specified in item 1(d), Industrial Estates/parks/complexes/areas, export processing \
zones (EPZ), Special Economic Zones (SEZs), biotech parks, leather complexes specified in item \
7(c) and common hazardous waste treatment, storage and disposal facilities (TSDFs) specified in \
item 7(d), the appraisal shall be made at Central level even if located within 10 km."""

# Primary distance threshold (applies to all GC-covered project types)
GC_PRIMARY_DISTANCE_KM: float = 5.0

# Enhanced threshold — applies only to specific project types listed in GC "provided that" clause
GC_ENHANCED_DISTANCE_KM: float = 10.0

# Schedule item numbers that use the 10 km (enhanced) threshold
GC_ENHANCED_THRESHOLD_ITEMS: list[str] = [
    "1(c)",   # River Valley Projects
    "1(d)",   # Thermal Power Plants
    "7(c)",   # Industrial Estates/parks/complexes/areas, EPZ, SEZ, biotech parks, leather complexes
    "7(d)",   # Common hazardous waste TSDFs
]

# Sector descriptions for enhanced threshold items
GC_ENHANCED_THRESHOLD_SECTORS: list[str] = [
    "River Valley Projects",
    "Thermal Power Plants",
    "Industrial Estates/parks/complexes/areas",
    "Export Processing Zones (EPZ)",
    "Special Economic Zones (SEZs)",
    "Biotech parks",
    "Leather complexes",
    "Common hazardous waste treatment, storage and disposal facilities (TSDFs)",
]

# Protected area types covered by the GC, with their legal basis
GC_PROTECTED_AREA_TYPES: dict[str, str] = {
    "national_park": "Protected Areas notified under the Wild Life (Protection) Act, 1972 (53 of 1972)",
    "wildlife_sanctuary": "Protected Areas notified under the Wild Life (Protection) Act, 1972 (53 of 1972)",
    "eco_sensitive_zone": "Eco-sensitive areas as notified under sub-section (2) of section 3 of the Environment (Protection) Act, 1986",
    "critically_polluted_area": "Critically Polluted areas as identified by the Central Pollution Control Board constituted under the Water (Prevention and Control of Pollution) Act, 1974 (6 of 1974)",
    "inter_state_boundary": "inter-State boundaries",
    "international_boundary": "international boundaries",
}

# Feature types that map to GC clause (i) — Protected Areas under Wild Life (Protection) Act
GC_CLAUSE_I_TYPES: list[str] = ["national_park", "wildlife_sanctuary", "other_protected_area"]
# Feature types that map to GC clause (ii) — Critically Polluted Areas
GC_CLAUSE_II_TYPES: list[str] = ["critically_polluted_area"]
# Feature types that map to GC clause (iii) — Eco-sensitive areas
GC_CLAUSE_III_TYPES: list[str] = ["eco_sensitive_zone"]
# Feature types that map to GC clause (iv) — Boundaries
GC_CLAUSE_IV_TYPES: list[str] = ["inter_state_boundary", "international_boundary"]

# =============================================================================
# B1 / B2 DEFINITIONS — VERBATIM FROM CORPUS
# Source file: EIA_Notification_2006_including_all_amendments_till_March_2025 (1).pdf
# Approximate page: 6-7
# Stream position: ~44,719
# =============================================================================

B1_B2_VERBATIM = """The projects requiring an Environmental Impact Assessment report shall be \
termed Category 'B1' and remaining projects shall be termed Category 'B2' and will not require \
an Environment Impact Assessment report. For categorization of projects into B1 or B2 except \
item 8(b), the Ministry of Environment and Forests shall issue appropriate guidelines from time \
to time."""

# =============================================================================
# SCHEDULE STRUCTURE
# Source: Same file, approximate page 18, stream position ~143,370
# =============================================================================

SCHEDULE_COLUMN_HEADERS: list[str] = [
    "(1) Item No.",
    "(2) Project or Activity",
    "(3) Category A threshold",
    "(4) Category B threshold",
    "(5) Conditions if any",
]

SCHEDULE_TITLE: str = (
    "LIST OF PROJECTS OR ACTIVITIES REQUIRING PRIOR ENVIRONMENTAL CLEARANCE"
)

# Supported Schedule sectors mapped from the EIA Notification 2006 Schedule
SCHEDULE_SECTORS: dict[str, str] = {
    "1(a)": "Mining of minerals",
    "1(b)": "Offshore and onshore oil and gas exploration, development & production",
    "1(c)": "River Valley Projects",
    "1(d)": "Thermal Power Plants",
    "1(e)": "Nuclear power projects",
    "2(a)": "Coal washeries",
    "2(b)": "Mineral beneficiation",
    "2(c)": "Pellet plant",
    "3(a)": "Metallurgical industries",
    "3(b)": "Cement plants",
    "4(a)": "Petroleum refining",
    "4(b)": "Coke oven plants",
    "4(c)": "Asbestos milling",
    "4(d)": "Chlor-alkali industry",
    "4(e)": "Soda ash Industry",
    "4(f)": "Skin/hide processing",
    "5(a)": "Chemical fertilizers",
    "5(b)": "Pesticides industry",
    "5(c)": "Petro-chemical complexes",
    "5(d)": "Manmade fibres",
    "5(e)": "Petroleum products",
    "5(f)": "Synthetic organic chemicals industry",
    "5(g)": "Distilleries",
    "5(h)": "Integrated paint industry",
    "5(i)": "Pulp & paper industry",
    "5(j)": "Sugar Industry",
    "6(a)": "Oil & gas transportation pipeline",
    "6(b)": "Isolated storage & handling of hazardous chemicals",
    "7(a)": "Airports",
    "7(b)": "All ship breaking yards",
    "7(c)": "Industrial estates/ parks/ complexes/ areas, EPZs, SEZs, biotech parks, leather complexes",
    "7(d)": "Common hazardous waste treatment, storage and disposal facilities (TSDFs)",
    "7(da)": "Bio-Medical Waste Treatment Facilities",
    "7(e)": "Ports, harbors, break waters, dredging",
    "7(f)": "Highways",
    "7(g)": "Aerial ropeways",
    "7(h)": "Common Effluent Treatment Plants (CETPs)",
    "7(i)": "Common Municipal Solid Waste Management Facility (CMSWMF)",
    "8(a)": "Building and Construction projects",
    "8(b)": "Townships and Area Development projects",
}

# Cross-reference phrases to build the cross-reference index
# These are searched in corpus text to link provisions
CROSS_REFERENCE_PHRASES: list[str] = [
    "General Condition",
    "General Condition shall apply",
    "General Conditions shall apply",
    "General Condition shall not apply",
    "notwithstanding",
    "provided that",
    "Category B shall be treated as",
    "appraised at the Central Level as Category",
    "see paragraph",
    "as specified in item",
    "referred to in",
]
