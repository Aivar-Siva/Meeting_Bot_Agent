import asyncio
import httpx
import os
from api.routers.live import broadcast

ATTENDEE_BASE = os.environ.get("ATTENDEE_BASE_URL", "http://attendee-app:8000")
ATTENDEE_KEY = os.environ.get("ATTENDEE_API_KEY", "")

# Track last seen utterance count per bot
_last_seen: dict[str, int] = {}


async def poll_transcript(bot_id: str):
    """Poll Attendee transcript every 2s and push new chunks to WebSocket clients."""
    headers = {"Authorization": f"Token {ATTENDEE_KEY}"}
    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            try:
                r = await client.get(
                    f"{ATTENDEE_BASE}/api/v1/bots/{bot_id}/transcript",
                    headers=headers
                )
                if r.status_code == 200:
                    utterances = r.json()
                    last = _last_seen.get(bot_id, 0)
                    new_utterances = utterances[last:]
                    for u in new_utterances:
                        chunk = {
                            "speaker": u.get("speaker_name", "Unknown"),
                            "text": u.get("transcription", {}).get("transcript", ""),
                            "timestamp_ms": u.get("timestamp_ms", 0),
                            "is_final": True,
                        }
                        if chunk["text"]:
                            await broadcast(bot_id, chunk)
                    _last_seen[bot_id] = len(utterances)

                # Check if meeting ended
                r2 = await client.get(
                    f"{ATTENDEE_BASE}/api/v1/bots/{bot_id}",
                    headers=headers
                )
                if r2.status_code == 200:
                    state = r2.json().get("state", "")
                    if state == "ended":
                        break

            except Exception as e:
                pass

            await asyncio.sleep(2)
