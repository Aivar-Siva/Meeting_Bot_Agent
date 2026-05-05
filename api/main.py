from fastapi import FastAPI
from api.routers import meetings, live, insights, search, webhooks, deepgram

app = FastAPI(title="Meeting Bot API", version="1.0.0")

app.include_router(meetings.router, prefix="/meetings", tags=["meetings"])
app.include_router(live.router, prefix="/ws", tags=["live"])
app.include_router(insights.router, prefix="/meetings", tags=["insights"])
app.include_router(search.router, prefix="/search", tags=["search"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
app.include_router(deepgram.router, prefix="/deepgram", tags=["deepgram"])


@app.get("/health")
def health():
    return {"status": "ok"}
