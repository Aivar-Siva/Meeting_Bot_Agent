from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from api.db import get_db, Webhook
import uuid, secrets

router = APIRouter()


class WebhookCreate(BaseModel):
    url: str
    event: str   # bot.joined | meeting.ended | insights.ready | transcript.chunk


@router.post("")
def register(req: WebhookCreate, db: Session = Depends(get_db)):
    wh = Webhook(id=str(uuid.uuid4()), url=req.url,
                 event=req.event, secret=secrets.token_hex(16))
    db.add(wh)
    db.commit()
    return {"id": wh.id, "secret": wh.secret}


@router.get("")
def list_webhooks(db: Session = Depends(get_db)):
    return db.query(Webhook).all()


@router.delete("/{webhook_id}")
def delete_webhook(webhook_id: str, db: Session = Depends(get_db)):
    wh = db.query(Webhook).filter(Webhook.id == webhook_id).first()
    if not wh:
        raise HTTPException(404, "Not found")
    db.delete(wh)
    db.commit()
    return {"deleted": True}
