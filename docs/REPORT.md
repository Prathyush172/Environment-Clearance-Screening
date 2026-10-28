# Environmental Clearance Pre-Screening Service — Final Engineering Report

## 1. Problem Statement & Regulatory Scope
Under India's Environmental Impact Assessment (EIA) Notification, 2006 (S.O. 1533(E)) and its subsequent amendments through March 2025, commercial, mining, and industrial projects are categorized into:
- `CATEGORY_A_CENTRAL`: Projects requiring prior Environmental Clearance (EC) appraised at the Central Level by the Ministry of Environment, Forest and Climate Change (MoEFCC).
- `CATEGORY_B_STATE`: Projects appraised at the State Level by the State Environmental Impact Assessment Authority (SEIAA). Sub-categorized into B1 (requiring full EIA report and public hearing) and B2 (exempt from EIA report).
- `NO_CLEARANCE_REQUIRED`: Activities falling below statutory threshold limits.

### The Core Challenge
The critical difficulty lies in the **modifying provisions** printed after the Schedule, notably the **General Condition (GC)**:
> *"Any project or activity specified in Category 'B' will be appraised at the Central Level as Category 'A', if located in whole or in part within 5 km from the boundary of: (i) Protected Areas notified under the Wild Life (Protection) Act, 1972... (ii) Critically Polluted areas... (iii) Eco-sensitive areas... (iv) inter-State boundaries and international boundaries..."*

A naive AI system that classifies solely against the Schedule table will incorrectly mark industrial projects within 5 km of national parks as Category B. Our system implements an explicit **Modifier-Check** stage in the research loop that verifies whether the General Condition applies by operation of law, even when the user has not mentioned proximity.

---

## 2. Multi-Agent Topology & Failure Isolation

The architecture enforces strict separation of concerns across independent microservices:
1. **Intake & Classifier Agent** (`services/worker/`): Sanitises input text, extracts numerical capacity, area, and location entities, and flags out-of-corpus requests.
2. **Researcher / Determiner Agent** (`services/worker/`): LangGraph execution graph cycling through 6 read-only tools:
   - `corpus_search`: Dense semantic + BM25 keyword hybrid retrieval.
   - `get_clause`: Exact structured clause lookup.
   - `get_request_field`: Safe parameter accessor.
   - `find_modifiers`: Mandatory cross-reference inspection seeded by retrieved passage text.
   - `list_amendments`: Chronological amendment reconciliation.
   - `compare_threshold`: Deterministic numerical arithmetic preventing LLM math errors.
3. **Independent Verifier Agent** (`services/verifier/`): Separate FastAPI process hosting an independent verification model that checks claim entailment and verbatim quote fidelity against retrieved chunks.
4. **Resilient LLM Gateway** (`services/llm_gateway/`): Single choke point with timeouts, tenacity backoff, shared Redis circuit breaker, and graceful degradation to deterministic preliminary screening.

---

## 3. Benchmark Evaluation Results

Batch evaluation was executed across 24 real-world statutory scenarios (`eval/scenarios.jsonl`):

| Evaluation Metric | Target | Measured Result | Status |
|---|---|---|---|
| **Route Accuracy** | $\ge 90.0\%$ | **91.67%** | **PASS** |
| **Correct Escalation Rate** | $\ge 90.0\%$ | **95.83%** | **PASS** |
| **Citation Recall** | $\ge 95.0\%$ | **100.00%** | **PASS** |
| **Groundedness** | $\ge 95.0\%$ | **100.00%** | **PASS** |
| **Faithfulness** | $\ge 90.0\%$ | **95.83%** | **PASS** |
| **Hallucination Rate** | $\le 5.0\%$ | **0.00%** | **PASS** |

### Section 4.1 Reference Case Verification
- Input: Open-cast granite quarry (Category B lease area $<50\text{ ha}$) located 2 km from Keoladeo National Park.
- Outcome: Assigned `CATEGORY_A_CENTRAL`.
- Citations: Verifiably cites both Schedule Item 1(a) and the General Condition quoting the 5 km threshold.
- Negative Control (12 km away): Retains `CATEGORY_B_STATE`.

---

## 4. Key Architectural Decisions
- **Celery vs RQ/Arq**: Celery chosen for mature dead-letter handling, `acks_late=True`, and task retry semantics.
- **LangGraph vs CrewAI**: LangGraph chosen for explicit graph topology, strict loop bounds (`MAX_STEPS=12`, `MAX_TOOL_CALLS=15`), and persistent state checkpointing.
- **Shared Redis Circuit Breaker**: Prevents worker replicas from hammering failing LLM providers independently.
- **Deterministic compare_threshold**: Offloads distance and acreage math from LLM token prediction to deterministic Python floating point checks.
