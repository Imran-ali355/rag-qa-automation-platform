# Stage 7 — Release Notes & Sign-off Package

**Work item:** Local Ollama + ChromaDB RAG QA Platform (`rag-web`)  
**Release version recommendation:** `0.1.0-rc.1` after the outstanding release gates below are completed. This is a proposal only; no existing release version, tag, branch, or commit could be verified because this workspace is not a Git repository.  
**Release decision:** **Recommendation: NO-GO for general release at this time.** Stage 6 materially improved verification, but key real-model, production-Compose, and UI scenarios remain unverified. A human release owner must make the final decision.

## Release Summary & Highlights

### What is changing

This work delivers a local-first document Q&A and QA test-case generation application:

- A Flask web UI and JSON API for document-grounded Q&A, source citations, test-case generation, and JSON export.
- TXT and validated DOCX ingestion from the configured documents directory. Re-indexing is explicit through the UI or `POST /reindex`; files are checked and indexed into ChromaDB.
- Ollama-backed embeddings and chat using configurable models (defaults: `nomic-embed-text` and `llama3.2`). Answers are restricted to retrieved evidence, with source/chunk citation checks and a no-answer response when qualifying evidence is absent.
- Persistent ChromaDB indexing, a separate persistent Ollama model cache, Docker Compose local services, `/health`, and a GitHub Actions workflow using a deterministic Ollama HTTP contract stub.
- A narrow compatibility correction for pinned ChromaDB 0.6.3: cosine indexing is configured through the supported `hnsw:space` metadata. The updated regression test and full 22-test Docker suite passed.

There is no PDF ingestion. Inputs, prompts, and model answers have not been validated for production semantic quality. This package does not deploy or publish the application.

### Verification chronology and current recommendation

1. **Stage 5 QA report:** Recorded **NO-GO** because significant P0/P1 scenarios remained unverified. At that stage, 21 automated tests passed, and the production image build and Compose configuration checks passed; the report did not claim live Ollama, Chroma persistence, full Compose, or UI/E2E validation.
2. **Stage 6 follow-up:** Expanded the suite to **22 Docker tests**, including the real ChromaDB 0.6.3 compatibility regression. Compose configuration and application image build passed. A local **mock-Ollama** Compose flow verified health, re-index, ask/citation, application restart with persisted Chroma data, and project-scoped cleanup. This addresses some earlier integration gaps, but is not a live-model test.
3. **Still not verified:** actual Ollama model-backed answer/test-case quality; the model-pull flow; full production Compose with actual Ollama; browser UI/E2E; GitHub Actions execution; external `OLLAMA_BASE_URL` override behavior; or actual Ollama/Chroma persistence together in the production Compose stack.

Accordingly, recommend **NO-GO for general release** until the applicable outstanding P0/P1 validation is completed and reviewed. Human sign-off may explicitly accept or defer remaining risks, but Stage 7 does not make the release decision.

### Local startup and operating instructions

Requirements: Docker Engine and Docker Compose, an available host port (default `5000`), sufficient disk/RAM for the Ollama image and models, and approved local documents in `docs/`. Copy `.env.example` to `.env` if local overrides are needed; it contains configuration examples only.

Start the local Compose services:

```sh
docker compose up --build -d
```

Pull both required models into the Compose-managed Ollama service:

```sh
docker compose exec ollama ollama pull llama3.2
docker compose exec ollama ollama pull nomic-embed-text
```

After both model pulls complete, index the configured documents:

```sh
curl -X POST http://localhost:5000/reindex
```

Then verify:

- **UI:** `http://localhost:5000/`
- **Health JSON:** `http://localhost:5000/health` (HTTP 200 can still report `"status": "degraded"`; inspect `status`, `ollama`, `index_status`, and counts rather than treating HTTP 200 alone as model readiness).
- **API:** `POST http://localhost:5000/ask` with JSON such as `{"question":"What is documented?","mode":"qa"}`.

The Compose file persists ChromaDB data in the named `chroma_data` volume and Ollama models in the separate named `ollama_models` volume. `docker compose restart` restarts services; `docker compose stop` / `docker compose start` pauses and resumes them; `docker compose down` stops and removes the project containers/network while preserving named volumes. **Do not use `docker compose down -v` for routine stop/rollback:** it deletes the persistent index and model cache.

#### Native or externally managed Ollama caveats

- The Compose default is `OLLAMA_BASE_URL=http://ollama:11434`, which resolves to the Ollama service on the private Compose network. Pull models into that service using the commands above.
- If Ollama runs natively on the host while `rag-web` remains containerized, set `OLLAMA_BASE_URL` in `.env` to a host address reachable from the container (commonly `http://host.docker.internal:11434` on Docker Desktop). Linux Docker installations may require explicit host-gateway/network configuration. Do not assume the container's `localhost` refers to the host.
- If the application itself runs natively, its Ollama URL is normally `http://localhost:11434`; container service names such as `ollama` are not native host DNS names.
- For any external endpoint, confirm container routing, model availability, and trusted ownership. The configured Ollama endpoint receives retrieved document context and user prompts; using an external service changes the privacy boundary. The mock CI service is not a substitute for validating any of these configurations.

## Traceability Matrix

Status distinguishes **implemented/tested evidence** from full requirement acceptance. Test-case IDs below refer to `03-test-plan.md`; a passing suite does not mean every planned case passed or was executed.

| Requirements | Planned test cases | Implementation / evidence | Implementation and QA status |
|---|---|---|---|
| **FR-01 Ingestion, indexing, supported formats, configuration** | `ING-001–ING-016`, `CFG-001–CFG-004`, `BVA-013–BVA-014`, `BVA-018` | `rag/ingestion.py`, `rag/rag_service.py`, `rag/vector_store.py`, `rag/config.py`; Compose document mount is read-only. Handles direct-child TXT/DOCX, text validation, deterministic chunks, and candidate-index promotion. | Unit coverage includes UTF-8/BOM, invalid/binary/misnamed files, DOCX parsing, unsupported extensions, chunk IDs, config validation, and fake-store failure atomicity. Stage 6 mock Compose re-indexed a fixture. Chroma 0.6.3 regression passed. The entire `ING`/`CFG` plan is **not** proven: real-model re-index/model pull, many boundary/security cases, and production Compose indexing remain unverified. |
| **FR-02/FR-03 Grounded Q&A, retrieval, citations, no-answer** | `RET-001–RET-005`, `QA-001–QA-012`, `BVA-001` | `/ask` in `app.py`; retrieval, distance gate, prompts, citation validation and fallback in `rag/rag_service.py`; Ollama HTTP client in `rag/ollama_client.py`. | Tests cover request validation, inclusive distance/above-threshold behavior, valid and forged citation handling, and empty-index HTTP 200/no-answer. Stage 6 mock `/ask` verified a fixture citation after re-index and restart. Actual Ollama semantic grounding, answer quality, multi-source/conflicting/unsupported claim behavior, and model failure behavior remain unverified end-to-end. Citation identity validation does not establish that a cited passage entails a claim. |
| **FR-04 Structured test-case generation and export** | `TC-001–TC-014`, `UI-004–UI-005`, `BVA-005–BVA-006` | `rag/rag_service.py`, `rag/schemas.py`, `/ask` test-case mode, and `templates/index.html` table/download logic. | Unit tests cover a valid schema/reference, a boundary case requiring documented evidence, and invalid output rejection. Static UI implementation is present. No browser/UI E2E or JSON-download verification ran; actual model-produced test-case quality and most schema/count/ID boundaries remain unverified. |
| **FR-05 Health, re-index, error handling** | `HEALTH-001–HEALTH-006`, `IDX-001–IDX-010`, `UI-001–UI-003` | `/health` and `/reindex` in `app.py`; re-index locking, errors and service behavior in `rag/rag_service.py`; Chroma adapter in `rag/vector_store.py`. | Automated tests cover HTTP health/degraded state, API validation/error handling, no-answer, re-index lock policy, and candidate failure atomicity. A standalone unreachable-Ollama health smoke and Stage 6 mock-stack re-index passed. Full health/index failure matrix, UI states, and actual production service lifecycle are not verified. |
| **FR-06 Docker/Compose and persistence** | `OPS-001–OPS-012` | `Dockerfile`, `compose.yaml`, `.env.example`, `.dockerignore`, `rag/config.py`; named `chroma_data` and `ollama_models` volumes, web-only published port by default. | `docker compose config -q` and `docker compose build rag-web` passed. Stage 6 mock Compose verified application restart persistence for Chroma and cleanup of its uniquely scoped project. Actual Ollama models, production Compose restart/model-volume lifecycle, external URL override, and full production-stack behavior were not tested. |
| **FR-07 CI** | `CI-001–CI-008` | `.github/workflows/ci.yml`, `compose.ci.yaml`, `tests/support/ollama_stub.py`, and `tests/fixtures/ci-smoke.txt`. Workflow has bounded timeouts, read-only `contents` permission, mock Compose smoke, and scoped cleanup. | Local mock-only equivalent config/build/smoke/restart/cleanup passed as recorded in Stage 6. The GitHub Actions workflow itself was **not run**. Thus trigger behavior and hosted-runner execution remain unverified; CI does not validate real model quality. |
| **NFR-01–NFR-08 Grounding, locality, reliability, security, usability, portability** | Cross-cutting P0/P1 cases; `SEC-001–SEC-003`, `CFG-001–CFG-004`, `OPS-003/009/012` | Configuration and secrets hygiene reviewed in `.env.example`, `.dockerignore`, `compose.yaml`, app/config/service code and UI escaping functions. | Static review found no secret values in `.env.example` (configuration only); `.dockerignore` excludes `.env` and `.env.*` while allowing `.env.example`. The UI uses escaping in displayed dynamic values. No complete security, network exposure, browser, native-Ollama, or external endpoint test was run. Authentication is intentionally absent. |

### Contract clarification to carry forward

The accepted empty-index API behavior is HTTP 200 with the prescribed no-answer response, empty sources, and zero chunks. Stage 5 recorded the user's clarification and updated the test. Stage 1 **AC-01** still says HTTP 400 for no valid documents; Stage 2 `02-architecture.md` contains both the HTTP 200/no-answer contract and a conflicting recommendation for HTTP 400. These stale statements were not changed during Stage 7 and should be reconciled in a future approved requirements/design update. Current implementation follows HTTP 200/no-answer.

The Stage 3 traceability matrix also references `CIT-001–CIT-008`, `VAL-001–VAL-003`, and `CFG-005`, but those IDs have no separate detailed test-case rows in `03-test-plan.md`. This release matrix uses the detailed `QA`, `RET`, `ING`, and `CFG-001–CFG-004` cases instead. Reconcile or define those aliases in a future approved test-plan update.

## Known Issues & Rollback Plan

### Known limitations and risks

- **Model quality unverified:** No actual Ollama inference/model-quality tests were run. Passing deterministic mock tests demonstrates interface and plumbing behavior, not relevance, factual grounding, citation entailment, or useful test cases.
- **Production service flow unverified:** The actual `ollama/ollama` Compose service, model pulls, re-index against actual models, full real Compose stack, and combined Ollama/Chroma restart lifecycle were not exercised.
- **UI/E2E unverified:** Template source was reviewed, but no browser run checked workflows, escaping, states, table rendering, or downloaded JSON.
- **CI execution unverified:** `.github/workflows/ci.yml` exists and the local mock flow passed, but no GitHub Actions run occurred.
- **Overrides unverified:** Native/external Ollama routing and externally overridden `OLLAMA_BASE_URL` were not tested. Endpoint trust and network reachability are operator responsibilities.
- **Unauthenticated interface:** No authentication is provided. Anyone able to reach the published web port can query documents, trigger inference, and request re-indexing. Keep it on a trusted local machine/network; restrict access with host binding/firewall controls and do not expose it directly to the public internet or an untrusted LAN. The default Compose port mapping is not an authentication or access-control boundary.
- **Privacy depends on endpoint:** An external Ollama endpoint receives document snippets and prompts. Use only a trusted endpoint when local-only privacy is required; do not enter sensitive documents if endpoint handling is not approved.
- **Supported formats:** Direct-child `.txt` and validated `.docx` files are supported; PDF and recursive discovery are not. Invalid supported documents can block re-index promotion.
- **No-answer documentation conflict:** Stage 1 AC-01 and one Stage 2 sentence contradict the clarified HTTP 200 behavior; see above.
- **Backup and state:** ChromaDB and Ollama model data are separate persistent volumes. No production backup/restore procedure or known-good prior image/tag was validated. A successful re-index replaces the active collection; rollback of application code alone does not restore a prior index.
- **Repository/documentation state:** The workspace is not a Git repository, so branch, commit, tag, and clean/dirty status cannot be reported. A recursive README search found no `README.md`; `.env.example` does exist. No README was created as part of Stage 7.
- **Source-control secret hygiene:** A root `.gitignore` now excludes `.env` and `.env.*` while explicitly allowing `.env.example`; it also excludes Python caches/virtual environments and the local ChromaDB directory. `.dockerignore` separately excludes env files from image build context. No `.env` file is present. Because this workspace is not a Git repository, Git's ignore matching and tracked-file status could not be verified.

### Rollback steps

1. **Stop exposure first if there is a safety, privacy, or availability concern:** `docker compose stop rag-web`. Do not leave an unauthenticated service reachable while investigating.
2. **Preserve persistent data:** If stopping/removing the stack, use `docker compose down` **without** `-v`. Do not remove `chroma_data` or `ollama_models`. Preserve the current volumes and configuration until the human operator confirms recovery actions.
3. **Restore known-good application/configuration:** Use a human-approved known-good source/image and configuration. This workspace has no verified Git commit or previously published image tag, so no automatic application-code rollback target is available. If rebuilding from an approved known-good source, validate its Compose config and image before restarting.
4. **Restart and verify:** Start the approved version, check `docker compose ps` and logs, inspect `http://localhost:5000/health`, then verify the UI and a representative Q&A/citation. Re-index only if the approved rollback procedure requires it and the data/model compatibility is understood.
5. **Recover data only from an approved backup:** If Chroma data is corrupt or incompatible, stop the application and restore a verified Chroma volume backup using an operator-reviewed procedure. Do not assume application rollback reverses a successful re-index. Ollama model data is separate and normally should be retained.
6. **Avoid destructive cleanup:** Never run `docker compose down -v` or delete named volumes as a routine rollback. It permanently removes indexed Chroma data and pulled model files.

## Release Readiness Checklist

### Preflight and rollout checklist

- [ ] Human release owner reviews this recommendation and approves the intended audience/network boundary.
- [ ] Complete and review P0/P1 evidence for actual Ollama model pulls, model-backed re-index/Q&A/test-case behavior, and the production Compose service lifecycle; record results without substituting mock results.
- [ ] Run browser/UI E2E checks for Q&A, test-case rendering, error/loading/no-answer states, escaping, and downloaded JSON.
- [ ] Execute `.github/workflows/ci.yml` in GitHub Actions and review its logs/cleanup. Do not infer this from local runs.
- [ ] Validate external/native Ollama configuration if it is in scope; verify routing and that the configured endpoint is trusted.
- [ ] Resolve or formally accept the stale empty-index requirement/design discrepancy in a future approved document update; current behavior is HTTP 200/no-answer.
- [ ] Confirm intended documents are supported, UTF-8/valid, and approved for indexing; check document confidentiality and remove unintended files.
- [ ] Confirm Docker/Compose availability, port `5000` availability (or approved `WEB_PORT`), disk/RAM capacity, model-download network access, and persistent-volume ownership/backup plan.
- [ ] Review `.env` overrides before startup. Do not place credentials or secrets in `.env.example`, source, logs, or release notes. `.env.example` is configuration-only; `.dockerignore` excludes `.env`/`.env.*` from the build context with an explicit `.env.example` exception.
- [ ] Before source-control publication, verify the new `.gitignore` with Git in the actual repository and ensure any `.env`, local database, model/cache, and other sensitive/generated files are not already tracked; ignore rules do not remove previously tracked data.
- [ ] Restrict web access to the intended local/trusted host or network with appropriate host binding/firewall controls. Confirm no untrusted party can reach the unauthenticated web/API port.
- [ ] Confirm `OLLAMA_BASE_URL` points to the intended trusted service, and explain to operators that an external endpoint receives prompts and retrieved context.
- [ ] Back up or otherwise protect existing `chroma_data` before any re-index or upgrade that could alter the active collection. Retain the separate `ollama_models` volume.
- [ ] Validate Compose configuration and build before rollout; then follow the startup, model-pull, and `POST /reindex` instructions in **Release Summary & Highlights**.
- [ ] After startup/pull/re-index, confirm `/health` reports expected model names, `ollama: available`, index ready, and expected file/chunk counts. Exercise one known-answer query with exact source citation and one out-of-corpus query.
- [ ] Record rollout owner, date, exact approved version/image, configuration choices (without secrets), validation results, monitoring contact, and rollback owner.

### Final human sign-off

- [ ] **Decision:** Human release owner selects Go, conditional Go, or No-Go; this document's recommendation is not authorization.
- [ ] **Accepted scope:** Confirm this is a local/trusted-network MVP with no authentication, supported TXT/DOCX only, and no claim of validated model quality until real-model tests pass.
- [ ] **Open risks:** Explicitly accept or block release on each outstanding validation item and the empty-index documentation inconsistency.
- [ ] **Operations:** Confirm model pulls, volume persistence/backup, trusted Ollama endpoint, network restrictions, runbook, and rollback owner.
- [ ] **Release identity:** Approve a version/image identifier and source revision through the authorized repository/release process; none is verified in this workspace.
- [ ] **Approval record:** Name, role, decision, date/time, conditions, and any accepted exceptions: ______________________________

**Stage 7 action:** Release package prepared only. No deployment, GitHub Actions run, merge, release, commit, or edits to artifacts 01–06 were performed. Stop here for final human sign-off.
