"""Shared platform contract and error types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class PostOutcome:
    """The useful result of a successful publish operation."""

    posted_url: str | None
    public_access: bool


class PlatformError(Exception):
    """A platform rejected the post or could not be reached."""


class PlatformNotConfigured(PlatformError):
    """Required credentials for a platform are missing."""


class Platform(ABC):
    name: str

    @abstractmethod
    async def publish(
        self, client: httpx.AsyncClient, message: str, cta_url: str
    ) -> PostOutcome:
        """Publish a message and return its URL and public-access state."""


def http_error(response: httpx.Response) -> PlatformError:
    """Build a concise, safe error from an unsuccessful API response."""

    detail = ""
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        for key in ("error", "message", "description", "detail"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                detail = value
                break
            if isinstance(value, dict):
                nested = value.get("message")
                if isinstance(nested, str) and nested.strip():
                    detail = nested
                    break

    if not detail:
        detail = response.text

    detail = " ".join(detail.split())[:300]
    suffix = f": {detail}" if detail else ""
    return PlatformError(f"HTTP {response.status_code}{suffix}")
