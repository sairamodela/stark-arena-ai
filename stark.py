"""Local-only Stark Arena. One command: python stark.py"""
import asyncio
import logging
import os
import time

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

from core.message_bus import bus
from core.tony_orchestrator import TonyMaster
from agents.friday import FridayAgent
from agents.jarvis import JarvisAgent
from chat.server import app, push
from chat.telegram_adapter_final import GROUP_ID, TOKENS, room as adapter_room
import uvicorn

HOST = "127.0.0.1"
PORT = 8001
AGENTS = ("tony", "friday", "jarvis")
_ORIGINAL_SEND = bus.send


def require_tokens():
    missing = []
    for key in ("TONY_TOKEN", "FRIDAY_TOKEN", "JARVIS_TOKEN"):
        value = os.getenv(key) or ""
        if not value.strip() or "YOUR_NEW" in value or "PUT_" in value:
            missing.append(key)
    if missing:
        raise SystemExit(f"Missing tokens in .env: {', '.join(missing)}")


class LocalTelegramRoom:
    """Three bots, local long-poll only. No webhooks."""

    def __init__(self):
        from telegram import Bot

        self.bots = {}
        for name, token in TOKENS.items():
            if token and "YOUR_NEW" not in token and "PUT_" not in token:
                self.bots[name] = Bot(token=token)
        adapter_room.bots = self.bots

    async def send_as_agent(self, agent_id, content, thread_id=None):
        await adapter_room.send_as_agent(agent_id, content, thread_id)

    async def mirror_local(self, content, thread_id=None):
        await adapter_room.mirror_local(content, thread_id)

    async def run_polling(self):
        await adapter_room.run_polling()


def web_thread(thread_id):
    if thread_id in ("main", "second"):
        return thread_id
    return "main"


def telegram_chat(message):
    thread_id = str(message.get("thread_id") or "")
    if thread_id in ("main", "second", ""):
        return GROUP_ID
    return thread_id


async def bus_to_channels(local_room: LocalTelegramRoom):
    while True:
        message = await bus.recv("user")
        agent_id = message.get("from")
        if agent_id not in AGENTS:
            continue
        web = dict(message)
        web["thread_id"] = web_thread(message.get("thread_id"))
        print(f"[LOCAL] [{agent_id.upper()}] {str(message.get('content') or '')[:80]}", flush=True)
        await push(web)
        chat_id = telegram_chat(message)
        if chat_id:
            print(f"[TELEGRAM] [{agent_id.upper()}] -> {chat_id}", flush=True)
            await local_room.send_as_agent(agent_id, message.get("content") or "", chat_id)


async def run_agent(name, factory):
    while True:
        try:
            print(f"[BUS] starting {name}", flush=True)
            await factory().run()
            print(f"[BUS] {name} stopped; restart in 5s", flush=True)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[BUS] {name} crashed: {exc}; restart in 5s", flush=True)
        await asyncio.sleep(5)


async def serve_web():
    config = uvicorn.Config(app, host=HOST, port=PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def start_once():
    require_tokens()
    local_room = LocalTelegramRoom()

    async def send_and_bridge(to, message):
        await _ORIGINAL_SEND(to, message)
        platform = message.get("platform")
        sender = message.get("from")
        if platform == "telegram" and sender not in AGENTS:
            web = dict(message)
            web["thread_id"] = "main"
            print(f"[LOCAL] telegram user -> {to}: {str(message.get('content') or '')[:80]}", flush=True)
            await push(web)
        elif platform == "local" and sender == "user":
            print(f"[TELEGRAM] local user -> Arena Room: {str(message.get('content') or '')[:80]}", flush=True)
            await local_room.mirror_local(message.get("content") or "", GROUP_ID)

    bus.send = send_and_bridge

    print("STARK ARENA — local only", flush=True)
    print(f"Local: http://{HOST}:{PORT}", flush=True)
    print(f"Telegram Arena Room ID: {GROUP_ID}", flush=True)

    tony_task = asyncio.create_task(run_agent("tony", TonyMaster), name="tony")
    friday_task = asyncio.create_task(run_agent("friday", FridayAgent), name="friday")
    jarvis_task = asyncio.create_task(run_agent("jarvis", JarvisAgent), name="jarvis")
    print("Agents active: tony, friday, jarvis", flush=True)

    await asyncio.gather(
        tony_task,
        friday_task,
        jarvis_task,
        serve_web(),
        local_room.run_polling(),
        bus_to_channels(local_room),
    )


def main():
    require_tokens()
    while True:
        try:
            asyncio.run(start_once())
        except KeyboardInterrupt:
            print("Stark stopped", flush=True)
            return
        except Exception as exc:
            print(f"[BUS] process error: {exc}; restart in 5s", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
