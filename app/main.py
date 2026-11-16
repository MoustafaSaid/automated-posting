"""FastAPI entry point for the automated multi-platform posting system."""

from __future__ import annotations

from fastapi import FastAPI

from app.schemas import PostingRequest, PostingResponse, extract_cta_url
from app.services.posting_service import PostingService

app = FastAPI(
    title="Automated Multi-Platform Posting System",
    version="1.0.0",
    description=(
        "Publishes one short message with a single CTA link to Mastodon, "
        "Bluesky, Telegram, Discord and DEV.to."
    ),
)

posting_service = PostingService()


@app.post(
    "/posting",
    response_model=PostingResponse,
    summary="Publish a message to every configured platform",
)
async def create_posting(request: PostingRequest) -> PostingResponse:
    cta_url = extract_cta_url(request.message)
    results = await posting_service.post(request.message, cta_url)
    return PostingResponse(
        success=any(result.status == "success" for result in results),
        results=results,
    )
