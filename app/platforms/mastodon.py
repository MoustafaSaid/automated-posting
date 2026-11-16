"""Mastodon integration using the statuses API."""

from __future__ import annotations

import httpx

from app.platforms.base import (
    Platform,
    PlatformError,
    PlatformNotConfigured,
    PostOutcome,
    http_error,
)


class MastodonPlatform(Platform):
    name = "Mastodon"

    def __init__(self, base_url: str | None, access_token: str | None) -> None:
        self.base_url = base_url.rstrip("/") if base_url else None
        self.access_token = access_token

    async def publish(
        self, client: httpx.AsyncClient, message: str, cta_url: str
    ) -> PostOutcome:
        if not self.base_url or not self.access_token:
            raise PlatformNotConfigured(
                "Set MASTODON_BASE_URL and MASTODON_ACCESS_TOKEN"
            )

        response = await client.post(
            f"{self.base_url}/api/v1/statuses",
            headers={"Authorization": f"Bearer {self.access_token}"},
            json={"status": message, "visibility": "public"},
        )
        if not response.is_success:
            raise http_error(response)

        data = response.json()
        posted_url = data.get("url")
        if not posted_url:
            raise PlatformError("Mastodon response did not include a status URL")

        public_access = data.get("visibility", "public") in {"public", "unlisted"}
        return PostOutcome(posted_url=posted_url, public_access=public_access)
