import asyncio
import httpx
import os
from api.routers.live import broadcast

ATTENDEE_BASE = os.environ.get("ATTENDEE_BASE_URL", "http://attendee-app:8000")
ATTENDEE_KEY = os.environ.get("ATTENDEE_API_KEY", "")

_last_seen: dict[str, int] = {}


async def poll_transcript(bot_id: str):
    """Poll Attendee every 2s, push new chunks to WebSocket, auto-trigger insights on end."""
    from api.db import SessionLocal, Meeting
    from api.routers.insights import _run_pipeline
    from services.attendee_client import AttendeeClient

    headers = {"Authorization": f"Token {ATTENDEE_KEY}"}

    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            try:
                # Get transcript chunks
                r = await client.get(f"{ATTENDEE_BASE}/api/v1/bots/{bot_id}/transcript", headers=headers)
                if r.status_code == 200:
                    utterances = r.json()
                    last = _last_seen.get(bot_id, 0)
                    for u in utterances[last:]:
                        chunk = {
                            "speaker": u.get("speaker_name", "Unknown"),
                            "text": u.get("transcription", {}).get("transcript", ""),
                            "timestamp_ms": u.get("timestamp_ms", 0),
                            "is_final": True,
                        }
                        if chunk["text"]:
                            await broadcast(bot_id, chunk)
                    _last_seen[bot_id] = len(utterances)

                # Get bot status
                r2 = await client.get(f"{ATTENDEE_BASE}/api/v1/bots/{bot_id}", headers=headers)
                if r2.status_code == 200:
                    bot_data = r2.json()
                    state = bot_data.get("state", "")
                    transcription_state = bot_data.get("transcription_state", "")

                    # Update meeting status in DB
                    db = SessionLocal()
                    meeting = db.query(Meeting).filter(Meeting.id == bot_id).first()
                    if meeting and meeting.status != state:
                        meeting.status = state
                        db.commit()
                    db.close()

                    # Auto-trigger insights when transcription is complete
                    if transcription_state == "complete":
                        transcript = _last_seen.get(f"{bot_id}_transcript_fetched")
                        if not transcript:
                            _last_seen[f"{bot_id}_transcript_fetched"] = True
                            attendee = AttendeeClient()
                            full_transcript = attendee.get_transcript(bot_id)
                            if full_transcript:
                                asyncio.create_task(_run_pipeline(bot_id, full_transcript))
                        break  # Stop polling — meeting is done

            except Exception:
                pass

            await asyncio.sleep(2)
