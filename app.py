"""Flask routes for the local RAG application; imports do not index or contact services."""

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge

from rag.config import Config
from rag.ingestion import discover_supported_filenames
from rag.ollama_client import OllamaClient
from rag.rag_service import RAGService
from rag.schemas import APIError, validate_request
from rag.vector_store import VectorStore


def create_app(config=None, service=None, store=None, ollama=None):
    config = config or Config.from_env()
    store = store or VectorStore(config)
    ollama = ollama or OllamaClient(config)
    service = service or RAGService(config, store, ollama)

    application = Flask(__name__)
    application.config["MAX_CONTENT_LENGTH"] = config.max_request_bytes
    application.extensions["rag_config"] = config
    application.extensions["rag_store"] = store
    application.extensions["rag_ollama"] = ollama
    application.extensions["rag_service"] = service

    @application.errorhandler(APIError)
    def handle_api_error(error):
        body = {"error": {"code": error.code, "message": error.message}}
        if error.details is not None:
            body["error"]["files"] = error.details
        return jsonify(body), error.status

    @application.errorhandler(RequestEntityTooLarge)
    def handle_too_large(_error):
        return jsonify({"error": {
            "code": "request_too_large",
            "message": "Request body exceeds the configured size limit.",
        }}), 413

    @application.errorhandler(404)
    def handle_not_found(_error):
        return jsonify({"error": {"code": "not_found", "message": "Endpoint not found."}}), 404

    @application.errorhandler(500)
    def handle_internal_error(_error):
        return jsonify({"error": {
            "code": "internal_error",
            "message": "The request could not be completed.",
        }}), 500

    @application.route("/", methods=["GET"])
    def index():
        return render_template("index.html")

    @application.route("/health", methods=["GET"])
    def health():
        try:
            index_status, chunks_indexed = store.status()
        except Exception:
            index_status, chunks_indexed = "unavailable", 0
        try:
            ollama_available = bool(ollama.is_available())
        except Exception:
            ollama_available = False
        status = "ok" if ollama_available and index_status != "unavailable" else "degraded"
        try:
            files = discover_supported_filenames(config.docs_dir)
        except OSError:
            files = []
            status = "degraded"
        return jsonify({
            "status": status,
            "chat_model": config.chat_model,
            "embed_model": config.embed_model,
            "files_count": len(files),
            "files": files,
            "chunks_indexed": chunks_indexed,
            "ollama": "available" if ollama_available else "unavailable",
            "index_status": index_status,
        }), 200

    @application.route("/reindex", methods=["POST"])
    def reindex():
        result = service.reindex()
        return jsonify({"message": "Documents re-indexed successfully.", **result})

    @application.route("/ask", methods=["POST"])
    def ask():
        if not request.is_json:
            raise APIError("invalid_content_type", "Content-Type must be application/json.", 400)
        try:
            data = request.get_json()
        except (BadRequest, ValueError, TypeError):
            raise APIError("invalid_json", "Request body must contain valid JSON.", 400)
        question, mode = validate_request(data, config.max_question_chars)
        return jsonify(service.ask(question, mode)), 200

    return application


# WSGI import is deliberately side-effect free: adapters are constructed lazily,
# and no Chroma client, document indexing, or Ollama request is made here.
app = create_app()


if __name__ == "__main__":
    runtime_config = app.extensions["rag_config"]
    app.run(host="0.0.0.0", port=runtime_config.port, debug=False)
