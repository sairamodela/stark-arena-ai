import asyncio
import pathlib
import sys
from unittest.mock import AsyncMock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from chat.telegram_adapter_final import GROUP_ID, PLACEHOLDER_GROUP, StarkTelegramRoom, is_explicit_yes
from core.message_bus import bus


async def test_routing():
    room = StarkTelegramRoom()
    sent = []

    async def capture(to, message):
        sent.append((to, message))

    original = bus.send
    bus.send = capture
    try:
        chat = GROUP_ID or PLACEHOLDER_GROUP
        await room.handle_telegram_message("@friday find the bug", chat, "human")
        await room.handle_telegram_message("@Friday_Arena_AgentBot git log", chat, "human")
        await room.handle_telegram_message("@jarvis build it", chat, "human")
        await room.handle_telegram_message("hello team", chat, "human")
        await room.handle_telegram_message("YES", chat, "human")
        await room.handle_telegram_message("No keep working", chat, "human")
        ignored = await room.handle_telegram_message("loop", chat, "Tony_Arena_MasterBot")
    finally:
        bus.send = original

    chat = GROUP_ID or PLACEHOLDER_GROUP
    assert ignored is None
    assert sent[0][0] == "friday" and sent[0][1]["thread_id"] == str(chat)
    assert sent[1][0] == "friday"
    assert sent[2][0] == "jarvis"
    assert sent[3][0] == "tony" and sent[3][1]["type"] == "user_msg"
    assert sent[4][1]["type"] == "approval" and is_explicit_yes(sent[4][1]["content"])
    assert sent[5][1]["type"] == "approval" and not is_explicit_yes(sent[5][1]["content"])
    print("PASS: Telegram routing and approval")


async def test_send_as_agent():
    room = StarkTelegramRoom()
    fake = AsyncMock()
    room.bots["tony"] = fake
    chat = GROUP_ID or PLACEHOLDER_GROUP
    await room.send_as_agent("tony", "hello room", chat)
    await room.send_as_agent("tony", "x" * 5000, chat)
    assert fake.send_message.await_count == 3
    first = fake.send_message.await_args_list[0].kwargs
    assert first["chat_id"] == str(chat)
    assert first["text"].startswith("🧠 [TONY]:")
    assert len(fake.send_message.await_args_list[1].kwargs["text"]) <= 4000
    print("PASS: send_as_agent format and length")


def test():
    asyncio.run(test_routing())
    asyncio.run(test_send_as_agent())
    print("\nAll telegram tests PASS")


if __name__ == "__main__":
    test()
