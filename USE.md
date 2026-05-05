# Meeting Bot Agent — API Reference

Base URL: `http://35.89.213.164:8000`

Interactive docs: `http://35.89.213.164:8000/docs`

---

## Meetings

### Schedule a bot
```
POST /meetings/schedule
Content-Type: application/json

{ "meeting_url": "https://zoom.us/j/...", "bot_name": "Meeting Bot" }
```
Response: `{ "meeting_id": "bot_xxx", "status": "joining" }`

### List all meetings
```
GET /meetings
```
Response: Array of `{ meeting_id, meeting_url, bot_name, status, created_at }`

### Get meeting status
```
GET /meetings/{meeting_id}
```

### Get transcript (post-call)
```
GET /meetings/{meeting_id}/transcript
```

---

## Live Transcript

### WebSocket stream (during call)
```
WS ws://35.89.213.164:8000/ws/meetings/{meeting_id}/live
```
Receives chunks:
```json
{ "speaker": "Name", "text": "...", "timestamp_ms": 1200, "is_final": true }
```

---

## Insights

### Generate post-call insights (AI)
```
POST /meetings/{meeting_id}/insights/generate
```
Triggers Llama 4 Maverick pipeline. Takes ~30s.

### Get insights
```
GET /meetings/{meeting_id}/insights
```
Response:
```json
{
  "meeting_id": "bot_xxx",
  "summary": "...",
  "key_decisions": ["..."],
  "action_items": [{ "owner": "Name", "task": "...", "due_date": null }],
  "topics": ["..."],
  "risks": ["..."],
  "sentiment": { "overall": "positive", "per_speaker": { "Name": "neutral" } }
}
```

---

## Search

### Natural language search over past meetings
```
GET /search?q=what did we decide about the API design
GET /search?q=action items&from_date=2026-05-01&speaker=Arjun
```
Response:
```json
{ "answer": "...", "sources": [{ "meeting_id", "speaker", "text", "meeting_date" }] }
```

---

## Webhooks

### Register webhook
```
POST /webhooks
Content-Type: application/json

{ "url": "https://your-app.com/hook", "event": "insights.ready" }
```
Events: `bot.joined` | `meeting.ended` | `insights.ready` | `transcript.chunk`

### List webhooks
```
GET /webhooks
```

### Delete webhook
```
DELETE /webhooks/{webhook_id}
```

---

## Deepgram Callback (internal)
```
POST /deepgram/callback?bot_id={meeting_id}
```
Called by Deepgram during live transcription. Not for external use.

---

## UI
```
GET /   → Web UI (Schedule, Insights, Search)
```
