"""Contract tests for the platform API integrations (HTTP is mocked)."""

from __future__ import annotations

import json

import httpx
import pytest

from app.platforms.base import PlatformError
from app.platforms.bluesky import BlueskyPlatform
from app.platforms.devto import DevToPlatform
from app.platforms.discord import DiscordPlatform
from app.platforms.mastodon import MastodonPlatform
from app.platforms.telegram import TelegramPlatform

MESSAGE = "Read more at https://example.com"
CTA_URL = "https://example.com"


@pytest.mark.asyncio
async def test_mastodon_posts_a_public_status():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://mastodon.example/api/v1/statuses"
        assert request.headers["authorization"] == "Bearer token"
        assert json.loads(request.content) == {
            "status": MESSAGE,
            "visibility": "public",
        }
        return httpx.Response(
            200,
            json={
                "url": "https://mastodon.example/@user/123",
                "visibility": "public",
            },
        )

    platform = MastodonPlatform("https://mastodon.example/", "token")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        outcome = await platform.publish(client, MESSAGE, CTA_URL)

    assert outcome.posted_url == "https://mastodon.example/@user/123"
    assert outcome.public_access is True


@pytest.mark.asyncio
async def test_telegram_posts_and_builds_a_public_channel_url():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/bottoken/sendMessage"
        payload = json.loads(request.content)
        assert payload["chat_id"] == "@mychannel"
        assert payload["text"] == MESSAGE
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": {
                    "message_id": 42,
                    "chat": {"username": "mychannel"},
                },
            },
        )

    platform = TelegramPlatform("token", "@mychannel")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        outcome = await platform.publish(client, MESSAGE, CTA_URL)

    assert outcome.posted_url == "https://t.me/mychannel/42"
    assert outcome.public_access is True


@pytest.mark.asyncio
async def test_telegram_private_chat_has_no_public_url():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": {"message_id": 42, "chat": {"id": -100123}},
            },
        )

    platform = TelegramPlatform("token", "-100123")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        outcome = await platform.publish(client, MESSAGE, CTA_URL)

    assert outcome.posted_url is None
    assert outcome.public_access is False


@pytest.mark.asyncio
async def test_discord_executes_webhook_and_waits_for_message():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["wait"] == "true"
        assert json.loads(request.content) == {"content": MESSAGE}
        return httpx.Response(
            200,
            json={
                "id": "333",
                "channel_id": "222",
                "guild_id": "111",
            },
        )

    platform = DiscordPlatform("https://discord.com/api/webhooks/1/token")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        outcome = await platform.publish(client, MESSAGE, CTA_URL)

    assert outcome.posted_url == "https://discord.com/channels/111/222/333"
    assert outcome.public_access is False


@pytest.mark.asyncio
async def test_bluesky_authenticates_and_posts_with_utf8_link_facet():
    message = "Héllo 👋 read https://example.com"
    start = message.index(CTA_URL)
    expected_byte_start = len(message[:start].encode("utf-8"))
    expected_byte_end = expected_byte_start + len(CTA_URL.encode("utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("com.atproto.server.createSession"):
            assert json.loads(request.content) == {
                "identifier": "user.bsky.social",
                "password": "app-password",
            }
            return httpx.Response(
                200,
                json={
                    "accessJwt": "jwt",
                    "did": "did:plc:abc",
                    "handle": "user.bsky.social",
                },
            )

        assert request.url.path.endswith("com.atproto.repo.createRecord")
        assert request.headers["authorization"] == "Bearer jwt"
        payload = json.loads(request.content)
        assert payload["repo"] == "did:plc:abc"
        record = payload["record"]
        assert record["text"] == message
        facet = record["facets"][0]
        assert facet["index"] == {
            "byteStart": expected_byte_start,
            "byteEnd": expected_byte_end,
        }
        assert facet["features"][0]["uri"] == CTA_URL
        return httpx.Response(
            200,
            json={"uri": "at://did:plc:abc/app.bsky.feed.post/3abc"},
        )

    platform = BlueskyPlatform(
        "user.bsky.social", "app-password", "https://bsky.social"
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        outcome = await platform.publish(client, message, CTA_URL)

    assert (
        outcome.posted_url
        == "https://bsky.app/profile/user.bsky.social/post/3abc"
    )
    assert outcome.public_access is True


@pytest.mark.asyncio
async def test_devto_creates_a_published_article():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://dev.to/api/articles"
        assert request.headers["api-key"] == "key"
        payload = json.loads(request.content)["article"]
        assert payload["body_markdown"] == MESSAGE
        assert payload["published"] is True
        return httpx.Response(
            201, json={"url": "https://dev.to/user/read-more-123"}
        )

    platform = DevToPlatform("key")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        outcome = await platform.publish(client, MESSAGE, CTA_URL)

    assert outcome.posted_url == "https://dev.to/user/read-more-123"
    assert outcome.public_access is True


@pytest.mark.asyncio
async def test_http_errors_are_reported_without_leaking_credentials():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401, json={"error": "The access token is invalid"}
        )

    platform = MastodonPlatform("https://mastodon.example", "secret-token")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(PlatformError) as exc_info:
            await platform.publish(client, MESSAGE, CTA_URL)

    assert "HTTP 401" in str(exc_info.value)
    assert "The access token is invalid" in str(exc_info.value)
    assert "secret-token" not in str(exc_info.value)
