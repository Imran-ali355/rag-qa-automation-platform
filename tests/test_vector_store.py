import tempfile
import unittest

from rag.config import Config
from rag.ingestion import Chunk
from rag.vector_store import VectorStore


class FakeCollection:
    def __init__(self, name, metadata):
        self.name = name
        self.metadata = metadata
        self.items = []
        self.fail_add = False

    def add(self, ids, documents, embeddings, metadatas):
        if self.fail_add:
            raise RuntimeError("simulated candidate failure")
        self.items = list(zip(ids, documents, embeddings, metadatas))

    def count(self):
        return len(self.items)


class FakeChroma:
    def __init__(self):
        self.collections = {}
        self.fail_next_add = False

    def create_collection(self, name, metadata, configuration=None):
        collection = FakeCollection(name, metadata)
        collection.fail_add = self.fail_next_add
        self.fail_next_add = False
        self.collections[name] = collection
        return collection

    def get_collection(self, name):
        return self.collections[name]

    def delete_collection(self, name):
        del self.collections[name]


class VectorStoreAtomicityTests(unittest.TestCase):
    def test_candidate_promotion_and_failure_preserve_active_index(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Config.from_env({"DB_DIR": directory})
            client = FakeChroma()
            store = VectorStore(config, client=client)
            chunk = Chunk("id-1", "text", "guide.txt", 1, "fingerprint")
            self.assertEqual(store.replace([chunk], [[0.1]], "first"), 1)
            active_name = store._active_name
            client.fail_next_add = True
            with self.assertRaises(Exception):
                store.replace([chunk], [[0.2]], "second")
            self.assertEqual(store._active_name, active_name)
            self.assertEqual(store.count(), 1)


class ChromaCompatibilityTests(unittest.TestCase):
    def test_pinned_chroma_collection_replace_uses_cosine_metric(self):
        try:
            import chromadb
        except ImportError:
            self.skipTest("ChromaDB 0.6.3 is required for this integration regression test.")

        self.assertEqual(chromadb.__version__, "0.6.3")
        with tempfile.TemporaryDirectory() as directory:
            config = Config.from_env({
                "DB_DIR": directory,
                "COLLECTION_NAME": "chroma_compat_test",
            })
            client = chromadb.PersistentClient(path=directory)
            store = VectorStore(config, client=client)
            chunks = [
                Chunk("aligned", "cosine-aligned", "aligned.txt", 1, "fp-aligned"),
                Chunk("near-euclidean", "euclidean-near", "near.txt", 1, "fp-near"),
            ]

            self.assertEqual(
                store.replace(chunks, [[10.0, 0.0], [0.8, 0.6]], "fingerprint"),
                2,
            )
            collection = client.get_collection(name=store._active_name)
            self.assertEqual(collection.metadata["distance_metric"], "cosine")
            self.assertEqual(collection.metadata["hnsw:space"], "cosine")

            results = store.query([1.0, 0.0], top_k=2)
            self.assertEqual(results[0]["text"], "cosine-aligned")
            self.assertAlmostEqual(results[0]["distance"], 0.0, places=5)


if __name__ == "__main__":
    unittest.main()
