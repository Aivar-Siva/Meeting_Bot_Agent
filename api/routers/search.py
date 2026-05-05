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
    prompt = f"Answer this question using only the meeting transcript excerpts below. Be concise.\n\nQuestion: {q}\n\nExcerpts:\n{context}\n\nAnswer:"
    answer = await chat(prompt)
    return {"answer": answer, "sources": chunks}
