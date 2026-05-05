from fastapi import APIRouter
from services.vector_store import search_transcripts
from services.llm_client import chat

router = APIRouter()


@router.get("")
async def search(q: str, from_date: str = None, speaker: str = None):
    chunks = await search_transcripts(q, from_date=from_date, speaker=speaker)
    if not chunks:
        return {"answer": "No relevant meeting data found. Try generating insights first to index the transcripts.", "sources": []}

    context = "\n".join(
        f"[{c['meeting_date']} - {c['speaker']}]: {c['text']}" for c in chunks
    )
    prompt = f"Answer in 2-3 sentences maximum. Be direct and concise.\n\nQuestion: {q}\n\nMeeting excerpts:\n{context}\n\nAnswer:"
    answer = await chat(prompt, max_tokens=150)
    return {"answer": answer, "sources": chunks}
