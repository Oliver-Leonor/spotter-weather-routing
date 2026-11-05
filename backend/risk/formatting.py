"""Formatting measurements for people without contradicting their risk band."""

from __future__ import annotations

from collections.abc import Callable

from .levels import RiskLevel

MAX_DECIMALS = 6


def format_measurement(value: float, decimals: int, classify: Callable[[float], RiskLevel]) -> str:
    """Format `value` with at least `decimals` places, adding places while the rounded number
    would fall in a different risk band than the value itself.

    1.000394 in/h of rain is No Travel (above 1.00). Shown as "1.00" it would read as allowed, so
    it is shown as "1.0004". Likewise 54.9913 mph is shown as "54.99", not "55.0".
    """
    band = classify(value)
    for places in range(decimals, MAX_DECIMALS + 1):
        if classify(round(value, places)) is band:
            break
    return f"{value:.{places}f}"
