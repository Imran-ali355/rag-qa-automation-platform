"""Small deterministic Ollama HTTP contract stub for isolated CI Compose runs."""

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


HOST = "0.0.0.0"
PORT = 11434
VECTOR_SIZE = 32
REFERENCE_PATTERN = re.compile(r"^\[([^\]\r\n]+ \(Chunk #\d+\))\]\s*$", re.MULTILINE)


def _vector(_text):
    # A fixed, non-zero vector is deterministic and keeps this contract stub
    # independent of model packages, network services, and fixture contents.
    return [1.0] + [0.0] * (VECTOR_SIZE - 1)


class OllamaStubHandler(BaseHTTPRequestHandler):
    server_version = "OllamaContractStub/1.0"

    def log_message(self, _format, *_args):
        # Do not log prompts, document contents, or request bodies.
        return

    def _send_json(self, status, payload):
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 1024 * 1024:
                return None
            return json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            return None

    def do_GET(self):
        if self.path != "/api/tags":
            self._send_json(404, {"error": "not found"})
            return
        self._send_json(200, {
            "models": [{
                "name": "llama3.2:latest",
                "model": "llama3.2:latest",
                "modified_at": "2026-01-01T00:00:00Z",
                "size": 0,
                "digest": "ci-contract-stub",
                "details": {},
            }]
        })

    def do_POST(self):
        payload = self._read_json()
        if not isinstance(payload, dict):
            self._send_json(400, {"error": "invalid JSON request"})
            return

        if self.path == "/api/embed":
            inputs = payload.get("input")
            if isinstance(inputs, str):
                inputs = [inputs]
            if not isinstance(inputs, list) or not all(isinstance(item, str) for item in inputs):
                self._send_json(400, {"error": "input must be a string or list of strings"})
                return
            self._send_json(200, {
                "model": str(payload.get("model", "nomic-embed-text")),
                "embeddings": [_vector(item) for item in inputs],
            })
            return

        if self.path == "/api/chat":
            messages = payload.get("messages")
            if not isinstance(messages, list):
                self._send_json(400, {"error": "messages must be a list"})
                return
            prompt = "\n".join(
                item.get("content", "")
                for item in messages
                if isinstance(item, dict) and isinstance(item.get("content"), str)
            )
            references = REFERENCE_PATTERN.findall(prompt)
            if not references:
                self._send_json(422, {"error": "no evidence reference in prompt"})
                return
            reference = references[0]
            if payload.get("format") == "json":
                content = json.dumps({
                    "test_cases": [{
                        "id": "TC-001",
                        "title": "Verify the documented CI smoke fixture",
                        "type": "Positive",
                        "preconditions": "The CI fixture is indexed.",
                        "steps": ["Submit a question about the indexed fixture."],
                        "expected_result": "The response cites the indexed fixture.",
                        "source_ref": reference,
                    }]
                })
            else:
                content = (
                    "The indexed CI fixture provides deterministic smoke-test evidence. "
                    f"{reference}"
                )
            self._send_json(200, {
                "model": str(payload.get("model", "llama3.2")),
                "created_at": "2026-01-01T00:00:00Z",
                "message": {"role": "assistant", "content": content},
                "done": True,
                "done_reason": "stop",
                "total_duration": 1,
                "load_duration": 0,
                "prompt_eval_count": 1,
                "prompt_eval_duration": 1,
                "eval_count": 1,
                "eval_duration": 1,
            })
            return

        self._send_json(404, {"error": "not found"})


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), OllamaStubHandler).serve_forever()
