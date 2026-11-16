"""Discord integration using channel webhooks."""

from __future__ import annotations

import httpx

from app.platforms.base import (
    Platform,
    PlatformNotConfigured,
    PostOutcome,
    http_error,
)


class DiscordPlatform(Platform):
    name = "Discord"

    def __init__(self, webhook_url: str | None) -> None:
        self.webhook_url = webhook_url

    async def publish(
        self, client: httpx.AsyncClient, message: str, cta_url: str
    ) -> PostOutcome:
        if not self.webhook_url:
            raise PlatformNotConfigured("Set DISCORD_WEBHOOK_URL")

        # wait=true makes Discord return the created message instead of 204.
        response = await client.post(
            self.webhook_url,
            params={"wait": "true"},
            json={"content": message},
        )
        if not response.is_success:
            raise http_error(response)

        try:
            data = response.json()
        except ValueError:
            data = {}

        guild_id = data.get("guild_id")
        channel_id = data.get("channel_id")
        message_id = data.get("id")
        posted_url = (
            f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"
            if guild_id and channel_id and message_id
            else None
        )

        # Discord channel content always requires authentication and membership.
        return PostOutcome(posted_url=posted_url, public_access=False)
