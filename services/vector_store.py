import os
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, Range
from sentence_transformers import SentenceTransformer
import uuid

COLLECTION = "transcripts"
VECTOR_DIM = 384

_client = None
_model = None


def _get_client():
    global _client
    if _client is None:
        _client = QdrantClient(url=os.environ.get("QDRANT_URL", "http://localhost:6333"))
        # Create collection if not exists
        existing = [c.name for c in _client.get_collections().collections]
        if COLLECTION not in existing:
            _client.create_collection(COLLECTION, vectors_config=VectorParams(
                size=VECTOR_DIM, distance=Distance.COSINE
            ))
    return _client


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _embed(text: str) -> list:
    return _get_model().encode(text).tolist()


async def index_transcript(meeting_id: str, transcript: list, meeting_date: str = None):
    client = _get_client()
    date = meeting_date or datetime.utcnow().strftime("%Y-%m-%d")

    # Chunk transcript into ~200-word pieces
    chunks, current, current_speaker = [], [], None
    for item in transcript:
        speaker = item.get("speaker_name", "Unknown")
        text = item.get("words", "").strip()
        if not text:
            continue
        if speaker != current_speaker and current:
            chunks.append({"speaker": current_speaker, "text": " ".join(current)})
            current = []
        current_speaker = speaker
        current.append(text)
    if current:
        chunks.append({"speaker": current_speaker, "text": " ".join(current)})

    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=_embed(c["text"]),
            payload={
                "meeting_id": meeting_id,
                "speaker": c["speaker"],
                "text": c["text"],
                "meeting_date": date,
            }
        )
        for c in chunks if c["text"]
    ]
    if points:
        client.upsert(collection_name=COLLECTION, points=points)


async def search_transcripts(query: str, from_date: str = None, speaker: str = None, top_k: int = 5) -> list:
    client = _get_client()
    vector = _embed(query)

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
