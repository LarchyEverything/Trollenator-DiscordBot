"""Offline flow tests: fake interactions drive the real command code (nothing talks to Discord)."""
import asyncio
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

import strings as strings_mod
from control import ControlBot, ControlCommands, ControlSettings, ControlTree
from store import Store
from trollenator import BotEntry, TrollenatorBot, TrollenatorHost

GUILD, ADMIN, MOD, RANDOM = 5, 1000000000000000001, 1000000000000000002, 1000000000000000003
TARGET = 1000000000000000009


@pytest.fixture(autouse=True)
def _strings():
    strings_mod.load_strings()


def fake_interaction(user_id, guild_id=GUILD):
    i = MagicMock()
    i.user = SimpleNamespace(id=user_id, name="u", __str__=lambda s: "u")
    i.guild_id = guild_id
    i.id = 42
    i.token = "tok"
    i.extras = {}
    i.created_at = discord.utils.utcnow()
    i.type = discord.InteractionType.application_command
    i.command = SimpleNamespace(qualified_name="ban")
    i.response.is_done.return_value = False
    i.response.defer = AsyncMock()
    i.response.send_message = AsyncMock()
    i.followup.send = AsyncMock()
    return i


async def make(tmp_path):
    store = Store(tmp_path / "t.db")
    await store.init()
    host = TrollenatorHost({}, store)
    settings = ControlSettings(token="x", guild_id=GUILD, admins=frozenset({ADMIN}), mods=frozenset({MOD}))
    control = ControlBot(host, settings)
    control.fetch_user = AsyncMock(return_value=SimpleNamespace(name="Target", display_avatar=SimpleNamespace(url="https://x/y.png")))
    return store, host, control, ControlCommands(control)


def sent(i):
    """Everything said privately to the invoker, as one string."""
    calls = list(i.response.send_message.call_args_list) + list(i.followup.send.call_args_list)
    return "\n".join(str(c.args[0]) if c.args else str(c.kwargs.get("content", c.kwargs.get("embed"))) for c in calls)


def test_ban_unban_cycle_and_permissions(tmp_path):
    async def go():
        store, host, control, cog = await make(tmp_path)
        # mod bans a user
        i = fake_interaction(MOD)
        await cog.ban.callback(cog, i, user=f"<@{TARGET}>", notify="yes", duration="1h", reason="spam")
        assert "Banned" in sent(i) and store.active_ban(TARGET).notify
        assert 3500 < store.active_ban(TARGET).expires_at - time.time() <= 3600
        # again → already banned, nothing changed
        i = fake_interaction(MOD)
        await cog.ban.callback(cog, i, user=str(TARGET), notify=None, duration=None, reason=None)
        assert "already banned" in sent(i)
        # mod cannot ban an admin, a mod, or themselves; admin can ban a mod but not themselves
        for target in (ADMIN, MOD):
            i = fake_interaction(MOD)
            await cog.ban.callback(cog, i, user=str(target), notify=None, duration=None, reason=None)
            assert store.active_ban(target) is None
        i = fake_interaction(ADMIN)
        await cog.ban.callback(cog, i, user=str(ADMIN), notify=None, duration=None, reason=None)
        assert store.active_ban(ADMIN) is None
        i = fake_interaction(ADMIN)
        await cog.ban.callback(cog, i, user=str(MOD), notify=None, duration=None, reason="x")
        assert store.active_ban(MOD) is not None
        # a mod can't lift or edit a mod's ban, an admin can
        i = fake_interaction(MOD)
        await cog.unban.callback(cog, i, user=str(MOD))
        await cog.banedit.callback(cog, i, user=str(MOD), reason="changed")
        assert store.active_ban(MOD).reason == "x"
        i = fake_interaction(ADMIN)
        await cog.unban.callback(cog, i, user=str(MOD))
        assert store.active_ban(MOD) is None
        # bad input never reaches the database
        for bad_user in ("abc", "²²²", "<@&5>"):
            i = fake_interaction(MOD)
            await cog.ban.callback(cog, i, user=bad_user, notify=None, duration=None, reason=None)
            assert "numeric" in sent(i)
        i = fake_interaction(MOD)
        await cog.ban.callback(cog, i, user="1000000000000000050", notify=None, duration="forever", reason=None)
        assert "duration" in sent(i)
        # unknown Discord user (typo) is refused
        control.fetch_user = AsyncMock(side_effect=discord.NotFound(MagicMock(status=404, reason="x"), "unknown user"))
        i = fake_interaction(MOD)
        await cog.ban.callback(cog, i, user="1000000000000000051", notify=None, duration=None, reason=None)
        assert store.active_ban(1000000000000000051) is None and "no user" in sent(i)
        # baninfo / bans / banedit / unban
        i = fake_interaction(MOD)
        await cog.bans.callback(cog, i, page=1)
        assert i.response.send_message.await_count == 1
        i = fake_interaction(MOD)
        await cog.banedit.callback(cog, i, user=str(TARGET), reason="better")
        assert store.active_ban(TARGET).reason == "better"
        i = fake_interaction(MOD)
        await cog.unban.callback(cog, i, user=str(TARGET))
        assert store.active_ban(TARGET) is None
        i = fake_interaction(MOD)
        await cog.unban.callback(cog, i, user=str(TARGET))
        assert "not currently banned" in sent(i)
        await store.close()
    asyncio.run(go())


def test_tree_check_rejects_wrong_server_and_strangers(tmp_path):
    async def go():
        store, host, control, cog = await make(tmp_path)
        tree = control.tree
        assert isinstance(tree, ControlTree)
        # staff in the right server: allowed
        assert await tree.interaction_check(fake_interaction(MOD)) is True
        assert await tree.interaction_check(fake_interaction(ADMIN)) is True
        # a stranger in the right server: refused with a private message
        i = fake_interaction(RANDOM)
        assert await tree.interaction_check(i) is False and "permission" in sent(i)
        # admin in a DIFFERENT server: refused, no answer at all
        i = fake_interaction(ADMIN, guild_id=777)
        assert await tree.interaction_check(i) is False and sent(i) == ""
        # dev panel is admin-only even for mods
        i = fake_interaction(MOD)
        await cog.devpannel.callback(cog, i)
        assert "admin" in sent(i)
        await store.close()
    asyncio.run(go())


def test_user_app_guard_uses_the_ban_list_instantly(tmp_path):
    async def go():
        store, host, control, cog = await make(tmp_path)
        troll = TrollenatorBot(host, BotEntry(token="t", key="k"))
        i = fake_interaction(TARGET)
        assert await troll.guard(i) is True
        await store.add_ban(TARGET, reason="rude <@&1> @everyone", banned_by=ADMIN, expires_at=None, notify=True)
        i = fake_interaction(TARGET)
        assert await troll.guard(i) is False                       # effective on the very next press
        msg = sent(i)
        assert "rude" in msg and "@everyone" not in msg.replace("@\u200beveryone", "")   # mentions are neutralised
        i = fake_interaction(TARGET)
        i.type = discord.InteractionType.autocomplete
        assert await troll.guard(i) is False and sent(i) == ""
        await store.remove_ban(TARGET)
        assert await troll.guard(fake_interaction(TARGET)) is True
        # notify off → reason stays private
        await store.add_ban(TARGET, reason="secret", banned_by=ADMIN, expires_at=None, notify=False)
        i = fake_interaction(TARGET)
        assert await troll.guard(i) is False and "secret" not in sent(i)
        await store.close()
    asyncio.run(go())
