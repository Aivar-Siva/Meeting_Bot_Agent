from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from api.routers import meetings, live, insights, search, webhooks, deepgram, chat

app = FastAPI(title="Meeting Bot API", version="1.0.0")

app.include_router(meetings.router, prefix="/meetings", tags=["meetings"])
app.include_router(live.router, prefix="/ws", tags=["live"])
app.include_router(insights.router, prefix="/meetings", tags=["insights"])
app.include_router(search.router, prefix="/search", tags=["search"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
app.include_router(deepgram.router, prefix="/deepgram", tags=["deepgram"])
app.include_router(chat.router, tags=["chat"])

app.mount("/static", StaticFiles(directory="api/static"), name="static")


@app.get("/")
def root():
    return FileResponse("api/static/index.html")


@app.get("/health")
def health():
    return {"status": "ok"}
