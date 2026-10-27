# Environmental Clearance Pre-Screening Service

> **Notice:** SCREENING OPINION ONLY: This is not a legal determination of environmental clearance requirements. An accredited environmental consultant must make the final determination. This system performs pre-screening only and does not constitute environmental impact assessment.

A production-grade pre-screening service classifying project proposals under India's **Environment Impact Assessment (EIA) Notification, 2006 (S.O. 1533(E))** and gazetted amendments up to March 2025.

---

## Architecture Overview

```
User Submission (Web / API)
       │
       ▼
[Validation + Guardrails] ──reject──▶ Quarantine Table (HTTP 422)
       │
       ▼ enqueue (Celery / Redis)
       │
[Intake & Classifier Agent]
       │
[Researcher / Determiner Agent] ◄─── Tools (ChromaDB, Clause Lookup, Modifier Check)
       │
[Independent Verifier Service] (HTTP 8001)
       │
[FinalResult] ──▶ Route (Category A / Category B / No Clearance / Escalated)
```

---

## Clean-Clone Quickstart (≤ 10 Commands)

```bash
# 1. Clone repository
git clone <repo-url> && cd environment_clearance_screening

# 2. Copy environment configuration
cp .env.example .env

# 3. Build container images
docker compose build

# 4. Start core infrastructure and services
docker compose up -d

# 5. Run initial corpus ingestion pipeline
docker compose run --rm ingest python -m ingest run --corpus /data/corpus

# 6. Run test suite
docker compose run --rm api pytest /app/tests/unit -v

# 7. Open Web UI
open http://localhost:3000

# 8. Access API documentation & OpenAPI spec
open http://localhost:8000/docs

# 9. Access Observability (Jaeger Traces & Grafana Dashboards)
open http://localhost:16686   # Jaeger
open http://localhost:3001    # Grafana (admin / admin)
```

---

## Service Endpoints

| Service | Port | Endpoint / Role |
|---|---|---|
| `web` | 3000 | React / Vite Frontend SPA |
| `api` | 8000 | FastAPI Gateway & Screening API (`/v1/screenings`) |
| `verifier` | 8001 | Independent Verification Service (`/v1/verify`) |
| `llm-gateway` | 8002 | Outbound LLM Gateway & Resiliency Layer |
| `llm-stub` | 8080 | Deterministic mock LLM with latency & failure simulation |
| `prometheus` | 9090 | Metrics Scraping |
| `grafana` | 3001 | Dashboards |
| `jaeger` | 16686 | Distributed Tracing UI |

---

## Directory Structure

```
.
├── corpus/                 # Source PDF corpus (EIA Notification 2006 + amendments)
├── docs/                   # Implementation plan, architecture decisions, reference case
├── infra/                  # Prometheus, Grafana, OpenTelemetry Collector configs
├── libs/common/            # Common config, DB models, Pydantic contracts, logging, tracing
├── prompts/                # Versioned YAML prompts for intake, researcher, verifier
├── services/
│   ├── api/                # FastAPI screening submission and status API
│   ├── worker/             # Celery worker with linear & LangGraph agents
│   ├── verifier/           # Independent verifier microservice
│   ├── llm_gateway/        # LLM gateway & resilience router
│   ├── llm_stub/           # Deterministic OpenAI-compatible mock LLM
│   ├── ingest/             # PDF text extraction & structure-aware chunking pipeline
│   └── web/                # React/TypeScript/Tailwind CSS frontend
├── tests/                  # Unit and integration test suite
├── docker-compose.yml      # Complete multi-container orchestration
└── Makefile                # Developer workflow targets
```
