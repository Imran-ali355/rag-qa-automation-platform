"""Bounded HTTP client for the local Ollama API."""

import time

import requests


class OllamaUnavailable(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, config, session=None):
        self.config = config
        self.session = session or requests.Session()

    def _post(self, endpoint, payload, read_timeout=None):
        url = f"{self.config.ollama_base_url}{endpoint}"
        timeout = (self.config.ollama_connect_timeout, read_timeout or self.config.ollama_read_timeout)
        for attempt in range(3):
            try:
                response = self.session.post(url, json=payload, timeout=timeout)
                response.raise_for_status()
                return response.json()
            except (requests.ConnectionError, requests.Timeout) as exc:
                if attempt < 2:
                    time.sleep(0.1 * (2 ** attempt))
                    continue
                raise OllamaUnavailable("Ollama request did not complete.") from exc
            except (requests.RequestException, ValueError) as exc:
                raise OllamaUnavailable("Ollama returned an invalid response.") from exc

    def embed(self, texts):
        if not texts:
            return []
        result = []
        for offset in range(0, len(texts), 32):
            batch = texts[offset : offset + 32]
            data = self._post(
                "/api/embed",
                {"model": self.config.embed_model, "input": batch},
                self.config.ollama_embed_timeout,
            )
            embeddings = data.get("embeddings") if isinstance(data, dict) else None
            if (
                not isinstance(embeddings, list)
                or len(embeddings) != len(batch)
                or any(not isinstance(vector, list) or not vector for vector in embeddings)
            ):
                raise OllamaUnavailable("Ollama returned invalid embeddings.")
            result.extend(embeddings)
        return result

    def chat(self, prompt, json_mode=False):
        payload = {
            "model": self.config.chat_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.1},
        }
        if json_mode:
            payload["format"] = "json"
        data = self._post("/api/chat", payload, self.config.ollama_read_timeout)
        try:
            content = data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise OllamaUnavailable("Ollama returned an invalid chat response.") from exc
        if not isinstance(content, str):
            raise OllamaUnavailable("Ollama returned an invalid chat response.")
        return content.strip()

    def is_available(self):
        try:
            response = self.session.get(
                f"{self.config.ollama_base_url}/api/tags",
                timeout=(self.config.ollama_connect_timeout, min(2.0, self.config.ollama_read_timeout)),
            )
            response.raise_for_status()
            return True
        except requests.RequestException:
            return False
