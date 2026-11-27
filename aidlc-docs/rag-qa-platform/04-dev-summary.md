# Stage 4 — Development Summary

## Branch & Scope Summary

- **Work item:** `rag-qa-platform` (`rag-web`).
- **Git status/branch:** The supplied environment identifies the working directory as not being a Git repository. No branch or Git status could be verified; no repository was initialized and no changes were committed.
- **Scope:** Implemented local TXT/DOCX ingestion, grounded retrieval and Q&A, validated test-case output, operational API behavior, Docker/Compose support, and focused unit/API tests. PDF, CI/Stage 6, QA/Stage 5, and release work were not added.
- Application/module imports construct only local Python objects. They do not contact Ollama, initialize Chroma, or index documents; indexing is explicit through `POST /reindex`.

## Files Created / Modified

- **Created:** `rag/__init__.py`, `rag/config.py`, `rag/ingestion.py`, `rag/vector_store.py`, `rag/ollama_client.py`, `rag/rag_service.py`, `rag/schemas.py`.
- **Modified:** `app.py`, `templates/index.html`.
- **Created runtime/deployment files:** `requirements.txt`, `Dockerfile`, `compose.yaml`, `.dockerignore`, `.env.example`.
- **Created tests:** `tests/__init__.py`, `tests/test_ingestion.py`, `tests/test_rag_service.py`, `tests/test_vector_store.py`, `tests/test_api.py`.
- **Created this Stage 4 artifact:** `aidlc-docs/rag-qa-platform/04-dev-summary.md`. No other workflow-stage artifacts were modified.

## Unit Tests Added & Execution Results

- Tests cover strict UTF-8/BOM handling, binary and misnamed-file rejection, DOCX extraction/validation, unsupported PDF exclusion, deterministic chunking/configuration, inclusive distance filtering, citation and test-case schema checks, candidate-index failure atomicity, HTTP validation, health status, and request-size limits.
- Tests use temporary directories and injected fakes; they do not call live Ollama or Chroma services.
- Added regression coverage for fabricated filename-suffix citations, refusing boundary cases without a documented rule/limit, and rejecting overlapping re-index requests.
- Added a real ChromaDB 0.6.3 regression test for collection creation with cosine metric, candidate replacement, and query ordering.
- **Initial Stage 4 execution:** `python -m unittest discover -s tests -v` — **20 tests passed** in an isolated Python 3.12 environment with Flask, requests, and python-docx installed.
- **Latest Docker execution after the Stage 4 Chroma correction:** **22 tests passed**, including the ChromaDB 0.6.3 integration regression and Stage 5 empty-index contract test.
- **Compilation:** `python -m compileall -q app.py rag tests` — passed.
- Installing all dependencies directly on Windows was not possible because `chromadb`'s `chroma-hnswlib` dependency required Microsoft C++ Build Tools. The Linux container image build installed the full requirements successfully.

## Build & Verification Status

- `docker compose config -q` — passed.
- `docker compose build rag-web` — passed after final implementation updates.
- Container smoke test using `OLLAMA_BASE_URL=http://127.0.0.1:9` — `GET /health` returned HTTP 200 with `status: "degraded"`, `ollama: "unavailable"`, and `index_status: "empty"`; the temporary container was removed.
- A full Compose run with live Ollama and model downloads was not run. No model-quality checks were run.
- No CI workflow was created or changed.

## Notes for QA & PR Review

- Defaults are `llama3.2`, `nomic-embed-text`, `MAX_DISTANCE=1.0` (inclusive), and `MAX_CASES=8`. Supported inputs are direct-child UTF-8 TXT and validated DOCX files only; invalid supported files block re-index promotion. There is no PDF ingestion or authentication.
- Re-indexing stages into a candidate Chroma collection and promotes it through an atomic active-index pointer only after validation and embedding. Retrieval uses a configurable distance gate; no qualifying evidence returns the prescribed no-answer response. Model citations and test-case references are checked against retrieved evidence.
- Compose includes `rag-web` and Ollama with persistent data volumes and permits an `OLLAMA_BASE_URL` override. Only the web service port is published by default. An external Ollama endpoint receives prompt/document context; use only a trusted endpoint for local privacy.
- **Review note:** The workspace is not a Git repository, so branch/status confirmation is unavailable. No QA Stage 5, merge, or deployment work was performed.

## Stage 4 Correction — ChromaDB Configuration Compatibility

- Updated collection creation to configure cosine HNSW through ChromaDB's supported `hnsw:space` metadata field. This avoids passing a plain dictionary through the `configuration` API in pinned ChromaDB 0.6.3, while retaining the existing application-level cosine metadata and behavior.
- Added a focused regression test using an actual persistent ChromaDB client and temporary directory. It verifies replacement, both cosine metadata fields, and cosine-based query ordering.
- **Validation:** The focused regression and complete 22-test suite passed inside the rebuilt application Docker image. The end-to-end mock Compose smoke/persistence flow is recorded in `06-pipeline-notes.md`.
