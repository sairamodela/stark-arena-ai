from agents.base import BaseAgent
from core.arena_client import ask_arena, channel_prompt
from core.tony_orchestrator import agent_mode_enabled

class FridayAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Friday", agent_id="friday", role="Researcher")

    async def handle_mention(self, msg):
        content = msg.get("content") or ""
        sender = msg.get("from") or "user"
        depth = int(msg.get("depth") or 0)
        if not agent_mode_enabled():
            self.relay = False
            return "[Friday] Agent Mode is off."
        if sender == "jarvis" or depth >= 1:
            self.relay = False
        try:
            return await ask_arena("friday", channel_prompt("Friday", sender, content))
        except Exception as exc:
            self.relay = False
            return f"[Friday] Arena error: {exc}"
