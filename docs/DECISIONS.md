# Architecture Decisions

## D1: Celery vs RQ vs Arq

**Chosen:** Celery with Redis broker

**Alternatives considered:**
- RQ (Redis Queue): simpler than Celery, good for simple Python functions. Rejected because: lacks the robust task routing, retry policies, acks_late semantics, and task canvas features we need. Less mature ecosystem.
- Arq: asyncio-native, clean API. Rejected because: smaller ecosystem, fewer production deployments in high-throughput use cases, missing some retry/dead-letter features.

**Why Celery:**
- Mature, production-proven at scale
- `acks_late=True` ensures at-least-once delivery even if worker crashes
- `task_reject_on_worker_lost=True`: if worker dies, task re-queued rather than lost
- Rich retry policy with exponential backoff
- Dead-letter queue support
- Idempotency by task_id = run_id
- `--scale N` works natively with docker compose

---

## D2: ChromaDB vs pgvector vs Qdrant

**Chosen:** ChromaDB server mode for dense vector retrieval

**Alternatives considered:**
- pgvector: Single datastore with PostgreSQL, but lacks built-in collection lifecycle management, lightweight HTTP endpoints, and native client abstractions in early prototype phases.
- Qdrant: Powerful Rust vector engine, but heavier container resource footprint for small gazette corpus.

**Why ChromaDB:**
- Native integration with Python and LangChain ecosystems
- Embedded or lightweight server mode with Docker (`chromadb/chroma:0.5.20`)
- Built-in cosine/HNSW search and metadata filtering
- Persistence to volume (`/chroma/chroma`)
- Fast startup and low memory footprint (~100MB)

---

## D3: LangGraph vs Linear LangChain / CrewAI

**Chosen:** LangGraph state graph with persistent checkpointer (M2+)

**Alternatives considered:**
- Pure LangChain AgentExecutor: deprecated, inflexible loop control, opaque state machine.
- CrewAI / Autogen: multi-agent frameworks with excess prompt overhead and unpredictable conversational drift.

**Why LangGraph:**
- Explicit graph topology with cyclic execution (research -> modifier check -> entailment -> retry)
- Strict bounds control (`MAX_STEPS`, `MAX_TOOL_CALLS`) enforced by state counter
- Stateful persistence across checkpoints (allows crash resume)
- Clear separation between intake, researcher, and verifier roles

---

## D4: FastAPI for API and Microservices

**Chosen:** FastAPI with Pydantic v2 and async SQLAlchemy 2.0

**Alternatives considered:**
- Flask: Synchronous by default, requires gevent/gunicorn wrappers for high concurrency.
- Django / DRF: Monolithic, heavy ORM overhead, overkill for stateless microservices.

**Why FastAPI:**
- Async-native HTTP handling, achieving sub-second 202 submission response
- Automatic OpenAPI / Swagger generation
- Direct integration with Pydantic v2 models for schema validation
- First-class support for Prometheus metrics and OpenTelemetry instrumentation

---

## D5: Independent Verifier Microservice

**Chosen:** Decoupled Verifier running on a separate HTTP service port (8001)

**Alternatives considered:**
- In-process Python function inside agent worker.

**Why Decoupled Microservice:**
- Separation of concerns: Verifier must NOT share the researcher's intermediate reasoning, biases, or tool call context.
- Independent scaling and failure domain: If the verifier is unreachable or times out, the circuit breaker safely degrades or marks the run as ESCALATED rather than returning an unverified answer.
- Supports independent model routing (e.g. researcher on Claude 3.5 Sonnet, verifier on GPT-4o).

---

## D6: Structure-Aware Chunking for EIA Corpus

**Chosen:** Table-aware and clause-aware chunking (one chunk per Schedule item, General Condition as dedicated chunk)

**Alternatives considered:**
- Naive fixed 500-word / token chunking with overlap.

**Why Structure-Aware Chunking:**
- EIA Notification 2006 contains a 5-column Schedule table with multi-line rows. Naive chunking splits rows across chunks, separating project activities from their corresponding Category A/B threshold rules.
- The General Condition (Footnote 93) must apply to ALL Category B items; assigning it a distinct `chunk_type="general_condition"` and `applies_to_all_schedule_items=True` metadata tag enables deterministic lookup in modifier check loops.

---

## D7: Quarantine Pattern for Malformed Submissions

**Chosen:** Isolate rejected payloads into a `quarantine` database table with HTTP 422

**Alternatives considered:**
- Simple HTTP 400 Bad Request with immediate discard.

**Why Quarantine Pattern:**
- Security forensics: inspect adversarial prompt injection attempts without executing worker tasks.
- Auditability: consultants and users can see exact validation errors and field locators.
- Queue protection: prevents invalid tasks from reaching Redis/Celery worker queues.
