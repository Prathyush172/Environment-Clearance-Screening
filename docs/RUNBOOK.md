# Operational Runbook

This runbook covers detection, verification, and recovery procedures for the two primary failure modes of the Environmental Clearance Pre-Screening Service.

---

## Failure Mode 1: LLM Upstream Outage / Circuit Breaker Open

### 1. Symptoms
- Prometheus alerts trigger on `circuit_breaker_state{provider="primary"} == 2`.
- Log entries report: `primary_breaker_open_routing_fallback` or `all_providers_unavailable_entering_degraded_mode`.
- Screening responses return `degraded: true` with escalation reason `PROVIDER_UNAVAILABLE`.
- Endpoints respond normally with HTTP 200/202, but no confident categorizations are produced.

### 2. Diagnosis
1. Inspect gateway health endpoint:
   ```bash
   curl http://localhost:8002/health
   ```
   Check `"primary_breaker": "OPEN"`.
2. Inspect Prometheus metric:
   ```bash
   curl -s http://localhost:8002/metrics | grep circuit_breaker_state
   ```
3. Check upstream provider connectivity / API key quotas.

### 3. Recovery Steps
1. Verify if upstream provider connectivity has been restored.
2. If using real LLM provider, verify API keys in `.env` and restart gateway:
   ```bash
   docker compose restart llm-gateway
   ```
3. If simulated via fault injection, issue the reset command:
   ```bash
   curl -X POST http://localhost:8002/admin/faults \
     -H "Content-Type: application/json" \
     -d '{"fault_type": "reset", "admin_token": "change-me-admin-token-32chars-min"}'
   ```
4. Verify circuit breaker transitions: `OPEN -> HALF_OPEN -> CLOSED`.

---

## Failure Mode 2: Missing, Corrupted, or Stale Vector Index

### 1. Symptoms
- Retrieval tools return empty results or fallback passages.
- Worker logs report: `Could not connect to a Chroma server` or `Collection eia_corpus not found`.
- Ingestion status reports doc count 0 or outdated index timestamp.

### 2. Diagnosis
1. Check Chroma service health:
   ```bash
   curl http://localhost:8000/api/v1/heartbeat
   ```
2. Check ingestion status:
   ```bash
   docker compose run --rm ingest python -m ingest status
   ```

### 3. Recovery Steps
1. Re-run idempotent ingestion pipeline across the corpus:
   ```bash
   docker compose run --rm ingest python -m ingest run --corpus /data/corpus
   ```
2. If embedding model was updated, trigger complete re-embedding:
   ```bash
   docker compose run --rm ingest python -m ingest run --corpus /data/corpus --reembed
   ```
3. Check index manifest in Postgres to confirm upserted chunk count and hash consistency.
