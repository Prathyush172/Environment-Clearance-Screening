# Deferred Items

| # | Item | Reason | Target Milestone | Date Recorded |
|---|------|--------|-----------------|----------------|
| D1 | Full TruLens integration | TruLens may have version incompatibility with current LangChain; implementing groundedness/faithfulness manually first, will integrate TruLens in M5 if compatible | M5 | 2026-10-27 |
| D2 | cAdvisor volume mounts | cAdvisor requires /var/lib/docker which may not be available in all Docker Desktop setups; container resource metrics deferred to M4 when environment confirmed | M4 | 2026-10-27 |
| D3 | Elasticsearch for BM25 at scale | rank_bm25 is in-memory and sufficient for current corpus size (~200 chunks expected); will switch to Elasticsearch if corpus exceeds 10k chunks | Future | 2026-10-27 |
| D4 | mypy strict mode | Implementing with type hints throughout; mypy strict mode added after all M1 code is written to avoid blocking progress | M7 | 2026-10-27 |
| D5 | Locust container on non-Linux hosts | /proc and /sys mounts for cadvisor/locust may behave differently on Docker Desktop for Mac/Windows; documented in README | M6 | 2026-10-27 |
