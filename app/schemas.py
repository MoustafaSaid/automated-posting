"""Request and response schemas for the posting API."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
)

_HTTP_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_TRAILING_PUNCTUATION = ".,;:!?)]}"
_URL_ADAPTER = TypeAdapter(AnyHttpUrl)


def extract_cta_url(message: str) -> str:
    """Return the single validated CTA URL from a message.

    Trailing sentence punctuation is ignored so that a natural sentence such
    as "Read more at https://example.com." is still valid.
    """

    urls = _HTTP_URL_RE.findall(message)
    if len(urls) != 1:
        raise ValueError(
            "Message must contain exactly one CTA link (http:// or https://)"
        )

    candidate = urls[0].rstrip(_TRAILING_PUNCTUATION)
    try:
        _URL_ADAPTER.validate_python(candidate)
    except ValidationError as exc:
        raise ValueError(f"Invalid CTA URL: {candidate}") from exc
    return candidate


class PostingRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    message: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Short message containing exactly one http(s) CTA link.",
        examples=[
            "Check out our latest business platform and grow your online "
            "visibility. https://example.com"
        ],
    )

    @field_validator("message")
    @classmethod
    def _validate_cta_link(cls, value: str) -> str:
        extract_cta_url(value)
        return value


class PlatformResult(BaseModel):
    platform: str
    status: Literal["success", "failed"]
    posted_url: str | None = None
    public_access: bool = False
    date: str | None = Field(None, description="UTC date, YYYY-MM-DD")
    time: str | None = Field(None, description="UTC time, HH:MM:SS")
    error: str | None = None


class PostingResponse(BaseModel):
    success: bool = Field(
        ...,
        description="True when at least one platform published successfully.",
    )
    results: list[PlatformResult]
