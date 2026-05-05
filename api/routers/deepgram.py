from fastapi import APIRouter, Request, BackgroundTasks
from api.routers.live import broadcast
from api.db import SessionLocal, SpeakerMap

router = APIRouter()


@router.post("/callback")
async def deepgram_callback(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()
    meeting_id = request.query_params.get("bot_id", "unknown")

    # Extract transcript chunk from Deepgram Results event
    if body.get("type") != "Results":
        return {"ok": True}

    alt = body.get("channel", {}).get("alternatives", [{}])[0]
    transcript = alt.get("transcript", "").strip()
    if not transcript:
        return {"ok": True}

    # Get speaker index from first word
    words = alt.get("words", [])
    speaker_index = str(words[0].get("speaker", 0)) if words else "0"
    start_ms = int(words[0].get("start", 0) * 1000) if words else 0

    # Resolve speaker name from DB map
    db = SessionLocal()
    mapping = db.query(SpeakerMap).filter(
        SpeakerMap.meeting_id == meeting_id,
        SpeakerMap.speaker_index == speaker_index
    ).first()
    speaker_name = mapping.name if mapping else f"Speaker {speaker_index}"
    db.close()

    chunk = {
        "speaker": speaker_name,
        "speaker_index": speaker_index,
        "text": transcript,
        "timestamp_ms": start_ms,
        "is_final": body.get("is_final", False),
    }

    background_tasks.add_task(broadcast, meeting_id, chunk)
    return {"ok": True}
