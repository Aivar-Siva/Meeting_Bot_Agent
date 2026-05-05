from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from api.db import get_db, Insight
from services.insights_pipeline import generate_insights
from services.attendee_client import AttendeeClient
from services.vector_store import index_transcript

router = APIRouter()
attendee = AttendeeClient()


@router.get("/{meeting_id}/insights")
def get_insights(meeting_id: str, db: Session = Depends(get_db)):
    insight = db.query(Insight).filter(Insight.meeting_id == meeting_id).first()
    if not insight:
        return {"status": "not_ready"}
    return insight.data


@router.post("/{meeting_id}/insights/generate")
async def trigger_insights(meeting_id: str, background_tasks: BackgroundTasks,
                           db: Session = Depends(get_db)):
    """Called by Attendee webhook when transcription_state = complete."""
    transcript = attendee.get_transcript(meeting_id)
    background_tasks.add_task(_run_pipeline, meeting_id, transcript)
    return {"status": "processing"}


async def _run_pipeline(meeting_id: str, transcript: list):
    insights = await generate_insights(meeting_id, transcript)
    db = SessionLocal()
    db.merge(Insight(meeting_id=meeting_id, data=insights))
    db.commit()
    db.close()
    await index_transcript(meeting_id, transcript)
