import os
import httpx
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, Range
import uuid

COLLECTION = "transcripts"
VECTOR_DIM = 1024  # Amazon Titan Embed v2

LAMBDA_URL = os.environ.get("BEDROCK_LAMBDA_URL", "")

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = QdrantClient(url=os.environ.get("QDRANT_URL", "http://localhost:6333"))
        existing = [c.name for c in _client.get_collections().collections]
        if COLLECTION not in existing:
            _client.create_collection(COLLECTION, vectors_config=VectorParams(
                size=VECTOR_DIM, distance=Distance.COSINE
            ))
        else:
            # Recreate if vector size changed (e.g. switching from MiniLM 384 to Titan 1024)
            info = _client.get_collection(COLLECTION)
            if info.config.params.vectors.size != VECTOR_DIM:
                _client.delete_collection(COLLECTION)
                _client.create_collection(COLLECTION, vectors_config=VectorParams(
                    size=VECTOR_DIM, distance=Distance.COSINE
                ))
    return _client


async def _embed(text: str) -> list:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(LAMBDA_URL, json={
            "model_id": "amazon.titan-embed-text-v2:0",
            "inputText": text,
            "stream": False
        })
        r.raise_for_status()
        return r.json()["embedding"]


async def index_transcript(meeting_id: str, transcript: list, meeting_date: str = None):
    client = _get_client()
    date = meeting_date or datetime.utcnow().strftime("%Y-%m-%d")

    # Group consecutive utterances by speaker into chunks
    chunks, current, current_speaker = [], [], None
    for item in transcript:
        speaker = item.get("speaker_name", "Unknown")
        text = item.get("transcription", {}).get("transcript", "").strip()
        if not text:
            continue
        if speaker != current_speaker and current:
            chunks.append({"speaker": current_speaker, "text": " ".join(current)})
            current = []
        current_speaker = speaker
        current.append(text)
    if current:
        chunks.append({"speaker": current_speaker, "text": " ".join(current)})

    points = []
    for c in chunks:
        if not c["text"]:
            continue
        vector = await _embed(c["text"])
        points.append(PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={
                "meeting_id": meeting_id,
                "speaker": c["speaker"],
                "text": c["text"],
                "meeting_date": date,
            }
        ))

    if points:
        client.upsert(collection_name=COLLECTION, points=points)
        return len(points)
    return 0


async def search_transcripts(query: str, from_date: str = None, speaker: str = None, top_k: int = 5) -> list:
    client = _get_client()
    vector = await _embed(query)

    conditions = []
    if from_date:
        conditions.append(FieldCondition(key="meeting_date", range=Range(gte=from_date)))
    if speaker:
        conditions.append(FieldCondition(key="speaker", match=MatchValue(value=speaker)))

    results = client.search(
        collection_name=COLLECTION,
        query_vector=vector,
        limit=top_k,
        query_filter=Filter(must=conditions) if conditions else None,
        with_payload=True,
    )
    return [r.payload for r in results]
