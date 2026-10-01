from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .agent import run_agent
from .tools import DRAFTS, SCHEMES

app = FastAPI(title="Yojana Saathi - Sarkari Yojana AI Agent")
STATIC = Path(__file__).parent.parent / "static"


class ChatIn(BaseModel):
    message: str
    session_id: str = "default"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(body: ChatIn):
    return run_agent(body.session_id, body.message)


@app.get("/schemes")
def schemes():
    return [{"id": s["id"], "name": s["name"], "benefit": s["benefit"]} for s in SCHEMES.values()]


@app.get("/draft/{draft_id}", response_class=PlainTextResponse)
def draft(draft_id: str):
    text = DRAFTS.get(draft_id)
    if text is None:
        raise HTTPException(404, "draft not found")
    return PlainTextResponse(text, headers={"Content-Disposition": f'attachment; filename="letter-{draft_id}.txt"'})


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
