"""DEV.to integration using the Forem articles API."""

from __future__ import annotations

import httpx

from app.platforms.base import (
    Platform,
    PlatformError,
    PlatformNotConfigured,
    PostOutcome,
    http_error,
)


def _article_title(message: str) -> str:
    first_line = message.strip().splitlines()[0]
    return first_line if len(first_line) <= 100 else f"{first_line[:97].rstrip()}..."


class DevToPlatform(Platform):
    name = "DEV.to"

    def __init__(self, api_key: str | None) -> None:
        self.api_key = api_key

    async def publish(
        self, client: httpx.AsyncClient, message: str, cta_url: str
    ) -> PostOutcome:
        if not self.api_key:
            raise PlatformNotConfigured("Set DEVTO_API_KEY")

        response = await client.post(
            "https://dev.to/api/articles",
            headers={
                "api-key": self.api_key,
                "Accept": "application/vnd.forem.api-v1+json",
            },
            json={
                "article": {
                    "title": _article_title(message),
                    "body_markdown": message,
                    "published": True,
                }
            },
        )
        if not response.is_success:
            raise http_error(response)

        posted_url = response.json().get("url")
        if not posted_url:
            raise PlatformError("DEV.to response did not include an article URL")

        return PostOutcome(posted_url=posted_url, public_access=True)
