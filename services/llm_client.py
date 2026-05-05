import os, httpx

LAMBDA_URL = os.environ["BEDROCK_LAMBDA_URL"]
INSIGHTS_MODEL = "us.meta.llama4-maverick-17b-instruct-v1:0"
SEARCH_MODEL = "us.meta.llama3-3-70b-instruct-v1:0"


async def chat(prompt: str, model: str = SEARCH_MODEL, max_tokens: int = 1024) -> str:
    """Call Bedrock Lambda proxy and collect SSE streaming response."""
    import json

    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("POST", LAMBDA_URL, json={
            "model_id": model,
            "prompt": prompt,
            "max_gen_len": max_tokens,
        }) as r:
            r.raise_for_status()
            text = ""
            async for line in r.aiter_lines():
                if line.startswith("data: "):
                    try:
                        chunk = json.loads(line[6:])
                        text += chunk.get("generation", "")
                    except Exception:
                        pass
            return text.strip()


async def chat_insights(prompt: str) -> str:
    return await chat(prompt, model=INSIGHTS_MODEL, max_tokens=2048)
