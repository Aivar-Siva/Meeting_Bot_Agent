# Meeting Bot Agent — Hackathon Implementation Plan

## Project Overview

A developer-facing Meeting Bot API that joins online calls, captures audio in real time, generates live transcripts with speaker attribution, produces AI-powered post-call insights, and exposes REST + WebSocket + webhook endpoints for third-party integration. The system is built on top of **attendee-labs/attendee** as the bot infrastructure layer, with custom layers for streaming, AI insights, vector search, and developer API.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    YOUR BUILD (FastAPI Layer)                    │
│                                                                 │
│  WebSocket        AI Insights      Vector Search    Webhooks    │
│  Streaming        Pipeline         (Qdrant)         Fan-out     │
│  (API GW WS)      (GPT-4o)        (NL queries)     (Lambda)    │
└───────────────────────────┬─────────────────────────────────────┘
                            │ uses
┌───────────────────────────▼─────────────────────────────────────┐
│                  ATTENDEE (Bot Infrastructure)                   │
│                                                                 │
│   Bot Join          Audio Capture        Raw Transcripts        │
│   (Zoom/Meet)       (Deepgram STT)       (speaker chunks)       │
└─────────────────────────────────────────────────────────────────┘
                            │ persists to
┌───────────────────────────▼─────────────────────────────────────┐
│                      AWS Infrastructure                          │
│                                                                 │
│  EC2 t3.micro     RDS Postgres t3.micro    DynamoDB (WS state)  │
│  (Attendee app)   (metadata DB)            (always free)        │
│                                                                 │
│  Lambda + API GW  S3 (transcripts)         Qdrant Cloud (free)  │
│  (FastAPI layer)  (audio/files)            (vector search)      │
└─────────────────────────────────────────────────────────────────┘
```

---

## What Attendee Solves (Pre-Built)

| Requirement | Status | Detail |
|---|---|---|
| Join Zoom / Google Meet as visible bot | ✅ Done | `POST /api/v1/bots` with `meeting_url` + `bot_name` |
| Appears as named participant | ✅ Done | Configurable `bot_name` field |
| Audio capture from the call | ✅ Done | Headless Chrome (Meet) + Zoom Meeting SDK |
| Raw transcript chunks during call | ✅ Done | `GET /api/v1/bots/<id>/transcript` works mid-call |
| Speaker attribution | ✅ Done | Each chunk has `speaker_name`, `speaker_uuid`, `timestamp_ms` |
| Deepgram STT integration | ✅ Done | Built-in, 400 free hours on signup |
| Bot lifecycle state management | ✅ Done | `joining → in_call → post_processing → ended` |
| Raw transcript persistence | ✅ Done | Stored in Attendee's Postgres |

**Attendee covers ~35% of the full problem spec.**

---

## What You Must Build

### Layer 1 — WebSocket Live Transcript Streaming

**Why:** Attendee only exposes polling. The spec requires a live stream endpoint.

**How it works:**
1. Create bot with Deepgram `callback_url` pointing to your Lambda endpoint
2. Deepgram pushes transcript events to your server in real time
3. Your FastAPI server fans out chunks to connected frontend WebSocket clients

**Key files to build:**
- `api/routers/live.py` — WebSocket endpoint `/ws/meetings/{bot_id}/live`
- `services/deepgram_receiver.py` — parses Deepgram `Results` events, extracts speaker + text
- `services/connection_manager.py` — maps `bot_id` → list of active WebSocket `connectionId`s (stored in DynamoDB)

**Deepgram event shape received at your callback:**
```json
{
  "type": "Results",
  "is_final": true,
  "channel": {
    "alternatives": [{
      "words": [
        {"word": "hello", "speaker": 0, "start": 1.2, "confidence": 0.98}
      ],
      "transcript": "hello everyone"
    }]
  }
}
```

**Output shape sent to frontend:**
```json
{
  "speaker": "Arjun Kumar",
  "text": "hello everyone",
  "timestamp_ms": 1200,
  "is_final": true
}
```

**Estimated effort:** 1 day

---

### Layer 2 — Post-Call AI Insights Pipeline

**Why:** Attendee gives raw text. The spec requires structured machine-readable insights.

**Trigger:** Webhook from Attendee when `transcription_state = complete`

**Pipeline steps:**
1. Fetch full transcript from `GET /api/v1/bots/<id>/transcript`
2. Format as `Speaker: text` pairs
3. Single GPT-4o call with structured JSON prompt
4. Store result in RDS `insights` table (JSONB column)
5. Trigger webhook delivery to registered third-party URLs

**Required output schema:**
```json
{
  "meeting_id": "bot_xxx",
  "generated_at": "2026-05-05T13:00:00Z",
  "summary": "string",
  "key_decisions": ["string"],
  "action_items": [
    {"owner": "string", "task": "string", "due_date": "string | null"}
  ],
  "topics": ["string"],
  "risks": ["string"],
  "sentiment": {
    "overall": "positive | neutral | negative",
    "per_speaker": {"Speaker Name": "positive | neutral | negative"}
  }
}
```

**Key files to build:**
- `services/insights_pipeline.py` — GPT-4o call + JSON parsing
- `api/routers/insights.py` — `GET /meetings/{id}/insights`
- `workers/post_call_worker.py` — Lambda triggered by Attendee state webhook

**Estimated effort:** 0.5 day

---

### Layer 3 — Vector Search over Past Meetings

**Why:** Attendee has no search capability. The spec requires natural language queries like *"what did we decide about the API design last Thursday?"*

**Stack:** Qdrant Cloud (free 1 GB cluster) + `text-embedding-3-small`

**Indexing pipeline (runs after insights are ready):**
1. Split transcript into chunks (~200 tokens each)
2. Embed each chunk with OpenAI `text-embedding-3-small`
3. Upsert into Qdrant with metadata payload:
   ```json
   {
     "bot_id": "bot_xxx",
     "speaker": "Arjun Kumar",
     "text": "chunk text",
     "timestamp_ms": 1200,
     "meeting_date": "2026-05-05",
     "meeting_title": "API Design Review"
   }
   ```

**Search flow:**
1. Receive NL query: `"find all action items assigned to me this week"`
2. Embed query → similarity search in Qdrant with date filter
3. Retrieve top-K chunks → pass to LLM for answer synthesis
4. Return structured response with source meeting references

**API endpoint:** `GET /search?q=<query>&from_date=2026-05-01&speaker=Arjun`

**Key files to build:**
- `services/vector_store.py` — Qdrant upsert + search logic
- `services/embeddings.py` — OpenAI embedding wrapper
- `api/routers/search.py` — search endpoint with NL query support

**Estimated effort:** 1 day

---

### Layer 4 — Webhook Fan-out System

**Why:** Third-party apps need push notifications, not polling.

**Events to support:**
| Event | Trigger |
|---|---|
| `bot.joined` | Bot successfully joins the call |
| `transcript.chunk` | New live transcript chunk available |
| `meeting.ended` | Call has ended |
| `insights.ready` | Post-call AI insights generated |
| `search.result` | (optional) async search result ready |

**Implementation:**
1. `POST /webhooks` — register a callback URL + event type + secret
2. On event: fetch all registered URLs for that event → HTTP POST with HMAC-signed payload
3. Retry on failure: 3 attempts with exponential backoff via SQS

**Webhook payload shape:**
```json
{
  "event": "transcript.chunk",
  "bot_id": "bot_xxx",
  "timestamp": "2026-05-05T13:01:00Z",
  "data": {
    "speaker": "Arjun Kumar",
    "text": "Let us finalize the API design",
    "is_final": true
  }
}
```

**Key files to build:**
- `api/routers/webhooks.py` — register/list/delete endpoints
- `services/webhook_delivery.py` — HMAC signing + HTTP POST + retry logic
- `workers/webhook_worker.py` — SQS consumer Lambda

**Estimated effort:** 0.5 day

---

### Layer 5 — Developer REST API + Documentation

**Endpoints to expose:**

| Method | Path | Description |
|---|---|---|
| `POST` | `/meetings/schedule` | Create and launch a bot into a meeting |
| `GET` | `/meetings/{id}` | Bot status and metadata |
| `GET` | `/meetings/{id}/transcript` | Full transcript (post-call) |
| `WS` | `/ws/meetings/{id}/live` | Live transcript stream |
| `GET` | `/meetings/{id}/insights` | Structured post-call AI JSON |
| `GET` | `/search` | NL search over past meetings |
| `POST` | `/webhooks` | Register webhook callback |
| `DELETE` | `/webhooks/{id}` | Remove webhook |

**Documentation:** FastAPI auto-generates `/docs` (Swagger UI) and `/redoc` — no extra work needed. Add example payloads and response schemas to all route decorators.

**Estimated effort:** 0.5 day

---

## AWS Infrastructure (Free Tier)

All services stay within AWS free tier for a hackathon demo.

| Service | Purpose | Free Limit |
|---|---|---|
| EC2 t3.micro | Run Attendee Django app | 750 hrs/month (12 months) |
| RDS Postgres t3.micro | Metadata DB (meetings, transcripts, insights) | 750 hrs/month (12 months) |
| Lambda | FastAPI handlers, post-call worker, webhook worker | 1M requests/month (always free) |
| API Gateway HTTP | REST API endpoints | 1M calls/month (12 months) |
| API Gateway WebSocket | Live transcript streaming | 750K connection-mins/month |
| DynamoDB | WebSocket connection state (`connectionId → bot_id`) | 25 GB (always free) |
| S3 | Transcript and audio file storage | 5 GB (12 months) |
| SQS | Webhook retry queue | 1M requests/month (always free) |
| CloudWatch | Logs and monitoring | 5 GB ingestion (12 months) |

**External free tiers:**
- **Qdrant Cloud** — 1 GB free cluster (vector search)
- **Deepgram** — 400 free hours (STT, built into Attendee)
- **OpenAI** — use free credits for GPT-4o insights pipeline

---

## Repository Structure

```
meeting-bot-api/
├── attendee/                    # Attendee submodule or Docker setup
│   └── dev.docker-compose.yaml
│
├── api/                         # FastAPI application
│   ├── main.py
│   ├── routers/
│   │   ├── meetings.py          # /meetings endpoints
│   │   ├── live.py              # WebSocket /ws/meetings/{id}/live
│   │   ├── insights.py          # /meetings/{id}/insights
│   │   ├── search.py            # /search
│   │   └── webhooks.py          # /webhooks CRUD
│   └── models/
│       ├── meeting.py
│       ├── transcript.py
│       └── insight.py
│
├── services/
│   ├── attendee_client.py       # Wrapper for Attendee REST API
│   ├── deepgram_receiver.py     # Parse Deepgram callback events
│   ├── connection_manager.py    # DynamoDB WebSocket state
│   ├── insights_pipeline.py     # GPT-4o structured insights
│   ├── vector_store.py          # Qdrant upsert + search
│   ├── embeddings.py            # OpenAI embedding wrapper
│   └── webhook_delivery.py      # HMAC sign + HTTP POST + retry
│
├── workers/
│   ├── post_call_worker.py      # Lambda: triggered on meeting end
│   └── webhook_worker.py        # Lambda: SQS consumer for fan-out
│
├── infra/
│   ├── template.yaml            # AWS SAM / CloudFormation
│   └── docker-compose.yaml      # Local dev stack
│
├── tests/
│   ├── test_live_stream.py
│   ├── test_insights.py
│   └── test_search.py
│
└── README.md                    # Developer integration guide
```

---

## Implementation Timeline

### Day 1 — Foundation
- [ ] Set up Attendee on EC2 t3.micro with Docker
- [ ] Create bot, verify it joins Google Meet, confirm transcript polling works
- [ ] Set up RDS Postgres, create schema (meetings, transcripts, insights, webhooks)
- [ ] Build `attendee_client.py` wrapper
- [ ] Build `POST /meetings/schedule` and `GET /meetings/{id}` endpoints

### Day 2 — Live Streaming
- [ ] Set up API Gateway WebSocket API
- [ ] Build `deepgram_receiver.py` — parse Deepgram callback events
- [ ] Build `connection_manager.py` — DynamoDB connectionId store
- [ ] Build `/ws/meetings/{id}/live` WebSocket endpoint
- [ ] End-to-end test: join a meeting, see live transcript in browser

### Day 3 — AI Insights + Storage
- [ ] Build `insights_pipeline.py` — GPT-4o structured JSON output
- [ ] Build `post_call_worker.py` — Lambda triggered on meeting end
- [ ] Build `GET /meetings/{id}/insights` endpoint
- [ ] Set up Qdrant Cloud cluster
- [ ] Build `vector_store.py` + `embeddings.py`
- [ ] Index transcripts from 2+ test meetings into Qdrant

### Day 4 — Search + Webhooks
- [ ] Build `GET /search` endpoint with NL query → Qdrant → LLM synthesis
- [ ] Test: "what did we decide last Thursday?" returns correct chunks
- [ ] Build `POST /webhooks` registration + HMAC signing
- [ ] Build `webhook_worker.py` SQS consumer
- [ ] Test end-to-end webhook delivery to a simple receiver app

### Day 5 — Polish + Submission
- [ ] Write developer README with quickstart, endpoint reference, webhook guide
- [ ] Verify FastAPI `/docs` Swagger UI is clean and complete
- [ ] Record demo: bot joining → live captions → post-call insights → NL search
- [ ] Write architecture write-up: real-time audio capture, speaker diarisation, live-vs-post-call pipeline split
- [ ] Deploy final stack to AWS, run smoke tests

---

## Submission Checklist

- [ ] Working bot joins a real Google Meet or Zoom call and appears as a named participant
- [ ] Live transcript visible during the call (WebSocket stream, not just post-call)
- [ ] Speaker attribution on every transcript chunk
- [ ] Sample post-call insight JSON from a completed session (structured, machine-readable)
- [ ] Working NL search query demonstrated over at least 2 past meetings
- [ ] REST API documented via Swagger UI (`/docs`)
- [ ] Architecture write-up covering: real-time audio capture, speaker diarisation, live-vs-post-call pipeline split
- [ ] Participant consent handled (bot visible, recording announced in chat)

---

## Key Credentials Required

| Credential | Source |
|---|---|
| Attendee API Key | Self-hosted Attendee UI → API Keys |
| Zoom Client ID + Secret | Zoom Marketplace → General App → Meeting SDK |
| Deepgram API Key | deepgram.com (400 free hours) |
| OpenAI API Key | platform.openai.com (free credits) |
| Qdrant Cloud URL + API Key | cloud.qdrant.io (free 1 GB cluster) |
| AWS credentials | IAM user with Lambda, API GW, DynamoDB, RDS, S3 access |
