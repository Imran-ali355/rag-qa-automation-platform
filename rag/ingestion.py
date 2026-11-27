"""Safe direct-child TXT/DOCX ingestion and deterministic text chunking."""

from dataclasses import dataclass
import hashlib
import io
import re
import stat
import zipfile
from pathlib import Path

from docx import Document


MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_ZIP_MEMBERS = 2000
MAX_EXPANDED_BYTES = 100 * 1024 * 1024
MAX_MEMBER_BYTES = 40 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200
INVALID_REASONS = {
    "invalid_utf8", "binary_text", "malformed_docx", "docx_limits",
    "file_too_large", "unreadable",
}


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    source: str
    chunk_num: int
    content_fingerprint: str


@dataclass
class IngestionResult:
    chunks: list[Chunk]
    filenames: list[str]
    fingerprint: str
    invalid_files: list[dict]


class InvalidDocument(ValueError):
    def __init__(self, reason):
        self.reason = reason if reason in INVALID_REASONS else "unreadable"
        super().__init__(self.reason)


def _read_txt(data: bytes) -> str:
    if data.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08", b"%PDF-")) or b"\x00" in data:
        raise InvalidDocument("binary_text")
    try:
        text = data.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise InvalidDocument("invalid_utf8") from exc
    controls = sum(1 for char in text if ord(char) < 32 and char not in "\t\r\n\f")
    if text and controls / len(text) > 0.01:
        raise InvalidDocument("binary_text")
    return text


def _read_docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ZIP_MEMBERS:
                raise InvalidDocument("docx_limits")
            total = 0
            names = set()
            for info in infos:
                names.add(info.filename)
                total += info.file_size
                if (
                    info.flag_bits & 0x1
                    or info.file_size > MAX_MEMBER_BYTES
                    or total > MAX_EXPANDED_BYTES
                    or (info.compress_size == 0 and info.file_size > 0)
                    or (
                        info.compress_size > 0
                        and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO
                    )
                ):
                    raise InvalidDocument("docx_limits")
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise InvalidDocument("malformed_docx")
            if archive.testzip() is not None:
                raise InvalidDocument("malformed_docx")
        document = Document(io.BytesIO(data))
        parts = [paragraph.text for paragraph in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                parts.append(" ".join(cell.text for cell in row.cells))
        return "\n".join(parts)
    except InvalidDocument:
        raise
    except Exception as exc:
        raise InvalidDocument("malformed_docx") from exc


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def chunk_text(text: str, filename: str, content_fingerprint: str, chunk_size: int, overlap: int):
    clean = _normalize(text)
    if not clean:
        return []
    step = chunk_size - overlap
    result = []
    for start in range(0, len(clean), step):
        part = clean[start : start + chunk_size].strip()
        if part:
            number = len(result) + 1
            chunk_id = hashlib.sha256(
                f"{filename}\0{content_fingerprint}\0{number}".encode("utf-8")
            ).hexdigest()
            result.append(Chunk(chunk_id, part, filename, number, content_fingerprint))
    return result


def ingest_directory(directory, chunk_size=500, overlap=80) -> IngestionResult:
    root = Path(directory)
    chunks, filenames, invalid, fingerprints = [], [], [], []
    if not root.exists():
        return IngestionResult([], [], hashlib.sha256(b"").hexdigest(), [])
    entries = sorted(root.iterdir(), key=lambda path: path.name.casefold())
    supported = [path for path in entries if path.suffix.casefold() in {".txt", ".docx"}]
    folded_names = {}
    for path in supported:
        folded_names.setdefault(path.name.casefold(), []).append(path.name)
    duplicates = {name for names in folded_names.values() if len(names) > 1 for name in names}
    for path in supported:
        if path.name in duplicates:
            invalid.append({"filename": path.name, "reason": "duplicate_filename"})
            continue
        try:
            if path.is_symlink() or not stat.S_ISREG(path.lstat().st_mode):
                invalid.append({"filename": path.name, "reason": "unreadable"})
                continue
            data = path.read_bytes()
            if len(data) > MAX_FILE_BYTES:
                raise InvalidDocument("docx_limits" if path.suffix.casefold() == ".docx" else "file_too_large")
            text = _read_docx(data) if path.suffix.casefold() == ".docx" else _read_txt(data)
            content_hash = hashlib.sha256(data).hexdigest()
            fingerprints.append((path.name, content_hash))
            filenames.append(path.name)
            chunks.extend(chunk_text(text, path.name, content_hash, chunk_size, overlap))
        except InvalidDocument as exc:
            invalid.append({"filename": path.name, "reason": exc.reason})
        except (OSError, PermissionError):
            invalid.append({"filename": path.name, "reason": "unreadable"})
    hasher = hashlib.sha256()
    for filename, digest in sorted(fingerprints, key=lambda row: row[0].casefold()):
        hasher.update(filename.encode("utf-8") + b"\0" + digest.encode("ascii") + b"\n")
    return IngestionResult(chunks, filenames, hasher.hexdigest(), invalid)


def discover_supported_filenames(directory):
    root = Path(directory)
    if not root.exists():
        return []
    return sorted(
        path.name for path in root.iterdir()
        if not path.is_symlink() and path.is_file() and path.suffix.casefold() in {".txt", ".docx"}
    )
