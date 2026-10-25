from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "jobs.sqlite"
RESUME_PATH = DATA_DIR / "resume.pdf"
SAMPLE_WATCHLIST = ROOT / "companies.example.toml"

USER_AGENT = (
    "PersonalJobBoard/0.1 (personal local research; "
    "+https://www.wikidata.org/wiki/Wikidata:Data_access)"
)


def load_env() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
