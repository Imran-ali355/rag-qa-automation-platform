import tempfile
import unittest

from app import create_app
from rag.config import Config
from rag.rag_service import RAGService
from rag.schemas import APIError


class StubService:
    def ask(self, question, mode):
        return {"mode": mode, "answer": question, "sources": [], "chunks_used": 0}

    def reindex(self):
        raise APIError("ollama_unavailable", "Unavailable.", 503)


class StubStore:
    def __init__(self, state=("empty", 0)):
        self.state = state

    def status(self):
        return self.state


class EmptyStore:
    def count(self):
        return 0

    def query(self, _embedding, _top_k):
        return []


class StubOllama:
    def __init__(self, available=True):
        self.available = available

    def is_available(self):
        return self.available


class APITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        config = Config.from_env({"DOCS_DIR": self.temp.name, "MAX_REQUEST_BYTES": "256"})
        self.app = create_app(
            config,
            service=StubService(),
            store=StubStore(),
            ollama=StubOllama(),
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def test_health_is_http_200_and_reports_ready_or_degraded(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["status"], "ok")
        self.app.extensions["rag_ollama"].available = False
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["status"], "degraded")

    def test_ask_validates_content_json_question_and_mode(self):
        response = self.client.post("/ask", json={"question": "hello"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["mode"], "qa")
        self.assertEqual(self.client.post("/ask", json={"question": "  "}).status_code, 400)
        self.assertEqual(self.client.post("/ask", json={"question": "x", "mode": "bad"}).status_code, 400)
        self.assertEqual(
            self.client.post("/ask", data="{", content_type="application/json").status_code,
            400,
        )
        self.assertEqual(self.client.post("/ask", data="{}", content_type="text/plain").status_code, 400)

    def test_reindex_error_is_json_and_non_success(self):
        response = self.client.post("/reindex")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["error"]["code"], "ollama_unavailable")

    def test_request_body_limit(self):
        response = self.client.post(
            "/ask",
            data='{"question":"' + ("x" * 300) + '"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 413)

    def test_ask_with_no_indexed_documents_returns_no_answer(self):
        config = self.app.extensions["rag_config"]
        store = EmptyStore()
        ollama = StubOllama()
        app = create_app(
            config,
            service=RAGService(config, store, ollama),
            store=store,
            ollama=ollama,
        )

        response = app.test_client().post("/ask", json={"question": "What is documented?"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json["answer"],
            "This information is not available in the indexed documents.",
        )
        self.assertEqual(response.json["sources"], [])
        self.assertEqual(response.json["chunks_used"], 0)


if __name__ == "__main__":
    unittest.main()
