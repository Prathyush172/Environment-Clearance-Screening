# Reference Case — Section 4.1

> **Status:** Ground-truth established from corpus extraction.  
> **Source:** `EIA_Notification_2006_including_all_amendments_till_March_2025 (1).pdf`  
> **IMPORTANT:** All text below is extracted verbatim from the corpus. Never paraphrase from memory.

---

## 1. Exact Corpus Passages This Case Depends On

### 1.1 The General Condition (GC) — Verbatim from Corpus

**Source file:** `EIA_Notification_2006_including_all_amendments_till_March_2025 (1).pdf`  
**Approximate page:** 29  
**Footnote number:** 93  
**Stream character position:** ~350,000–352,500

> **General Condition (GC)⁹³:**
>
> Any project or activity specified in Category 'B' will be appraised at the Central Level as Category 'A', if located in whole or in part within **5 km** from the boundary of: (i) Protected Areas notified under the Wild Life (Protection) Act, 1972 (53 of 1972); (ii) Critically Polluted areas as identified by the Central Pollution Control Board⁹⁴ constituted under the Water (Prevention and Control of Pollution) Act, 1974 (6 of 1974) from time to time; (iii) Eco-sensitive areas as notified under sub-section (2) of section 3 of the Environment (Protection) Act, 1986, and (iv) inter-State boundaries and international boundaries; **provided that** for River Valley Projects specified in item 1(c), Thermal Power Plants specified in item 1(d), Industrial Estates/parks/complexes/areas, export processing zones (EPZ), Special Economic Zones (SEZs), biotech parks, leather complexes specified in item 7(c) and common hazardous waste treatment, storage and disposal facilities (TSDFs) specified in item 7(d), the appraisal shall be made at Central level even if located within **10 km**.
>
> Provided further that the requirement regarding distance of 5 km or 10 km, as the case may be, of the inter-State boundaries can be reduced or completely done away with by an agreement between the respective States or the Union Territories sharing the common boundary in case the activity does not fall within 5 km or 10 km, as the case may be of the areas mentioned at item (i), (ii), and (iii) above.

**Key extracted thresholds:**
- Primary: **5 km** from the boundary of Protected Areas, Critically Polluted areas, Eco-sensitive areas, inter-State boundaries, international boundaries
- Enhanced (10 km) for: River Valley Projects (item 1(c)), Thermal Power Plants (item 1(d)), Industrial Estates/EPZ/SEZ/biotech parks/leather complexes (item 7(c)), TSDFs (item 7(d))

### 1.2 Schedule Structure

**Source:** Same file, approximate page 18, stream position ~143,370

The Schedule is titled:
> **SCHEDULE** *(See paragraph 2 and 7)*  
> **LIST OF PROJECTS OR ACTIVITIES REQUIRING PRIOR ENVIRONMENTAL CLEARANCE**

The Schedule is a **5-column table**:

| Column # | Header |
|---|---|
| (1) | Item number (e.g., 1, 1(a), 1(b)...) |
| (2) | Project or Activity |
| (3) | Category A threshold |
| (4) | Category B threshold |
| (5) | Conditions if any |

The first sector heading:
> **1** — "Mining, extraction of natural resources and power generation (for a specified production capacity)"
> **1(a)** — "(i) Mining of minerals" — with Category A and Category B thresholds

### 1.3 B1 / B2 Sub-Category Definition

**Source:** Same file, paragraph 7, stream position ~44,719

> "The projects requiring an Environmental Impact Assessment report shall be termed Category **'B1'** and remaining projects shall be termed Category **'B2'** and will not require an Environment Impact Assessment report. For categorization of projects into B1 or B2 except item 8(b), the Ministry of Environment and Forests shall issue appropriate guidelines from time to time."

---

## 2. The Reference Case Input Values

### Base Case (must route to CATEGORY_A_CENTRAL)
```json
{
  "client_id": "demo-client-001",
  "project_name": "Granite Quarry Project, Rajasthan",
  "description": "Open-cast mining of granite covering 10 hectares in Rajasthan. The project will extract approximately 0.5 MTPA of granite stone for construction use.",
  "sector_hint": "Mining of minerals",
  "capacity": {"value": 0.5, "unit": "MTPA"},
  "area_ha": 10,
  "location": {"state": "Rajasthan", "district": "Jodhpur"},
  "proximity": [
    {"feature_type": "national_park", "distance_km": 2.0, "name": "Keoladeo National Park"}
  ]
}
```

**Expected:**
- `route`: `CATEGORY_A_CENTRAL`
- `citations` MUST include:
  1. The Schedule row for Mining of Minerals (1(a)) giving it as Category B
  2. The General Condition passage (GC, page ~29) — verbatim quote must contain "5 km"
- Returning Schedule category alone (Category B) **is a FAIL** — the GC upgrade must be applied and cited

---

## 3. Distance Variant Test Cases

All variants use the same base project (Category B mining). Protected area type: national_park.

### 3.1 Variant: 0 km (inside the protected area boundary)
```json
{"feature_type": "national_park", "distance_km": 0.0, "name": "Keoladeo National Park"}
```
**Expected:** `route = CATEGORY_A_CENTRAL` (0 < 5 km threshold — GC applies)  
**Must cite:** Schedule B row + GC passage

### 3.2 Variant: 2 km (well within GC threshold) — THE PRIMARY REFERENCE CASE
```json
{"feature_type": "national_park", "distance_km": 2.0, "name": "Keoladeo National Park"}
```
**Expected:** `route = CATEGORY_A_CENTRAL` (2 < 5 km — GC applies)  
**Must cite:** Schedule B row + GC passage

### 3.3 Variant: 4.9 km (just inside GC threshold)
```json
{"feature_type": "national_park", "distance_km": 4.9, "name": "Keoladeo National Park"}
```
**Expected:** `route = CATEGORY_A_CENTRAL` (4.9 < 5.0 — GC applies)  
**Must cite:** Schedule B row + GC passage

### 3.4 Variant: 5.0 km (exactly at threshold)
```json
{"feature_type": "national_park", "distance_km": 5.0, "name": "Keoladeo National Park"}
```
**Expected:** `route = CATEGORY_A_CENTRAL` (5.0 km — "within 5 km" — boundary case; the GC says "within 5 km from the boundary of"; whether 5.0 km exactly qualifies is ambiguous — ESCALATE with reason PROXIMITY_UNCERTAIN, noting the boundary ambiguity)  
**Note for eval:** This is a deliberate boundary ambiguity test. The correct handling is escalation, not guessing.

### 3.5 Variant: 5.1 km (just outside GC threshold)
```json
{"feature_type": "national_park", "distance_km": 5.1, "name": "Keoladeo National Park"}
```
**Expected:** `route = CATEGORY_B_STATE` (5.1 > 5.0 — GC does NOT apply)  
**Must cite:** Schedule B row + GC passage (to show GC was considered but threshold not met)  
**This is the negative control — GC evaluated but distance exceeds threshold**

### 3.6 Variant: 6 km (clearly outside GC threshold)
```json
{"feature_type": "national_park", "distance_km": 6.0, "name": "Keoladeo National Park"}
```
**Expected:** `route = CATEGORY_B_STATE` (6 > 5 — GC does NOT apply)  
**Must cite:** Schedule B row + GC passage

### 3.7 Variant: 12 km (far outside GC threshold) — NEGATIVE CONTROL
```json
{"feature_type": "national_park", "distance_km": 12.0, "name": "Keoladeo National Park"}
```
**Expected:** `route = CATEGORY_B_STATE`  
**Must cite:** Schedule B row + GC passage (GC checked but not triggered)  
**FAIL if:** System returns CATEGORY_A_CENTRAL — the GC was misapplied

---

## 4. Protected Area Type Variants (all at 2 km — must all be CATEGORY_A_CENTRAL)

### 4.1 Wildlife Sanctuary
```json
{"feature_type": "wildlife_sanctuary", "distance_km": 2.0, "name": "Sariska Wildlife Sanctuary"}
```
**Expected:** `CATEGORY_A_CENTRAL`  
**Note:** Wildlife sanctuary is a "Protected Area under Wild Life (Protection) Act, 1972" — same GC clause (i)

### 4.2 Eco-Sensitive Zone
```json
{"feature_type": "eco_sensitive_zone", "distance_km": 2.0, "name": "Aravallis Eco-Sensitive Zone"}
```
**Expected:** `CATEGORY_A_CENTRAL`  
**Note:** GC clause (iii)

### 4.3 Critically Polluted Area
```json
{"feature_type": "critically_polluted_area", "distance_km": 2.0, "name": "Vapi Critically Polluted Area"}
```
**Expected:** `CATEGORY_A_CENTRAL`  
**Note:** GC clause (ii); must cite CPCB reference in GC

### 4.4 Inter-State Boundary
```json
{"feature_type": "inter_state_boundary", "distance_km": 2.0}
```
**Expected:** `CATEGORY_A_CENTRAL`  
**Note:** GC clause (iv) — "provided that" carve-out for inter-state boundaries applies only if states have an agreement

### 4.5 International Boundary
```json
{"feature_type": "international_boundary", "distance_km": 2.0}
```
**Expected:** `CATEGORY_A_CENTRAL`  
**Note:** GC clause (iv)

### 4.6 Protected Area Type Unspecified — ESCALATE
```json
{"feature_type": "other_protected_area", "distance_km": 2.0, "name": "Some Forest Area"}
```
**Expected:** `ESCALATED_TO_HUMAN`, `reason_code = PROXIMITY_UNCERTAIN`  
**Reason:** Cannot determine if GC applies without knowing the exact category of protected area under the relevant Acts

---

## 5. Ambiguous Proximity — ESCALATE

### 5.1 "Near a forest" in description only (no structured proximity)
```json
{
  "description": "...the project site is near a forest area...",
  "proximity": []
}
```
**Expected:** `ESCALATED_TO_HUMAN`, `reason_code = PROXIMITY_UNCERTAIN`  
**Reason:** "near" is ambiguous — no distance given, and the GC threshold is a specific numeric distance

### 5.2 "Adjacent to" in description
```json
{
  "description": "...the site is adjacent to the national park boundary..."
}
```
**Expected:** `ESCALATED_TO_HUMAN`, `reason_code = PROXIMITY_UNCERTAIN`  
**Reason:** "adjacent" implies very close proximity but no numeric distance — could trigger GC, cannot determine without distance

---

## 6. Enhanced Threshold (10 km) Variants

For Thermal Power Plant (item 1(d)) at 7 km from a national park:
```json
{
  "sector_hint": "Thermal Power Plants",
  "capacity": {"value": 500, "unit": "MW"},
  "proximity": [{"feature_type": "national_park", "distance_km": 7.0}]
}
```
**Expected:** `CATEGORY_A_CENTRAL`  
**Reason:** Thermal Power Plants use the 10 km threshold; 7 < 10 — GC applies  
**Must cite:** GC text specifically mentioning "item 1(d)" and "10 km"

---

## 7. How to Run the Reference Case

```bash
# Using the API directly:
curl -X POST http://localhost:8000/v1/screenings \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "demo-ref-case",
    "project_name": "Granite Quarry Reference Case",
    "description": "Open-cast mining of granite covering 10 hectares. Will extract 0.5 MTPA.",
    "sector_hint": "Mining of minerals",
    "capacity": {"value": 0.5, "unit": "MTPA"},
    "area_ha": 10,
    "location": {"state": "Rajasthan", "district": "Jodhpur"},
    "proximity": [{"feature_type": "national_park", "distance_km": 2.0, "name": "Keoladeo National Park"}]
  }'

# Poll until terminal:
curl http://localhost:8000/v1/screenings/{run_id}

# Verify citations include GC:
# The result.citations array MUST contain an entry where quote contains "5 km"
# and doc_title references the EIA Notification.
```

Using the demo preset in the web UI: Navigate to `http://localhost:3000`, click "Reference case 4.1 (Category B, 2km from park)" in the demo presets sidebar.

---

## 8. Pass/Fail Criteria for the Reference Case

The reference case (2 km variant) **PASSES** only if ALL of the following are true:

1. `route == "CATEGORY_A_CENTRAL"`
2. `citations` contains at least 2 entries
3. At least one citation has `clause_ref` referencing the Schedule (e.g., "Schedule Item 1(a)" or similar)
4. At least one citation has `clause_ref` referencing "General Condition" and `quote` contains "5 km"
5. `verification.passed == true`
6. `escalation == null` (not escalated)
7. `degraded == false`
8. `disclaimer` field is present and non-empty

The reference case **FAILS** if:
- `route == "CATEGORY_B_STATE"` (forgot to apply GC)
- `route == "ESCALATED_TO_HUMAN"` (over-cautious)
- GC is not cited (even if route is correct, uncited GC is a fail)
- `verification.passed == false` and result was still returned as confident

---

*Written: 2026-10-27 | GC text extracted from corpus, not from memory*
