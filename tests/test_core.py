import asyncio
import json
import re
import sqlite3
import time
from pathlib import Path

import pytest

import strings as strings_mod
from appconfig import parse_id_list, parse_snowflake
from store import Store, clean_reason

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _strings():
    strings_mod.load_strings()


# ── appconfig ────────────────────────────────────────────────────────────────
def test_snowflake_parsing():
    assert parse_snowflake(123456789012345678) == 123456789012345678
    assert parse_snowflake("123456789012345678") == 123456789012345678
    for bad in (True, 0, -5, "-5", "12a", "²", "٣٣٣", "", None, 1.5, 2 ** 63, "9" * 25, [1]):
        assert parse_snowflake(bad) is None, bad


def test_id_list_ignores_bad_entries():
    assert parse_id_list([1, "2", "x", True, None], "admins") == frozenset({1, 2})
    assert parse_id_list("nope", "admins") == frozenset()
    assert parse_id_list(None, "admins") == frozenset()


# ── strings ──────────────────────────────────────────────────────────────────
def test_render_never_crashes_and_does_not_reformat_values():
    assert strings_mod.render("troll_ctl_unban_success", {"id": "{evil}"}) == "✅ Unbanned `{evil}`."
    assert "troll_ctl_unban_success" not in strings_mod.render("troll_ctl_unban_success", {})   # missing value: template shown
    assert strings_mod.render("no_such_key", {}) == "«no_such_key»"


def test_command_names_localise_template_not_user_text():
    from trollenator import CommandNames, t
    CommandNames.prefix = "trolle-"
    try:
        assert "/trolle-embed" in t("troll_embed_expired")
        out = t("troll_embed_message", content="please run /say now")
        assert "/say now" in out and "trolle-" not in out
    finally:
        CommandNames.prefix = ""


def test_every_string_key_used_in_code_exists():
    from control import missing_string_keys
    assert missing_string_keys() == []


def test_no_stale_hombre_names_and_all_placeholders_balanced():
    data = json.loads((ROOT / "Configs" / "strings.json").read_text(encoding="utf-8"))
    for key, text in data.items():
        if key.startswith("_"):
            continue
        assert "hombre" not in text.lower(), key
        assert "bot" not in text, key
        list(__import__("string").Formatter().parse(text))        # raises on unbalanced braces


# ── store ────────────────────────────────────────────────────────────────────
def run(coro):
    return asyncio.run(coro)


def test_store_roundtrip_and_restart(tmp_path):
    async def go():
        db = Store(tmp_path / "t.db")
        await db.init()
        assert db.active_ban(5) is None
        ban = await db.add_ban(5, reason="  spam\n\x00 ads ", banned_by=1, expires_at=None, notify=True)
        assert ban and ban.reason == "spam ads" and ban.notify
        assert await db.add_ban(5, reason="again", banned_by=1, expires_at=None, notify=False) is None   # already banned
        assert db.active_ban(5).reason == "spam ads"
        assert (await db.set_reason(5, "new")).reason == "new"
        assert await db.set_reason(99, "x") is None
        await db.close()
        db2 = Store(tmp_path / "t.db")                       # survives a restart
        await db2.init()
        assert db2.active_ban(5).reason == "new" and db2.active_ban(5).notify
        assert await db2.remove_ban(5) is True
        assert await db2.remove_ban(5) is False
        assert db2.active_ban(5) is None
        await db2.close()
    run(go())


def test_expired_bans_are_ignored_and_replaceable(tmp_path):
    async def go():
        db = Store(tmp_path / "t.db")
        await db.init()
        past = int(time.time()) - 10
        await db.add_ban(7, reason="old", banned_by=1, expires_at=past, notify=False)
        assert db.active_ban(7) is None and db.list_bans() == []     # expired = not banned, immediately
        assert (await db.add_ban(7, reason="fresh", banned_by=1, expires_at=None, notify=False)).reason == "fresh"
        await db.close()
        con = sqlite3.connect(tmp_path / "t.db")
        assert con.execute("SELECT count(*) FROM user_bans").fetchone()[0] == 1
        con.close()
    run(go())


def test_concurrent_bans_only_one_wins(tmp_path):
    async def go():
        db = Store(tmp_path / "t.db")
        await db.init()
        results = await asyncio.gather(*(db.add_ban(3, reason=str(i), banned_by=1, expires_at=None, notify=False) for i in range(20)))
        assert sum(r is not None for r in results) == 1
        await db.close()
    run(go())


def test_sql_injection_and_big_ids_are_just_data(tmp_path):
    async def go():
        db = Store(tmp_path / "t.db")
        await db.init()
        evil = "x'); DROP TABLE user_bans;--"
        big = 2 ** 63 - 1
        await db.add_ban(big, reason=evil, banned_by=big, expires_at=None, notify=False)
        assert db.active_ban(big).reason == evil
        await db.close()
        db2 = Store(tmp_path / "t.db")
        await db2.init()
        assert db2.active_ban(big).reason == evil
        await db2.close()
    run(go())


def test_reason_is_capped():
    assert len(clean_reason("a" * 5000)) == 300


# ── control helpers ──────────────────────────────────────────────────────────
def test_user_ref_and_duration_parsing():
    from control import MAX_BAN_SECONDS, parse_ban_duration, parse_user_ref
    assert parse_user_ref("<@123456789012345678>") == 123456789012345678
    assert parse_user_ref("<@!123456789012345678>") == 123456789012345678
    assert parse_user_ref(" 123456789012345678 ") == 123456789012345678
    for bad in ("<@12> junk", "@everyone", "²²²", "1e5", "", "-1", "<@&123>"):
        assert parse_user_ref(bad) is None, bad
    assert parse_ban_duration("30m") == 1800 and parse_ban_duration("2W") == 1209600
    for bad in ("", "0m", "1", "1y", "10 d", "99999d", "9999w", "-5m", "1.5h"):
        with pytest.raises(ValueError):
            parse_ban_duration(bad)
    assert parse_ban_duration("1800d") <= MAX_BAN_SECONDS


def test_control_settings_validation():
    from control import ADMIN, MOD, ControlSettings
    tok = "A" * 24 + "." + "b" * 6 + "." + "c" * 30
    s, problems = ControlSettings.from_config({})
    assert s is None and problems
    s, _ = ControlSettings.from_config({"control_token": tok})
    assert s is None                                               # no guild id → refuses to run
    s, _ = ControlSettings.from_config({"control_token": tok, "control_guild_id": "x"})
    assert s is None
    s, problems = ControlSettings.from_config({"control_token": "has space", "control_guild_id": 5})
    assert s is None
    s, problems = ControlSettings.from_config({"control_token": tok, "control_guild_id": 5, "admins": [1, 2], "mods": [2, 3, "bad"]})
    assert s and not problems and s.guild_id == 5
    assert s.level_of(1) == ADMIN and s.level_of(2) == ADMIN and s.level_of(3) == MOD and s.level_of(4) is None   # an admin listed as mod stays admin
    s, problems = ControlSettings.from_config({"control_token": tok, "control_guild_id": 5})
    assert s and problems                                          # runs, but warns that nobody is admin


def test_control_token_is_never_a_user_app():
    from trollenator import parse_bot_entries, token_key
    a = "A" * 24 + "." + "b" * 6 + "." + "c" * 30
    b = "B" * 24 + "." + "b" * 6 + "." + "c" * 30
    entries = parse_bot_entries({"token": a, "tokens": [b, {"token": a}]}, frozenset({token_key(a)}))
    assert [e.token for e in entries] == [b]


# ── command trees (offline: nothing logs in) ─────────────────────────────────
def test_command_trees_are_what_we_expect():
    import discord
    from control import ControlBot, ControlCommands, ControlSettings
    from store import Store as S
    from trollenator import BASE_COMMANDS, TrollenatorBot, TrollenatorHost, make_prefix, BotEntry

    async def go():
        host = TrollenatorHost({}, S(Path("/nonexistent")))
        settings = ControlSettings(token="x", guild_id=5, admins=frozenset({1}), mods=frozenset({2}))
        control = ControlBot(host, settings)
        guild = discord.Object(id=5)
        await control.add_cog(ControlCommands(control), guild=guild)
        names = sorted(c.name for c in control.tree.get_commands(guild=guild))
        assert names == ["ban", "baninfo", "banedit", "bans", "devpannel", "unban"] or names == sorted(["ban", "baninfo", "banedit", "bans", "devpannel", "unban"])
        assert control.tree.get_commands() == []                  # nothing global: the commands exist only in the control server
        assert control.intents.guilds and not control.intents.message_content and not control.intents.members
        for cmd in control.tree.get_commands(guild=guild):
            d = cmd.to_dict(control.tree)
            assert d["name"] == cmd.name

        troll = TrollenatorBot(host, BotEntry(token="t", key="k"))
        troll.cmd_prefix = make_prefix("Trollenator")
        from trollenator import TrollCommands
        await troll.add_cog(TrollCommands(troll))
        troll._apply_command_prefix()
        got = sorted(c.name for c in troll.tree.get_commands())
        assert got == sorted(f"trolle-{b}" for b in BASE_COMMANDS)
        assert "devpannel" not in " ".join(got)                   # the dev panel is not reachable through the user app
    run(go())
