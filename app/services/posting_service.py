"""Runs all platform integrations concurrently and normalises their results."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from app.config import get_settings
from app.platforms.base import (
    Platform,
    PlatformNotConfigured,
    PostOutcome,
)
from app.platforms.bluesky import BlueskyPlatform
from app.platforms.devto import DevToPlatform
from app.platforms.discord import DiscordPlatform
from app.platforms.mastodon import MastodonPlatform
from app.platforms.telegram import TelegramPlatform
from app.schemas import PlatformResult

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 15.0


def build_platforms() -> list[Platform]:
    settings = get_settings()
    return [
        MastodonPlatform(
            settings.mastodon_base_url, settings.mastodon_access_token
        ),
        BlueskyPlatform(
            settings.bluesky_handle,
            settings.bluesky_app_password,
            settings.bluesky_pds_url,
        ),
        TelegramPlatform(settings.telegram_bot_token, settings.telegram_chat_id),
        DiscordPlatform(settings.discord_webhook_url),
        DevToPlatform(settings.devto_api_key),
    ]


def _failed(platform: str, error: str) -> PlatformResult:
    return PlatformResult(
        platform=platform,
        status="failed",
        posted_url=None,
        public_access=False,
        date=None,
        time=None,
        error=error,
    )


class PostingService:
    def __init__(self, platforms: list[Platform] | None = None) -> None:
        self._platforms = platforms if platforms is not None else build_platforms()

    async def post(self, message: str, cta_url: str) -> list[PlatformResult]:
        """Publish concurrently; a failure in one platform never stops another."""

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            return list(
                await asyncio.gather(
                    *(
                        self._publish(platform, client, message, cta_url)
                        for platform in self._platforms
                    )
                )
            )

    async def _publish(
        self,
        platform: Platform,
        client: httpx.AsyncClient,
        message: str,
        cta_url: str,
    ) -> PlatformResult:
        try:
            outcome: PostOutcome = await platform.publish(
                client, message, cta_url
            )
        except PlatformNotConfigured as exc:
            error = str(exc)
            logger.warning("%s not configured: %s", platform.name, error)
            return _failed(platform.name, error)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # isolate failures per platform
            detail = " ".join(str(exc).split())[:500] or exc.__class__.__name__
            logger.warning("%s failed: %s", platform.name, detail)
            return _failed(platform.name, detail)

        posted_at = datetime.now(timezone.utc)
        logger.info(
            "%s posted successfully: %s", platform.name, outcome.posted_url
        )
        return PlatformResult(
            platform=platform.name,
            status="success",
            posted_url=outcome.posted_url,
            public_access=outcome.public_access,
            date=posted_at.strftime("%Y-%m-%d"),
            time=posted_at.strftime("%H:%M:%S"),
            error=None,
        )
