"""Bluesky integration using the AT Protocol XRPC API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.platforms.base import (
    Platform,
    PlatformError,
    PlatformNotConfigured,
    PostOutcome,
    http_error,
)


def _link_facets(text: str, cta_url: str) -> list[dict[str, Any]]:
    """Create a Bluesky richtext facet so the CTA is a clickable link.

    Bluesky uses UTF-8 byte offsets, not Python character offsets.
    """

    start = text.find(cta_url)
    if start == -1:
        return []

    end = start + len(cta_url)
    return [
        {
            "$type": "app.bsky.richtext.facet",
            "index": {
                "byteStart": len(text[:start].encode("utf-8")),
                "byteEnd": len(text[:end].encode("utf-8")),
            },
            "features": [
                {
                    "$type": "app.bsky.richtext.facet#link",
                    "uri": cta_url,
                }
            ],
        }
    ]


class BlueskyPlatform(Platform):
    name = "Bluesky"

    def __init__(
        self, handle: str | None, app_password: str | None, pds_url: str
    ) -> None:
        self.handle = handle
        self.app_password = app_password
        self.pds_url = pds_url.rstrip("/")

    async def publish(
        self, client: httpx.AsyncClient, message: str, cta_url: str
    ) -> PostOutcome:
        if not self.handle or not self.app_password:
            raise PlatformNotConfigured(
                "Set BLUESKY_HANDLE and BLUESKY_APP_PASSWORD"
            )

        session_response = await client.post(
            f"{self.pds_url}/xrpc/com.atproto.server.createSession",
            json={"identifier": self.handle, "password": self.app_password},
        )
        if not session_response.is_success:
            raise http_error(session_response)

        session = session_response.json()
        access_jwt = session.get("accessJwt")
        did = session.get("did")
        if not access_jwt or not did:
            raise PlatformError("Bluesky authentication response was incomplete")

        record: dict[str, Any] = {
            "$type": "app.bsky.feed.post",
            "text": message,
            "createdAt": datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
        }
        facets = _link_facets(message, cta_url)
        if facets:
            record["facets"] = facets

        create_response = await client.post(
            f"{self.pds_url}/xrpc/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {access_jwt}"},
            json={
                "repo": did,
                "collection": "app.bsky.feed.post",
                "record": record,
            },
        )
        if not create_response.is_success:
            raise http_error(create_response)

        uri = create_response.json().get("uri")
        if not uri:
            raise PlatformError("Bluesky response did not include a post URI")

        rkey = uri.rsplit("/", 1)[-1]
        handle = session.get("handle") or self.handle
        posted_url = f"https://bsky.app/profile/{handle}/post/{rkey}"
        return PostOutcome(posted_url=posted_url, public_access=True)
