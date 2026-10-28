# Service Level Objectives (SLO)

> **Declared:** 2026-10-28  
> **Status:** APPROVED & BASELINED  
> **Target Environment:** Production Docker Compose deployment (api, worker, verifier, gateway, redis, postgres)

---

## 1. Service Context & Justification

The Environmental Clearance Pre-Screening Service is a **decision-support pre-screening tool**, not an interactive search autocomplete. A complete screening run requires:
1. Ingestion validation and quarantine screening ($< 1\text{ s}$).
2. Celery enqueue and asynchronous worker dispatch.
3. LangGraph agent execution:
   - Schedule clause retrieval (Chroma semantic search + clause index)
   - Mandatory Modifier Check (cross-reference lookup + General Condition evaluation)
   - Follow-up query generation and retrieval
   - Deterministic threshold arithmetic (`compare_threshold`)
   - HTTP dispatch to independent Verifier service for claim entailment
   - Statutory FinalResult synthesis and disclaimer attachment

Given an average stub / model call delay of $1.5\text{ s} - 3.5\text{ s}$ per agent step across 3 agent nodes + verifier:
- Expected processing latency: $12\text{ s} - 25\text{ s}$.
- Polling interval on client side: $1.5\text{ s}$.

---

## 2. Declared Objectives

| Objective | Metric | Target | Rationale |
|---|---|---|---|
| **API Ingestion Latency** | HTTP POST `/v1/screenings` response time | **p95 $\le 1.0\text{ s}$** | Immediate validation, quarantine or 202 enqueue |
| **Complete Run Latency** | End-to-end turnaround (submission $\rightarrow$ terminal result) | **p95 $\le 45.0\text{ s}$** at 10 concurrent requests | Decision support workflow allows async polling |
| **Availability / Success** | Successful terminal status rate | **$\ge 99.0\%$** | Unrecoverable failures escalate or degrade safely |
| **Rate Limiter Responsiveness** | HTTP 429 + Retry-After header | **$100\%$ compliance** | Protects downstream LLM budget |
| **Circuit Breaker Trip Time** | Breaker status $\rightarrow$ OPEN upon 5 consecutive provider failures | **$\le 500\text{ ms}$** | Shared Redis state trips all workers immediately |

---

## 3. Concurrency & Scaling Derivation

With a single worker process (`--scale agent-worker=1`) processing $\approx 15\text{ s}$ tasks with concurrency 2:
- Throughput capacity: $\sim 0.13\text{ runs/s}$ ($\approx 8\text{ runs/min}$).
- Scaling to 3 workers (`--scale agent-worker=3`):
  - Throughput capacity increases linearly to $\approx 24\text{ runs/min}$.
  - Bottlenecks transition to Redis enqueue latency and Postgres connection pool.
