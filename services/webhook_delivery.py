import hmac, hashlib, json, httpx
from api.db import SessionLocal, Webhook


async def deliver(event: str, bot_id: str, data: dict):
    db = SessionLocal()
    webhooks = db.query(Webhook).filter(Webhook.event == event).all()
    db.close()

    payload = json.dumps({"event": event, "bot_id": bot_id, "data": data})

    async with httpx.AsyncClient(timeout=10) as client:
        for wh in webhooks:
            sig = hmac.new(wh.secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
            try:
                await client.post(wh.url, content=payload, headers={
                    "Content-Type": "application/json",
                    "X-Signature": sig,
                })
            except Exception:
                pass  # TODO: add retry queue
