"""Where M20 keeps things. Every path and port can be overridden from the
environment; nothing here is a secret."""

import os
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent

#: PORTS.txt: M20 is API 8120, web 5220.
PORT = int(os.getenv("BACKEND_PORT", "8120"))
DATABASE_URL = os.getenv("M20_DATABASE_URL", f"sqlite:///{(BACKEND / 'dev.db').as_posix()}")
#: Uploaded files, stored once by content hash.
STORAGE_DIR = Path(os.getenv("M20_STORAGE_DIR", str(BACKEND / "storage")))
#: The catalogue the sync job writes (packages/catalogue/amrita.json).
CATALOGUE_FILE = Path(
    os.getenv("M20_CATALOGUE", str(ROOT / "packages" / "catalogue" / "amrita.json"))
)
#: Largest file one upload may carry.
MAX_UPLOAD_BYTES = int(os.getenv("M20_MAX_UPLOAD_MB", "50")) * 1024 * 1024
MODULE_JSON = ROOT / "module.json"
