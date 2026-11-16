"""Telegram integration using the Bot API."""

from __future__ import annotations

import httpx

from app.platforms.base import (
    Platform,
    PlatformError,
    PlatformNotConfigured,
    PostOutcome,
    http_error,
)


class TelegramPlatform(Platform):
    name = "Telegram"

    def __init__(self, bot_token: str | None, chat_id: str | None) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id

    async def publish(
        self, client: httpx.AsyncClient, message: str, cta_url: str
    ) -> PostOutcome:
        if not self.bot_token or not self.chat_id:
            raise PlatformNotConfigured(
                "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID"
            )

        response = await client.post(
            f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
            json={
                "chat_id": self.chat_id,
                "text": message,
                "disable_web_page_preview": False,
            },
        )

        try:
            data = response.json()
        except ValueError:
            data = {}

        if not response.is_success or not data.get("ok"):
            if not response.is_success:
                raise http_error(response)
            raise PlatformError(data.get("description") or "Telegram rejected the message")

        result = data.get("result") or {}
        message_id = result.get("message_id")
        username = (result.get("chat") or {}).get("username")

        # Numeric chat ids do not have a public t.me URL. A username makes the
        # channel/group publicly addressable.
        posted_url = (
            f"https://t.me/{username}/{message_id}"
            if username and message_id
            else None
        )
        return PostOutcome(posted_url=posted_url, public_access=bool(posted_url))
