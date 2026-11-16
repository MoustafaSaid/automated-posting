# Automated Multi-Platform Posting System

A small FastAPI service that publishes one short message (with exactly one CTA
link) to five independent platforms and returns a per-platform result.

**Platforms:** Mastodon, Bluesky, Telegram, Discord, DEV.to

If one platform is down, misconfigured, or rejects the post, the other
platforms still run. Requests are sent concurrently and each platform has its
own credential set.

## Project structure

```text
.
├── app/
│   ├── main.py                 # FastAPI app and POST /posting
│   ├── schemas.py              # Pydantic validation and response models
│   ├── config.py               # Environment configuration
│   ├── platforms/
│   │   ├── base.py             # Platform contract + shared HTTP errors
│   │   ├── mastodon.py
│   │   ├── bluesky.py
│   │   ├── telegram.py
│   │   ├── discord.py
│   │   └── devto.py
│   └── services/
│       └── posting_service.py  # Concurrent orchestration
├── tests/
│   ├── test_posting.py         # API, validation, failure isolation
│   └── test_platforms.py       # Platform API contracts (mock HTTP)
├── docs/
│   ├── test-run.txt
│   └── example-server.log
├── .env.example
├── requirements.txt
└── README.md
```

## Requirements

- Python 3.10+
- A public (or reachable) account/API credentials for each platform you want
  to test

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and fill in the platforms you want to use.
```

`app/config.py` loads `.env` automatically with `python-dotenv`. Real shell
environment variables take precedence over values in `.env`.

Start the API on the required port:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 4000
```

Then open:

- Swagger UI: <http://localhost:4000/docs>
- ReDoc: <http://localhost:4000/redoc>

## Environment variables

Every platform is optional. A platform with missing credentials is reported as
`failed` with a "not configured" error, while the other platforms continue.

| Variable | Platform | How to obtain it |
| --- | --- | --- |
| `MASTODON_BASE_URL` | Mastodon | Your instance URL, e.g. `https://mastodon.social` |
| `MASTODON_ACCESS_TOKEN` | Mastodon | Preferences → Development → New application, with `write:statuses` |
| `BLUESKY_HANDLE` | Bluesky | Your handle, e.g. `name.bsky.social` |
| `BLUESKY_APP_PASSWORD` | Bluesky | Settings → App Passwords → Add App Password |
| `BLUESKY_PDS_URL` | Bluesky | Optional, defaults to `https://bsky.social` |
| `TELEGRAM_BOT_TOKEN` | Telegram | Create a bot with [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | Telegram | `@channel_name` or a numeric chat id; add the bot as an admin |
| `DISCORD_WEBHOOK_URL` | Discord | Channel settings → Integrations → Webhooks → Copy Webhook URL |
| `DEVTO_API_KEY` | DEV.to | Settings → Extensions → DEV Community API Keys |

Official API documentation used for the integrations:

- Mastodon statuses: <https://docs.joinmastodon.org/methods/statuses/#create>
- Bluesky/AT Protocol posts: <https://docs.bsky.app/docs/tutorials/creating-a-post>
- Telegram `sendMessage`: <https://core.telegram.org/bots/api#sendmessage>
- Discord execute webhook: <https://discord.com/developers/docs/resources/webhook#execute-webhook>
- DEV.to (Forem) create article: <https://developers.forem.com/api/v1#tag/articles/operation/createArticle>

## API

### `POST /posting`

Publishes to all five platforms. Platform selection is internal; there is no
platform parameter in the request.

#### Request

```bash
curl -X POST http://localhost:4000/posting \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Check out our latest business platform and grow your online visibility. https://example.com"
  }'
```

```json
{
  "message": "Check out our latest business platform and grow your online visibility. https://example.com"
}
```

#### Validation rules

- `message` is required, non-empty, and at most **200 characters** (after
  trimming surrounding whitespace).
- It must contain **exactly one** CTA link using `http://` or `https://`.
- The URL must be a valid absolute URL.
- Trailing sentence punctuation is not treated as part of the URL, so
  `Read more at https://example.com.` is valid.
- Invalid input returns FastAPI's standard **422 Unprocessable Entity**
  response with the reason. Two links, no link, an invalid URL, or a message
  over 200 characters are all rejected before any platform is called.

#### Successful response

`success` is `true` when **at least one** platform published successfully.
Partial failures still return HTTP 200 so the caller can inspect every result.
`date` and `time` are UTC and are `null` for failed posts.

```json
{
  "success": true,
  "results": [
    {
      "platform": "Mastodon",
      "status": "success",
      "posted_url": "https://mastodon.social/@demo/113456789012345678",
      "public_access": true,
      "date": "2026-11-16",
      "time": "10:30:01",
      "error": null
    },
    {
      "platform": "Bluesky",
      "status": "success",
      "posted_url": "https://bsky.app/profile/demo.bsky.social/post/3lbnexample",
      "public_access": true,
      "date": "2026-11-16",
      "time": "10:30:01",
      "error": null
    },
    {
      "platform": "Telegram",
      "status": "success",
      "posted_url": "https://t.me/demo_channel/42",
      "public_access": true,
      "date": "2026-11-16",
      "time": "10:30:02",
      "error": null
    },
    {
      "platform": "Discord",
      "status": "success",
      "posted_url": "https://discord.com/channels/111111111/222222222/333333333",
      "public_access": false,
      "date": "2026-11-16",
      "time": "10:30:02",
      "error": null
    },
    {
      "platform": "DEV.to",
      "status": "failed",
      "posted_url": null,
      "public_access": false,
      "date": null,
      "time": null,
      "error": "HTTP 401: Invalid API key"
    }
  ]
}
```

> The response above illustrates the exact response shape. Actual URLs,
> timestamps, and errors come from the live platform APIs.

#### Validation error example

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "message"],
      "msg": "Value error, Message must contain exactly one CTA link (http:// or https://)",
      "input": "This message has no link"
    }
  ]
}
```

#### Public access semantics

| Platform | `public_access` |
| --- | --- |
| Mastodon | `true` when the returned visibility is `public` or `unlisted` |
| Bluesky | `true` — posts are public |
| Telegram | `true` only when the chat has a public username; private/numeric chats return no public URL |
| Discord | `false` — Discord messages require login and server membership |
| DEV.to | `true` — the article is published |

### Failure isolation

Platform calls run with `asyncio.gather`. Each call is wrapped individually:

- `PlatformNotConfigured` → failed result with the missing environment variables
- HTTP errors → failed result with a concise status/body message
- Timeouts/network errors → failed result with the error
- No retry is performed, avoiding accidental duplicate posts

## Tests

```bash
pytest -q
```

```text
18 passed
```

The tests cover:

- endpoint response shape and per-platform results
- message length, missing link, multiple links, and invalid URL validation
- the 200-character boundary and trailing punctuation handling
- failure isolation across platforms
- Mastodon, Bluesky, Telegram, Discord, and DEV.to request contracts using
  `httpx.MockTransport`
- no credentials leaking into HTTP error messages

A captured test run is available in [`docs/test-run.txt`](docs/test-run.txt).
The tests use mocked HTTP, so they do not post anything or need real keys.

## Logs

[`docs/example-server.log`](docs/example-server.log) contains a local run of the
required Uvicorn command with one valid request and one invalid request. It was
generated without real credentials; the expected "not configured" failures
demonstrate that all platforms are attempted independently.

## Security

- `.env` and local environment files are ignored by Git.
- `.env.example` contains names and placeholders only; no credentials.
- Credentials are read from environment variables, never from request bodies.
- API error messages are capped at 300 characters.
- Webhook URLs and bot tokens should still be treated as secrets.

## Notes and limitations

- DEV.to has no microblog endpoint, so the message becomes a published article
  body and its first line becomes the title.
- Telegram requires the bot to be an administrator of the target channel/group.
- Discord webhook messages are not publicly accessible without authentication.
- The message must use an explicit `http://` or `https://` scheme.
- `date`/`time` are recorded in UTC when the post succeeds.
- Real credentials and account permissions are required to create live posts.
