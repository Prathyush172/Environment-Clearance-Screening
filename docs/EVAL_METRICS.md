# Evaluation Metrics & Methodology

This document details the exact computation and methodology for the quality, accuracy, and grounding metrics used in the Environmental Clearance Pre-Screening Service.

---

## 1. Statutory Ground Truth & Benchmark Dataset
The evaluation harness runs across a benchmark suite of 24 real-world test scenarios defined in `eval/scenarios.jsonl`.
Scenarios cover:
- Standard Category A Schedule thresholds (e.g. mining area $\ge 50\text{ ha}$)
- Standard Category B State appraisals
- The complete Section 4.1 Reference Case (0 km, 2 km, 4.9 km, 5.0 km boundary, 5.1 km, and 12 km negative control)
- Each protected feature type recognized under the General Condition:
  - Wild Life (Protection) Act, 1972 Protected Areas (National Parks, Wildlife Sanctuaries)
  - Eco-Sensitive Zones (Environment Protection Act, 1986)
  - Critically Polluted Areas (CPCB identified)
  - Inter-State and International Boundaries
- Enhanced 10 km General Condition threshold items (Thermal Power, River Valley, Industrial Estates)
- Ambiguous proximity and unclassified protected areas requiring human escalation
- Prompt-injection and adversarial jailbreak inputs

---

## 2. Metric Computations

### 2.1 Route Accuracy
$$\text{Route Accuracy} = \frac{1}{N} \sum_{i=1}^N \mathbb{I}(\text{Actual Route}_i = \text{Expected Route}_i)$$
Measures whether the system assigns the correct regulatory routing decision (`CATEGORY_A_CENTRAL`, `CATEGORY_B_STATE`, `NO_CLEARANCE_REQUIRED`, or `ESCALATED_TO_HUMAN`).

### 2.2 Correct Escalation Rate
$$\text{Correct Escalation Rate} = \frac{1}{N} \sum_{i=1}^N \mathbb{I}(\text{Escalation Status}_i = \text{Expected Status}_i)$$
Crucial safety metric: measures whether ambiguous distances, out-of-corpus projects, or prompt-injection attempts are escalated rather than guessed.

### 2.3 Citation Recall
$$\text{Citation Recall} = \frac{1}{|C_{\text{expected}}|} \sum_{c \in C_{\text{expected}}} \mathbb{I}(c \in C_{\text{actual}})$$
Verifies that every mandatory statutory passage (e.g. Schedule row and General Condition text) is cited in the determination.

### 2.4 Groundedness
$$\text{Groundedness} = \frac{|\text{Claims with Resolving Citations}|}{|\text{Total Claims}|}$$
Measures whether every statement in the basis is backed by a retrieved passage ID and quote.

### 2.5 Faithfulness
$$\text{Faithfulness} = 1.0 - \frac{|\text{Contradictions or Misapplied Logic}|}{|\text{Total Decisional Steps}|}$$
Measures whether the determined route is strictly entailed by the cited threshold text without fabricated arithmetic.

### 2.6 Hallucination Rate
$$\text{Hallucination Rate} = \frac{|\text{Phantom Citations or Fabricated Thresholds}|}{|\text{Total Citations}|}$$
Enforced to 0% by deterministic verification against retrieved chunk IDs.

---

## 3. Measured Milestone 5 Benchmark Results

| Metric | Target | Measured (researcher.v2) | Pass/Fail |
|---|---|---|---|
| **Route Accuracy** | $\ge 90.0\%$ | **91.67%** | **PASS** |
| **Correct Escalation Rate** | $\ge 90.0\%$ | **95.83%** | **PASS** |
| **Citation Recall** | $\ge 95.0\%$ | **100.00%** | **PASS** |
| **Groundedness** | $\ge 95.0\%$ | **100.00%** | **PASS** |
| **Faithfulness** | $\ge 90.0\%$ | **95.83%** | **PASS** |
| **Hallucination Rate** | $\le 5.0\%$ | **0.00%** | **PASS** |

Recorded in `docs/results/eval_latest.json`.
