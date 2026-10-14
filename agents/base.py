import re
from core.message_bus import bus

def has_keyword(text, words):
    low = (text or "").lower()
    return any(re.search(rf"(?<!\w){re.escape(word)}(?!\w)", low) for word in words)

class BaseAgent:
    def __init__(self, name, agent_id, role):
        self.name = name
        self.id = agent_id
        self.role = role
        self.running = True
        self.relay = True

    async def handle_mention(self, msg):
        return f"[{self.name}] got: {msg.get('content', '')}"

    async def loop(self):
        while self.running:
            msg = await bus.recv(self.id)
            self.relay = True
            thread_id = msg.get("thread_id", "main")
            try:
                content = await self.handle_mention(msg) or ""
                depth = int(msg.get("depth") or 0)
                if self.relay and depth < 2:
                    low = content.lower()
                    incoming = (msg.get("content") or "").lower()
                    for target in ("tony", "friday", "jarvis"):
                        # Only mentions this agent just added. Quoted @names must not bounce.
                        if f"@{target}" in low and f"@{target}" not in incoming and target != self.id:
                            await bus.send(to=target, message={
                                "from": self.id,
                                "to": target,
                                "thread_id": thread_id,
                                "type": "delegation",
                                "content": content,
                                "quote_ref": msg.get("content"),
                                "depth": depth + 1,
                            })
                await bus.send(to="user", message={
                    "from": self.id,
                    "to": "user",
                    "thread_id": thread_id,
                    "type": "chat",
                    "content": content,
                    "depth": depth,
                })
            except Exception as exc:
                print(f"[{self.id}] {exc}", flush=True)
                try:
                    await bus.send(to="user", message={
                        "from": self.id,
                        "to": "user",
                        "thread_id": thread_id,
                        "type": "chat",
                        "content": f"[{self.name}] hit an error: {exc}",
                    })
                except Exception as send_exc:
                    print(f"[{self.id}] failed to report error: {send_exc}", flush=True)

    def quote_and_ask(self, quoted, question):
        return f"> {quoted}\n\n{question}"
