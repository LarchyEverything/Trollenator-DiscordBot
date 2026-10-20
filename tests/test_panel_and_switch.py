import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

import strings as strings_mod
from control import ControlBot, ControlSettings, diag_embed, run_self_test, DiagView, SwitchConfirmView, AddTokenModal
from store import Store
from tests.test_flows import ADMIN, GUILD, fake_interaction
from trollenator import BotEntry, BotInfo, RosterItem, TokenProblem, TrollenatorHost, token_key


@pytest.fixture(autouse=True)
def _strings():
    strings_mod.load_strings()


def tok(c):
    return c * 24 + "." + "b" * 6 + "." + "c" * 30


async def make(tmp_path, cfg=None):
    store = Store(tmp_path / "t.db")
    await store.init()
    host = TrollenatorHost(cfg or {"tokens": [tok("A"), tok("B")]}, store, control_key=token_key(tok("Z")))
    control = ControlBot(host, ControlSettings(token=tok("Z"), guild_id=GUILD, admins=frozenset({ADMIN}), mods=frozenset()))
    return store, host, control


def test_panel_embed_and_selftest_run_without_error(tmp_path):
    async def go():
        store, host, control = await make(tmp_path)
        host.probe = AsyncMock(side_effect=[BotInfo(1, "Alpha"), BotInfo(2, "Beta")])
        roster = await host.roster()
        i = fake_interaction(ADMIN)
        i.user = SimpleNamespace(id=ADMIN, name="a")
        embed = await diag_embed(control, i, 12, roster)
        assert len(embed) < 6000 and all(len(f.value) <= 1024 for f in embed.fields)
        lines = await run_self_test(control, i, 12)
        assert not [l for l in lines if l.startswith("❌") and "ffmpeg" not in l and "Voice" not in l], lines
        view = DiagView(control, i, clip=None, roster=roster)
        assert view._menu is not None and len(view._menu.options) == 2
        await store.close()
    asyncio.run(go())


def test_switch_success_failure_restore_and_shutdown(tmp_path):
    async def go():
        store, host, control = await make(tmp_path)
        a, b = host.entries
        host.probe = AsyncMock(return_value=BotInfo(7, "Beta"))
        host._stop_bot = AsyncMock()
        host._remember_active = MagicMock()
        launches = []

        async def fake_launch(entry):
            launches.append(entry.key)
            if entry.key == b.key:
                return False, "boom"
            host.troll = MagicMock(cmd_prefix="beta-", user=SimpleNamespace(name="Alpha"))
            host.active = entry
            return True, ""
        host._launch_and_wait = fake_launch
        host.active = a
        # failure of B → A restored
        r = await host.switch_to(b.key)
        assert r.status == "failed" and r.restored and launches == [b.key, a.key]
        assert "Switched back" in host.switch_text(r) or "running again" in host.switch_text(r)
        # unknown key, busy, control app, rejected token
        assert (await host.switch_to("nope")).status == "unknown"
        host.control_app_id = 7
        assert (await host.switch_to(b.key)).status == "is_control"
        host.control_app_id = 0
        host.probe = AsyncMock(side_effect=TokenProblem("rejected"))
        assert (await host.switch_to(b.key)).status == "rejected"
        host._stopping = True
        assert (await host.switch_to(b.key)).status == "unavailable"
        for status in ("ok", "same", "busy", "unknown", "unavailable", "is_control", "rejected", "unreachable", "not_a_bot"):
            from trollenator import SwitchResult
            assert "«" not in host.switch_text(SwitchResult(status, name="x", prefix="p"))
        await store.close()
    asyncio.run(go())


def test_add_token_refuses_control_token_and_duplicates(tmp_path):
    async def go():
        store, host, control = await make(tmp_path)
        panel = SimpleNamespace(control=control, origin=fake_interaction(ADMIN), reload=AsyncMock())
        for value, expect in ((tok("Z"), "control bot"), (tok("A"), "already"), ("garbage", "token")):
            modal = AddTokenModal(panel)
            modal.in_token = SimpleNamespace(value=value)
            i = fake_interaction(ADMIN)
            await modal.on_submit(i)
            assert expect in i.followup.send.call_args.args[0].lower() or expect in i.followup.send.call_args.args[0], (value, i.followup.send.call_args)
        # a token whose application IS the control app is refused after the probe, and nothing is written
        host.control_app_id = 99
        host.probe = AsyncMock(return_value=BotInfo(99, "Ctl"))
        modal = AddTokenModal(panel)
        modal.in_token = SimpleNamespace(value=tok("Y"))
        i = fake_interaction(ADMIN)
        await modal.on_submit(i)
        assert "control bot" in i.followup.send.call_args.args[0] and len(host.entries) == 2
        await store.close()
    asyncio.run(go())


def test_add_token_writes_config_atomically(tmp_path, monkeypatch):
    import json, os, stat
    import trollenator
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"enabled": True, "admins": [1], "tokens": [tok("A")]}))
    trollenator.write_config_token(cfg, tok("B"))
    data = json.loads(cfg.read_text())
    assert data["tokens"] == [tok("A"), tok("B")] and data["admins"] == [1]
    assert stat.S_IMODE(os.stat(cfg).st_mode) == 0o600
    cfg.write_text("[]")
    with pytest.raises(ValueError):
        trollenator.write_config_token(cfg, tok("C"))
    assert cfg.read_text() == "[]"                                  # nothing written on a refused update
    cfg.write_text("{ not json")
    with pytest.raises(json.JSONDecodeError):
        trollenator.write_config_token(cfg, tok("C"))
    assert cfg.read_text() == "{ not json"
    assert not [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
