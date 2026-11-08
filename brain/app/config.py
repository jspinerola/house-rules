"""Environment settings shared by brain modules (module modes live in registry.py)."""
from __future__ import annotations

import os
from pathlib import Path

BRAIN_DIR = Path(__file__).resolve().parents[1]


def sqlite_path() -> str:
    return os.environ.get("SQLITE_PATH") or str(BRAIN_DIR / "house.db")


def gateway_url() -> str:
    return os.environ.get("GATEWAY_URL", "http://localhost:8787")
