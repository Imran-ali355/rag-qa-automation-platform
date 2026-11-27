import tempfile
import unittest
from pathlib import Path

from docx import Document

from rag.config import Config
from rag.ingestion import chunk_text, ingest_directory


class IngestionTests(unittest.TestCase):
    def test_strict_utf8_txt_and_one_based_chunks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "notes.txt"
            path.write_bytes(b"\xef\xbb\xbfAlpha  beta\ngamma")
            result = ingest_directory(directory, chunk_size=20, overlap=2)
            self.assertEqual(result.invalid_files, [])
            self.assertEqual(result.filenames, ["notes.txt"])
            self.assertEqual(result.chunks[0].text, "Alpha beta gamma")
            self.assertEqual(result.chunks[0].chunk_num, 1)

    def test_rejects_misnamed_docx_and_invalid_utf8(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docx_path = root / "binary.txt"
            docx_path.write_bytes(b"PK\x03\x04fake")
            (root / "bad.txt").write_bytes(b"\xff")
            result = ingest_directory(directory)
            self.assertEqual(
                {entry["reason"] for entry in result.invalid_files},
                {"binary_text", "invalid_utf8"},
            )
            self.assertEqual(result.chunks, [])

    def test_rejects_corrupt_docx_and_pdf_renamed_as_txt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "broken.docx").write_bytes(b"not a zip archive")
            (root / "report.txt").write_bytes(b"%PDF-1.7\nbinary")
            result = ingest_directory(directory)
            self.assertEqual(
                {entry["reason"] for entry in result.invalid_files},
                {"malformed_docx", "binary_text"},
            )

    def test_extracts_valid_docx_paragraph_and_table(self):
        with tempfile.TemporaryDirectory() as directory:
            document = Document()
            document.add_paragraph("Login is available.")
            table = document.add_table(rows=1, cols=1)
            table.cell(0, 0).text = "Password length: 8–20."
            document.save(Path(directory) / "guide.docx")
            result = ingest_directory(directory)
            combined = " ".join(chunk.text for chunk in result.chunks)
            self.assertIn("Login is available.", combined)
            self.assertIn("Password length: 8–20.", combined)

    def test_ignores_pdf_and_other_extensions(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "ignored.pdf").write_bytes(b"%PDF-1.7")
            (Path(directory) / "ignored.md").write_text("not indexed", encoding="utf-8")
            result = ingest_directory(directory)
            self.assertEqual(result.filenames, [])
            self.assertEqual(result.invalid_files, [])

    def test_config_defaults_and_numeric_validation(self):
        config = Config.from_env({})
        self.assertEqual(config.chat_model, "llama3.2")
        self.assertEqual(config.embed_model, "nomic-embed-text")
        self.assertEqual(config.max_cases, 8)
        self.assertEqual(config.max_distance, 1.0)
        with self.assertRaises(ValueError):
            Config.from_env({"MAX_DISTANCE": "NaN"})
        with self.assertRaises(ValueError):
            Config.from_env({"CHUNK_SIZE": "10", "CHUNK_OVERLAP": "10"})

    def test_chunking_has_stable_ids_and_numbering(self):
        chunks = chunk_text("abcdefghijk", "a.txt", "hash", 5, 1)
        self.assertEqual([item.chunk_num for item in chunks], [1, 2, 3])
        self.assertEqual(chunks, chunk_text("abcdefghijk", "a.txt", "hash", 5, 1))


if __name__ == "__main__":
    unittest.main()
