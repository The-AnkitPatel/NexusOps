# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.3.0] — 2026-11-17

Theme: **from honest to standout — measurement, real observability, and extensibility.**

### Added
- **Evaluation harness** (`evals/`): a 17-query labelled set and a runner that
  reports intent accuracy, retrieval Precision@1 / Recall@k / MRR, SQL success,
  grounding pass-rate, and latency. `make eval` fills the README Benchmarks block;
  a pytest regression-guards the metrics. (88% intent, 92% P@1, 100% Recall@3, 0.962 MRR.)
- **Observability stack**: `docker compose up` now also starts an **OpenTelemetry
  Collector + Jaeger**; the gateway exports OTLP and traces are viewable at `:16686`.
- **Pluggable dense embeddings** (`nexus/rag/embeddings.py`): an `EmbeddingProvider`
  Protocol with `TfidfEmbedder` (offline default) and a key-gated `GeminiEmbedder`
  that degrades gracefully; `/v1/health` reports the active embedder.
- **Optional live-Gemini intent routing** with the keyword classifier as a
  guaranteed fallback. The LLM only routes — executable SQL stays deterministic.
- **SSE streaming** endpoint `POST /v1/agent/query/stream`.
- **Request-id + structured access-log** middleware (`X-Request-ID`).
- **UI**: the execution trace now renders as an Altair **Gantt timeline**.

### Changed
- Version `0.3.0`; test suite **27 → 32** (+ the eval regression guard); README gains
  Benchmarks and Observability sections.

## [0.2.0] — 2026-11-17

Theme: **make every headline claim real and honest, and wrap it in production rigor.**

### Changed — retrieval is now genuinely hybrid
- Replaced the ad-hoc "dense semantic cosine" (which was word-overlap + an acronym
  boost) with a **real TF-IDF vector space + L2-normalised cosine similarity**.
- Replaced the simplified term-frequency score with **textbook Okapi BM25**
  (idf + average-doc-length normalisation, `k1=1.5`, `b=0.75`).
- Both channels fused with **Reciprocal Rank Fusion (k=60)**; citations now expose
  per-channel `bm25_score` and `dense_score`. Pure numpy, no new dependency.

### Changed — SQL agent is honest and safer
- Renamed "synthesizer" → **deterministic schema-aware planner** (it maps intents
  to vetted templates; it is not an LLM, and no longer claims to be).
- Execution now uses a **read-only `mode=ro` connection** + `PRAGMA query_only`,
  plus a single-statement `SELECT`/`WITH` check and a forbidden-keyword scan.
- Added live **schema introspection** from the SQLite catalog.

### Changed — telemetry is honest
- Removed hardcoded per-step token counts (`45/120/95/70`). Token usage is now
  **estimated from each step's real text** (~4 chars/token) and labelled as an
  estimate everywhere (state, spans, UI).
- Spans use current GenAI semantic-convention names (`gen_ai.usage.input_tokens`),
  cost moved to a custom `nexus.usage.cost_usd` attribute, and `gen_ai.system`
  defaults to the accurate `gemini` (Gemini Developer API, not Vertex AI).
- Added **real OTLP/HTTP span export** when `OTEL_EXPORTER_OTLP_ENDPOINT` is set.

### Added — engineering rigor
- GitHub Actions CI (lint · format · types · tests on 3.11/3.12 + Docker build).
- `ruff` + `mypy` configuration, `pre-commit` hooks, and a `Makefile`.
- Structured JSON logging (`nexus/logging.py`); `print()` calls removed.
- Test suite expanded **8 → 27** tests; added `conftest.py`, API contract tests,
  SQL-guardrail tests, and retrieval-correctness tests.
- Hardened `Dockerfile` (non-root user + healthcheck); cleaned `docker-compose.yml`.
- `.gitignore` added; the generated SQLite DB is no longer tracked.
- README rewritten to describe the system accurately.

## [0.1.0]
- Initial NexusOps gateway: FastAPI + Streamlit, keyword routing, template SQL,
  approximate retrieval, in-memory OpenTelemetry spans.
