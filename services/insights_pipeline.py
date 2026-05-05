import json
from datetime import datetime
from services.llm_client import chat_insights

PROMPT_TEMPLATE = """You are analyzing a meeting transcript. Return ONLY valid JSON, no explanation.

Transcript:
{transcript}

Return this exact JSON structure:
{{
  "summary": "2-3 sentence summary",
  "key_decisions": ["decision 1", "decision 2"],
  "action_items": [
    {{"owner": "name", "task": "description", "due_date": null}}
  ],
  "topics": ["topic 1", "topic 2"],
  "risks": ["risk 1"],
  "sentiment": {{
    "overall": "positive|neutral|negative",
    "per_speaker": {{"Speaker Name": "positive|neutral|negative"}}
  }}
}}"""


async def generate_insights(meeting_id: str, transcript: list) -> dict:
    # Format transcript as "Speaker: text" lines
    lines = [f"{c.get('speaker_name', 'Unknown')}: {c.get('words', '')}"
             for c in transcript]
    formatted = "\n".join(lines)

    prompt = PROMPT_TEMPLATE.format(transcript=formatted)
    raw = await chat_insights(prompt)

    # Extract JSON from response
    start = raw.find("{")
    end = raw.rfind("}") + 1
    data = json.loads(raw[start:end])

    return {
        "meeting_id": meeting_id,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        **data
    }
