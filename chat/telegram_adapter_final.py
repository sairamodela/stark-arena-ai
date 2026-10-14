"""Telegram group = one Stark room. Tokens come from .env."""
import asyncio
import logging
import os

from dotenv import load_dotenv

load_dotenv()

from core.message_bus import bus, is_own_bot, parse_mention, shorten_mentions

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger("stark.telegram")

TOKENS = {
    "tony": os.getenv("TONY_TOKEN"),
    "friday": os.getenv("FRIDAY_TOKEN"),
    "jarvis": os.getenv("JARVIS_TOKEN"),
}
GROUP_ID = os.getenv("TELEGRAM_GROUP_ID")
EXPLICIT_YES = {"yes", "y", "yes work done"}
APPROVAL_TEXT = EXPLICIT_YES | {"no", "no keep working", "keep working"}
PLACEHOLDER_GROUP = "-1001234567890"


def is_explicit_yes(text: str) -> bool:
    return (text or "").strip().lower() in EXPLICIT_YES


def is_approval_text(text: str) -> bool:
    return (text or "").strip().lower() in APPROVAL_TEXT


def _accept_chat(chat_id: str) -> bool:
    global GROUP_ID
    if not GROUP_ID or GROUP_ID == PLACEHOLDER_GROUP:
        GROUP_ID = str(chat_id)
        _save_group_id(GROUP_ID)
        log.info("Learned Telegram group id %s", GROUP_ID)
        return True
    return str(chat_id) == str(GROUP_ID)


def _save_group_id(chat_id: str):
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    try:
        lines = open(path).read().splitlines() if os.path.exists(path) else []
    except OSError:
        return
    found = False
    updated = []
    for line in lines:
        if line.startswith("TELEGRAM_GROUP_ID="):
            updated.append(f"TELEGRAM_GROUP_ID={chat_id}")
            found = True
        else:
            updated.append(line)
    if not found:
        updated.append(f"TELEGRAM_GROUP_ID={chat_id}")
    try:
        open(path, "w").write("\n".join(updated) + "\n")
    except OSError as exc:
        log.warning("Could not save group id: %s", exc)


class StarkTelegramRoom:
    def __init__(self):
        from telegram import Bot

        self.bots = {}
        self._seen = set()
        for name, token in TOKENS.items():
            if token and "YOUR_NEW" not in token and "PUT_" not in token:
                self.bots[name] = Bot(token=token)
                log.info("[TELEGRAM] Bot ready: %s", name)
        if GROUP_ID == PLACEHOLDER_GROUP:
            log.warning("TELEGRAM_GROUP_ID is still the placeholder. Replace it with the real group id.")

    async def handle_telegram_message(self, text: str, chat_id: str, from_user: str):
        if not text or not str(text).strip():
            return None
        if is_own_bot(from_user):
            log.info("[TELEGRAM] Ignoring own bot message from %s", from_user)
            return None
        if not _accept_chat(chat_id):
            log.info("[TELEGRAM] Ignoring chat %s; room is %s", chat_id, GROUP_ID)
            return None

        to_agent = parse_mention(text, from_user) or "tony"

        msg_type = "approval" if is_approval_text(text) else "user_msg"
        message = {
            "from": from_user or "human",
            "to": to_agent,
            "thread_id": str(chat_id),
            "platform": "telegram",
            "type": msg_type,
            "content": text,
            "chat_id": str(chat_id),
            "depth": 0,
        }
        log.info("[TELEGRAM] %s %s -> %s (%s): %s", chat_id, from_user, to_agent, msg_type, text[:80])
        await bus.send(to=to_agent, message=message)
        return message

    async def mirror_local(self, content: str, thread_id: str = None):
        thread_id = str(thread_id or GROUP_ID or "")
        bot = self.bots.get("tony")
        if not bot or not thread_id:
            return
        text = f"[LOCAL] {shorten_mentions(content or '')}"
        try:
            await bot.send_message(chat_id=thread_id, text=text[:4000])
            log.info("[TELEGRAM] mirrored local message to %s", thread_id)
        except Exception as exc:
            log.error("[TELEGRAM] local mirror failed: %s", exc)

    async def send_as_agent(self, agent_id: str, content: str, thread_id: str = None):
        thread_id = str(thread_id or GROUP_ID or "")
        bot = self.bots.get(agent_id)
        if not bot or not thread_id:
            log.warning("No bot or group for %s", agent_id)
            return
        emoji = {"tony": "🧠", "friday": "🔍", "jarvis": "🔧"}.get(agent_id, "🤖")
        formatted = f"{emoji} [{agent_id.upper()}]: {shorten_mentions(content or '')}"
        chunks = [formatted[i:i + 4000] for i in range(0, len(formatted), 4000)] or [formatted]
        for chunk in chunks:
            try:
                await bot.send_message(chat_id=thread_id, text=chunk)
                log.info("[TELEGRAM SEND] %s -> %s (%s chars)", agent_id, thread_id, len(chunk))
            except Exception as exc:
                log.error("[TELEGRAM ERROR %s]: %s", agent_id, exc)

    def _mark_seen(self, chat_id, message_id) -> bool:
        key = (str(chat_id), int(message_id))
        if key in self._seen:
            return False
        self._seen.add(key)
        if len(self._seen) > 5000:
            self._seen = set(list(self._seen)[-2500:])
        return True

    async def poll_bot(self, name: str):
        bot = self.bots.get(name)
        if bot is None:
            log.warning("[TELEGRAM] %s token missing. Polling skipped.", name)
            return
        # python-telegram-bot 20.7 Application/Updater crashes on Python 3.13+.
        # Bot.get_updates is the same local long-poll, without webhooks.
        await bot.delete_webhook(drop_pending_updates=True)
        offset = None
        log.info("[TELEGRAM] polling %s for group %s", name, GROUP_ID)
        while True:
            try:
                updates = await bot.get_updates(
                    offset=offset,
                    timeout=30,
                    allowed_updates=["message", "my_chat_member"],
                )
            except Exception as exc:
                log.error("[TELEGRAM] %s poll error: %s", name, exc)
                await asyncio.sleep(5)
                continue
            for update in updates:
                offset = update.update_id + 1
                member = update.my_chat_member
                if member is not None:
                    log.info(
                        "[TELEGRAM] %s membership in chat %s (%s)",
                        name,
                        member.chat.id,
                        member.chat.title,
                    )
                    _accept_chat(str(member.chat.id))
                message = update.message
                if message is None or not message.text:
                    continue
                if message.text.startswith("/"):
                    continue
                if not self._mark_seen(message.chat_id, message.message_id):
                    continue
                user = message.from_user
                if user is not None and user.is_bot:
                    continue
                await self.handle_telegram_message(
                    message.text,
                    str(message.chat_id),
                    (user.username if user else None) or "human",
                )

    async def run_polling(self):
        if not self.bots:
            log.warning("[TELEGRAM] no bot tokens. Polling skipped.")
            return
        await asyncio.gather(*[self.poll_bot(name) for name in self.bots])

    async def ensure_webhook(self):
        base = (os.getenv("TELEGRAM_WEBHOOK_BASE") or "").rstrip("/")
        bot = self.bots.get("tony")
        if not base or bot is None:
            log.warning("Webhook mode needs TELEGRAM_WEBHOOK_BASE and TONY_TOKEN.")
            return
        url = f"{base}/telegram/webhook/tony"
        await bot.set_webhook(url)
        log.info("Tony webhook set to %s", url)


room = StarkTelegramRoom()


def register_webhook(app):
    from fastapi import Request

    @app.post("/telegram/webhook/{bot_name}")
    async def telegram_webhook(bot_name: str, request: Request):
        if bot_name != "tony":
            return {"ok": True}
        data = await request.json()
        message = data.get("message") or {}
        text = message.get("text") or ""
        chat = message.get("chat") or {}
        user = message.get("from") or {}
        if not text or "id" not in chat or user.get("is_bot"):
            return {"ok": True}
        await room.handle_telegram_message(text, str(chat["id"]), user.get("username") or "human")
        return {"ok": True}
