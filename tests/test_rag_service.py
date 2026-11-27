import json
import unittest
from tempfile import TemporaryDirectory

from rag.config import Config
from rag.rag_service import RAGService
from rag.schemas import APIError, NO_ANSWER, validate_test_cases


class FakeStore:
    def __init__(self, chunks):
        self.chunks = chunks
        self.query_calls = 0

    def count(self):
        return len(self.chunks)

    def query(self, _embedding, _top_k):
        self.query_calls += 1
        return self.chunks


class FakeOllama:
    def __init__(self, answer):
        self.answer = answer
        self.chat_calls = 0

    def embed(self, _texts):
        return [[0.1, 0.2]]

    def chat(self, _prompt, json_mode=False):
        self.chat_calls += 1
        return self.answer


class RAGServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.config = Config.from_env({
            "DOCS_DIR": self.temp.name,
            "DB_DIR": self.temp.name + "/db",
            "MAX_DISTANCE": "1.0",
        })
        self.evidence = {
            "text": "Password length is 8 to 20 characters.",
            "source": "guide.txt",
            "chunk_num": 1,
            "distance": 1.0,
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_inclusive_distance_threshold_and_valid_citation(self):
        ollama = FakeOllama("Password length is 8 to 20 characters. guide.txt (Chunk #1)")
        service = RAGService(self.config, FakeStore([self.evidence]), ollama)
        result = service.ask("What is the password length?", "qa")
        self.assertIn("guide.txt (Chunk #1)", result["answer"])
        self.assertEqual(result["chunks_used"], 1)

    def test_above_threshold_returns_fallback_without_chat(self):
        chunk = {**self.evidence, "distance": 1.0001}
        ollama = FakeOllama("must not be used")
        result = RAGService(self.config, FakeStore([chunk]), ollama).ask("Question", "qa")
        self.assertEqual(result["answer"], NO_ANSWER)
        self.assertEqual(ollama.chat_calls, 0)

    def test_forged_citation_falls_back(self):
        ollama = FakeOllama("A claim. other.txt (Chunk #7)")
        result = RAGService(self.config, FakeStore([self.evidence]), ollama).ask("Question", "qa")
        self.assertEqual(result["answer"], NO_ANSWER)
        self.assertEqual(result["sources"], [])

    def test_citation_cannot_be_forged_as_filename_suffix(self):
        ollama = FakeOllama("A claim. notguide.txt (Chunk #1)")
        result = RAGService(self.config, FakeStore([self.evidence]), ollama).ask("Question", "qa")
        self.assertEqual(result["answer"], NO_ANSWER)
        self.assertEqual(result["sources"], [])

    def test_test_case_schema_and_evidence_reference(self):
        case = {
            "id": "TC-001",
            "title": "Check password length",
            "type": "Boundary",
            "preconditions": "The login feature is available.",
            "steps": ["Enter a documented value."],
            "expected_result": "The documented behavior occurs.",
            "source_ref": "guide.txt (Chunk #1)",
        }
        ollama = FakeOllama(json.dumps({"test_cases": [case]}))
        result = RAGService(self.config, FakeStore([self.evidence]), ollama).ask("Generate", "test_cases")
        self.assertEqual(result["test_cases"], [case])

    def test_boundary_case_requires_a_documented_limit_or_rule(self):
        case = {
            "id": "TC-001",
            "title": "Check the boundary",
            "type": "Boundary",
            "preconditions": "The login feature is available.",
            "steps": ["Submit a value."],
            "expected_result": "The documented behavior occurs.",
            "source_ref": "guide.txt (Chunk #1)",
        }
        with self.assertRaises(ValueError):
            validate_test_cases(
                {"test_cases": [case]},
                {"guide.txt (Chunk #1)"},
                8,
                {"guide.txt (Chunk #1)": "Login is available."},
            )

    def test_reindex_rejects_concurrent_operation(self):
        service = RAGService(self.config, FakeStore([]), FakeOllama(""))
        self.assertTrue(service._reindex_lock.acquire(blocking=False))
        try:
            with self.assertRaises(APIError) as raised:
                service.reindex()
            self.assertEqual(raised.exception.status, 409)
            self.assertEqual(raised.exception.code, "reindex_in_progress")
        finally:
            service._reindex_lock.release()

    def test_invalid_test_case_is_rejected_without_partial_response(self):
        ollama = FakeOllama(json.dumps({"test_cases": [{
            "id": "TC-001", "title": "bad", "type": "Invented",
        }]}))
        service = RAGService(self.config, FakeStore([self.evidence]), ollama)
        with self.assertRaises(APIError) as raised:
            service.ask("Generate", "test_cases")
        self.assertEqual(raised.exception.status, 422)


if __name__ == "__main__":
    unittest.main()
