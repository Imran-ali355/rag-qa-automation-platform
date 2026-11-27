# Stage 6 — Pipeline Notes

## Pipeline Files Created / Updated

- **Created:** `.github/workflows/ci.yml` — push and pull-request workflow with read-only `contents` permission, bounded job/step timeouts, Python dependency caching, tests, image build, and the mock-only Compose smoke flow.
- **Created:** `compose.ci.yaml` — replaces the Compose `ollama` service with `python:3.11-slim` running the stdlib contract stub and overrides only the app document bind mount with the CI fixture. The production `rag-web` image/build, Chroma named volume, and project-scoped Compose volume behavior are retained.
- **Created:** `tests/support/ollama_stub.py` — dependency-free HTTP stub for `/api/tags`, `/api/embed`, and `/api/chat`. It returns deterministic fixed-size embeddings and derives a real `filename (Chunk #N)` reference from prompt evidence markers.
- **Created:** `tests/fixtures/ci-smoke.txt` — valid deterministic fixture for CI re-index and persistence checks.

The Stage 6 pipeline additions do not change app routes/UI or the production `compose.yaml`. A separately user-authorized Stage 4 correction updated `rag/vector_store.py` and added a real-Chroma regression test; its results are recorded below and in `04-dev-summary.md`. The actual `ollama/ollama` image and models are not used by this CI override. The workflow does not trigger deployment, tags, or releases.

## Stages & Commands Configured

1. Checkout source and set up Python 3.11 with pip cache keyed by `requirements.txt`.
2. Install runtime dependencies using `python -m pip install -r requirements.txt`.
3. Run `python -m unittest discover -s tests -v`, `python -m compileall -q app.py rag tests`, and explicit module imports.
4. Validate the composed configuration with `docker compose -f compose.yaml -f compose.ci.yaml config --quiet`.
5. Build only the application service using `docker compose -f compose.yaml -f compose.ci.yaml build rag-web`.
6. Start the isolated mock stack with `docker compose -f compose.yaml -f compose.ci.yaml up -d --no-build`.
7. Poll `/health` for up to 90 one-second attempts, require the mock to be available, `POST /reindex`, validate a non-empty indexed corpus, call `/ask` and assert the answer/source citation contract, restart `rag-web`, confirm ready indexed state, and re-ask to exercise persisted Chroma data.
8. Always run `docker compose -f compose.yaml -f compose.ci.yaml down --volumes --remove-orphans --timeout 10` under `if: always()`. The unique `COMPOSE_PROJECT_NAME` scopes cleanup and named volumes to this workflow attempt.

Request calls have explicit curl timeouts; the smoke step, cleanup step, and whole job also have upper bounds. The stub logs no request bodies. No test-report artifact is produced because the configured standard-library unittest run has no report output; failures remain visible in workflow logs.

## Environment Variables & Secrets Required

- Workflow-provided: `COMPOSE_PROJECT_NAME=rag-ci-${{ github.run_id }}-${{ github.run_attempt }}` and `WEB_PORT=5000`.
- Compose uses its existing local model defaults; the override explicitly pins `OLLAMA_BASE_URL` to `http://ollama:11434` and changes the docs source to `tests/fixtures`, preventing an inherited external Ollama URL from being used by the app.
- **Secrets required:** none. Workflow token permission is limited to `contents: read`.

## Local Stage 6 Verification

Docker was available. The merged CI Compose configuration validated successfully, and the production `rag-web` image built. The local mock-only Compose project started without the production Ollama image:

1. `GET /health` returned HTTP 200 with `status: "ok"` and `ollama: "available"`.
2. `POST /reindex` indexed one fixture file and one chunk.
3. `POST /ask` returned the expected answer and `ci-smoke.txt (Chunk #1)` citation.
4. After restarting `rag-web`, `/health` still reported one indexed chunk and `/ask` returned the same valid citation, verifying Chroma volume persistence.
5. `down --volumes --remove-orphans` removed the uniquely scoped containers, network, and named volumes; cleanup was verified by Docker resource labels.

The first local run exposed a Stage 4 ChromaDB 0.6.3 configuration incompatibility (`dict` has no `to_json`). The user authorized a narrow Stage 4 correction; collection creation now sets cosine via the supported `hnsw:space` metadata. The real-Chroma regression test and full suite passed after rebuilding the image.

No real Ollama image/model was started or downloaded. No GitHub Actions run or deployment was triggered.

## Pipeline Risks & Manual Steps

- The stub uses deterministic identical vectors by design. It verifies Ollama HTTP compatibility, indexed retrieval plumbing, citation identity, and persistence—not semantic relevance, model answer quality, or production inference.
- CI still needs to download Python dependencies, the application base image dependencies, and the lightweight `python:3.11-slim` image. The job/step timeouts bound waiting; no model download is configured.
- The production `compose.yaml` remains unchanged. Use both Compose files and the unique project name for CI/local mock checks; never run cleanup against another project or persistent data.
- Latest Docker-mounted unit/API suite: **22 passed**, including a real ChromaDB 0.6.3 integration regression. `docker compose -f compose.yaml -f compose.ci.yaml config -q` and `docker compose build rag-web` passed.
- The full mock-only local Compose smoke flow passed through health, re-index, ask/citation validation, application restart, persisted retrieval, and project-scoped cleanup. This does not verify actual Ollama model quality or a GitHub-hosted workflow run.
- No GitHub Actions workflow was triggered. Human pipeline approval is still required before Stage 7; release readiness and real-model checks remain outside this stage.
