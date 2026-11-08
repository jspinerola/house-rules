"""Shared message formatting."""
from __future__ import annotations


def money(x: float) -> str:
    """$2,400 for whole dollars, $133.33 otherwise."""
    return f"${x:,.0f}" if abs(x - round(x)) < 0.005 else f"${x:,.2f}"
