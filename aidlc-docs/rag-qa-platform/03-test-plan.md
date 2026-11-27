# Stage 3 — Test Plan and Test Cases

**Work item:** Local Ollama + ChromaDB RAG QA Platform (`rag-web`)  
**Status:** Proposed; requires human approval before Stage 4  
**Artifact path:** `aidlc-docs/rag-qa-platform/03-test-plan.md`  
**Requirements basis:** `aidlc-docs/rag-qa-platform/01-requirements.md`  
**Architecture basis:** `aidlc-docs/rag-qa-platform/02-architecture.md`

## Test Strategy & Scope

### Objective

Verify that the platform ingests only supported, valid documents; retrieves document-grounded evidence using an inclusive configurable distance threshold; generates validated QA output; preserves data during failures and restarts; exposes truthful health and re-index behavior; and starts cleanly in Docker/Compose and GitHub Actions.

### In-scope

- Direct-child discovery in `DOCS_DIR` for case-insensitive `.txt` and `.docx` suffixes.
- Strict UTF-8 TXT validation, DOCX ZIP/OOXML validation and bounded text extraction.
- Chunk metadata, fingerprints, persistent ChromaDB, embeddings, retrieval, grounding, citations, and no-answer behavior.
- `/`, `/health`, `/reindex`, and `/ask` behavior, including JSON/error contracts.
- QA test-case JSON schema, limits, source references, and browser JSON export.
- Atomic re-index, concurrency, Ollama/Chroma failures, Docker/Compose persistence and health checks.
- GitHub Actions image build and deterministic Ollama mock smoke behavior.
- Windows and Linux behavior, external `OLLAMA_BASE_URL`, and configuration overrides.

### Out of scope

- PDF ingestion, OCR, recursive directory indexing, upload endpoint, authentication/authorization, and direct browser access to Ollama/Chroma.
- Distributed/multi-replica coordination, semantic entailment proof, model-quality benchmarking, GPU availability, or third-party hosted Ollama.
- Execution of macros, embedded objects, or archive entry extraction.
- Direct verification of real model answer quality in CI; real Ollama model validation is a manual/release test.

### Approved decisions controlling this plan

- Supported formats are `.txt` and `.docx` only; `.pdf` and binary/misnamed supported files are rejected or ignored as documented.
- Citations are exactly `filename (Chunk #N)` and use one-based chunk numbers.
- `MAX_DISTANCE` is inclusive: `distance <= MAX_DISTANCE` is eligible; it is a distance threshold, not confidence/similarity.
- Default `MAX_DISTANCE` is `1.0`, but the expected value is metric and embedding-model dependent.
- `TOP_K` default is `5`; `MAX_CASES` default is `8`; documented default models are `llama3.2` and `nomic-embed-text`.
- Compose includes Ollama and supports external `OLLAMA_BASE_URL` overrides; CI uses a mock Ollama endpoint and does not download full models.
- No-answer text is exactly/substantively `This information is not available in the indexed documents.`

### Test levels

| Level | Primary coverage |
|---|---|
| Unit | UTF-8/ZIP/DOCX validation, normalization/chunking/fingerprints, numeric/config range checks, threshold filtering, citation/schema validators, duplicate IDs and source references |
| Integration | Ingestion to Chroma, Ollama HTTP adapters, retrieval-to-prompt validation, re-index candidate promotion, Chroma collection metadata |
| API | HTTP methods, status codes, JSON requests/responses, malformed/oversized input, stable errors, no partial success |
| UI/E2E | Health/loading/error/no-result states, Q&A and test-case modes, source rendering, safe text rendering, JSON download |
| Container | Dockerfile runtime, Compose networking/startup, volumes, health/restart, external URL override |
| CI | Dependency/syntax validation, image build, deterministic Compose mock smoke, cleanup and timeout |

### Test types

- Positive and negative functional testing
- Equivalence partitioning (EP) and boundary value analysis (BVA)
- State/error-path testing
- Data/API contract testing
- Persistence/restart and atomicity testing
- Security-oriented malformed archive/path/XSS input testing
- Concurrency and resource-limit testing
- Docker/CI smoke and operational testing

### Entry/exit criteria

**Entry:** Stage 1/2 artifacts approved; implementation exposes documented routes/configuration; test fixtures and mock Ollama are available.

**Exit:** All P0/P1 cases pass or have approved exceptions; no P0/P1 defect remains open; P2 cases have documented outcomes; artifact export and Docker/CI cleanup execute successfully; no test evidence contains secrets or absolute filesystem paths.

### Priorities

- **P0:** Security/atomicity, no hallucination/no evidence, API data contracts, ingestion safety, restart/persistence, health truthfulness.
- **P1:** Core positive flows, citation/schema validation, re-index success/failure, Docker/Compose and CI.
- **P2:** Usability, uncommon configuration, escaping, and non-critical diagnostics.

## Traceability

| Requirement/decision | Test case IDs |
|---|---|
| FR-01.1–1.7 TXT/DOCX discovery, metadata, persistence, re-index and configuration | ING-001–ING-016, CFG-001–CFG-005 |
| FR-02.1–2.9 Q&A request, retrieval, context, citations, no-answer, stable errors | QA-001–QA-012, VAL-001–VAL-003 |
| FR-03.1–3.6 exact citations, anti-hallucination, no-answer, low temperature, no embeddings | CIT-001–CIT-008, QA-006–QA-012 |
| FR-04.1–4.12 test-case schema, types, IDs, boundaries, export, invalid output | TC-001–TC-014, UI-004–UI-005 |
| FR-05.1–5.5 health, re-index, errors, UI states | HEALTH-001–HEALTH-006, IDX-001–IDX-010, UI-001–UI-005 |
| FR-06.1–6.8 Dockerfile/Compose, persistence, health, startup | OPS-001–OPS-012 |
| FR-07.1–7.7 GitHub Actions build, syntax, smoke, cleanup | CI-001–CI-008 |
| NFR-01–08 grounding, locality, reliability, performance, usability, security, maintainability, portability | Cross-cutting cases marked P0/P1 |
| ADR-1 `.txt`/`.docx` validation | ING-001–ING-016 |
| ADR-2 Flask/Chroma/Ollama architecture | ARCH/API, health/re-index/Q&A cases |
| ADR-3 inclusive `MAX_DISTANCE` gate | RET-001–RET-005 |
| ADR-4 strict citation/test-case validation | CIT-001–CIT-008, TC-001–TC-014 |
| ADR-5 HTTP 200 degraded health | HEALTH-001–HEALTH-006 |
| ADR-6 Compose/external Ollama | OPS-001–OPS-012 |
| ADR-7 CI Ollama contract mock | CI-001–CI-008 |
| ADR-8 no authentication/trusted local scope | SEC-001–SEC-003 |

## Test Environment

### Runtime matrix

| Scenario | Native Windows | Native Linux | Docker/Compose | GitHub Actions |
|---|---:|---:|---:|---:|
| Unit/API tests | Required | Required | Optional | Required |
| Real Ollama smoke | Required on manual environment | Required on manual environment | Optional | Not required |
| Mock Ollama contract | Required | Required | Required | Required |
| Restart/persistence | Optional | Optional | Required | Required |

### Baseline services and fixtures

- Ollama stub deterministic for `/api/embed`, `/api/chat`, and lightweight availability checks.
- Chroma persistent temporary directory; no fixture copy of production `chroma_txt_db/`.
- Positive UTF-8 TXT fixture containing an explicit range, e.g. `Password length: 8–20 characters.` and a workflow.
- Valid DOCX fixture with paragraph and table text.
- Binary, NUL-bearing, invalid UTF-8, PDF, misnamed DOCX-as-`.txt`, malformed DOCX, non-ZIP `.docx`, missing OOXML member, encrypted ZIP, and ZIP-bomb-shaped files.
- Duplicate/case-preserving basename collision fixture; filenames include spaces and HTML-like text for escaping checks.
- `MAX_DISTANCE` values `0.999`, `1.0`, `1.001`, with a non-finite/negative/oversized configuration set.
- Mock answers include supported, unsupported/mixed, exact/forged/missing citations, malformed/extra-key JSON, duplicate IDs, excess cases, and invalid `source_ref`.

## Functional & Negative Test Cases

### Ingestion

| ID | Priority | Requirements | Prerequisites | Steps | Expected result |
|---|---|---|---|---|---|
| ING-001 | P0 | FR-01.1, FR-01.3, ADR-1 | Empty persistent DB; valid UTF-8 `guide.txt` | 1. Place fixture in `DOCS_DIR`. 2. Re-index. | HTTP 200; file count 1; normalized text is chunked and stored in Chroma with stable `source` and one-based `chunk_num`. |
| ING-002 | P0 | FR-01.1, FR-01.6, ADR-1 | Valid TXT with BOM | Re-index and query. | UTF-8 BOM is accepted and stripped; text is indexed without BOM. |
| ING-003 | P0 | FR-01.6, EC-04 | `.txt` fixture with invalid UTF-8/invalid byte | Re-index. | HTTP 422; safe `{filename, reason:"invalid_utf8"}` diagnostic; no candidate promoted. |
| ING-004 | P0 | FR-01.6, ADR-1 | `.txt` containing NUL/binary bytes | Re-index. | Rejection; no active-index replacement; diagnostic category is safe and no absolute path or stack trace appears. |
| ING-005 | P0 | FR-01.6, ADR-1 | Rename valid DOCX to `.txt` | Re-index. | ZIP/DOCX signature is detected and rejected as invalid text, not decoded or indexed. |
| ING-006 | P0 | FR-01.6, ADR-1 | Rename valid PDF to `.txt` | Re-index. | Rejected as invalid binary/text; PDF signature is never extracted or accepted. |
| ING-007 | P0 | FR-01.1, ADR-1 | Valid DOCX with paragraphs/tables | Re-index. | HTTP 200; readable paragraph/table text is extracted and indexed; no macros or embedded objects execute. |
| ING-008 | P0 | FR-01.6, ADR-1 | `.docx` containing plain text/non-ZIP bytes | Re-index. | HTTP 422 with `malformed_docx`-family diagnostic; candidate not promoted. |
| ING-009 | P0 | FR-01.6, ADR-1 | `.docx` ZIP lacking `Content_Types` or `document.xml` | Re-index. | Rejected as malformed/unparseable OOXML; no partial index. |
| ING-010 | P0 | FR-01.6, ADR-1 | Encrypted or unreadable `.docx` ZIP | Re-index. | Rejected safely; no password prompt or archive extraction. |
| ING-011 | P0 | FR-01.6, ADR-1 | ZIP with excessive member count/expanded size or high compression ratio | Re-index. | Bounded resource checks reject the archive before parsing; no filesystem extraction or process instability. |
| ING-012 | P1 | FR-01.1, EC-09 | Valid `.TXT` and `.DoCx` names plus `.pdf`, `.md`, hidden temporary files | Re-index. | Only case-insensitive `.txt`/`.docx` direct children are processed; unsupported names are ignored/countable, not indexed. |
| ING-013 | P0 | FR-01.2, EC-05 | Two direct-child files with same basename in different subtrees; symlinks | Re-index. | Duplicate/cross-directory ambiguity cannot reach citations; symlinks/recursion do not escape `DOCS_DIR`, and safety is reported. |
| ING-014 | P1 | FR-01.2, ADR-1 | Whitespace-only TXT and empty DOCX | Re-index. | Files are reported/skipped, contribute zero chunks, and do not by themselves invalidate a candidate. |
| ING-015 | P1 | FR-01.5 | Existing index; add/change/rename supported fixture | 1. Call re-index. 2. Query. | Success refreshes/changes chunks and collection fingerprint, then retrieval reflects the new content. |
| ING-016 | P1 | FR-01.4, FR-01.5 | Existing index; unchanged corpus | Explicit re-index. | Re-index succeeds deterministically and existing source/chunk identity is stable for unchanged content. |

### Retrieval and grounding

| ID | Priority | Requirements | Prerequisites | Steps | Expected result |
|---|---|---|---|---|---|
| RET-001 | P0 | FR-02.2, ADR-3 | One indexed fixture; Chroma returns distance `1.0` | Ask a matching question. | Distance equal to default `MAX_DISTANCE=1.0` is eligible; chat is called with its chunk. |
| RET-002 | P0 | ADR-3 | Chroma returns distance `0.999` | Ask. | Eligible; lower distance is not special-cased; threshold rule is inclusive. |
| RET-003 | P0 | ADR-3 | Chroma returns distance `1.001` | Ask. | Chunk is discarded as above threshold; no chat call for no evidence. |
| RET-004 | P0 | FR-03.4, FR-02.6 | Empty or all above-threshold corpus | Ask in `qa` mode. | HTTP 200 no-answer response, `sources=[]`, `chunks_used=0`; chat is not called. |
| RET-005 | P0 | ADR-3 | Configure `MAX_DISTANCE=0.5` | Return `0.500` and `0.5001`; ask. | `0.500` remains eligible; `0.5001` is excluded; changing threshold does not require other API shape changes. |
| QA-001 | P0 | FR-02.1, FR-02.9 | Valid index | Send `{}` and whitespace-only question. | HTTP 400 stable JSON error; no chat/retrieval call. |
| QA-002 | P0 | FR-02.9, NFR-06 | Valid index | Send malformed JSON, wrong `question` type, unsupported mode, and oversized body in separate requests. | HTTP 400/413 as applicable; stable error object; no successful/partial output. |
| QA-003 | P0 | FR-02.1, FR-02.7 | Valid index; stub question answered only by source | Ask factual question. | HTTP 200 grounded answer plus exact `filename (Chunk #N)` citation and qualifying `sources`. |
| QA-004 | P0 | FR-02.5, FR-02.8 | Fixture fact spans two chunks/files | Ask summary/list. | Multiple source references in `sources` and answer; no unrelated or duplicate source claims. |
| QA-005 | P0 | FR-02.6, FR-03.4 | Chunk text exists but answer absent | Ask unrelated fact. | No-answer sentence with no unsupported detail and `chunks_used=0` or qualifying evidence count only if retrieval returned context. |
| QA-006 | P0 | FR-02.7, FR-03.3 | Retrieved chunk supports fact A not fact B | Stub answer contains A plus unsupported B. | No-answer or reject/replace unsupported claim consistently; answer never attributes B to a source. |
| QA-007 | P0 | FR-03.1, FR-03.2 | Stub emits exact citation | Ask. | Exact human-readable citation accepted only if filename/chunk exists in evidence. |
| QA-008 | P0 | FR-03.2, EC-09 | Stub emits forged or nonexistent citation | Ask. | HTTP 422 invalid model output or designated no-answer; no fabricated cited success. |
| QA-009 | P0 | FR-03.1 | Stub omits required citation | Ask backed fact. | Invalid grounded answer handling: no-answer or validation error; no success-shaped uncited answer. |
| QA-010 | P0 | FR-03.5 | Real/mock chat adapter | Ask same deterministic fixture twice. | Temperature 0.1/low temperature and grounded prompt are used; `no conversation state` and stable evidence contract. |
| QA-011 | P1 | FR-02.8 | Fixture contains conflicting statements | Ask conflicting fact. | Response states conflict or no-answer with citations; no invented precedence. |
| QA-012 | P0 | NFR-06 | Prompt fixture contains instruction-like text and HTML | Ask. | Retrieved text is treated as untrusted context; UI escapes text; prompt injection does not alter policies or execute markup. |

### Test-case generator

| ID | Priority | Requirements | Prerequisites | Steps | Expected result |
|---|---|---|---|---|---|
| TC-001 | P0 | FR-04.1, FR-04.3 | Valid evidence containing positive and negative behavior | POST `mode:test_cases` with documented feature. | HTTP 200 with complete `test_cases`, `sources`, and `chunks_used`; no extra/partial success fields. |
| TC-002 | P0 | FR-04.4 | Stub valid array | Generate. | Every `type` is exactly `Positive`, `Negative`, or `Boundary`; invalid type yields 422. |
| TC-003 | P0 | FR-04.5 | Stub returns 3 cases | Generate. | IDs are unique and sequential `TC-001`, `TC-002`, `TC-003`. |
| TC-004 | P0 | ADR-4 | Stub duplicates `TC-001` | Generate. | Entire result rejected HTTP 422; no partial array. |
| TC-005 | P0 | ADR-4 | Stub omits/has wrong type for required field | Generate. | Required string fields and non-empty string-array `steps` are validated; 422 on violation. |
| TC-006 | P0 | FR-04.6 | Source contains no unlisted feature | Ask. | No generated case invents fields/workflows/preconditions absent from context. |
| TC-007 | P0 | FR-04.7, EC-12 | Source states no range/limit | Generate. | No Boundary cases are fabricated; conventional limits are not inferred. |
| TC-008 | P0 | FR-04.7 | Source explicitly states password length 8–20 | Generate boundary cases. | Boundary values derive only from 8/20 or direct rule boundaries; no unmentioned adjacent rules are invented. |
| TC-009 | P0 | ADR-4 | Stub returns valid 8-case array | Generate. | Exactly at most 8 cases accepted. |
| TC-010 | P0 | ADR-4 | Stub returns 9 cases | Generate. | HTTP 422 excess-cases rejection; no truncation into apparent success. |
| TC-011 | P0 | FR-04.12, ADR-4 | Stub `source_ref` exists in retrieved evidence | Generate. | Accepted single `filename (Chunk #N)` reference. |
| TC-012 | P0 | ADR-4 | Stub forges/misses a source pair | Generate. | Entire result rejected 422 or no-answer handling; no bogus source reference. |
| TC-013 | P0 | FR-04.11 | Ollama chat returns malformed/non-JSON text | Generate. | HTTP 422/clear 500-level JSON error per contract; no success-shaped partial test cases. |
| TC-014 | P0 | FR-04.11, ADR-4 | Stub extra key or wrong root is present | Generate. | Ambiguous extra-field response is rejected or normalized only per strict contract; no partial success. |

### Health and re-index

| ID | Priority | Requirements | Prerequisites | Steps | Expected result |
|---|---|---|---|---|---|
| HEALTH-001 | P0 | FR-05.1, ADR-5 | Healthy Ollama/Chroma/indexed corpus | GET `/health`. | HTTP 200; `status=ok`, Ollama available, index ready, models/counts/files/chunks included. |
| HEALTH-002 | P0 | ADR-5 | Ollama endpoint unreachable | GET `/health`. | HTTP 200 `status=degraded`, `ollama=unavailable`; bounded call, no index/generation. |
| HEALTH-003 | P0 | ADR-5 | Chroma unreadable | GET `/health`. | HTTP 200 `status=degraded`, `index_status=unavailable`; no crash. |
| HEALTH-004 | P1 | FR-05.1, ADR-5 | Empty valid corpus, web/Chroma healthy | GET `/health`. | HTTP 200 `status=ok`, `index_status=empty`, zero counts and valid model config. |
| HEALTH-005 | P1 | FR-05.5, NFR-04 | Running web, Ollama/Chroma unavailable | Call health repeatedly. | Response remains quick/bounded and never waits for model download or triggers re-index. |
| HEALTH-006 | P0 | NFR-07 | Override model names/URLs/env | GET `/health`. | Health reports override chat/embed model names and not secrets/raw environment. |
| IDX-001 | P0 | FR-05.2 | Valid corpus and embeddings | POST `/reindex` no body/`{}`. | HTTP 200 success message, files/chunks counts, active candidate promoted. |
| IDX-002 | P0 | FR-05.3, EC-04 | Invalid supported file | POST `/reindex`. | HTTP 422; safe per-file filename/reason diagnostics; active collection unchanged. |
| IDX-003 | P0 | FR-01.6, ADR-1 | Duplicate/case collision basename | POST `/reindex`. | HTTP 422; ambiguous source is not promoted. |
| IDX-004 | P0 | FR-05.3, EC-15 | Ollama embeddings unavailable | POST `/reindex`. | HTTP 503 after bounded retry; no success message or active-index replacement. |
| IDX-005 | P0 | FR-05.3 | Chroma/disk/write failure on candidate | POST `/reindex`. | HTTP 500 generic storage error; existing active index remains readable. |
| IDX-006 | P0 | NFR-03, NFR-04 | Existing index and interrupted candidate write | Inject failure mid-promotion. | No partial promotion; active collection remains available; stale candidate cleaned or retained safely. |
| IDX-007 | P0 | FR-01.4 | Two re-index requests overlap | Send concurrently. | Exactly one serialized result and 409 if architecture-selected second behavior is chosen consistently, or second waits and receives completed result; no concurrent writers. |
| IDX-008 | P0 | EC-17 | Modify file while re-index snapshot processes | Trigger re-index then change source bytes. | Fingerprint/snapshot mismatch discards candidate; operator receives failure/retry instruction; active index unchanged. |
| IDX-009 | P1 | EC-16 | Start against incompatible collection metadata/model/metric | Start app/request re-index. | No silent cross-metric/model query; mismatch is detected and explicit full re-index required. |
| IDX-010 | P0 | FR-05.4 | `/ask` retrieval/Chroma throws | Ask. | HTTP 500 or Ollama-specific 503 with stable JSON; no crash or success-shaped output. |

## Boundary & Edge Case Scenarios

| ID | Priority | Derived rule/range | Boundary test data and expected result |
|---|---|---|---|
| BVA-001 | P0 | `MAX_DISTANCE=1.0` inclusive | Test distances `0.9999`, `1.0`, `1.0001`: eligible/eligible/discarded respectively. |
| BVA-002 | P1 | Configurable threshold | Configure minimum valid usable value `0.0` and test distance `0.0` vs `0.0001`; at 0.0 eligible if metric permits. |
| BVA-003 | P0 | `MAX_DISTANCE` numeric config | Values `-0.01`, `NaN`, `Infinity`, malformed string, and out-of-domain value: startup rejects with non-sensitive config error. |
| BVA-004 | P1 | `TOP_K=5` | Index 6 chunks; retrieve at most 5; 6th is never context. |
| BVA-005 | P0 | `MAX_CASES=8` | Generate arrays of 7, 8, 9: 7/8 accepted; 9 rejected, never truncated. |
| BVA-006 | P0 | Sequential case IDs | 1 case = `TC-001`; 8 cases = `TC-001` to `TC-008`; missing/gapped/duplicate IDs rejected. |
| BVA-007 | P1 | Question maximum length | Send exact configured maximum, one over maximum, and empty: exact accepted/over rejected 413 or 400 per contract; empty 400. |
| BVA-008 | P1 | Request body ceiling | Exact ceiling, ceiling+1, malformed/truncated JSON: ceiling partitions apply consistently; oversize 413. |
| BVA-009 | P1 | `CHUNK_SIZE=500`, overlap `80` | Text lengths 499, 500, 501 and overlap boundary: deterministic normalized chunks, one chunk start/step no more than configured size, overlap `<` size. |
| BVA-010 | P0 | Overlap configuration | `CHUNK_OVERLAP >= CHUNK_SIZE`, negative, non-integer: startup rejects. |
| BVA-011 | P1 | Chunk numbering | First/last chunk of source: first is `Chunk #1`, subsequent are sequential and no zero/gap. |
| BVA-012 | P1 | Source filename/citation | Names with spaces, Unicode and HTML-like characters: exact basename plus chunk is represented and rendered safely. |
| BVA-013 | P1 | Empty usable text | TXT all whitespace and DOCX with no usable text: zero chunks/no evidence, no fabricated success. |
| BVA-014 | P1 | Archive limits | Exact and over file/member/expanded-size/compression-ratio limits: exact accepted where valid, over limit rejected before resource exhaustion. |
| BVA-015 | P1 | Timeout bounds | Read timeout exactly below/at/over bounded values: bounded failure, no hang, retries limited to transient failures. |
| BVA-016 | P1 | Ollama startup delay | Start web then late Ollama/model availability: web remains alive/degraded, health 200, then re-index/retrieval succeeds after readiness. |
| BVA-017 | P1 | Model/metric mismatch | Change embed model or metric and reuse old collection: mismatch blocks silent query and requires full re-index. |
| BVA-018 | P1 | Fingerprint-only change | Change source bytes while same size/modtime: changed content hash detects re-index. |

### UI and JSON export

| ID | Priority | Requirements | Prerequisites | Steps | Expected result |
|---|---|---|---|---|---|
| UI-001 | P1 | FR-05.5 | UI running | Exercise loading/success/no-result/error states. | Distinct loading, success, no-result and actionable error UI states; success is never shown on failed HTTP. |
| UI-002 | P1 | FR-02.5 | Q&A response with sources | Submit and inspect. | Retrieved source list is human-readable and escaped. |
| UI-003 | P1 | EC-23, EC-25 | Answer/test case includes quotes, line breaks, HTML-like text | Submit. | Browser inserts content with text escaping; markup is not executed and JSON remains valid. |
| UI-004 | P1 | FR-04.8 | Valid test-case array | Submit test mode. | Cases render in readable table with all fields and type badges. |
| UI-005 | P0 | FR-04.9, FR-04.10 | Valid test-case response | Click Export JSON. | Downloads valid human-readable JSON preserving every required field and exactly the displayed case data. |

### Docker, persistence and external configuration

| ID | Priority | Requirements | Prerequisites | Steps | Expected result |
|---|---|---|---|---|---|
| OPS-001 | P0 | FR-06.1, ADR-2 | Docker available | Build from Dockerfile. | Image builds with compatible pinned/bounded dependencies; runs non-root/production WSGI, exposes port 5000. |
| OPS-002 | P0 | FR-06.2, FR-06.6 | Docker Compose | Run documented Compose command. | `rag-web` and `ollama` start; only web UI/API host port is published by default. |
| OPS-003 | P1 | FR-06.7 | Compose override env | Set model names, DB/docs/collection/path variables and external URL. | Overrides take effect without source edit; health/retrieval uses override values. |
| OPS-004 | P1 | ADR-6 | Compose external Ollama | Set `OLLAMA_BASE_URL` to external host and remove local dependency for app route where test permits. | App routes external endpoint; compose local Ollama is not required for app startup. |
| OPS-005 | P0 | FR-06.4, NFR-03 | Indexed stack | Re-index, stop/restart, and query. | Chroma named/host volume persists active chunks, source metadata and collection metadata across restart. |
| OPS-006 | P0 | ADR-6 | Ollama model volume | Start/stop/restart Ollama in Compose. | Model cache is distinct from Chroma and persists across Ollama/container restart. |
| OPS-007 | P0 | FR-06.5 | Running containers | Run Docker health check and GET `/health`. | Container reports/live process state from bounded HTTP 200 JSON; degraded JSON is truthful. |
| OPS-008 | P1 | FR-06.8 | Slow Ollama startup | Start Compose. | Web stays alive; health is degraded or empty/ready truthfully; web retries bounded and never crash-waits indefinitely. |
| OPS-009 | P1 | EC-19, EC-22 | Host port conflict or network DNS mismatch | Start compose with override/conflict. | Safe operator-visible diagnostics; no secret leakage; host port override and external URL examples work. |
| OPS-010 | P1 | FR-06.2 | Stop Ollama during operation | Ask/chat and re-index. | `/ask` uses 503/no fabricated answer; re-index 503; web process remains available. |
| OPS-011 | P1 | ADR-2 | Mount docs read-only; modify host file | Re-index via host. | Read-only mount is used for source discovery only; active DB remains writable. |
| OPS-012 | P1 | NFR-06 | Image/build logs | Inspect Docker/Compose environment. | No credentials/secrets in env examples/workflows/logs; source data is not copied into image or third-party endpoint. |

### Security and configuration

| ID | Priority | Requirements | Prerequisites | Steps | Expected result |
|---|---|---|---|---|---|
| CFG-001 | P0 | FR-01.7, NFR-07 | Environment with valid settings | Set DOCS_DIR, DB_DIR, COLLECTION_NAME, OLLAMA URL/models. | All settings are used and reported safely; no source code edit. |
| CFG-002 | P0 | NFR-07 | Invalid negative/non-finite config for numeric ranges | Start app. | Startup rejects invalid settings; no silent default substitution. |
| CFG-003 | P0 | ADR-1 | DOCS_DIR contains traversal/symlink names | Re-index. | Direct children only; no symlinks or outside paths read; no absolute paths in output. |
| CFG-004 | P0 | NFR-06 | Filename or model error with attacker-like characters | Trigger safe error/citation. | Safe basename, no parser stack, no absolute path, no rendered HTML; no credentials. |
| SEC-001 | P0 | NFR-02 | External URL unset | Ask with local Ollama/Chroma. | Text and vectors remain local; no third-party request. |
| SEC-002 | P1 | ADR-8 | Service bound on loopback/trusted host | Probe unauthenticated API. | MVP remains intentionally unauthenticated; deployment guidance warns loopback/firewall/local-trusted access. |
| SEC-003 | P0 | NFR-06 | Model output/document includes `<script>` or Markdown | Render/return. | UI uses text escaping; API no raw stack trace or prompt. |

## GitHub Actions Cases

| ID | Priority | Requirements | Prerequisites | Steps | Expected result |
|---|---|---|---|---|---|
| CI-001 | P1 | FR-07.1 | Push/PR default branch | Trigger workflow. | CI executes on pushes and PRs to default branch. |
| CI-002 | P1 | FR-07.2 | CI checkout | Install dependencies and run syntax/import checks. | Dependency install and Python syntax/import verification complete with explicit pass/fail. |
| CI-003 | P0 | FR-07.3 | Docker-in-CI | Build application image. | Image build succeeds/fails clearly without third-party model downloads. |
| CI-004 | P0 | FR-07.4, ADR-7 | CI Compose with mock Ollama | Start temporary Compose project. | Stack starts with mock endpoint, health `/health` returns HTTP 200 in bounded time. |
| CI-005 | P0 | FR-07.5 | Mock fixture and `/ask` | Call `/health` and at least one `/ask`. | Health fields and successful deterministic ask/test-case JSON contract are verified. |
| CI-006 | P0 | ADR-7 | CI environment | Inspect mock/workflow. | Stub implements only consumed Ollama HTTP shapes; no full model pull/run. |
| CI-007 | P0 | FR-07.6 | Success and forced-failure CI | Execute cleanup path. | Containers, temporary volumes/network/project storage are cleaned after success/failure; cleanup never targets production volumes. |
| CI-008 | P1 | FR-07.7, EC-20, EC-24 | Secrets absent and slow runner | Run workflow. | No secrets are logged/source-controlled; no unbounded model wait or timeout; job makes bounded mock-only progress. |

## Test Data Notes

### Required fixture classes

- **TXT-valid:** UTF-8 with/without BOM, Unicode, whitespace normalization, explicit range, positive/negative workflow, contradiction, HTML-like text.
- **TXT-invalid:** invalid UTF-8, NUL/binary, ZIP/DOCX signature, PDF signature, and empty/whitespace-only content.
- **DOCX-valid:** paragraphs and tables, Unicode, one-based chunk text.
- **DOCX-invalid:** plain/non-ZIP `.docx`, missing `[Content_Types].xml`, missing `word/document.xml`, malformed XML, encrypted ZIP, corrupted central directory, resource-limit shape.
- **Retrieval:** returned `distance` values around `MAX_DISTANCE`, over-threshold-only evidence, mixed supported/unsupported context, exact and forged citations.
- **Generator:** valid array; malformed JSON; missing fields; wrong types; duplicate/gapped IDs; 8 and 9 cases; valid/forged source refs; extra keys.
- **Config:** valid defaults and overrides, negative/non-finite numeric values, overlap ≥ size, model/metric mismatch.
- **Operations:** temporary Chroma/DB, read-only docs mount, external Ollama URL, slow Ollama, unavailable Ollama, unavailable Chroma, disk/write failure.

### Deterministic Ollama mock contract

The mock should return:

- `/api/embed`: stable vectors for fixture strings and questions.
- `/api/chat`: controlled plain-text and JSON content via a fixture-controlled response mapping.
- Availability checks: deterministic available/unavailable states.

It must not call/download real models. CI chat output may validate grounding interface/schema, not factual model quality.

### Synthetic ranges and boundary derivation

Use boundary values in test cases only when the fixture explicitly documents them. Examples: `8–20 characters` tests 8, 20 and directly outside values 7/21 only if test design derives adjacency from the documented range. Do not infer an omitted minimum/maximum. `MAX_DISTANCE=1.0`, `MAX_CASES=8`, `TOP_K=5`, and `CHUNK_SIZE=500/overlap=80` are implementation-documented ranges and may be tested directly. Numeric settings such as negative/non-finite values are derived from the explicit startup rejection rule.

### Cleanup and sensitive data

- Use temporary directory names and temporary/fixture-only Docker volumes.
- Do not copy `chroma_txt_db/` into an image or CI fixture.
- Never log request prompts, document contents, embeddings, absolute paths, environment dumps, credentials or external URL credentials.
- Run CI cleanup on success and every failure path.
