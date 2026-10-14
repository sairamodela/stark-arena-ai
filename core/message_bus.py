import asyncio
import re
from collections import defaultdict, deque

MENTION_RE = re.compile(
    r"@(tony|friday|jarvis)(?:_\w+)?(?:_arena_\w+bot)?",
    re.IGNORECASE,
)
OWN_BOTS = {
    "tony_arena_masterbot",
    "friday_arena_agentbot",
    "jarvis_arena_agentbot",
    "tonyystarkkmasterr",
}


def is_own_bot(from_user: str) -> bool:
    name = (from_user or "").lstrip("@").lower()
    if not name or name in ("tony", "friday", "jarvis", "user", "human"):
        return False
    if name in OWN_BOTS:
        return True
    return bool(re.fullmatch(r"(tony|friday|jarvis)(?:_\w+)+", name))


def shorten_mentions(text: str) -> str:
    return MENTION_RE.sub(lambda match: "@" + match.group(1).lower(), text or "")


def parse_mention(text: str, from_user: str = None) -> str:
    """Route @tony / @Tony_Arena_MasterBot / @friday_research_bot to tony|friday|jarvis."""
    if is_own_bot(from_user):
        return None
    found = [match.group(1).lower() for match in MENTION_RE.finditer(text or "")]
    if "friday" in found:
        return "friday"
    if "jarvis" in found:
        return "jarvis"
    if "tony" in found:
        return "tony"
    return "tony"


class MessageBus:
    def __init__(self):
        self.inboxes = defaultdict(lambda: asyncio.Queue())
        self.threads = defaultdict(list)
        self.history = defaultdict(lambda: deque(maxlen=500))

    async def send(self, to: str, message: dict):
        if to not in ("tony", "friday", "jarvis", "user"):
            to = parse_mention(message.get("content"), message.get("from")) or "tony"
            message["to"] = to
        thread = message.get("thread_id", "main")
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
