from agents.base import BaseAgent
from core.arena_client import ask_arena, channel_prompt
from core.message_bus import bus
from chat.telegram_adapter_final import is_explicit_yes
import yaml, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
PRIMARY_CONFIG = ROOT / ".github" / "agents.yml"
CONFIG_CANDIDATES = (
    PRIMARY_CONFIG,
    ROOT / ".github" / "agents.yaml",
    ROOT / "agents.yaml",
    ROOT / "agents.yml",
)
DEFAULT_CONFIG = {
    "agent_mode": True,
    "github_toggle": True,
    "master": "tony",
    "agents": {"friday": "researcher", "jarvis": "coder"},
    "all_in_one_channel": True,
}

def load_config():
    for path in CONFIG_CANDIDATES:
        try:
            if path.exists():
                data = yaml.safe_load(path.read_text()) or {}
                merged = dict(DEFAULT_CONFIG)
                merged.update(data)
                merged["agent_mode"] = bool(merged.get("agent_mode", True))
                merged["github_toggle"] = bool(merged.get("github_toggle", True))
                return merged
        except Exception:
            continue
    return dict(DEFAULT_CONFIG)

def save_config(agent_mode, github_toggle):
    data = load_config()
    data["agent_mode"] = bool(agent_mode)
    data["github_toggle"] = bool(github_toggle)
    PRIMARY_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    PRIMARY_CONFIG.write_text(yaml.safe_dump(data, sort_keys=False))
    return load_config()

def agent_mode_enabled():
    return load_config()["agent_mode"]

def github_toggle_enabled():
    return load_config()["github_toggle"]

class TonyMaster(BaseAgent):
    def __init__(self):
        super().__init__(name="Tony", agent_id="tony", role="Master Orchestrator")

    def _outbound(self, msg, target, content, msg_type):
        return {
            "from": self.id,
            "to": target,
            "thread_id": msg.get("thread_id", "main"),
            "platform": msg.get("platform"),
            "type": msg_type,
            "content": content,
            "depth": int(msg.get("depth") or 0) + 1,
        }

    async def handle_mention(self, msg):
        content = msg.get("content") or ""
        sender = msg.get("from") or "user"
        depth = int(msg.get("depth") or 0)
        if msg.get("type") == "approval":
            self.relay = False
            if is_explicit_yes(content):
                await bus.send(to="jarvis", message=self._outbound(
                    msg, "jarvis", "Human approved YES - write REPORT.md", "write_final"
                ))
                return "Perfect satisfaction - writing final"
            await bus.send(to="friday", message=self._outbound(
                msg, "friday", "Human wants more work - research deeper. Keep working.", "continue"
            ))
            await bus.send(to="jarvis", message=self._outbound(
                msg, "jarvis", "Human wants more work - keep building. Keep working.", "continue"
            ))
            return "Continuing work as requested. Keep working."
        if not agent_mode_enabled():
            self.relay = False
            return "[Tony] Direct mode. Switch the chat back to Agent Mode."
        if sender in ("friday", "jarvis") or depth >= 1:
            self.relay = False
        try:
            return await ask_arena("tony", channel_prompt("Tony", sender, content))
        except Exception as exc:
            self.relay = False
            return f"[Tony] Arena error: {exc}"
