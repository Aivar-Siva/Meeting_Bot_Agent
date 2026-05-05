import os, httpx

LAMBDA_URL = os.environ["BEDROCK_LAMBDA_URL"]
INSIGHTS_MODEL = "us.meta.llama4-maverick-17b-instruct-v1:0"
SEARCH_MODEL = "us.meta.llama3-3-70b-instruct-v1:0"


async def chat(prompt: str, model: str = SEARCH_MODEL, max_tokens: int = 1024) -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(LAMBDA_URL, json={
            "model_id": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        })
        r.raise_for_status()
        data = r.json()
        # Handle both response formats from the proxy
        if "content" in data:
            return data["content"][0]["text"]
        return data.get("generation", data.get("output", ""))


async def chat_insights(prompt: str) -> str:
    return await chat(prompt, model=INSIGHTS_MODEL, max_tokens=2048)
