# Stage 2 — Architecture Design

**Work item:** Local Ollama + ChromaDB RAG QA Platform (`rag-web`)  
**Status:** Proposed; requires human approval before Stage 3  
**Artifact path:** `aidlc-docs/rag-qa-platform/02-architecture.md`

## Architecture Overview

### Goals and scope

Retain the existing Flask single-page UI and `/ask`, `/health`, and `/reindex` endpoints, while separating configuration, ingestion, retrieval, model access, and response validation into small modules. The platform indexes valid UTF-8 `.txt` and `.docx` files from the configured local documents directory and uses local Ollama embeddings/chat with persistent ChromaDB storage.

PDF ingestion is **out of scope**. Files with `.pdf` extensions are not indexed. A PDF, DOCX, or other binary file renamed `.txt` must be rejected as invalid text rather than decoded or indexed. Invalid supported-extension files are reported and excluded; a re-index operation that encounters invalid input must not report success or publish a partial replacement index.

There is no upload endpoint in this MVP. An operator places files in the configured documents directory and invokes re-indexing. Authentication is intentionally omitted for the trusted local MVP; binding the service to a non-loopback interface or exposing it beyond a trusted host/network requires network-level controls.

### Logical architecture

```text
Browser (templates/index.html)
        | same-origin HTTP/JSON
        v
Flask application (app.py; routes and error mapping)
        |
        +-- RAG service: validate input, retrieve evidence, build grounded prompts,
        |                validate citations / test-case response
        +-- Ingestion service: discover, validate, extract, normalize, chunk files
        +-- Chroma adapter: persistent collection, candidate index, metadata
        +-- Ollama adapter: embeddings, chat, bounded HTTP timeouts/retries
        |
        +---------------------> Persistent ChromaDB directory/volume
        +---------------------> Ollama HTTP API
                                  (Compose service or configured external URL)
```

The browser never accesses Ollama or ChromaDB directly. Document text and prompts remain within the configured local Ollama/ChromaDB environment. The Compose Ollama service is reachable only over the Compose network by default; only the web port is published to the host. Configuring `OLLAMA_BASE_URL` for an external Ollama host is supported, but that host receives the prompts and document context and must be trusted. Do not configure a hosted third-party endpoint if local-only privacy is required.

### Request and indexing flows

**Startup / indexing**

1. Load and validate environment configuration; create the configured document and database directories.
2. Open the persistent ChromaDB client and collection without requiring Ollama to be online.
3. Discover supported extensions only. Read `.txt` as strict UTF-8 (accept and strip a UTF-8 BOM); validate and extract `.docx` text as described below. Skip empty documents. Record invalid files by safe basename and reason category.
4. Normalize whitespace, chunk deterministically with configurable chunk size/overlap, and attach stable source filename and one-based per-file chunk number metadata. Build a content fingerprint from sorted filenames and file bytes/content, not modification time alone.
5. If initial indexing is required or the operator requests re-indexing, generate embeddings and build a candidate index. Promote the candidate only after all documents and vectors validate and are written successfully; retain the currently active index on failure. Clean up obsolete candidate/previous collections only after promotion.
6. If Ollama is unavailable at startup, keep the web process alive with the existing persistent index where possible, mark health degraded, and retry transient Ollama calls with bounded exponential backoff. Do not perform unbounded startup waits. An explicit re-index returns an error if embedding cannot complete.

Re-indexing is serialized within the application to prevent concurrent writers. Files are read into a stable in-memory snapshot for that operation, and a fingerprint/snapshot mismatch during processing causes the candidate to be discarded and the operator to retry. ChromaDB uses a persistent local directory (or named Compose volume); the active collection name and embedding model/collection configuration are recorded so incompatible configuration is not silently queried as if valid.

**Q&A / test-case request**

1. Validate JSON body, question, mode, configured collection and request-size limits.
2. Embed the question with the configured embedding model, query a bounded top-K from Chroma, and discard results whose Chroma distance exceeds the configured maximum.
3. If no qualifying evidence remains, return the designated no-answer result without calling chat.
4. Send only qualifying chunk text and source metadata as context to the configured chat model, with low temperature, explicit grounding instructions, and an instruction that document text is untrusted data rather than executable instructions.
5. For Q&A, require citation references in the exact human-readable form `filename (Chunk #N)` and validate each citation against the retrieved evidence set. Reject or replace unsupported/unresolvable output with the no-answer response; do not treat citation-format validation as proof that each natural-language claim is semantically entailed.
6. For test cases, parse JSON and validate the response against the strict schema and evidence set. Return no partial success on invalid JSON or schema violations.
7. Return structured JSON and the set of retrieved sources to the browser. The browser renders model/document content as text and escapes it before inserting into the page.

### Configuration and recommended defaults

| Variable | Recommended default | Purpose |
|---|---|---|
| `DOCS_DIR` | `docs` | Local source directory; mounted read-only in Compose |
| `DB_DIR` | `chroma_txt_db` | Persistent ChromaDB storage path |
| `COLLECTION_NAME` | `local_rag_docs` | Active collection name (migration from current `local_txt_docs` is an implementation concern) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` natively; `http://ollama:11434` in Compose | Ollama API base URL; external URL may be configured |
| `CHAT_MODEL` | `llama3.2` | Ollama chat model |
| `EMBED_MODEL` | `nomic-embed-text` | Ollama embedding model |
| `MAX_DISTANCE` | `1.0` | Inclusive maximum Chroma distance; greater distances are not eligible as evidence |
| `TOP_K` | `5` | Maximum retrieved chunks before threshold filtering |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `500` / `80` characters | Deterministic text chunking; overlap must be smaller than size |
| `MAX_CASES` | `8` | Upper bound on generated test cases |
| `OLLAMA_CONNECT_TIMEOUT` | `5` seconds | Connection timeout |
| `OLLAMA_READ_TIMEOUT` | `180` seconds for chat; shorter configurable embedding timeout | Bounded inference time |
| `PORT` | `5000` | Web service port |

`MAX_DISTANCE` is a maximum **distance**, not a similarity score; lower is more relevant. The initial `1.0` default is a conservative starting point for the configured Chroma distance metric and must be reviewed against representative local queries. Keep the collection metric consistent across indexing and querying; changing embedding model or distance metric requires a full re-index. Reject invalid, negative, or non-finite numeric settings during startup rather than silently substituting values. Compose must permit overriding `OLLAMA_BASE_URL` and both model names without source changes.

## Component & File Changes

The repository currently has `app.py`, `templates/index.html`, `docs/`, `chroma_txt_db/`, and `cli_chat.py`; no dependency manifest, Docker configuration, or GitHub Actions workflow was present in the inspected tree. The following are **design targets for a later implementation stage only**. Stage 2 changes this architecture document only.

| File / module | Responsibility |
|---|---|
| `app.py` | Flask app factory/route registration and WSGI entry point; retain `/`, `/health`, `/reindex`, `/ask`. Routes delegate to services and map known exceptions to stable API errors. Avoid model calls or indexing as import-time side effects. |
| `rag/config.py` | Typed environment configuration, defaults, range checks, safe URL handling, and path/model settings. |
| `rag/ingestion.py` | Discovery limited to direct children of `DOCS_DIR`; UTF-8 TXT validation; DOCX container validation and text extraction; normalization, chunking, fingerprinting, and safe invalid-file diagnostics. |
| `rag/vector_store.py` | Chroma persistent client/collection access, metadata contract, distance metric, serialized candidate-index creation and promotion, and cleanup. |
| `rag/ollama_client.py` | HTTP client for `/api/embed`, `/api/chat`, and lightweight availability/model checks; timeouts, limited retry for transient connection failures, response validation, and sanitized failures. |
| `rag/rag_service.py` | Query orchestration, threshold filtering, evidence context formatting, prompts, no-answer handling, citation validation, test-case JSON parsing/schema/evidence validation. |
| `rag/schemas.py` (or equivalent) | Request/response and test-case schema constants/validation; avoid introducing a heavyweight validation framework for this small API. |
| `templates/index.html` | Preserve both modes, display degraded health and source citations, handle loading/error/no-result responses including re-index failures, and use safe DOM/text rendering. |
| `requirements.txt` | Declare compatible, pinned or bounded Flask, ChromaDB, requests, and `python-docx` runtime dependencies. Pin a Python-compatible dependency set; do not install unused PDF tooling. |
| `Dockerfile` | Small Python runtime image, non-root application user, deterministic dependency install, working directory, exposed web port, and Flask production WSGI server rather than the development server. |
| `compose.yaml` | `rag-web` and `ollama` services, app/Ollama model environment, web port mapping, persistent Chroma and Ollama model volumes, read-only docs mount, network isolation, health check, and startup dependency semantics. |
| `.dockerignore` | Exclude local databases, caches, virtual environments, VCS metadata, and secrets from build context. |
| `.env.example` / run documentation | Document safe variable names/defaults, model setup, host port, persistence, native versus Compose Ollama URL, re-index operation, and local-network exposure caveat. Never include credentials. |
| `.github/workflows/ci.yml` | Push/PR workflow described below; no secrets required for the local-model contract checks. |
| `tests/` | Unit and API tests for ingestion validation, threshold/citation behavior, schema validation, error mapping, and the deterministic Ollama HTTP contract stub. |
| `compose.ci.yaml` and `tests/support/ollama_stub.py` (or equivalent CI fixture) | CI-only mock Ollama endpoint and override for `OLLAMA_BASE_URL`; deterministic embeddings/chat responses enable container smoke tests without downloading models. Keep the stub outside production runtime. |

`cli_chat.py` is a secondary consumer of current `app.py` globals and should either be updated to consume the service interfaces or explicitly left as a legacy utility. It must not preserve a separate, unvalidated retrieval path that disagrees with web citations and thresholds. Local `chroma_txt_db/` contents are runtime data and must not be copied into the image or committed as application fixtures.

### DOCX and TXT validation policy

- Accept only case-insensitive `.txt` and `.docx` filename suffixes in the configured directory; ignore other extensions, including PDF. Do not recursively follow symlinks or process paths outside the configured directory.
- TXT decoding is strict UTF-8; a decoding failure, NUL/binary content, or a ZIP/DOCX signature under `.txt` makes the file invalid. Do not fall back to a legacy encoding or index replacement characters.
- Use `python-docx` for normal paragraph/table text extraction. Before parsing, use `zipfile` inspection to verify the file is a readable, non-encrypted ZIP with expected OOXML members including `[Content_Types].xml` and `word/document.xml`. A non-ZIP, missing-member, malformed, encrypted, or unparseable `.docx` is invalid, not silently treated as text.
- Apply conservative configurable limits to source file bytes, ZIP member count, expanded total bytes, and per-member compression ratio before DOCX parsing to reduce ZIP-bomb/resource risks. Do not extract archive entries to the filesystem. Treat text, XML, and embedded document content as untrusted; never execute macros or embedded objects.
- Preserve a clean basename as the source identity; detect duplicate basenames/collisions and fail the candidate index rather than making citations ambiguous. A file with no usable extracted text is reported/skipped and contributes no chunks.
- Re-index validation is all-or-nothing for supported files: if a supported file is invalid, report its basename and category and do not replace the active index. Unsupported extensions can be ignored and counted separately. The response must not expose absolute paths or parser stack traces.

## API / Data Contracts

All API responses use `application/json`, UTF-8, and stable error objects. Requests have a documented body-size ceiling; reject unsupported content types and malformed JSON with HTTP 400. Do not return stack traces, raw prompts, document contents, embeddings, or filesystem absolute paths in errors.

### `GET /`

Returns the existing single-page application. No data or model generation is performed.

### `GET /health`

Always returns HTTP 200 when the Flask process can serve the endpoint, including when Ollama is unavailable. Health checks are bounded and do not index documents, generate text, or wait for model download.

```json
{
  "status": "ok",
  "chat_model": "llama3.2",
  "embed_model": "nomic-embed-text",
  "files_count": 2,
  "files": ["guide.docx", "guide.txt"],
  "chunks_indexed": 14,
  "ollama": "available",
  "index_status": "ready"
}
```

Use `"status": "degraded"` and `"ollama": "unavailable"` when the configured Ollama endpoint is unreachable; use `"index_status": "unavailable"` if ChromaDB cannot be read. An empty but healthy corpus may report `"status": "ok"`, `"index_status": "empty"`, zero counts, and a successful service health signal. Include model configuration and counts only—never prompts, document contents, environment dumps, or secrets. Ollama/model availability checks use a short timeout and should avoid expensive model inference; health is an operational status, not proof that a configured model can successfully generate.

### `POST /reindex`

Request: empty JSON object or no body. Re-indexes the current valid supported files. This is the explicit refresh path; fingerprint checks may also trigger a refresh according to the implementation policy.

Success `200`:

```json
{
  "message": "Documents re-indexed successfully.",
  "files_count": 2,
  "chunks_indexed": 14
}
```

Failures:

- `422` for invalid supported files or duplicate source basenames; include safe per-file `{ "filename": "...", "reason": "invalid_utf8" }` diagnostics and do not promote the candidate index.
- `503` when embedding service is unavailable after bounded retries.
- `500` for storage/index failures, with a generic non-sensitive error code/message.
- `409` if another re-index operation is currently in progress (or serialize requests and return the completed result; choose one behavior consistently).

The browser must inspect HTTP status and JSON body, show success only for a successful response, and present safe actionable errors.

### `POST /ask`

Request:

```json
{
  "question": "What is the documented password length range?",
  "mode": "qa"
}
```

`question` is a required non-empty trimmed string subject to a configured maximum length. `mode` is optional and defaults to `"qa"`; allowed values are `"qa"` and `"test_cases"`. Reject malformed JSON, wrong field types, empty question, unsupported mode, and oversized payloads with HTTP `400` (oversize may use `413`). No conversation state is accepted or retained.

Q&A success `200`:

```json
{
  "mode": "qa",
  "answer": "The documented range is 8–20 characters. guide.docx (Chunk #2)",
  "sources": ["guide.docx (Chunk #2)"],
  "chunks_used": 1
}
```

Test-case success `200`:

```json
{
  "mode": "test_cases",
  "test_cases": [
    {
      "id": "TC-001",
      "title": "Accept a documented valid value",
      "type": "Positive",
      "preconditions": "The documented feature is available.",
      "steps": ["Enter a value within the documented range.", "Submit the value."],
      "expected_result": "The documented successful outcome occurs.",
      "source_ref": "guide.docx (Chunk #2)"
    }
  ],
  "sources": ["guide.docx (Chunk #2)"],
  "chunks_used": 1
}
```

`source_ref` must be exactly one or more retrieved source references in `filename (Chunk #N)` form (a single reference is preferred per case); every referenced pair must exist in the evidence supplied to the model. `sources` represents qualifying retrieved evidence, not a claim that every chunk supports every generated statement.

No evidence / no qualifying result returns HTTP 200 with a successful no-answer result and no model-generated claims:

```json
{
  "mode": "qa",
  "answer": "This information is not available in the indexed documents.",
  "sources": [],
  "chunks_used": 0
}
```

For `test_cases`, use the same no-answer sentence in a documented `message` field with an empty `test_cases` array and empty sources; do not fabricate cases when evidence is absent.

Stable error contract:

```json
{ "error": { "code": "ollama_unavailable", "message": "The local model service is unavailable. Check Ollama and try again." } }
```

Recommended statuses: `400` malformed/invalid request or no valid indexed documents; `413` body too large; `422` invalid model output (including malformed JSON, invalid case schema, or unsupported citations); `503` Ollama unavailable; `500` unexpected Chroma/storage/RAG processing failure. No failure response contains a successful partial `answer` or `test_cases`.

### Retrieval, answer and test-case validation

- Query Chroma for at most `TOP_K` nearest chunks and apply `distance <= MAX_DISTANCE` before composing context. Chroma distance and threshold are tied to the collection's configured metric; store metric/model identity with the index and require re-index on a mismatch.
- Empty corpus, empty retrieval, or all chunks above threshold short-circuits to the no-answer response. The threshold is the system-level evidence gate; the model cannot override it.
- The Q&A prompt demands only evidence-supported claims, the exact fallback sentence for missing facts, and citations as `filename (Chunk #N)`. Validate every emitted citation against the request's retrieved reference set. If output contains an invalid citation or fails the citation contract, do not return it as grounded; return the designated no-answer response or a validation error, consistently.
- Citation validation confirms source/chunk identity, not entailment. Prompting, low-temperature generation, evidence-only context, and conservative fallback reduce risk but do not mathematically prove semantic grounding. A later stage should test unsupported/mixed questions and avoid representing citation presence as a formal factuality guarantee.
- The generator may return at most `MAX_CASES` (default 8), with unique sequential IDs (`TC-001` through the returned count), required non-empty string fields, non-empty string-array `steps`, and `type` restricted to `Positive`, `Negative`, or `Boundary`. Reject extra/invalid fields if they make rendering ambiguous.
- Validate every `source_ref` against retrieved source/chunk pairs. Invalid references, duplicate IDs, excess cases, malformed JSON, or missing/incorrect fields invalidate the response; do not truncate a malformed response into apparent success.
- Generate boundary cases only from explicit documented limits/ranges or boundaries directly identifiable from a documented rule. Do not infer conventional min/max values, numeric limits, or unmentioned validation behavior. If no boundary is documented, omit boundary cases rather than invent one.
- Prompts explicitly treat retrieved text as untrusted content, not system instructions. This is a prompt-injection mitigation, not a sandbox or guarantee; model output always passes schema and evidence-reference validation.

### Chroma record contract

Each chunk record contains:

```text
id: stable opaque identifier derived from source identity/content version/chunk number
document: normalized chunk text
embedding: vector from configured EMBED_MODEL
metadata:
  source: safe basename (case-preserving)
  chunk_num: one-based integer within that source
  content_fingerprint: source content hash/version
  embedding_model: configured model identifier
```

Collection-level metadata records schema version, fingerprint of sorted supported source files, embedding model, and distance metric. Citations are built from `source` + `chunk_num`, not vector IDs. Keep document text and vectors local; no API response returns embeddings or raw database records.

## Architecture Decision Records (ADRs)

### ADR-1: Separate ingestion formats and safely support `.txt` plus `.docx`

**Decision:** Decode `.txt` strictly as UTF-8 and parse validated OOXML `.docx` with `python-docx`, preceded by bounded ZIP/member checks. Reject misnamed or malformed formats; PDF remains out of scope.

**Rationale:** Satisfies the explicit scope while preventing binary data from silently becoming evidence. `python-docx` handles ordinary paragraphs/tables with less custom XML code; ZIP validation and resource limits protect against malformed/oversized archives.

**Trade-offs:** Adds one runtime dependency and DOCX parsing edge cases. Unsupported or corrupt files require operator correction. PDF conversion/extraction and OCR are intentionally not included.

### ADR-2: Keep Flask, ChromaDB, and Ollama as the core runtime

**Decision:** Preserve Flask and Chroma persistent local storage, communicate with Ollama through its HTTP API, and extract responsibilities into focused Python modules rather than introducing a new web framework, hosted vector service, or distributed architecture.

**Rationale:** Aligns with the working baseline and local-only objective; keeps deployment and operations lightweight.

**Trade-offs:** Single-process application-level serialization is not a distributed lock. Running multiple web replicas against one local Chroma persistence directory is unsupported; use a single app instance for the MVP.

### ADR-3: Gate evidence with configurable maximum Chroma distance

**Decision:** Apply a configurable inclusive maximum distance (`MAX_DISTANCE`, proposed default `1.0`) after top-K retrieval and before generation. No qualifying evidence means no-answer without chat generation.

**Rationale:** Prevents weakly related chunks from being treated as evidence and gives operators a tunable acceptance boundary.

**Trade-offs:** Distance scale varies with embedding model and collection metric; default requires evaluation and full re-index when model/metric changes. A strict threshold can increase false no-answers; a permissive threshold can admit irrelevant context. Do not present this as calibrated semantic confidence.

### ADR-4: Validate citations and generated test cases before responding

**Decision:** Require exact filename/chunk citation identifiers that match retrieved records, and validate test-case JSON schema, types, unique sequential IDs, references, and a maximum count of 8.

**Rationale:** Machine validation prevents invented source identifiers and malformed UI/export data; bounded output improves usability and protects local resources.

**Trade-offs:** A model can cite a real retrieved chunk that does not entail its claim. Semantic entailment remains an explicit residual risk. Strict validation may reject otherwise readable model output; rejected output must not become success-shaped partial data.

### ADR-5: Keep health HTTP 200 and expose degraded state

**Decision:** `/health` returns HTTP 200 whenever the web process can serve it; report `"status": "degraded"` when Ollama is unreachable, with separate Ollama and index status fields.

**Rationale:** Allows container monitoring to distinguish a live web process from unavailable inference while honoring the required HTTP behavior and retaining diagnosable state.

**Trade-offs:** A generic HTTP-only probe sees 200 in a degraded state. Deployment monitoring must inspect the JSON `status` field when model readiness matters. The health path must remain fast and bounded.

### ADR-6: Compose manages local Ollama; external Ollama remains configurable

**Decision:** Default Compose starts `rag-web` and `ollama` on a private Compose network with named persistent volumes. The app uses `http://ollama:11434` in Compose; `OLLAMA_BASE_URL` can target an externally managed Ollama service. Model names default to `llama3.2` and `nomic-embed-text`.

**Rationale:** Supports an all-local first run and native/external installations without source edits.

**Trade-offs:** Ollama models can consume substantial disk/RAM and initial pulls take time. Compose service startup does not mean model files are installed; provide explicit model-pull instructions and let health show degraded until usable. External URL configuration expands the trust boundary.

### ADR-7: Use deterministic Ollama contract mocks in CI

**Decision:** CI builds the production image and starts a Compose smoke stack with a CI-only HTTP-compatible Ollama stub, fixture documents, and temporary CI storage. The stub returns predictable embedding and chat responses and supports at least one end-to-end `/ask` request. Do not download full models in GitHub Actions.

**Rationale:** Validates container networking, app startup, index/retrieval, JSON contracts, and request handling quickly without GPU/model-cache assumptions or timeouts.

**Trade-offs:** Does not prove actual model quality, model availability, or grounding fidelity. Local/manual validation with the configured Ollama models remains necessary. CI must clean up containers and temporary volumes even on failure.

### ADR-8: No authentication in the local MVP

**Decision:** Keep the UI/API unauthenticated, as requested, and make the default deployment local/trusted-network oriented.

**Rationale:** Avoids overbuilding account/session infrastructure for a single-user local platform.

**Trade-offs:** Anyone who can reach the published port can query documents, trigger inference, and request re-indexing. Do not expose it directly to the public internet or an untrusted LAN. Restrict host binding/firewall access; authentication and CSRF/network protections are future scope if deployment expands.

## Risks & Edge Cases

### Security and privacy

- Documents and model output are untrusted input. Validate extensions, strict decoding, DOCX ZIP structure and size limits; do not execute or extract embedded content to arbitrary paths.
- Locality depends on configuration: an external `OLLAMA_BASE_URL` receives document snippets and prompts. Document this explicitly, avoid third-party inference endpoints, and do not log prompt/document bodies.
- Compose should publish only the web port; avoid publishing Ollama port by default. The Flask process should run as non-root, use a production WSGI server, and avoid debug mode.
- No auth means access to the web port grants access to indexed knowledge and compute. Loopback-only host binding is safest for local use; if exposing to LAN, apply firewall/reverse-proxy access restrictions. Do not claim the app itself enforces local-user identity.
- Escape generated text in the UI and avoid unsafe HTML insertion; test cases, citations, filenames, and errors can contain hostile markup.
- Prevent path traversal and symlink escape in directory discovery; never return absolute paths. Guard request body size, question length, number/size of files, number of chunks, and model output length.
- Chroma persistence contains sensitive derived data (documents/embeddings); volume permissions and backup/deletion practices must be documented. Ollama's model volume is separate from application index data.

### Reliability, startup, and persistence

- Ollama may start later than Flask, lack one or both models, time out, or fail between embedding and chat. Use bounded connection/read timeouts, a small retry policy only for transient failures, meaningful HTTP errors, and degraded health; never fabricate a fallback answer.
- Initial indexing requires Ollama embeddings. Start the HTTP service without a permanent crash if Ollama is unavailable; preserve/use the previous index and permit a later explicit re-index.
- Candidate index promotion must not delete the active collection before embeddings and all writes succeed. Handle failed candidate cleanup, incompatible Chroma persistence versions, disk-full errors, and process interruption during promotion.
- A model or distance metric change invalidates old vectors; detect metadata mismatch and require a complete re-index rather than mixing incompatible vectors.
- Avoid serving a mixture of files from a changing directory: snapshot files/fingerprints for a re-index and discard the candidate if inputs change mid-operation.
- Chroma's local persistent store is intended for one web instance. Concurrent replicas, shared network filesystems, and simultaneous CLI/web writers are not supported without a separate coordination design.
- Files with duplicate basenames create ambiguous citations and must be reported. Empty files and unsupported extensions do not create chunks. Invalid `.txt`/`.docx` files block candidate promotion and are reported safely.
- Existing local Chroma data uses the current collection name and TXT-era schema. Migration/re-index behavior must be explicit; do not assume old fingerprints, records, or incompatible embedding dimensions are reusable.

### Retrieval and output quality

- `MAX_DISTANCE=1.0` is a starting point, not a universal confidence score. Calibrate with representative in-scope/out-of-scope questions and make the effective metric/threshold visible in operator documentation.
- A relevant fact may span multiple chunks, be phrased differently, or conflict across documents. Return citations for the evidence actually used; do not resolve contradictions by inventing precedence. If evidence cannot support a clear answer, use the no-answer sentence and/or state the documented conflict with citations.
- Citation identifier validation catches nonexistent references but cannot guarantee entailment or that every claim is cited. CI mocks validate interface contracts only; human review and model-backed quality testing remain necessary.
- Ollama may return malformed/empty JSON, extra keys, invalid types, unsupported references, duplicate IDs, more than eight cases, or incomplete cases. Reject the entire generated result as invalid; never display/export a partial “successful” array.
- A model may propose boundary values not in the documents. Enforce that boundary cases and values derive only from documented rules/ranges; omit boundary coverage when no explicit boundary can be established.
- Large DOCX/TXT inputs can exhaust memory or produce excessive chunks. Apply documented file/expanded-size/chunk limits, process embedding batches, and return clear operator diagnostics.

### Docker and CI operations

- Compose must wait for Ollama process readiness where supported, but not wait indefinitely for model downloads. Provide model-pull instructions and ensure web health reports `degraded` while Ollama is unavailable.
- Preserve Chroma data and Ollama model cache using distinct named volumes. Do not use CI cleanup commands against production volumes; CI uses uniquely scoped temporary volumes and `down --volumes` only for its own project.
- Host port conflicts, path syntax differences on Windows/Linux, Docker Desktop DNS, and external Ollama host routing can prevent connectivity. Document port overrides and native/external URL examples; health diagnostics should identify service reachability without leaking URLs with credentials.
- GitHub Actions runners may be CPU-only and cannot reliably download/run full LLMs within job time limits. Contract stubs are deliberately not model-quality tests; always clean up on job failure and avoid secrets in logs/workflow files.
- The test stub must mimic only the Ollama endpoints and response shapes actually consumed by the application. Keep CI fixture behavior deterministic, and separately test real Ollama model setup outside CI.

**Stage gate:** This document is the Stage 2 proposal. Do not begin Stage 3 implementation until a human approves this architecture.
