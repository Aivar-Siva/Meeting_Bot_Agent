from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from collections import defaultdict
from typing import Dict, List

router = APIRouter()

# In-memory: bot_id -> list of connected WebSocket clients
connections: Dict[str, List[WebSocket]] = defaultdict(list)


@router.websocket("/meetings/{meeting_id}/live")
async def live_transcript(websocket: WebSocket, meeting_id: str):
    await websocket.accept()
    connections[meeting_id].append(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep alive
    except WebSocketDisconnect:
        connections[meeting_id].remove(websocket)


async def broadcast(meeting_id: str, chunk: dict):
    """Called by deepgram callback to push chunk to all connected clients."""
    dead = []
    for ws in connections.get(meeting_id, []):
        try:
            await ws.send_json(chunk)
        except Exception:
            dead.append(ws)
    for ws in dead:
        connections[meeting_id].remove(ws)
