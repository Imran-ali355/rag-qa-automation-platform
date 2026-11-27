"""Persistent Chroma adapter with candidate collections and atomic active-pointer promotion."""

import json
import os
import threading
import uuid
from pathlib import Path


class VectorStoreError(RuntimeError):
    pass


class SnapshotChangedError(VectorStoreError):
    pass


class VectorStore:
    def __init__(self, config, client=None):
        self.config = config
        self._client = client
        self._active_collection = None
        self._active_name = None
        self._lock = threading.RLock()
        self._pointer_path = Path(config.db_dir) / f".{config.collection_name}.active"

    def _get_client(self):
        if self._client is None:
            try:
                import chromadb
                Path(self.config.db_dir).mkdir(parents=True, exist_ok=True)
                self._client = chromadb.PersistentClient(path=str(self.config.db_dir))
            except Exception as exc:
                raise VectorStoreError("Vector database is unavailable.") from exc
        return self._client

    def _load_active(self):
        if self._active_collection is not None:
            return self._active_collection
        if self._active_name is None and self._pointer_path.exists():
            try:
                state = json.loads(self._pointer_path.read_text(encoding="utf-8"))
                self._active_name = state["collection"]
            except (OSError, ValueError, KeyError, TypeError) as exc:
                raise VectorStoreError("Index state is unreadable.") from exc
        if self._active_name is None:
            return None
        try:
            collection = self._get_client().get_collection(name=self._active_name)
            metadata = collection.metadata or {}
            if (
                metadata.get("embedding_model") != self.config.embed_model
                or metadata.get("distance_metric") != "cosine"
                or metadata.get("schema_version") != 1
            ):
                raise VectorStoreError("Index configuration mismatch; re-index is required.")
            self._active_collection = collection
            return collection
        except VectorStoreError:
            raise
        except Exception as exc:
            raise VectorStoreError("Active index is unavailable.") from exc

    def status(self):
        with self._lock:
            try:
                collection = self._load_active()
                return ("ready", collection.count()) if collection is not None else ("empty", 0)
            except Exception:
                return "unavailable", 0

    def count(self):
        with self._lock:
            collection = self._load_active()
            return collection.count() if collection is not None else 0

    def query(self, embedding, top_k):
        with self._lock:
            collection = self._load_active()
            if collection is None or collection.count() == 0:
                return []
            result = collection.query(
                query_embeddings=[embedding],
                n_results=min(top_k, collection.count()),
                include=["documents", "metadatas", "distances"],
            )
            docs = (result.get("documents") or [[]])[0]
            metadatas = (result.get("metadatas") or [[]])[0]
            distances = (result.get("distances") or [[]])[0]
            found = []
            for text, metadata, distance in zip(docs, metadatas, distances):
                try:
                    distance = float(distance)
                    source = metadata["source"]
                    chunk_num = int(metadata["chunk_num"])
                except (TypeError, ValueError, KeyError):
                    continue
                if isinstance(text, str) and source and chunk_num > 0:
                    found.append({
                        "text": text,
                        "source": source,
                        "chunk_num": chunk_num,
                        "distance": distance,
                    })
            return found

    def replace(self, chunks, embeddings, fingerprint, snapshot_is_current=None):
        if len(chunks) != len(embeddings):
            raise VectorStoreError("Embedding count does not match document chunks.")
        with self._lock:
            client = self._get_client()
            candidate_name = f"{self.config.collection_name[:45]}_{uuid.uuid4().hex[:12]}"
            old_name = self._active_name
            if old_name is None and self._pointer_path.exists():
                try:
                    old_name = json.loads(
                        self._pointer_path.read_text(encoding="utf-8")
                    ).get("collection")
                except (OSError, ValueError, TypeError):
                    old_name = None
            candidate = None
            try:
                candidate = client.create_collection(
                    name=candidate_name,
                    metadata={
                        "schema_version": 1,
                        "docs_fingerprint": fingerprint,
                        "embedding_model": self.config.embed_model,
                        "distance_metric": "cosine",
                        "hnsw:space": "cosine",
                    },
                )
                if chunks:
                    candidate.add(
                        ids=[chunk.id for chunk in chunks],
                        documents=[chunk.text for chunk in chunks],
                        embeddings=embeddings,
                        metadatas=[{
                            "source": chunk.source,
                            "chunk_num": chunk.chunk_num,
                            "content_fingerprint": chunk.content_fingerprint,
                            "embedding_model": self.config.embed_model,
                        } for chunk in chunks],
                    )
                candidate_count = candidate.count()
                if snapshot_is_current is not None and not snapshot_is_current():
                    raise SnapshotChangedError("Documents changed during indexing.")
                state = json.dumps({"collection": candidate_name}, separators=(",", ":"))
                self._pointer_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path = self._pointer_path.with_name(self._pointer_path.name + f".{uuid.uuid4().hex}.tmp")
                try:
                    with open(tmp_path, "w", encoding="utf-8") as handle:
                        handle.write(state)
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(tmp_path, self._pointer_path)
                finally:
                    if tmp_path.exists():
                        tmp_path.unlink()
                self._active_name = candidate_name
                self._active_collection = candidate
                if old_name and old_name != candidate_name:
                    try:
                        client.delete_collection(name=old_name)
                    except Exception:
                        pass
                return candidate_count
            except Exception as exc:
                if candidate is not None and candidate_name != self._active_name:
                    try:
                        client.delete_collection(name=candidate_name)
                    except Exception:
                        pass
                if isinstance(exc, VectorStoreError):
                    raise
                raise VectorStoreError("Index replacement failed; the prior index was retained.") from exc
