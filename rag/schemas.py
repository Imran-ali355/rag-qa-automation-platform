"""Small strict validators for public requests and model-produced test cases."""

import re
from dataclasses import dataclass


NO_ANSWER = "This information is not available in the indexed documents."
CASE_FIELDS = {
    "id", "title", "type", "preconditions", "steps", "expected_result", "source_ref"
}
CASE_TYPES = {"Positive", "Negative", "Boundary"}
CASE_ID = re.compile(r"TC-(\d{3})\Z")
BOUNDARY_RULE = re.compile(
    r"\b(?:"
    r"between\s+\d+(?:\.\d+)?\s+(?:and|to)\s+\d+(?:\.\d+)?"
    r"|\d+(?:\.\d+)?\s*(?:to|[-\u2013\u2014])\s*\d+(?:\.\d+)?"
    r"|(?:minimum|maximum|min|max|at least|at most|no more than|no less than|"
    r"greater than|less than|exactly|up to)\s+(?:of\s+)?\d+(?:\.\d+)?"
    r"|(?:must be empty|must not be empty|cannot be empty|only one|exactly one|"
    r"at least one|is required|is optional)"
    r")\b",
    re.IGNORECASE,
)


@dataclass
class APIError(Exception):
    code: str
    message: str
    status: int = 400
    details: list | None = None


def validate_request(data, max_question_chars: int):
    if not isinstance(data, dict):
        raise APIError("invalid_request", "A JSON object is required.", 400)
    question = data.get("question")
    if not isinstance(question, str) or not question.strip():
        raise APIError("invalid_question", "Question must be a non-empty string.", 400)
    question = question.strip()
    if len(question) > max_question_chars:
        raise APIError("question_too_large", "Question exceeds the configured length limit.", 413)
    mode = data.get("mode", "qa")
    if not isinstance(mode, str) or mode not in {"qa", "test_cases"}:
        raise APIError("invalid_mode", "Mode must be 'qa' or 'test_cases'.", 400)
    return question, mode


def validate_test_cases(payload, evidence_refs, max_cases: int, evidence_text=None):
    if not isinstance(payload, dict) or set(payload) != {"test_cases"}:
        raise ValueError("Model output must contain only a test_cases array.")
    evidence_text = evidence_text or {}
    cases = payload["test_cases"]
    if not isinstance(cases, list) or len(cases) > max_cases:
        raise ValueError("Model returned an invalid number of test cases.")
    validated = []
    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict) or set(case) != CASE_FIELDS:
            raise ValueError("A test case has missing or unexpected fields.")
        if case.get("id") != f"TC-{index:03d}" or not CASE_ID.fullmatch(case["id"]):
            raise ValueError("Test case IDs must be unique and sequential.")
        if case.get("type") not in CASE_TYPES:
            raise ValueError("Test case type is invalid.")
        for field in ("title", "preconditions", "expected_result", "source_ref"):
            if not isinstance(case.get(field), str) or not case[field].strip():
                raise ValueError(f"Test case field '{field}' must be a non-empty string.")
        if not isinstance(case.get("steps"), list) or not case["steps"]:
            raise ValueError("Test case steps must be a non-empty list.")
        if any(not isinstance(step, str) or not step.strip() for step in case["steps"]):
            raise ValueError("Test case steps must contain non-empty strings.")
        source_refs = case["source_ref"].split("; ")
        if any(not reference for reference in source_refs) or any(
            reference not in evidence_refs for reference in source_refs
        ):
            raise ValueError("Test case source_ref is not present in retrieved evidence.")
        if case["type"] == "Boundary" and not any(
            BOUNDARY_RULE.search(evidence_text.get(reference, ""))
            for reference in source_refs
        ):
            raise ValueError("Boundary cases require an explicit documented limit or rule.")
        validated.append(case)
    return validated
