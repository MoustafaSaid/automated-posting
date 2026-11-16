"""API and orchestration tests."""

from __future__ import annotations

import httpx
import pytest

import app.main as main_module
from app.platforms.base import Platform, PlatformError, PlatformNotConfigured, PostOutcome
from app.schemas import PostingRequest, extract_cta_url
from app.services.posting_service import PostingService

MESSAGE = (
    "Check out our latest business platform and grow your online visibility. "
    "https://example.com"
)
CTA_URL = "https://example.com"


class StubPlatform(Platform):
    def __init__(
        self,
        name: str,
        outcome: PostOutcome | None = None,
        error: Exception | None = None,
    ) -> None:
        self.name = name
        self.outcome = outcome or PostOutcome(
            f"https://example.com/{name.lower()}", True
        )
        self.error = error

    async def publish(self, client, message: str, cta_url: str) -> PostOutcome:
        if self.error:
            raise self.error
        return self.outcome


async def post_message(message: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=main_module.app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        return await client.post("/posting", json={"message": message})


@pytest.mark.asyncio
async def test_posting_continues_when_a_platform_fails():
    service = PostingService(
        [
            StubPlatform("Alpha"),
            StubPlatform("Broken", error=PlatformError("upstream unavailable")),
            StubPlatform(
                "No Credentials",
                error=PlatformNotConfigured("Set NO_CREDENTIALS_KEY"),
            ),
        ]
    )

    results = await service.post(MESSAGE, CTA_URL)

    assert [result.platform for result in results] == [
        "Alpha",
        "Broken",
        "No Credentials",
    ]
    assert [result.status for result in results] == ["success", "failed", "failed"]

    success, broken, unconfigured = results
    assert success.posted_url == "https://example.com/alpha"
    assert success.public_access is True
    assert success.date and success.time
    assert success.error is None

    assert broken.posted_url is None
    assert broken.public_access is False
    assert broken.date is None
    assert broken.time is None
    assert broken.error == "upstream unavailable"

    assert unconfigured.error == "Set NO_CREDENTIALS_KEY"


@pytest.mark.asyncio
async def test_posting_endpoint_returns_a_result_per_platform(monkeypatch):
    service = PostingService(
        [
            StubPlatform("Alpha"),
            StubPlatform("Broken", error=PlatformError("API is down")),
        ]
    )
    monkeypatch.setattr(main_module, "posting_service", service)

    response = await post_message(MESSAGE)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["results"]) == 2
    assert body["results"][0] == {
        "platform": "Alpha",
        "status": "success",
        "posted_url": "https://example.com/alpha",
        "public_access": True,
        "date": body["results"][0]["date"],
        "time": body["results"][0]["time"],
        "error": None,
    }
    assert body["results"][1]["status"] == "failed"
    assert body["results"][1]["error"] == "API is down"


@pytest.mark.asyncio
async def test_posting_endpoint_returns_success_false_when_all_fail(monkeypatch):
    service = PostingService(
        [StubPlatform("Broken", error=PlatformError("API is down"))]
    )
    monkeypatch.setattr(main_module, "posting_service", service)

    response = await post_message(MESSAGE)

    assert response.status_code == 200
    assert response.json()["success"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message",
    [
        "",
        "There is no link in this message",
        "Two links https://a.example and https://b.example",
        "Broken link https://[invalid",
        "x" * 201,
    ],
)
async def test_invalid_messages_are_rejected(message):
    response = await post_message(message)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_validation_error_explains_the_link_requirement():
    response = await post_message("No link here")
    assert response.status_code == 422
    assert "exactly one CTA link" in response.text


def test_message_may_be_exactly_200_characters():
    message = "x" * (200 - len(CTA_URL) - 1) + " " + CTA_URL
    assert len(message) == 200
    PostingRequest(message=message)


def test_trailing_sentence_punctuation_is_not_part_of_the_url():
    assert extract_cta_url("Read more at https://example.com.") == CTA_URL
