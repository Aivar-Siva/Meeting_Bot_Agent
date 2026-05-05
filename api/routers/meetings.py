from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from api.db import get_db, Meeting
from services.attendee_client import AttendeeClient
import uuid

router = APIRouter()
attendee = AttendeeClient()


class ScheduleRequest(BaseModel):
    meeting_url: str
    bot_name: str = "Meeting Bot"


@router.post("/schedule")
def schedule(req: ScheduleRequest, db: Session = Depends(get_db)):
    bot = attendee.create_bot(req.meeting_url, req.bot_name)
    meeting = Meeting(id=bot["id"], meeting_url=req.meeting_url,
                      bot_name=req.bot_name, status="joining")
    db.add(meeting)
    db.commit()
    return {"meeting_id": bot["id"], "status": "joining"}


@router.get("/{meeting_id}")
def get_meeting(meeting_id: str, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    bot = attendee.get_bot(meeting_id)
    return {"meeting_id": meeting_id, "status": bot.get("state"), "meeting_url": meeting.meeting_url}


@router.get("/{meeting_id}/transcript")
def get_transcript(meeting_id: str):
    return attendee.get_transcript(meeting_id)
