import asyncio
from collections import defaultdict, deque

class MessageBus:
    def __init__(self):
        self.inboxes = defaultdict(lambda: asyncio.Queue())
        self.threads = defaultdict(list)  # thread_id -> messages
        self.history = defaultdict(lambda: deque(maxlen=500))

    async def send(self, to: str, message: dict):
        thread = message.get('thread_id','main')
        self.threads[thread].append(message)
        self.history[to].append(message)
        await self.inboxes[to].put(message)
        preview = str(message.get("content", ""))[:80]
        print(f"[BUS {thread}] {message.get('from')} -> {to}: {preview}", flush=True)

    async def recv(self, agent_id: str):
        return await self.inboxes[agent_id].get()

    def get_thread(self, thread_id: str):
        return list(self.threads[thread_id])

bus = MessageBus()
