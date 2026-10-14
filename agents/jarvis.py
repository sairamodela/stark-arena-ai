from agents.base import BaseAgent
from core.arena_client import ask_arena, channel_prompt
from core.tony_orchestrator import agent_mode_enabled

class JarvisAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Jarvis", agent_id="jarvis", role="Coder")

    async def handle_mention(self, msg):
        content = msg.get("content") or ""
        sender = msg.get("from") or "user"
        depth = int(msg.get("depth") or 0)
        if not agent_mode_enabled():
            self.relay = False
            return "[Jarvis] Agent Mode is off."
        if sender == "friday" or depth >= 1:
            self.relay = False
        try:
            return await ask_arena("jarvis", channel_prompt("Jarvis", sender, content))
        except Exception as exc:
            self.relay = False
            return f"[Jarvis] Arena error: {exc}"
