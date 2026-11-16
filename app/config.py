"""Application configuration from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Load a local .env file when present. Existing environment variables win.
load_dotenv()


def _value(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


@dataclass(frozen=True)
class Settings:
    mastodon_base_url: str | None
    mastodon_access_token: str | None
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    discord_webhook_url: str | None
    bluesky_handle: str | None
    bluesky_app_password: str | None
    bluesky_pds_url: str
    devto_api_key: str | None


def get_settings() -> Settings:
    return Settings(
        mastodon_base_url=_value("MASTODON_BASE_URL"),
        mastodon_access_token=_value("MASTODON_ACCESS_TOKEN"),
        telegram_bot_token=_value("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=_value("TELEGRAM_CHAT_ID"),
        discord_webhook_url=_value("DISCORD_WEBHOOK_URL"),
        bluesky_handle=_value("BLUESKY_HANDLE"),
        bluesky_app_password=_value("BLUESKY_APP_PASSWORD"),
        bluesky_pds_url=_value("BLUESKY_PDS_URL") or "https://bsky.social",
        devto_api_key=_value("DEVTO_API_KEY"),
    )
