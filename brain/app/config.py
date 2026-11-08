"""Environment settings shared by brain modules (module modes live in registry.py)."""
from __future__ import annotations

import os
from pathlib import Path

BRAIN_DIR = Path(__file__).resolve().parents[1]


def sqlite_path() -> str:
    return os.environ.get("SQLITE_PATH") or str(BRAIN_DIR / "house.db")


def gateway_url() -> str:
    return os.environ.get("GATEWAY_URL", "http://localhost:8787")


def nessie_api_key() -> str:
    return (os.environ.get("NESSIE_API_KEY") or "").strip()


def nessie_base_url() -> str:
    # Prefer HTTPS; plain HTTP to api.nessieisreal.com often refuses connections.
    raw = (os.environ.get("NESSIE_BASE_URL") or "https://api.nessieisreal.com").rstrip("/")
    if raw.startswith("http://api.nessieisreal.com"):
        raw = "https://" + raw[len("http://"):]
    return raw


# Dashboard (Next.js) and Expo web dev servers. Expo Go's native fetch ignores CORS.
DEV_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000",
               "http://localhost:8081", "http://localhost:19006")


def cors_origins() -> list[str]:
    """Dev origins plus comma-separated CORS_ORIGINS and the Expo EXPO_TUNNEL_URL."""
    extra = os.environ.get("CORS_ORIGINS", "").split(",") + [os.environ.get("EXPO_TUNNEL_URL", "")]
    origins = list(DEV_ORIGINS)
    for o in (x.strip().rstrip("/") for x in extra):
        if o and o not in origins:
            origins.append(o)
    return origins
