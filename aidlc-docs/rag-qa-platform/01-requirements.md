# Stage 1 - Requirements

## Work Item Summary

**Work item:** Local Ollama + ChromaDB RAG QA Platform (`rag-web`)

**Purpose:** Provide a local, document-grounded quality assurance assistant that answers questions from indexed TXT documents and generates structured QA test cases. The delivered platform must cite exact supporting sources, reject unsupported answers, be runnable with Docker/Docker Compose, expose operational health information, and verify builds in GitHub Actions.

**Repository baseline:**
- `app.py` provides a Flask UI/API, local TXT indexing, ChromaDB retrieval, Ollama chat and embedding calls, `/health`, `/reindex`, and `/ask`.
- `templates/index.html` provides Document Q&A and QA Test Case Generator modes, source display, re-indexing, and JSON download.
- `docs/` currently contains `SRS_Highlighted_Review.txt` and `imran_ali_cv.txt`. `SRS_Highlighted_Review.txt` appears to be a DOCX file despite its `.txt` extension, which the current loader may read as binary text.
- No Dockerfile, Compose file, or `.github/workflows/` CI workflow exists in the baseline.

## User Stories

1. **As an SQA engineer**, I want to ask a question against approved local documents so that I receive an answer grounded only in that evidence.
2. **As an SQA engineer**, I want each factual answer to identify the source document and indexed chunk so that I can verify it directly.
3. **As an SQA reviewer**, I want unsupported questions to receive an explicit no-answer response rather than a fabricated answer.
4. **As an QA engineer**, I want test cases for a feature or requirement categorized as Positive, Negative, or Boundary so that coverage is structured and complete.
5. **As an QA engineer**, I want generated test cases exported as valid JSON so that I can save, review, or import them into another QA workflow.
6. **As a platform operator**, I want to re-index changed documents and inspect index/model health so that I can keep retrieval current.
7. **As a developer or operator**, I want Docker and Docker Compose support plus a `/health` endpoint so that I can run the platform consistently and monitor readiness.
8. **As a maintainer**, I want GitHub Actions to verify container startup and key platform behavior so that CI catches regressions.

## Functional Requirements

### FR-01 Document ingestion and indexing

- FR-01.1 The system shall discover supported `.txt` files in the configured document directory.
- FR-01.2 The system shall create stable document chunk metadata containing at least source filename and chunk number.
- FR-01.3 The system shall store chunks and embeddings in the configured persistent ChromaDB collection.
- FR-01.4 The system shall re-index when an explicit re-index request is made.
- FR-01.5 The system shall detect file/count/fingerprint changes and re-index automatically only when its configuration is designed to do so; an explicit re-index operation shall always remain available.
- FR-01.6 The system shall reject or clearly report unsupported document content instead of silently indexing binary/invalid text.
- FR-01.7 The system shall support configuration of document directory, database directory, collection name, Ollama base URL, embedding model, and chat model through environment variables.

### FR-02 Grounded document Q&A

- FR-02.1 The system shall accept a non-empty question in `/ask` mode `qa`.
- FR-02.2 The system shall embed the question using the configured Ollama embedding model and retrieve relevant chunks from ChromaDB.
- FR-02.3 The system shall provide retrieved chunk text and metadata to the chat model only as retrieval context.
- FR-02.4 The answer shall cite the exact source filename and chunk number for every factual claim that is supported by a document.
- FR-02.5 The UI shall display retrieved context sources even when multiple chunks are used.
- FR-02.6 If the indexed evidence does not answer the question, the system shall return exactly or substantively: `This information is not available in the indexed documents.`
- FR-02.7 The system shall not infer, speculate, use prior conversation, or add facts absent from retrieved context.
- FR-02.8 The system shall support questions that request a summary or list, while preserving source citations for the synthesized facts.
- FR-02.9 For malformed, empty, or out-of-service requests, the system shall return a stable JSON error and a suitable HTTP status.

### FR-03 Source citation and anti-hallucination guardrails

- FR-03.1 Every answer backed by one or more retrieved chunks shall include source references in the format `filename (Chunk #N)`.
- FR-03.2 A citation shall refer to an actual indexed source and chunk, not a generated or approximate reference.
- FR-03.3 The system shall omit an unsupported claim instead of attributing it to a source.
- FR-03.4 The system shall return the designated no-answer sentence for:
  - no indexed documents;
  - no relevant chunks;
  - questions whose requested facts are absent from retrieved context;
  - questions requesting information from outside the indexed corpus.
- FR-03.5 The system shall apply low-temperature generation for deterministic grounded responses.
- FR-03.6 The system shall not expose retrieval embeddings or internal database records as answer citations.

### FR-04 Structured QA Test Case Generator

- FR-04.1 The system shall accept a feature or requirement topic in `/ask` mode `test_cases`.
- FR-04.2 The system shall generate test cases strictly from retrieved document context.
- FR-04.3 Every generated test case shall contain:
  - `id`;
  - `title`;
  - `type`;
  - `preconditions`;
  - `steps`;
  - `expected_result`;
  - `source_ref`.
- FR-04.4 `type` shall be restricted to `Positive`, `Negative`, or `Boundary`.
- FR-04.5 IDs shall be unique and in a stable sequence such as `TC-001`, `TC-002`, and so on.
- FR-04.6 A test-case response shall not invent features, fields, workflows, limits, or preconditions absent from source context.
- FR-04.7 Boundary cases shall only use documented limits or clearly identifiable boundary values derived from the source.
- FR-04.8 The UI shall render generated cases in a readable table.
- FR-04.9 The UI shall allow downloading the full generated test-case array as valid, human-readable JSON.
- FR-04.10 Downloaded JSON shall preserve `id`, `title`, `type`, `preconditions`, `steps`, `expected_result`, and `source_ref`.
- FR-04.11 If Ollama does not return valid JSON, the API shall return a clear 500-level JSON error and shall not display a success-shaped partial response.
- FR-04.12 A response shall identify the set of source filenames and chunk numbers used to retrieve generation context.

### FR-05 Health, re-indexing, and error reporting

- FR-05.1 `GET /health` shall return HTTP 200 with JSON containing overall status, chat model, embedding model, document count, document filenames, and indexed chunk count.
- FR-05.2 `POST /reindex` shall re-create the configured collection index from currently valid documents and report the resulting chunk count.
- FR-05.3 Re-index failures shall return HTTP 500 with a non-sensitive error description.
- FR-05.4 Ollama or ChromaDB failures shall return JSON errors instead of crashing the Flask process.
- FR-05.5 The UI shall show loading, success, no-result, and error states for health, re-index, Q&A, and test-case operations.

### FR-06 Containerization

- FR-06.1 A Dockerfile shall build a runnable application image containing Flask and the application dependencies.
- FR-06.2 Docker Compose shall run the RAG web application and Ollama as local services.
- FR-06.3 Ollama shall remain local to the Compose network; the application shall not require an external hosted inference provider.
- FR-06.4 ChromaDB data shall persist across container restarts using a named or host-mounted volume.
- FR-06.5 `/health` shall be usable inside the container for readiness or health-check verification.
- FR-06.6 Compose configuration shall expose the web UI and API on a documented host port.
- FR-06.7 Container configuration shall use environment variables for paths and model settings.
- FR-06.8 Containers shall start in a deterministic order or retry dependency initialization until Ollama is ready.

### FR-07 GitHub Actions CI

- FR-07.1 CI shall run on pushes and pull requests to the repository's default branch.
- FR-07.2 CI shall verify dependency installation and Python syntax/imports.
- FR-07.3 CI shall build the application Docker image.
- FR-07.4 CI shall start the Docker Compose stack and wait for `/health` to report readiness.
- FR-07.5 CI shall verify `GET /health` and at least one `/ask` request for Q&A or test-case behavior using an available local Ollama model.
- FR-07.6 CI shall stop and clean up containers after success or failure.
- FR-07.7 CI shall not print secrets or add credentials to source-controlled workflow files.

## Non-Functional Requirements

### NFR-01 Grounding and correctness

- Q&A and test-case output shall be derived only from retrieved local document chunks.
- Exact source citations shall be present for any answer or test case that relies on source material.
- Unsupported content shall use the explicit no-answer guardrail or be rejected as invalid.

### NFR-02 Privacy and locality

- Document text, embeddings, chat prompts, and responses shall remain on the local Ollama/ChromaDB environment.
- The application shall not send indexed documents to third-party hosted APIs.

### NFR-03 Reliability

- Ollama and ChromaDB exceptions shall produce actionable HTTP JSON errors.
- Repeated identical requests shall return stable data and source references where model determinism is supported.
- Indexed data shall survive application/container restarts.

### NFR-04 Performance

- A user-facing `/ask` request should complete within 180 seconds under normal local hardware conditions.
- Health checks should return quickly and must not trigger re-indexing or model generation.
- Re-indexing progress shall not corrupt the existing collection.

### NFR-05 Usability

- The UI shall clearly distinguish Q&A from test-case generation.
- Citations and test-case source references shall be human-readable.
- JSON export shall require no additional local software beyond the browser.
- Error messages shall explain the required user or operator action without exposing stack traces.

### NFR-06 Security

- The API shall validate JSON input and non-empty query values.
- File discovery shall be limited to the configured directory and supported plain-text files.
- The application shall not execute content read from documents.
- Docker and CI configuration shall avoid embedded credentials and secrets.

### NFR-07 Maintainability and configuration

- Models, URLs, paths, and collection names shall be configurable through environment variables.
- Source code and workflow behavior shall use pinned or clearly documented application/runtime dependencies.
- Health output shall make configuration and index state inspectable.

### NFR-08 Portability

- The platform shall run on Windows and Linux hosts with Docker or Docker Compose using documented commands.
- Native Ollama execution and containerized Ollama execution shall not require source-code changes.

## Acceptance Criteria

### AC-01 Grounded Q&A with exact citations

**Given** at least one valid indexed TXT document  
**When** a user submits a factual question answered by that document  
**Then** `/ask` shall return a grounded answer containing the source filename and chunk number.

**Given** a factual claim supported by multiple chunks  
**When** the answer is generated  
**Then** the response shall include every source filename and chunk number actually used to support the claim.

**Given** a question whose answer is absent from the indexed documents  
**When** the user submits it  
**Then** the answer shall contain `This information is not available in the indexed documents.` and shall add no unsupported claims.

**Given** no valid documents are indexed  
**When** a user submits a Q&A request  
**Then** the API shall return HTTP 400 with a clear no-documents error.

### AC-02 Anti-hallucination behavior

**Given** a question requesting personal, technical, or requirement details not present in retrieved context  
**When** the question is processed  
**Then** the system shall not invent an answer or attach unrelated source citations.

**Given** a question combining an answered fact and an unsupported fact  
**When** the answer is generated  
**Then** the response shall include the supported fact with a citation and state that the unsupported fact is unavailable.

**Given** the Ollama chat service is unavailable  
**When** a user submits a request  
**Then** the API shall return HTTP 500 JSON with an Ollama/RAG failure message and no fabricated answer.

### AC-03 Test-case generation

**Given** a feature or requirement described in an indexed document  
**When** the user selects QA Test Case Generator and submits it  
**Then** `/ask` shall return valid JSON containing a `test_cases` array.

**Given** a generated test case  
**When** it is validated  
**Then** it shall include `id`, `title`, `type`, `preconditions`, `steps`, `expected_result`, and `source_ref`, with `type` equal to Positive, Negative, or Boundary.

**Given** a requirement topic with neither a valid positive workflow nor a documented negative or boundary scenario  
**When** test cases are generated  
**Then** the system shall create only cases supported by context and shall not invent feature behavior.

**Given** one or more generated test cases  
**When** the user clicks Export JSON  
**Then** the browser shall download a valid JSON file containing the same test-case data shown in the UI.

**Given** Ollama returns malformed JSON  
**When** the API processes the response  
**Then** the API shall return HTTP 500 JSON error information and shall not return a false success response.

### AC-04 Re-indexing

**Given** a valid TXT file is added or changed and re-indexing is requested  
**When** `POST /reindex` completes  
**Then** the collection metadata shall reflect the new documents and subsequent retrieval shall include their content.

**Given** re-indexing is requested with an unavailable Ollama embedding service  
**When** the request runs  
**Then** `/reindex` shall return HTTP 500 and shall not report successful re-indexing.

### AC-05 Health endpoint

**Given** the application and indexed collection are running  
**When** `GET /health` is called  
**Then** it shall return HTTP 200 JSON with status, chat model, embedding model, files count, files, and chunks indexed.

**Given** a containerized deployment  
**When** the container runtime performs a health check  
**Then** `/health` shall indicate whether the web process is healthy without starting re-indexing or generation.

### AC-06 Docker and Compose

**Given** Docker and Docker Compose are available  
**When** the operator runs the documented Compose command  
**Then** the web application and Ollama services shall start and the UI/API shall be reachable on the documented port.

**Given** the containers are restarted  
**When** ChromaDB data is mounted through persistent storage  
**Then** previously indexed chunks shall remain available.

**Given** Ollama starts more slowly than the web application  
**When** startup is in progress  
**Then** the web container shall retry or otherwise avoid crashing permanently, and `/health` shall remain a truthful readiness signal.

### AC-07 GitHub Actions

**Given** code is pushed or a pull request is opened  
**When** CI runs  
**Then** it shall install dependencies, verify syntax/imports, build the Docker image, and start the Compose stack.

**Given** the Compose stack is ready  
**When** CI calls `/health`  
**Then** the call shall return HTTP 200 and the expected health JSON fields.

**Given** CI performs its smoke test  
**When** Ollama and the indexed document fixture are ready  
**Then** at least one `/ask` request shall return a valid Q&A or test-case JSON response.

**Given** CI succeeds or fails  
**When** the job finishes  
**Then** Compose containers shall be stopped and cleaned up.

## Edge Cases

- EC-01: The question is empty, whitespace-only, or JSON is absent/malformed.
- EC-02: The collection is empty because no valid documents are present.
- EC-03: A document contains no usable text after whitespace cleaning.
- EC-04: A TXT file is actually binary or a DOCX/PDF renamed as `.txt`.
- EC-05: A document filename or chunk metadata is missing or duplicated.
- EC-06: Retrieval returns chunks below an acceptable relevance threshold.
- EC-07: The answer is split across multiple distant chunks or files.
- EC-08: The question asks for information in a prior conversation or outside uploaded documents.
- EC-09: The chat model repeats an unsupported detail or fabricates a source reference.
- EC-10: The model returns incomplete, escaped, duplicate, or malformed JSON.
- EC-11: A test-case response lacks one required field or contains an invalid type.
- EC-12: The source contains no boundaries or numeric limits.
- EC-13: The source contains contradictory statements or duplicate requirements.
- EC-14: Ollama embedding or chat model names are unavailable.
- EC-15: Ollama times out or becomes unavailable during embedding, chat, or re-index.
- EC-16: ChromaDB data is locked, missing, or incompatible with the application version.
- EC-17: A file is changed while re-indexing is in progress.
- EC-18: Very large TXT files produce many chunks or exceed request/resource limits.
- EC-19: Docker cannot reach Ollama due to host/container networking differences.
- EC-20: Ollama model downloads or startup exceed CI timeouts.
- EC-21: `/health` is called before the collection or Ollama service is ready.
- EC-22: The host port, volume path, or environment variable is already in use.
- EC-23: JSON export contains special characters, line breaks, or HTML-like text.
- EC-24: CI runs on a runner without GPU acceleration or sufficient model storage.
- EC-25: A source filename contains spaces or characters requiring safe UI escaping.

## Assumptions & Open Questions

### Assumptions

- `docs/` is the authoritative local knowledge base for the requested MVP.
- Plain UTF-8 `.txt` files are the supported document format; the current DOCX-renamed file should be converted or real format detection should be implemented before reliable grounding.
- Ollama is installed natively or supplied by Docker Compose, with `llama3.2` and `nomic-embed-text` available or configurable.
- ChromaDB persists locally and is not expected to provide user accounts or multi-tenancy in the MVP.
- `/health` is an application readiness signal, not a security or enterprise audit endpoint.
- The test-case JSON export is a local artifact and does not require direct integration with AIO Tests, Jira, or another test-management system.

### Open Questions

1. **Source format:** Should Stage 2 add support for PDF/DOCX ingestion, or should only true UTF-8 TXT files be accepted and misnamed DOCX files be explicitly rejected?
2. **Citation granularity:** Is filename plus chunk number sufficient, or must future output include character offsets or a retrievable excerpt link?
3. **Relevance threshold:** Should retrieval use a minimum similarity/distance threshold for no-answer decisions, or should all top-K chunks remain context until the model decides?
4. **Health semantics:** Should `/health` return HTTP 503 when Ollama or required models are unavailable, or does it need to report a degraded status while the web process remains usable?
5. **Container Ollama:** Should Docker Compose manage Ollama and model downloads, or require a separately running Ollama instance with configurable `OLLAMA_BASE_URL`?
6. **Models and hardware:** Is `llama3.2` plus `nomic-embed-text` mandatory, or may approved environment defaults replace them?
7. **Test-case quantity:** Is there a maximum or desired count for generated test cases, or should quantity remain context/model-driven?
8. **Boundary generation:** Should explicit boundary values come only from documents, or may common boundary conventions be inferred when a numeric range is stated?
9. **CI model availability:** Will GitHub Actions have a fixed Ollama model image/cache strategy, or should smoke tests mock only the Ollama HTTP contract?
10. **Authentication:** Is the MVP intended for a trusted local network without authentication, or will user/API authentication be required later?
