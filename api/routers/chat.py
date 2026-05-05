from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import httpx, os, json

router = APIRouter()

LAMBDA_URL = os.environ.get("BEDROCK_LAMBDA_URL", "")
SEARCH_MODEL = "us.meta.llama3-3-70b-instruct-v1:0"


class Message(BaseModel):
    role: str   # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]
    meeting_id: Optional[str] = None


async def _get_context(query: str, meeting_id: str = None) -> str:
    """Fetch relevant transcript chunks from Qdrant for context."""
    try:
        from services.vector_store import search_transcripts
        chunks = await search_transcripts(query, top_k=3)
        if not chunks:
            return ""
        return "\n".join(f"[{c['speaker']}]: {c['text']}" for c in chunks)
    except Exception:
        return ""


def _build_prompt(messages: List[Message], context: str) -> str:
    system = "You are a meeting assistant. Answer questions about meetings concisely in 2-3 sentences."
    if context:
        system += f"\n\nRelevant meeting context:\n{context}"

    parts = [f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n{system}<|eot_id|>"]
    for m in messages:
        role = "user" if m.role == "user" else "assistant"
        parts.append(f"<|start_header_id|>{role}<|end_header_id|>\n{m.content}<|eot_id|>")
    parts.append("<|start_header_id|>assistant<|end_header_id|>")
    return "".join(parts)


@router.post("/chat")
async def chat(req: ChatRequest):
    # Get context from Qdrant using the latest user message
    last_user_msg = next((m.content for m in reversed(req.messages) if m.role == "user"), "")
    context = await _get_context(last_user_msg, req.meeting_id)
    prompt = _build_prompt(req.messages, context)

    async def stream():
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", LAMBDA_URL, json={
                "model_id": SEARCH_MODEL,
                "prompt": prompt,
                "max_gen_len": 300,
            }) as r:
                async for line in r.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            chunk = json.loads(line[6:])
                            token = chunk.get("generation", "")
                            if token:
                                yield f"data: {json.dumps({'token': token})}\n\n"
                        except Exception:
                            pass
        # Send sources as final event
        if chunks:
            yield f"data: {json.dumps({'sources': chunks})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
