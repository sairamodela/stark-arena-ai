import asyncio
from core.message_bus import bus
from core.tony_orchestrator import TonyMaster
from agents.friday import FridayAgent
from agents.jarvis import JarvisAgent
from chat.server import app, push
import uvicorn

# Same event loop as the agents. A second thread cannot wake asyncio.Queue waiters.
original_send = bus.send

async def send_and_broadcast(to, message):
    await original_send(to, message)
    if message.get("to") == "user":
        await push(message)

bus.send = send_and_broadcast

async def main():
    tony = TonyMaster()
    friday = FridayAgent()
    jarvis = JarvisAgent()
    print("STARK ARENA - All 3 in ONE channel", flush=True)
    print("Tony (master) + Friday (researcher) + Jarvis (coder)", flush=True)
    print("Open http://127.0.0.1:8000", flush=True)
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await asyncio.gather(server.serve(), tony.loop(), friday.loop(), jarvis.loop())

if __name__ == "__main__":
    asyncio.run(main())
