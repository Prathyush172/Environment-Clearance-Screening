# Implementation Plan — Environmental Clearance Pre-Screening Service

> **Generated:** 2026-10-27  
> **Status:** ACTIVE — updated after each milestone  
> **Scope:** Production-grade Docker-Compose-deployed EIA Notification 2006 screening system

---

## Table of Contents
1. [Project Overview](#1-project-overview)
2. [Service Inventory](#2-service-inventory)
3. [Milestone Plan](#3-milestone-plan)
4. [Risk Register](#4-risk-register)
5. [Cross-Cutting Concerns](#5-cross-cutting-concerns)
6. [Acceptance Criteria](#6-acceptance-criteria)

---

## 1. Project Overview

The **Environmental Clearance Pre-Screening Service** classifies project proposals under India's EIA Notification, 2006 (SO 1533(E)) and all amendments up to March 2025. It is a **screening opinion tool only** — it never grants, denies, or determines clearance legally. Every response carries an explicit disclaimer that an accredited environmental consultant makes the final determination.

### Core decision flow
```
User Submission
      │
      ▼
[Validation + Guardrails]──reject──▶ quarantine table  (HTTP 422, no run)
      │
      ▼ enqueue (Celery / Redis)
      │
      ▼
[Intake & Classifier Agent]
      │ IntakeResult (typed)
      ▼
[Researcher / Determiner Agent]  ◄──── tools (corpus_search, get_clause,
      │   LangGraph loop             find_modifiers, list_amendments,
      │   ≤ MAX_STEPS/CALLS/SECS    compare_threshold, get_request_field)
      │ ResearchDraft (typed)
      ▼
[Verifier Agent]  (separate HTTP service)
      │ VerificationReport (typed)
      ▼
[FinalResult]
      │
      ├── NO_CLEARANCE_REQUIRED
      ├── CATEGORY_B_STATE
      ├── CATEGORY_A_CENTRAL
      └── ESCALATED_TO_HUMAN
```

### Key design principles
- **Knowing when NOT to answer** is more important than always answering.
- Every claim in the output must be grounded in and cite a retrieved corpus passage.
- The General Condition (printed after the Schedule) that upgrades Category B to A near protected/critically polluted/eco-sensitive areas and boundaries is **always checked** even when the user does not mention proximity — the modifier-check step is mandatory in the research loop.
- The system NEVER does impact assessment.

---

## 2. Service Inventory

| # | Service Name | Technology | Primary Role | Scaling |
|---|---|---|---|---|
| 1 | `api` | FastAPI 0.115+ | Ingestion, validation, status, SSE, feedback, admin | Stateless, H-scale |
| 2 | `agent-worker` | Celery 5+ / LangGraph | Intake+Researcher agents, task execution | H-scale (`--scale N`) |
| 3 | `verifier` | FastAPI + LangGraph | Independent Verifier agent (own process) | Single replica (circuit-breaker if down) |
| 4 | `llm-gateway` | FastAPI | Provider abstraction, retry, circuit-breaker, cost tracking | Stateless, H-scale |
| 5 | `llm-stub` | FastAPI | Fixed/delayed fake LLM responses for load/eval | Single replica |
| 6 | `chroma` | ChromaDB server | Vector store (dense retrieval) | Single replica + volume |
| 7 | `ingest` | Python CLI | PDF → chunk → embed → upsert pipeline (one-shot) | Run-once job |
| 8 | `redis` | Redis 7 | Celery broker, cache, rate-limit, circuit-breaker state | Single replica + AOF |
| 9 | `postgres` | PostgreSQL 16 | Durable store (runs, steps, feedback, quarantine, eval) | Single replica + WAL |
| 10 | `web` | React/Vite/TS + nginx | Frontend SPA + API proxy | Single replica (CDN-ready) |
| 11 | `otel-collector` | OpenTelemetry Collector | Trace aggregation to Jaeger | Single replica |
| 12 | `jaeger` | Jaeger all-in-one | Distributed tracing UI | Single replica |
| 13 | `prometheus` | Prometheus | Metrics scraping | Single replica |
| 14 | `grafana` | Grafana | Dashboards (provisioned as code) | Single replica |
| 15 | `redis-exporter` | redis_exporter | Redis to Prometheus | Single replica |
| 16 | `postgres-exporter` | postgres_exporter | PG to Prometheus | Single replica |
| 17 | `cadvisor` | cAdvisor | Container resource metrics to Prometheus | Single replica |
| 18 | `locust` | Locust | Load testing (profile: loadtest) | Profile only |
| 19 | `eval-runner` | Python CLI | Batch eval (profile: eval) | Profile only |

---

## 3. Milestone Plan

### M1 — Working End-to-End Path (Priority: CRITICAL)
**Goal:** `docker compose up` from a clean clone produces a working system. A user can submit a project description and poll for a (stub-backed) result.

**Deliverables:**
- [ ] Full repository layout created (`services/`, `libs/common/`, `prompts/`, `eval/`, `data/corpus/`, `infra/`, `scripts/`, `tests/`, `docs/`)
- [ ] `docker-compose.yml` with services: api, agent-worker, redis, postgres, chroma, llm-stub, web, ingest
- [ ] Health checks + `depends_on: condition: service_healthy` on all services
- [ ] `libs/common/`: config (pydantic-settings v2), structured logging (structlog), base models, db session, tracing stubs
- [ ] **Data pipeline** (`services/ingest/`):
  - PDF discovery in `data/corpus/` (no hardcoded filenames)
  - Text extraction: pdfplumber (primary) + OCR fallback (Tesseract/ocrmypdf)
  - Structure-aware chunking: one chunk per Schedule row, General Condition as own chunk with `applies_to_all` flag, prose overlap 50 tokens
  - Clause index (identifier to chunk_ids) in Postgres
  - Cross-reference index (phrases: "see", "General Condition", "notwithstanding", "provided that", "Category B shall be treated as A") in Postgres
  - Content hash per doc/chunk — idempotent upserts to Chroma
  - `index_manifest` table populated
  - CLI: `python -m ingest run [--corpus] [--reembed] [--only] [--dry-run]` + `python -m ingest status`
- [ ] **Validation layer** (`services/api/validation.py`):
  - All fields per data contract (Section 3 of spec)
  - All cross-field rules
  - Quarantine table insert on failure (raw payload + errors, PII redacted)
  - Returns HTTP 422 with field-level errors
  - `validation_rejected_total` Prometheus counter
  - No run row created on validation failure
- [ ] **API** (`services/api/`):
  - `POST /v1/screenings` returns 202 `{run_id, status_url, correlation_id}` in < 1 s
  - `GET /v1/screenings/{run_id}` returns status + partial progress
  - `GET /v1/quarantine/{id}`, `GET /v1/quarantine` list
  - `GET /health`, `GET /ready`, `GET /metrics`
  - Correlation ID: accept `X-Correlation-ID` header or generate UUID
- [ ] **Simple Agent** (agent-worker, no LangGraph yet — linear flow for M1):
  - Intake step: sanitise, classify sector
  - Research step: single `corpus_search` call via Chroma
  - Draft step: sends draft to LLM stub
  - Result stored in postgres `runs` table
- [ ] **llm-stub** service: returns fixed deterministic responses per prompt type with STUB_DELAY_MS_MIN/MAX delay
- [ ] **Web** (M1 minimal):
  - `/` form page with all input fields
  - `/runs/:id` polling the status endpoint (no SSE yet)
  - Persistent disclaimer banner
  - Demo presets sidebar
- [ ] **Postgres schema** (Alembic migrations): `runs`, `run_steps`, `quarantine`, `clause_index`, `cross_ref_index`, `index_manifest`, `feedback`, `eval_results`
- [ ] **Tests (M1)**: unit tests for validators, all cross-field rules, chunker; integration test that malformed request gives 422 + quarantine entry + no run row + Celery queue empty
- [ ] **Docs**: README (clean-clone-to-running), `docs/DECISIONS.md` (skeleton), `docs/DEFERRED.md`

**Success criterion:** `docker compose up` — submit a valid request — poll — see COMPLETED result (stub); submit malformed — 422 + quarantine; tests pass.

---

### M2 — Real LangGraph Research Loop + Verifier (Priority: CRITICAL)
**Goal:** The full agent topology runs. The Reference Case (Section 4.1) passes end-to-end.

**Deliverables:**
- [ ] **LangGraph graph** in agent-worker with nodes: `intake_classify`, `retrieve_provision`, `modifier_check`, `query_from_reading`, `draft_determination`, `claim_support_eval`, `retry_search`, `escalate`, `send_to_verifier`, `finalize`
- [ ] **Postgres-backed persistent checkpointer** (langgraph-checkpoint-postgres) for crash resume
- [ ] **All 6 tools** implemented as LangChain tools with schema validation, timeout, read-only enforcement
- [ ] **Verifier service** (`services/verifier/`) with own LangGraph graph, own prompts, own model config
  - Deterministic checks + LLM entailment check
  - On failure: re-search up to MAX_VERIFY_ATTEMPTS, then ESCALATED
- [ ] **Typed hand-off contracts**: `IntakeResult`, `ResearchDraft`, `VerificationReport`, `FinalResult` in `libs/common/models/`
- [ ] **All 9 escalation reason codes** implemented
- [ ] **Prompt files** (versioned): v1 and v2 for researcher, v1 for intake and verifier, `prompts/registry.yaml`
- [ ] **Reference Case** passes: 2 km from national park → CATEGORY_A_CENTRAL citing Schedule + GC
- [ ] **`docs/REFERENCE_CASE.md`**: exact corpus passages, all distance variants, negative control
- [ ] **Tests (M2)**: each escalation trigger, loop bounds, verifier failure → ESCALATED
- [ ] **Docs**: `docs/AGENT_DESIGN.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`

**Success criterion:** Reference Case returns `CATEGORY_A_CENTRAL` citing BOTH Schedule row AND General Condition.

---

### M3 — Gateway, Resilience, Guardrails, Prompt Versioning (Priority: HIGH)

**Deliverables:**
- [ ] **LLM Gateway** with timeouts, retry (tenacity), circuit breaker (Redis state), provider routing, token/cost accounting, guardrail hooks
- [ ] **Graceful degradation**: primary → fallback → DEGRADED (no LLM, lexical only, ESCALATED result) → hard fail
- [ ] **Guardrails**: input normalisation, injection detection, delimiter wrapping, output filtering, toxicity detection, metrics
- [ ] **Fault injection endpoint**: `POST /admin/faults` (guarded, disabled unless `ADMIN_FAULTS_ENABLED=true`)
- [ ] **Prompt versioning**: version from `prompts/registry.yaml`, recorded in every step and result
- [ ] **Tests (M3)**: adversarial inputs, circuit breaker state machine, degradation path, output guard

---

### M4 — Observability, Cost, Trace, SSE, Full UI (Priority: HIGH)

**Deliverables:**
- [ ] Structured logging (structlog) everywhere
- [ ] OpenTelemetry traces: api → Celery → LangGraph nodes → tools → verifier → gateway → LLM call; exported via otel-collector to Jaeger
- [ ] Prometheus metrics (all per spec); scraped from all services including exporters
- [ ] Three Grafana dashboards provisioned as code
- [ ] `GET /v1/screenings/{run_id}/trace` endpoint
- [ ] SSE endpoint `GET /v1/screenings/{run_id}/events`
- [ ] HMAC-signed callback
- [ ] Full Web UI: all 6 pages, light/dark theme, WCAG AA, responsive, keyboard nav
- [ ] `GET /v1/stats`, `/v1/index` endpoints

---

### M5 — Eval Set, TruLens Metrics, A/B Prompts, Live Scoring (Priority: HIGH)

**Deliverables:**
- [ ] `eval/scenarios.jsonl`: at least 24 scenarios covering all required cases
- [ ] Batch eval CLI + `make eval`
- [ ] TruLens (or equivalent) metrics: groundedness, context relevance, faithfulness, hallucination rate
- [ ] Additional metrics: route accuracy, citation recall, correct-escalation rate, false-answer rate
- [ ] Prompt A/B comparison: `make eval-ab` with comparison table
- [ ] Deliberate change experiment: before/after modifier-check step, `docs/results/before_after.md`
- [ ] Live quality scoring: background Celery task, Grafana chart
- [ ] `docs/EVAL_METRICS.md`

---

### M6 — Caching, Rate Limiting, SLO, Locust Load Tests (Priority: MEDIUM)

**Deliverables:**
- [ ] `docs/SLO.md` committed before any measurement (p95 target with derivation)
- [ ] Three-layer caching (embedding, retrieval, whole-run) with Redis, toggleable via env
- [ ] Rate limiting: token bucket per client and IP, concurrent cap, daily budget
- [ ] Cache benchmark script: `scripts/cache_benchmark.py` → `docs/results/caching.md`
- [ ] `scripts/cost_report.py`
- [ ] Locust load test with scale test and bottleneck identification, `make loadtest`
- [ ] Results saved to `docs/results/loadtest_<ts>.md`

---

### M7 — Documentation, Demo Script, Polish (Priority: MEDIUM)

**Deliverables:**
- [ ] All required documentation files complete and accurate
- [ ] `docs/DEMO.md`: one-command instructions for all 10 demo items
- [ ] `README.md`: clean-clone-to-running in ≤ 10 commands
- [ ] `docs/INCIDENT_LOG.md`: template + real entries (NO fabrications)
- [ ] `docs/REPORT.md`: course report skeleton
- [ ] `.env.example`: all variables documented
- [ ] `make test` passes; `make lint` passes; `make eval` completes
- [ ] `docs/DEFERRED.md` complete with all deferred items and reasons

---

## 4. Risk Register

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | General Condition text not found in corpus | Medium | CRITICAL | Ingest all PDFs; human-verify with `ingest status`; store raw extracted text |
| R2 | Schedule table parsed incorrectly (multi-row cells) | High | HIGH | pdfplumber + PyMuPDF fallback; structure-aware chunker tests with known rows |
| R3 | LLM hallination of Schedule thresholds | High | HIGH | `compare_threshold` tool is deterministic; Verifier rechecks; every claim must cite a passage |
| R4 | LangGraph-checkpoint-postgres incompatibility | Low | MEDIUM | Fallback: Redis checkpointer; document in DEFERRED.md if switched |
| R5 | ChromaDB server mode instability | Low | MEDIUM | Health checks; auto-restart; named volume; test with chroma reset scenario |
| R6 | Verifier always unreachable during load | Medium | HIGH | Circuit breaker; result = ESCALATED/DEGRADED; RUNBOOK.md |
| R7 | Corpus OCR quality (scanned PDFs) | Medium | MEDIUM | Tesseract + ocrmypdf; log OCR confidence; flag low-confidence chunks |
| R8 | Proximity data missing from user | High | MEDIUM | Entity extraction from free text; PROXIMITY_UNCERTAIN escalation trigger |
| R9 | Amendment conflicts | Medium | HIGH | `list_amendments` tool; `AMENDMENTS_CONFLICT` escalation trigger; chronological ordering |
| R10 | Docker build fails on clean clone | Medium | HIGH | Pin all dependencies; test clean build; README troubleshooting |
| R11 | sentence-transformers model download fails | Medium | MEDIUM | Bake model into ingest Docker image; HF_HOME volume; offline fallback documented |
| R12 | BM25 performance with large corpus | Low | LOW | rank_bm25 in-memory; if corpus grows, Elasticsearch documented as DEFERRED option |
| R13 | TruLens incompatibility | Medium | MEDIUM | Implement groundedness/faithfulness manually with sentence similarity |
| R14 | SSRF via callback_url | Low | CRITICAL | Allowlist validation (HTTPS only, no private IPs); test with internal URLs |
| R15 | Prompt injection via corpus text | Medium | HIGH | Corpus text delimited; tool args validated; output guard; adversarial eval tests |

---

## 5. Cross-Cutting Concerns

### 5.1 Secret Management
- Zero secrets in repo — enforced by `.gitignore` (.env) and recommended pre-commit hook (gitleaks)
- All credentials injected via `.env` at runtime
- `ADMIN_TOKEN` required for fault injection
- LLM API keys only mounted to `llm-gateway` service

### 5.2 Correlation ID Propagation Chain
```
API request → Celery task headers → LangGraph state → tool calls → verifier HTTP → llm-gateway → DB rows → logs → OTEL spans
```

### 5.3 Idempotency
- Celery tasks: `task_id = run_id`; check if run already terminal before processing
- Ingest: content hash per chunk; upsert (not insert) to Chroma
- Whole-run cache: if run_id already completed, return cached result

### 5.4 Type Safety
- Python 3.11+, type hints everywhere, Pydantic v2 models for all contracts
- `mypy --strict` added to lint step
- No `Any` without explicit justification comment

### 5.5 Read-Only Tools
All LangGraph tools are read-only; cannot write DB, make network calls, or read secrets.

---

## 6. Acceptance Criteria

| # | Criterion | Test / Evidence |
|---|---|---|
| AC1 | `docker compose up` brings up healthy system | `docker compose ps` all healthy |
| AC2 | Reference Case returns CATEGORY_A_CENTRAL citing Schedule + GC | `make eval` scenario `reference_case_2km` passes |
| AC3 | Same project at distance > GC limit stays Category B | `make eval` scenario `reference_case_12km` passes |
| AC4 | Malformed request gives 422 + quarantine + no run row + no Celery task | Integration test asserts queue empty |
| AC5 | Verifier unreachable gives ESCALATED (never confident wrong answer) | Integration test with verifier container stopped |
| AC6 | Provider down gives circuit breaker open and DEGRADED result | `POST /admin/faults {type: "provider_down"}` demo |
| AC7 | Prompt injection gives guardrail triggered + metric incremented | Adversarial eval scenarios pass |
| AC8 | All 6 web pages render correctly with no JS errors | Manual verification + e2e test |
| AC9 | `GET /v1/screenings/{run_id}/trace` returns complete trace | Integration test checks all required fields |
| AC10 | `make test` passes with zero failures | CI output |
| AC11 | `make lint` (ruff + mypy) passes | CI output |
| AC12 | `make eval` gives at least 90% route accuracy on stub | Eval report |
| AC13 | Locust p95 measured and documented vs SLO target | `docs/results/loadtest_*.md` exists |
| AC14 | All 10 demo items reproducible from `docs/DEMO.md` | Manual walkthrough |
| AC15 | No hardcoded credentials, endpoints, or model IDs in repo | `git grep` clean |

---

## Appendix A: Environment Variable Catalogue (preview — full in `.env.example`)

| Variable | Required | Description |
|---|---|---|
| `LLM_PROVIDER` | Yes | Primary LLM provider (openai, anthropic, azure_openai, stub) |
| `LLM_MODEL_ID` | Yes | Model identifier for primary provider |
| `LLM_API_KEY` | Cond. | API key (not required if provider=stub) |
| `LLM_BASE_URL` | No | Base URL override (for Azure / local) |
| `FALLBACK_LLM_PROVIDER` | No | Fallback provider (default: stub) |
| `FALLBACK_LLM_MODEL_ID` | No | Fallback model |
| `FALLBACK_LLM_API_KEY` | No | Fallback API key |
| `FALLBACK_LLM_BASE_URL` | No | Fallback base URL |
| `VERIFIER_LLM_PROVIDER` | No | Provider for Verifier agent (defaults to primary) |
| `VERIFIER_LLM_MODEL_ID` | No | Model for Verifier agent |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `REDIS_URL` | Yes | Redis connection string |
| `CHROMA_HOST` | Yes | Chroma server hostname |
| `CHROMA_PORT` | Yes | Chroma server port |
| `ADMIN_TOKEN` | Yes | Admin API token for fault injection |
| `ADMIN_FAULTS_ENABLED` | No | Enable fault injection endpoint (default: false) |
| `STUB_DELAY_MS_MIN` | No | Stub minimum delay ms (default: 1500) |
| `STUB_DELAY_MS_MAX` | No | Stub maximum delay ms (default: 4000) |
| `MAX_STEPS` | No | LangGraph loop bound (default: 12) |
| `MAX_TOOL_CALLS` | No | Tool call budget per run (default: 15) |
| `RUN_WALL_CLOCK_SECONDS` | No | Wall-clock timeout per run (default: 90) |
| `MAX_VERIFY_ATTEMPTS` | No | Verifier retry attempts (default: 2) |
| `MAX_REPLANS` | No | Researcher replan attempts (default: 2) |
| `GUARDRAIL_CLASSIFIER_ENABLED` | No | Enable HF classifier for injection detection (default: true) |
| `QUALITY_SAMPLE_RATE` | No | Live quality sampling rate 0-1 (default: 0.1) |
| `FEATURE_MODIFIER_CHECK_ENABLED` | No | Feature flag for modifier-check step (default: true) |
| `CALLBACK_HMAC_SECRET` | No | HMAC secret for callback signing |
| `RATE_LIMIT_RPM_PER_CLIENT` | No | Rate limit requests/minute per client (default: 60) |
| `MAX_CONCURRENT_RUNS_PER_CLIENT` | No | Max in-flight runs per client (default: 5) |

---

## Appendix B: Corpus Files Discovered

The following PDF files were found in `data/corpus/` (filenames discovered at runtime, not hardcoded in code):

| File | Size | Notes |
|---|---|---|
| `EIA_Notification_2006_including_all_amendments_till_March_2025 (1).pdf` | 274 KB | Primary compiled notification + amendments |
| `Compedium1.pdf` | 30 MB | Large compendium — likely contains Schedule + GC |
| `N36.pdf` | 77 MB | Very large — likely full gazette or compendium |
| `720.pdf` | 8 MB | Amendment or related notification |
| `216_OM_11_06_2019.pdf` | 4 MB | Office Memorandum, June 2019 |
| `4_SO3067E_01122009.pdf` | 1.7 MB | SO 3067(E) — Dec 2009 amendment |
| `63_SO1886E.pdf` | 1.4 MB | SO 1886(E) amendment |
| `32_SO3518E_23112016.pdf` | 1 MB | SO 3518(E) — Nov 2016 amendment |
| `26320.pdf` | 1.2 MB | Amendment/notification |
| `C24.pdf` | 510 KB | Amendment/OM |
| `27_SO141E_15012016.pdf` | 459 KB | SO 141(E) — Jan 2016 amendment |
| `15_SO1599_E_25062014.pdf` | 328 KB | SO 1599(E) — Jun 2014 amendment |
| `3_SO1737E_11102007.pdf` | 196 KB | SO 1737(E) — Oct 2007 amendment |
| `7 _om nbwl.pdf` | 128 KB | NBWL Office Memorandum |
| `2_SO1939E_13112006.pdf` | 32 KB | SO 1939(E) — Nov 2006 (early amendment) |

---

*Last updated: 2026-10-27 | Current milestone: M1 — Starting implementation*
