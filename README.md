# Local Ollama + ChromaDB RAG QA Platform

Local-first document Q&A and QA test-case generation using Flask, Ollama, and ChromaDB.

- **Repository:** [rag-qa-automation-platform](https://github.com/Imran-ali355/rag-qa-automation-platform.git)
- **Branch:** `main` (provided by the project owner)
- **Supported documents:** UTF-8 `.txt` and validated `.docx` files in `docs/`
- **Not supported:** PDF, OCR, recursive document discovery, authentication

## Requirements

- Docker Engine and Docker Compose
- Enough memory and disk space for Ollama and its models
- The model pull commands require network access to the configured Ollama model registry
- Documents you are authorized to index, placed directly in `docs/`

The Compose setup defaults to chat model `llama3.2`, embedding model `nomic-embed-text`, web port `5000`, and local persistent volumes for ChromaDB and Ollama models.

## Start locally with Docker Compose

Optionally create a local `.env` file for overrides:

```powershell
Copy-Item .env.example .env
```

Or on macOS/Linux:

```sh
cp .env.example .env
```

Start the application and Compose-managed Ollama service:

```sh
docker compose up --build -d
```

Pull both required models into the Compose-managed Ollama service:

```sh
docker compose exec ollama ollama pull llama3.2
docker compose exec ollama ollama pull nomic-embed-text
```

Before indexing, check that files in `docs/` use their actual format. The current repository includes `SRS_Highlighted_Review.txt`, which appears to be a DOCX file with a `.txt` extension. The loader correctly rejects binary/misnamed TXT files, so re-indexing will return an invalid-document error until you rename it to `.docx` if it is a valid Word document, convert it to UTF-8 plain text, or remove it from `docs/`.

Index or refresh the documents after the model pulls complete:

```sh
curl -X POST http://localhost:5000/reindex
```

PowerShell equivalent:

```powershell
Invoke-RestMethod -Uri http://localhost:5000/reindex -Method Post
```

Open the UI at [http://localhost:5000/](http://localhost:5000/). The health endpoint is [http://localhost:5000/health](http://localhost:5000/health).

`/health` returns HTTP 200 when the web process is responsive. Check its JSON `status`, `ollama`, and `index_status` fields: `status: "degraded"` means a dependency or index is unavailable.

## API examples

Ask a question grounded in indexed documents:

```sh
curl -X POST http://localhost:5000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What does the document say about login?","mode":"qa"}'
```

PowerShell:

```powershell
$body = '{"question":"What does the document say about login?","mode":"qa"}'
Invoke-RestMethod -Uri http://localhost:5000/ask -Method Post `
  -ContentType 'application/json' -Body $body
```

Generate structured QA cases by setting `"mode":"test_cases"`. Responses contain Positive, Negative, and/or Boundary cases supported by indexed evidence. The UI can export generated cases as JSON.

If no qualifying evidence is found, the API returns the prescribed no-answer response. Source references use `filename (Chunk #N)`.

## Run the test suite

With a compatible local Python installation:

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

The suite includes a real ChromaDB compatibility test. On Windows, installing `chroma-hnswlib` may require Microsoft C++ Build Tools. If local installation fails, run the tests using the built application image instead.

PowerShell:

```powershell
docker compose -p rag-qa-tests build rag-web
$testsPath = (Resolve-Path .\tests).Path
docker run --rm --workdir /app `
  --mount "type=bind,source=$testsPath,target=/tests,readonly" `
  rag-qa-tests-rag-web python -m unittest discover -s /tests -v
```

macOS/Linux:

```sh
docker compose -p rag-qa-tests build rag-web
docker run --rm --workdir /app \
  --mount "type=bind,source=$PWD/tests,target=/tests,readonly" \
  rag-qa-tests-rag-web python -m unittest discover -s /tests -v
```

## Native or externally managed Ollama

The default Compose URL is `http://ollama:11434`, which targets the Ollama service on the private Compose network. Pull models into that service with the commands above.

To use Ollama running on the host while the web app remains containerized, set `OLLAMA_BASE_URL` in `.env` to an address reachable from the container. Docker Desktop commonly provides:

```dotenv
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

On Linux, host-gateway routing may need additional Docker configuration. If the web app runs natively, its usual Ollama URL is `http://localhost:11434`.

The base Compose setup still starts its local Ollama service even when `OLLAMA_BASE_URL` points elsewhere. The configured endpoint receives prompts and retrieved document context; use only a trusted endpoint. Do not send sensitive documents to an unapproved external service.

## Data persistence and stopping services

Compose uses separate named volumes:

- `chroma_data` — indexed documents, vectors, and collection state
- `ollama_models` — downloaded Ollama models

Stop and restart without removing containers:

```sh
docker compose stop
docker compose start
```

Remove the project containers and network while preserving named volumes:

```sh
docker compose down
```

Do not use `docker compose down --volumes` for routine shutdown: it deletes both persistent volumes and requires re-indexing and model downloads.

## Local-use security notes

- The MVP has no authentication. Keep the web port on a trusted local machine/network; do not expose it directly to the public internet or an untrusted LAN.
- Review `.env` overrides locally. Never put credentials or secrets in `.env.example`, source code, or logs.
- Invalid supported files block re-indexing. Keep only intended, valid UTF-8 TXT or DOCX files in `docs/`.
- The deterministic Ollama stub used by CI validates API wiring and persistence, not real-model answer quality.
