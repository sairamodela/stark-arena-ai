import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from core.message_bus import is_own_bot, parse_mention, shorten_mentions


CASES = [
    ("@tony hello", "tony"),
    ("@Tony_Arena_MasterBot build analyzer", "tony"),
    ("@tony_arena_masterbot hi", "tony"),
    ("@friday research git log", "friday"),
    ("@Friday_Arena_AgentBot research", "friday"),
    ("@friday_research_bot git log", "friday"),
    ("@friday_anything_here", "friday"),
    ("@jarvis implement it", "jarvis"),
    ("@Jarvis_Arena_AgentBot code", "jarvis"),
    ("@jarvis_arena_agentbot hi", "jarvis"),
    ("please ask @friday and @jarvis", "friday"),
    ("cc @jarvis and @tony", "jarvis"),
    ("no mention at all", "tony"),
    ("YES", "tony"),
    ("No keep working", "tony"),
]


def test_parse_mention_variants():
    for text, expected in CASES:
        got = parse_mention(text)
        assert got == expected, f"{text!r} -> {got!r}, expected {expected!r}"


def test_ignore_own_bots():
    assert parse_mention("@friday research", from_user="Tony_Arena_MasterBot") is None
    assert parse_mention("@jarvis go", from_user="Friday_Arena_AgentBot") is None
    assert parse_mention("@tony hi", from_user="Jarvis_Arena_AgentBot") is None
    assert parse_mention("@friday hi", from_user="friday_research_bot") is None
    assert is_own_bot("tony") is False
    assert is_own_bot("Friday_Arena_AgentBot") is True
    assert is_own_bot("human") is False


def test_shorten_mentions():
    assert shorten_mentions("ask @Friday_Arena_AgentBot") == "ask @friday"
    assert shorten_mentions("@Tony_Arena_MasterBot ping @jarvis_arena_agentbot") == "@tony ping @jarvis"


def test():
    test_parse_mention_variants()
    test_ignore_own_bots()
    test_shorten_mentions()
    print("PASS: parse_mention routes tony/friday/jarvis for all username variants")


if __name__ == "__main__":
    test()
