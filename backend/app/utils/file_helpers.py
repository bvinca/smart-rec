# upload / temp file helpers
import os
import uuid
import tempfile
from typing import Optional
from pathlib import Path

from fastapi import HTTPException, UploadFile

try:  # pure-python magic-byte sniffer; no libmagic dependency
    import filetype  # type: ignore
    _FILETYPE_AVAILABLE = True
except Exception:  # pragma: no cover - optional at import time
    filetype = None  # type: ignore
    _FILETYPE_AVAILABLE = False

import logging
logger = logging.getLogger(__name__)


# MIME types we accept by *content* (magic bytes). DOCX is an OOXML zip so
# different sniffers report different things - accept them all.
_PDF_MIMES = {"application/pdf"}
_DOCX_MIMES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/zip",  # DOCX = zip; some sniffers report this
    "application/msword",
    "application/x-ole-storage",  # legacy .doc (compound file binary)
}


async def read_upload_capped(file: UploadFile, max_bytes: int) -> bytes:
    # chunked read with a hard byte cap. raises 413 over the limit so we
    # don't buffer an unbounded body into memory (trivial DoS).
    chunks = []
    total = 0
    chunk_size = 1024 * 1024  # 1 MB
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds the {max_bytes // (1024 * 1024)} MB upload limit.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


class FileHelper:
    # manages temp files under self.base_dir (default: "uploads")

    def __init__(self, base_dir: str = "uploads"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def save_uploaded_file(
        self,
        file_content: bytes,
        filename: str,
        prefix: Optional[str] = None
    ) -> str:
        # write bytes to disk under a uuid name, return the path
        file_ext = Path(filename).suffix or '.pdf'
        file_id = str(uuid.uuid4())
        
        if prefix:
            saved_filename = f"{prefix}_{file_id}{file_ext}"
        else:
            saved_filename = f"{file_id}{file_ext}"
        
        file_path = os.path.join(self.base_dir, saved_filename)
        
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        return file_path
    
    def create_temp_file(self, content: bytes, suffix: str = ".tmp") -> str:
        # write to a NamedTemporaryFile under self.base_dir, return the path
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix,
            dir=self.base_dir
        )
        temp_file.write(content)
        temp_file.close()
        
        return temp_file.name
    
    def delete_file(self, file_path: str) -> bool:
        # True if removed, False if missing or error
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except Exception as e:
            logger.exception(f"Error deleting file {file_path}: {e}")
            return False
    
    def get_file_size(self, file_path: str) -> int:
        try:
            return os.path.getsize(file_path)
        except Exception:
            return 0
    
    def validate_file_type(self, filename: str, allowed_types: list = None) -> bool:
        # extension allow-list check (default: pdf/docx/doc/txt)
        if allowed_types is None:
            allowed_types = ['.pdf', '.docx', '.doc', '.txt']
        
        file_ext = Path(filename).suffix.lower()
        return file_ext in allowed_types

    def validate_file_content(self, file_content: bytes, filename: str) -> bool:
        # validate by content (magic bytes), not just the name. defends
        # against a renamed binary (malware.exe → cv.pdf).
        # pdf/docx/doc: matching signature required.
        # txt: no magic, so we require it's NOT a known binary AND decodes as text.
        ext = Path(filename or "").suffix.lower()
        if ext not in {".pdf", ".docx", ".doc", ".txt"}:
            return False

        if not file_content:
            return False

        if not _FILETYPE_AVAILABLE:
            # fail-safe: no sniffer means we can't prove content matches the
            # extension. reject binary formats; allow only decodable text.
            logger.warning(
                "filetype library unavailable; falling back to text-only content validation."
            )
            return ext == ".txt" and self._looks_like_text(file_content)

        kind = filetype.guess(file_content)

        if ext == ".txt":
            # text should not have a recognised binary signature
            if kind is not None:
                return False
            return self._looks_like_text(file_content)

        if kind is None:
            return False
        mime = kind.mime
        if ext == ".pdf":
            return mime in _PDF_MIMES
        # .docx / .doc
        return mime in _DOCX_MIMES

    @staticmethod
    def _looks_like_text(file_content: bytes) -> bool:
        # leading 4 KB decodes as UTF-8 or Latin-1
        sample = file_content[:4096]
        for encoding in ("utf-8", "latin-1"):
            try:
                sample.decode(encoding)
                return True
            except UnicodeDecodeError:
                continue
        return False

    def cleanup_old_files(self, max_age_days: int = 30) -> int:
        # garbage-collect uploads older than max_age_days. returns count.
        import time
        deleted_count = 0
        current_time = time.time()
        max_age_seconds = max_age_days * 24 * 60 * 60
        
        for filename in os.listdir(self.base_dir):
            file_path = os.path.join(self.base_dir, filename)
            try:
                file_age = current_time - os.path.getmtime(file_path)
                if file_age > max_age_seconds:
                    if self.delete_file(file_path):
                        deleted_count += 1
            except Exception as e:
                logger.exception(f"Error checking file {file_path}: {e}")
        
        return deleted_count

