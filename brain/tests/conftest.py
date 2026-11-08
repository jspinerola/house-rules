from __future__ import annotations

import pytest

from app import registry

ALL_STUB = {env: "stub" for env in registry.ENV.values()}
# M11: everything real except the external services.
ALL_REAL = {**{env: "real" for env in registry.ENV.values()},
            "NESSIE_MODE": "stub", "LLM_MODE": "stub", "OUTBOX_MODE": "stub"}


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    for env in registry.ENV.values():
        monkeypatch.delenv(env, raising=False)
    for rid in ("ALEX", "SAM", "JORDAN"):
        monkeypatch.delenv(f"{rid}_HANDLE", raising=False)
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "house.db"))
    registry.reset()
    yield
    registry.reset()


@pytest.fixture
def use(monkeypatch):
    """use(tools="real") flips one module; use(profile=ALL_REAL) applies a whole profile."""
    def _use(profile: dict[str, str] | None = None, **modules: str) -> None:
        for env, m in (profile or {}).items():
            monkeypatch.setenv(env, m)
        for name, m in modules.items():
            monkeypatch.setenv(registry.ENV[name], m)
        registry.reset()
    return _use


def impl_params(name: str, real: str = "real"):
    """Parametrize over stub and real; real is skipped until it exists."""
    return pytest.mark.parametrize("mode", [
        "stub",
        pytest.param(real, marks=pytest.mark.skipif(
            not registry.available(name, real), reason=f"{name} {real} not implemented yet")),
    ])
