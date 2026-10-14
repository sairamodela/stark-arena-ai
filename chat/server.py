from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from core.arena_client import complete_job, take_job
from core.message_bus import bus, parse_mention
import asyncio, pathlib

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://arena.ai"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
clients = []
_send_lock = asyncio.Lock()
CHAT_DIR = pathlib.Path(__file__).resolve().parent
CLIENT_HTML = CHAT_DIR / "client.html"

app.mount("/static", StaticFiles(directory=str(CHAT_DIR)), name="static")

@app.get("/")
async def root():
    return FileResponse(CLIENT_HTML, headers={"Cache-Control": "no-cache"})

@app.get("/arena/job")
async def arena_job():
    return take_job()

@app.post("/arena/job")
async def arena_job_done(request: Request):
    data = await request.json()
    complete_job(data.get("id"), reply=data.get("reply"), error=data.get("error"))
    return {"ok": True}

@app.get("/health")
async def health():
    from core.tony_orchestrator import load_config
    config = load_config()
    return {
        "status": "Stark Arena - Tony + Friday + Jarvis - All 3 in ONE channel",
        "channels": ["main #build-room", "second #research-room"],
        "agent_mode": config["agent_mode"],
        "github_toggle": config["github_toggle"],
        "mode": "agent" if config["agent_mode"] else "direct",
    }

@app.post("/settings")
async def settings(request: Request):
    from core.tony_orchestrator import load_config, save_config
    payload = await request.json()
    current = load_config()
    agent_mode = payload.get("agent_mode", current["agent_mode"])
    github_toggle = payload.get("github_toggle", current["github_toggle"])
    saved = save_config(agent_mode, github_toggle)
    return {
        "agent_mode": saved["agent_mode"],
        "github_toggle": saved["github_toggle"],
        "mode": "agent" if saved["agent_mode"] else "direct",
    }

async def push(message):
    # One sender at a time. Agent replies can otherwise overlap the user echo.
    async with _send_lock:
        dead = []
        for ws in list(clients):
            try:
                await ws.send_json(message)
            except Exception as exc:
                print(f"[ws] drop client: {exc}", flush=True)
                dead.append(ws)
        for ws in dead:
            if ws in clients:
                clients.remove(ws)

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    clients.append(ws)
    try:
        while True:
            data = await ws.receive_json()
            content = (data.get("content") or "").strip()
            if not content:
                continue
            thread_id = data.get("thread_id") or "main"
            if thread_id not in ("main", "second"):
                thread_id = "main"
            to = parse_mention(content) or "tony"
            msg = {
                "from": "user",
                "to": to,
                "thread_id": thread_id,
                "platform": "local",
                "type": "user_msg",
                "content": content,
                "quote_ref": data.get("quote"),
                "depth": 0,
            }
            await bus.send(to=to, message=msg)
            await push(msg)
    except Exception as exc:
        print(f"ws disconnect {exc}", flush=True)
    finally:
        if ws in clients:
            clients.remove(ws)
