"""Timestamp formatting shared by the API payload builders."""

from __future__ import annotations

from datetime import UTC, datetime


def iso_utc(moment: datetime) -> str:
    """ISO 8601 in UTC with whole seconds and a `Z` suffix, as used throughout the API."""
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
