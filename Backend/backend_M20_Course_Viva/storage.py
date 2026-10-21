"""Files on disk, stored once by content hash.

The same lab manual added to five campuses' folders is one file (EC-20.4). A
path never comes from the uploader's filename, so no name can escape the
storage directory.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from . import config


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _suffix(filename: str) -> str:
    match = re.search(r"\.([A-Za-z0-9]{1,8})$", filename or "")
    return f".{match.group(1).casefold()}" if match else ""


def path_for(digest: str, filename: str, root: Path | None = None) -> Path:
    root = root or config.STORAGE_DIR
    return root / digest[:2] / f"{digest}{_suffix(filename)}"


def save(data: bytes, filename: str, root: Path | None = None) -> tuple[str, Path]:
    digest = sha256(data)
    path = path_for(digest, filename, root)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return digest, path
