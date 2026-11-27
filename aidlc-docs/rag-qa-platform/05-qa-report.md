# Stage 5 — QA Report

**Work item:** `rag-qa-platform` (`rag-web`)  
**Review scope:** Approved requirements, architecture, test plan, development summary, implementation, and test suite.  
**Workspace note:** The supplied workspace is not a Git repository. No repository was initialized.

## Test Execution Summary (Passed / Failed / Skipped)

| Result | Count |
|---|---:|
| Passed | 21 |
| Failed | 0 |
| Skipped by a test runner | 0 |
| Total | 21 |

The full automated suite was run in the existing application Docker image with the workspace tests mounted read-only:

```text
docker run --rm --workdir /app --mount type=bind,source=<workspace>\tests,target=/tests,readonly rag-web-rag-web python -m unittest discover -s /tests -v
```

The first run exposed a conflict between the approved requirements and architecture for an empty index. The user clarified that HTTP 200 with the prescribed no-answer payload is authoritative. The regression test was updated to assert that contract, and the complete rerun passed all 21 tests. No test cases were skipped.

Additional observed verification:

- `docker compose config -q` — passed.
- `docker compose build rag-web` — passed.
- A temporary container with an unreachable local Ollama URL returned HTTP 200 from `/health` with `status: "degraded"` and `ollama: "unavailable"`; Docker's configured health check reached `healthy`. The temporary container was removed.
- No Ollama model download, live inference request, or external inference service was used.

## Automated Tests Added / Updated

- Added `test_ask_with_no_indexed_documents_returns_no_answer` to `tests/test_api.py`. It exercises the real `RAGService` through Flask with an empty store and asserts HTTP 200, the prescribed fallback answer, empty sources, and zero chunks.
- The test initially failed against the Stage 1 AC-01 expectation of HTTP 400. After the user's clarification that HTTP 200/no-answer governs, the test was updated and passed on rerun.
- No production code, CI workflow, or deployment configuration was changed.

## Contract Clarification

The approved Stage 1 AC-01 says an empty index returns HTTP 400. The approved Stage 2 API contract says no evidence (including an empty corpus) returns HTTP 200 with the prescribed no-answer body, while another line in Stage 2 recommends HTTP 400 for no valid indexed documents. The user clarified during Stage 5 that **HTTP 200 with no-answer is authoritative**. Current behavior and the updated regression test match that decision. The Stage 1 AC-01 and contradictory Stage 2 recommendation remain stale documentation; reconcile them in the appropriate requirements/design update. No production code was changed.

Other material coverage/verification issues:

- The unit/API suite passes in Docker, but integration coverage remains incomplete.
- No CI workflow or Ollama contract-mock Compose setup is present in the Stage 4 file summary. CI plan cases are therefore not evidenced here and remain Stage 6 work.
- Docker image build and a single-container health smoke test were exercised. Chroma/Ollama persistence across restarts, the full Compose stack, mounted-document behavior, and external Ollama overrides were not exercised.
- Real Ollama answer quality, unsupported/mixed-fact behavior, and model-backed boundary-case quality were not tested. They must not be inferred from schema/citation checks.
- UI behavior was reviewed statically only; no browser/E2E execution verified escaping, loading/error states, or JSON export.

## Requirement & Test Coverage Status

Coverage below combines the executed unit/API run with source inspection; cases described as partial or not executed do not have complete passing runtime evidence.

### P0/P1 functional and API test-plan cases

| Plan cases | Static coverage assessment |
|---|---|
| `ING-001`–`ING-016` | **Partial.** Existing tests cover UTF-8 BOM, invalid UTF-8/binary and misnamed files, malformed DOCX, valid DOCX paragraph/table extraction, unsupported extensions, chunk numbering, and configuration defaults. No automated evidence covers candidate refresh/fingerprint stability, duplicate-basename behavior, symlink containment, empty inputs, or re-index through the API. |
| `RET-001`–`RET-005`, `BVA-001` | **Partial.** Existing service tests cover an inclusive distance of `1.0` and an over-threshold result that avoids chat. `0.999`, custom thresholds, the exact neighboring boundary set, and broader top-K behavior are not covered. |
| `QA-001`–`QA-012` | **Partial.** Request validation, malformed JSON/content type, request-size rejection, one valid citation, forged citation, and an above-threshold no-answer path have test code. Multi-source answers, unsupported/mixed claims, missing citations, prompt injection, conflicting evidence, and UI escaping are not tested end-to-end. |
| `TC-001`–`TC-014`, `BVA-005`–`BVA-006` | **Partial.** A valid schema/reference, a boundary case without a documented rule, and an invalid type have test code. The complete response contract, sequential/duplicate/gapped IDs, 7/8/9 count boundary, forged references, malformed model JSON, extra keys, and supported boundary values are not covered. |
| `HEALTH-001`–`HEALTH-006` | **Partial.** A test checks HTTP 200 and available/degraded state. Chroma-unavailable behavior, expected health fields/counts, empty corpus semantics, override reporting, and boundedness are not comprehensively tested. |
| `IDX-001`–`IDX-010` | **Partial.** A fake-store test covers candidate-write failure preserving the active index; a lock test checks the overlap/409 policy. Re-index API success and failure, invalid-file diagnostics, live snapshot changes, actual Chroma atomicity, storage failures, and retrieval error mapping remain unverified. |
| `UI-001`–`UI-005` | **Not automated/executed.** Template source contains rendering and export logic, but no browser test verifies the planned behaviors. |
| `OPS-001`–`OPS-012` | **Partial.** Image build and a standalone container health-check smoke test passed. Full Compose startup, volume persistence, docs mounts, external Ollama override, and model-volume lifecycle were not executed. |
| `CI-001`–`CI-008` | **Not implemented/verified in this scope.** The Stage 4 summary explicitly defers CI/Stage 6. |
| `BVA-002`–`BVA-004`, `BVA-007`–`BVA-018` | **Mostly uncovered.** Existing code/tests include some numeric config validation and deterministic chunk numbering. Most exact limits, file/archive resource boundaries, question/body limits at exact boundary, model/metric mismatch, timeouts, startup delay, and fingerprint-only change cases lack executed evidence. |
| `CFG-001`–`CFG-004`, `SEC-001`–`SEC-003` | **Partial/static only.** Defaults and a small set of configuration errors have test code; traversal, URL locality, secret-safe errors, and browser security behavior were not exercised. |

### Requirement/design review

- **FR-01 ingestion/indexing:** Several ingestion safety properties have unit-test source coverage. Full re-index, persistent Chroma, fingerprint refresh, and directory-boundary behavior remain unverified.
- **FR-02/FR-03 grounded Q&A/citations:** Threshold, no-evidence, and citation-identity paths have partial unit-test coverage. Claim entailment is not proven by citation validation; unsupported/mixed claims and multiple-source behavior remain gaps.
- **FR-04 test-case generator:** Basic schema validation is present; important count/ID/reference/malformed-output boundaries and UI export are not covered comprehensively.
- **FR-05 health/re-index:** Basic health and error route tests exist, and empty-index behavior matches the user's selected HTTP 200/no-answer contract. Stage 1 AC-01 and one Stage 2 recommendation remain stale; actual re-index and operational failure behavior are unverified.
- **FR-06 containerization:** Compose validation and image build passed, as did a standalone container health-check smoke test. Full Compose lifecycle and persistence remain unverified.
- **FR-07 CI:** Deferred per Stage 4 scope and not verified in Stage 5.

## Go / No-Go Recommendation

**NO-GO for release readiness.** The complete unit/API suite passes (21/21), Compose configuration and image build pass, and the standalone container health smoke test passes. However, several P0/P1 integration scenarios remain unverified: actual Chroma re-indexing and restart persistence, full Compose startup/volume lifecycle, browser JSON export and escaping, and CI mock-stack smoke behavior (CI is deferred to Stage 6). Reconcile the stale empty-index requirement/design text. Complete the remaining applicable P0 validation and obtain human Go/No-Go approval before release; Stage 6 remains subject to its own approval gate.
