"""
control.py — Trollenator's CONTROL BOT.

A small, private bot that is installed to ONE server of yours (a "guild install"). It does exactly this and nothing else:

  /ban /unban /bans /baninfo /banedit   manage who may use Trollenator          (admins and mods)
  /devpannel                            diagnostics + self-test, switch the active user app,
                                        add a bot token, voice/TTS tests            (admins only)

Who is who comes from Configs/trollenator_config.json:
  control_token      this bot's token                   control_guild_id   the one server it works in
  admins             user IDs allowed to do everything  mods              user IDs allowed to manage bans

Security model (each layer stands on its own):
  1. Its commands are registered as GUILD commands of control_guild_id only — nowhere else do they exist.
  2. Every command and button re-checks, at the moment it is used, that it comes from that server AND from a user ID
     in admins/mods. Discord's own role/permission settings are never trusted for this.
  3. It leaves any other server it is added to (it needs no other server, and the add-token form must not be reachable
     from anywhere else).
  4. Mods can't ban/unban/edit other mods, nobody can ban an admin or themselves, and the dev panel is admin-only.
  5. Its token must differ from every user app's: a user app can't be the control app (checked on add and on switch).
  6. Every action is written to the activity log (who, what, on whom, why).
Answers are private (ephemeral): only the person who ran the command sees them.
"""

import asyncio
import base64
import hashlib
import json
import logging
import math
import platform
import re
import shutil
import sqlite3
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Optional

import aiohttp
import discord
from discord import app_commands, ui
from discord.ext import commands

import strings as strings_mod
from appconfig import STATE_FILE, load_data, parse_id_list, parse_snowflake, save_data
from store import REASON_MAX, Ban
from trollenator import (
    BASE_COMMANDS, BUILDER_TIMEOUT, COMMAND_NAME_RE, MAX_BOTS, TOKEN_PROBLEM_KEYS, TOS_CODES, WAVEFORM_BUCKETS,
    AudioError, ReportMixin, RosterItem, ScanInput, SwitchResult, TokenProblem, TrollenatorHost, VoiceClip,
    VoiceSendError, _RE_TOKEN_SHAPE, _ffmpeg, clean_token, convert_to_voice, describe_missing, inline,
    interaction_age_ms, make_prefix, missing_to_post, post_voice_message, redact, register_secret, reply_private,
    safe_name, scan_content, session_id, should_warn, t, text_field, token_key,
)

log = logging.getLogger("trollenator.control")

ADMIN, MOD = "admin", "mod"
BANS_PER_PAGE = 15
MAX_BAN_SECONDS = 5 * 365 * 86400            # a ban can't be set for more than five years (leave empty = permanent)
_DURATION_UNITS = {"m": 60, "h": 3600, "d": 86400, "w": 604800}
_RE_DURATION = re.compile(r"([0-9]{1,4})([mhdw])")
_RE_MENTION = re.compile(r"<@!?([0-9]{1,20})>")
SOURCE_FILES = (Path(__file__).resolve(), Path(__file__).resolve().with_name("trollenator.py"))
# strings.json keys that are built at runtime (f"troll_poll_warn_{kind}"), so a scan for "troll_…" literals can't find them.
DYNAMIC_STRING_KEYS = (
    "troll_poll_warn_too_many", "troll_poll_warn_too_long", "troll_poll_warn_no_text",
    *(f"troll_tos_{code}" for code in TOS_CODES),
)


# ─────────────────────────────────────────────────────────────────────────────
# Pure helpers
# ─────────────────────────────────────────────────────────────────────────────

def parse_user_ref(raw: str) -> Optional[int]:
    """'<@123…>', '<@!123…>' or '123…' (ASCII digits) → user ID, else None. Nothing else is accepted."""
    s = (raw or "").strip()
    m = _RE_MENTION.fullmatch(s)
    return parse_snowflake(m.group(1) if m else s)


def parse_ban_duration(raw: str) -> int:
    """'30m' · '1h' · '7d' · '2w' → seconds (at most five years). Raises ValueError for anything else."""
    m = _RE_DURATION.fullmatch((raw or "").strip().lower())
    if not m:
        raise ValueError(raw)
    seconds = int(m.group(1)) * _DURATION_UNITS[m.group(2)]
    if not 0 < seconds <= MAX_BAN_SECONDS:
        raise ValueError(raw)
    return seconds


def when(epoch: Optional[int]) -> str:
    """Discord timestamp markup (the viewer's own time zone), or 'Permanent'."""
    if epoch is None:
        return t("troll_ctl_permanent")
    return f"<t:{epoch}:R> (<t:{epoch}:f>)"


def shown_reason(ban_reason: str) -> str:
    return discord.utils.escape_mentions(ban_reason) or t("troll_ctl_no_reason")


# ─────────────────────────────────────────────────────────────────────────────
# Settings
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ControlSettings:
    token: str = ""
    guild_id: int = 0
    admins: frozenset = frozenset()
    mods: frozenset = frozenset()          # never contains an admin

    def level_of(self, user_id: int) -> Optional[str]:
        if user_id in self.admins:
            return ADMIN
        if user_id in self.mods:
            return MOD
        return None

    @classmethod
    def from_config(cls, cfg: dict) -> tuple[Optional["ControlSettings"], list[str]]:
        """
        (settings, problems). settings is None when the control bot can't or shouldn't run; `problems` are plain
        sentences for the log. No control_token = not configured (a warning, not a crash).
        """
        problems: list[str] = []
        raw_token = cfg.get("control_token")
        if raw_token in (None, ""):
            return None, ['"control_token" is not set — the control bot is OFF, so bans and the dev panel can\'t be used.']
        token = clean_token(raw_token)
        if not token or len(token) > 200 or not re.fullmatch(r"[\x21-\x7e]+", token):
            return None, ['"control_token" doesn\'t look like a bot token — the control bot is OFF.']
        register_secret(token)
        guild_id = parse_snowflake(cfg.get("control_guild_id"))
        if guild_id is None:
            return None, ['"control_guild_id" is missing or not a valid server ID — the control bot is OFF (it refuses to run '
                          "without knowing which server it belongs to)."]
        admins = parse_id_list(cfg.get("admins"), "admins")
        mods = parse_id_list(cfg.get("mods"), "mods") - admins
        if not admins:
            problems.append('"admins" is empty — nobody can use the dev panel or ban mods until you add a user ID.')
        return cls(token=token, guild_id=guild_id, admins=admins, mods=mods), problems


# ─────────────────────────────────────────────────────────────────────────────
# Diagnostics helpers (used by /devpannel)
# ─────────────────────────────────────────────────────────────────────────────

async def ffmpeg_summary() -> tuple[bool, str]:
    """(can /voice convert audio?, one-line description for the diagnostics)."""
    path = shutil.which("ffmpeg")
    if not path:
        return False, t("troll_test_ffmpeg_missing")
    try:
        banner = (await _ffmpeg(path, "-version")).decode(errors="replace")
        encoders = (await _ffmpeg(path, "-encoders")).decode(errors="replace")
    except AudioError:
        return False, t("troll_test_ffmpeg_missing")
    found = re.search(r"ffmpeg version (\S+)", banner)
    version = found.group(1) if found else "?"
    if "libopus" not in encoders:
        return False, t("troll_test_ffmpeg_noopus", version=version)
    return True, t("troll_test_ffmpeg_ok", version=version)


async def make_test_clip() -> VoiceClip:
    """A 2-second 440 Hz tone, run through the same conversion as an uploaded file."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise AudioError("no_ffmpeg")
    wav = await _ffmpeg(ffmpeg, "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-f", "wav", "pipe:1")
    return await convert_to_voice(wav, "test-tone.wav")


def missing_string_keys() -> list[str]:
    """troll_* keys the code uses that strings.json doesn't have (the classic forgotten-string bug)."""
    keys: set[str] = set(DYNAMIC_STRING_KEYS)
    for path in SOURCE_FILES:
        try:
            keys |= set(re.findall(r'"(troll_[a-z0-9_]+)"', path.read_text(encoding="utf-8")))
        except OSError:
            pass
    known = strings_mod.known_keys()
    return sorted(k for k in keys if k not in known)


def roster_lines(roster: list[RosterItem]) -> str:
    """The "Bots" field: one line per configured bot, cut so it always fits an embed field."""
    lines: list[str] = []
    used = 0
    for n, item in enumerate(roster, start=1):
        if item.info is None:
            line = t("troll_bots_problem_rejected" if item.problem == "rejected" else "troll_bots_problem_unreachable", n=n)
        else:
            line = t("troll_bots_active" if item.active else "troll_bots_idle",
                     name=safe_name(item.info.name), prefix=item.prefix)
        if used + len(line) + 1 > 900:
            lines.append(t("troll_bots_more", count=len(roster) - n + 1))
            break
        lines.append(line)
        used += len(line) + 1
    return "\n".join(lines) or "—"


async def diag_embed(control: "ControlBot", interaction: discord.Interaction, age_ms: int, roster: list[RosterItem]) -> discord.Embed:
    host = control.host
    troll = host.troll
    _, ffmpeg_text = await ffmpeg_summary()
    try:
        db_text = f"{await host.store.ping_ms()} ms"
    except Exception as e:
        db_text = f"error ({type(e).__name__})"

    def ms(latency: float) -> object:
        return round(latency * 1000) if math.isfinite(latency) else "?"

    embed = discord.Embed(title=t("troll_test_title"), colour=discord.Colour.blurple())
    embed.add_field(name=t("troll_test_status_label"), inline=True, value=t(
        "troll_test_status", control_latency=ms(control.latency), latency=ms(troll.latency) if troll else "—", age=age_ms, db=db_text,
        uptime=str(timedelta(seconds=int(time.monotonic() - control.started_at)))))
    embed.add_field(name=t("troll_test_system_label"), inline=True, value=t(
        "troll_test_system", dpy=discord.__version__, aiohttp=aiohttp.__version__,
        python=platform.python_version(), system=f"{platform.system()} {platform.machine()}", ffmpeg=ffmpeg_text))
    if troll is not None and troll.user is not None:
        app_text = t("troll_test_app", app=troll.user, app_id=troll.application_id, count=len(troll.tree.get_commands()),
                     sync=t("troll_test_sync_ok" if troll.is_synced() else "troll_test_sync_stale"),
                     cooldown=host.cooldown, prefix=troll.cmd_prefix or "—")
    else:
        app_text = t("troll_test_app_none")
    embed.add_field(name=t("troll_test_app_label"), inline=False, value=app_text)
    embed.add_field(name=t("troll_test_bots_label"), inline=False, value=roster_lines(roster))
    embed.add_field(name=t("troll_test_control_label"), inline=False, value=t(
        "troll_test_control", guild=control.settings.guild_id, admins=len(control.settings.admins),
        mods=len(control.settings.mods), bans=len(host.store.list_bans()), user=interaction.user, user_id=interaction.user.id))
    embed.set_footer(text=t("troll_test_footer"))
    return embed


async def run_self_test(control: "ControlBot", interaction: discord.Interaction, age_ms: int) -> list[str]:
    """Check each moving part and return one ✅/⚠️/❌ line per check."""
    host = control.host
    troll = host.troll
    lines: list[str] = []

    # 1 + 2 — ffmpeg and the whole voice pipeline
    usable, ffmpeg_text = await ffmpeg_summary()
    lines.append(f"{'✅' if usable else '❌'} ffmpeg: {ffmpeg_text}")
    if usable:
        started = time.monotonic()
        try:
            clip = await make_test_clip()
            problems = []
            if clip.data[:4] != b"OggS":
                problems.append("output isn't an Ogg file")
            if abs(clip.duration - 2.0) > 0.25:
                problems.append(f"duration came out as {clip.duration}s instead of ≈2s")
            if len(base64.b64decode(clip.waveform)) != WAVEFORM_BUCKETS:
                problems.append("waveform has the wrong length")
            ms = round((time.monotonic() - started) * 1000)
            if problems:
                lines.append("❌ Voice conversion: " + "; ".join(problems))
            else:
                lines.append(f"✅ Voice conversion: 2 s tone → {len(clip.data)} bytes of Ogg/Opus, "
                             f"duration {clip.duration}s, {WAVEFORM_BUCKETS}-point waveform ({ms} ms)")
        except AudioError as e:
            lines.append(f"❌ Voice conversion failed ({e.code})")

    # 2b — the ToS scanner still flags what it should and leaves ordinary text alone
    try:
        risky = scan_content(ScanInput(ping_text="@everyone claim your free nitro", texts=["@everyone claim your free nitro"]))
        calm = scan_content(ScanInput(ping_text="see you at 8", texts=["see you at 8"]))
        if should_warn(risky) and not should_warn(calm):
            lines.append(f"✅ ToS scanner: flags a sample scam, ignores a sample ordinary message "
                         f"({'custom term list loaded' if host.tos_terms is not None else 'no custom term list'})")
        else:
            lines.append("❌ ToS scanner: sample checks gave the wrong result")
    except Exception as e:
        lines.append(f"❌ ToS scanner failed: {type(e).__name__}: {e}")

    # 3 — a poll object builds into a payload
    try:
        poll = discord.Poll(question="Test?", duration=timedelta(hours=1))
        poll.add_answer(text="Yes", emoji="👍")
        poll.add_answer(text="No")
        payload = poll._to_dict()
        lines.append(f"✅ Poll payload builds ({len(payload.get('answers', []))} answers)")
    except Exception as e:
        lines.append(f"❌ Poll payload failed: {type(e).__name__}: {e}")

    # 4 — database
    try:
        lines.append(f"✅ Ban database: answers in {await host.store.ping_ms()} ms, {len(host.store.list_bans())} active ban(s) in memory")
    except Exception as e:
        lines.append(f"❌ Ban database failed: {type(e).__name__}: {e}")

    # 5 — strings
    if missing := missing_string_keys():
        lines.append(f"❌ {len(missing)} string(s) missing from strings.json: " + ", ".join(f"`{k}`" for k in missing[:12]))
    else:
        lines.append("✅ Every troll_* string the code uses exists in strings.json")

    # 6 — the user app's slash commands: synced, prefixed, valid, and exactly the set the message texts know about
    if troll is None or troll.user is None:
        lines.append("⚠️ No user app is running — nothing to check its commands against")
    else:
        names = [c.name for c in troll.tree.get_commands()]
        if troll.is_synced():
            lines.append(f"✅ {len(names)} slash commands, in sync with Discord")
        else:
            lines.append("⚠️ Slash commands changed since the last sync — restart Trollenator to push them")
        bases = {troll.base_name(n) for n in names}
        bad = [n for n in names if not COMMAND_NAME_RE.fullmatch(n)]
        if bad or bases != set(BASE_COMMANDS) or not all(n.startswith(troll.cmd_prefix) for n in names):
            lines.append(f"❌ Command names: {', '.join(sorted(bad)) + ' invalid' if bad else 'the set differs from BASE_COMMANDS'}"
                         " — BASE_COMMANDS in trollenator.py must list every command's base name")
        else:
            lines.append(f"✅ Command names: {len(names)} commands, all start with `{troll.cmd_prefix}` and are valid")

    # 6b — the bot list
    roster_now = await host.roster()
    lines.append(f"{'✅' if all(r.info for r in roster_now) else '⚠️'} Bots configured: {len(roster_now)} "
                 f"({sum(1 for r in roster_now if r.info)} reachable)")

    # 7 — timing headroom for Discord's 3-second window
    if age_ms > 2000:
        lines.append(f"⚠️ This command reached the bot ≈{age_ms} ms after Discord sent it — close to the 3 s limit")
    else:
        lines.append(f"✅ Interaction age ≈{age_ms} ms (limit 3000 ms)")

    # 8 — the control bot itself
    others = [g for g in control.guilds if g.id != control.settings.guild_id]
    lines.append(f"{'✅' if not others else '⚠️'} Control bot is in {len(control.guilds)} server(s)"
                 + ("" if not others else " — it should only be in the control server (it leaves others on its own)"))
    return lines


# ─────────────────────────────────────────────────────────────────────────────
# Dev panel: switch bot, add token
# ─────────────────────────────────────────────────────────────────────────────

async def refuse_not_admin(control: "ControlBot", interaction: discord.Interaction) -> bool:
    """True if the user is NOT an admin right now (and has been told so)."""
    if control.level_of(interaction.user.id) == ADMIN and interaction.guild_id == control.settings.guild_id:
        return False
    control.note_refusal(interaction, "admin only")
    try:
        await reply_private(interaction, t("troll_ctl_admin_only"))
    except discord.HTTPException:
        pass
    return True


class SwitchConfirmView(ui.View):
    """
    "Switch to <bot>?" — a separate private message, so a stray tap on the menu can't take the running bot offline.
    The control bot stays online during the swap, so the outcome is simply written back into this message.
    """

    def __init__(self, panel: "DiagView", item: RosterItem) -> None:
        super().__init__(timeout=120)
        self.panel = panel
        self.control = panel.control
        self.item = item
        self.source: Optional[discord.Interaction] = None       # the interaction that created this message
        self.settled = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return not await refuse_not_admin(self.control, interaction)

    async def on_timeout(self) -> None:
        if not self.settled and self.source is not None:
            try:
                await self.source.edit_original_response(content=t("troll_switch_expired"), view=None)
            except discord.HTTPException:
                pass

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: ui.Item) -> None:
        await self.control.report_error(interaction, error, "/devpannel · switch bot", sid=session_id(self.panel.origin))

    @ui.button(label="Switch", emoji="🔁", style=discord.ButtonStyle.danger, row=0)
    async def on_confirm(self, interaction: discord.Interaction, button: ui.Button) -> None:
        if self.settled:
            return await interaction.response.defer()
        self.settled = True
        self.stop()
        host = self.control.host
        who = self.item.info.name if self.item.info else "?"
        await interaction.response.edit_message(content=t("troll_switch_working", name=safe_name(who)), view=None)
        started = time.monotonic()
        old_label = host.tlog.app_label
        try:
            result = await host.switch_to(self.item.entry.key)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.exception("Trollenator switch crashed")
            host.tlog.record("fail", "Switching the active bot crashed", interaction, sid=session_id(self.panel.origin), error=e,
                             summary=f"{type(e).__name__}: {inline(str(e), 300)}")
            result = SwitchResult("failed", name=who, reason="an internal error — see the log")
        level = {"ok": "ok", "same": "info", "busy": "info"}.get(result.status, "fail" if result.status == "failed" else "warn")
        host.tlog.record(
            level, "Active bot switch", interaction, sid=session_id(self.panel.origin),
            summary=f"{old_label or '?'} → {result.name or '?'}: {result.status}"
                    + (f" ({result.reason})" if result.reason else "")
                    + (" · previous bot restored" if result.restored else "")
                    + f" · took {time.monotonic() - started:.1f} s")
        try:
            await interaction.edit_original_response(content=host.switch_text(result), view=None)    # text built AFTER the swap: new prefix
        except discord.HTTPException:
            pass
        await self.panel.reload(force=True)

    @ui.button(label="Cancel", emoji="✖️", style=discord.ButtonStyle.secondary, row=0)
    async def on_cancel(self, interaction: discord.Interaction, button: ui.Button) -> None:
        self.settled = True
        self.stop()
        await interaction.response.edit_message(content=t("troll_switch_cancelled"), view=None)


class AddTokenModal(ui.Modal):
    """Paste a new bot token: it is checked with Discord, saved to the config, and a switch to it is offered."""

    def __init__(self, panel: "DiagView") -> None:
        super().__init__(title="Add a bot token", timeout=300)
        self.panel = panel
        self.in_token, label = text_field(
            "Bot token", required=True, max_length=200, placeholder="Paste the token from the Developer Portal",
            description="Saved to Configs/trollenator_config.json. It is never shown or logged.")
        self.add_item(label)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        await interaction.response.defer(ephemeral=True)           # the checks below make web requests
        return not await refuse_not_admin(self.panel.control, interaction)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await self.panel.control.report_error(interaction, error, "/devpannel · add token", sid=session_id(self.panel.origin))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        control = self.panel.control
        host = control.host
        token = clean_token(self.in_token.value)
        if not _RE_TOKEN_SHAPE.fullmatch(token):
            return await interaction.followup.send(t("troll_token_bad_format"), ephemeral=True)
        register_secret(token)                                     # from here on it can't leak into a log line or an error
        key = token_key(token)
        if key == host.control_key:
            return await interaction.followup.send(t("troll_token_is_control"), ephemeral=True)
        if any(e.key == key for e in host.entries):
            return await interaction.followup.send(t("troll_token_duplicate"), ephemeral=True)
        if len(host.entries) >= MAX_BOTS:
            return await interaction.followup.send(t("troll_token_limit", limit=MAX_BOTS), ephemeral=True)
        try:
            info = await host.probe(token)
        except TokenProblem as e:
            return await interaction.followup.send(t(TOKEN_PROBLEM_KEYS[e.kind]), ephemeral=True)
        if host.control_app_id and info.id == host.control_app_id:
            return await interaction.followup.send(t("troll_token_is_control"), ephemeral=True)
        try:
            entry = await host.add_token(token)
        except ValueError as e:                                    # lost a race with another admin, or the limit
            key_name = {"duplicate": "troll_token_duplicate", "control": "troll_token_is_control"}.get(str(e), "troll_token_limit")
            return await interaction.followup.send(t(key_name, limit=MAX_BOTS), ephemeral=True)
        except (OSError, json.JSONDecodeError) as e:
            log.error(redact(f"Could not save a new token to the config: {type(e).__name__}: {e}"))
            return await interaction.followup.send(t("troll_token_save_failed"), ephemeral=True)
        host.remember(entry, info)
        host.tlog.record("ok", "/devpannel · bot token added", interaction, sid=session_id(self.panel.origin),
                         summary=f"Added the bot {inline(info.name, 60)} (application {info.id}). {len(host.entries)} bot(s) configured.")
        item = RosterItem(entry, info, False, make_prefix(info.name, entry.prefix, info.id))
        view = SwitchConfirmView(self.panel, item)
        await interaction.followup.send(
            t("troll_token_added", name=safe_name(info.name), prefix=item.prefix), view=view, ephemeral=True, wait=True)
        view.source = interaction
        await self.panel.reload()                                   # the new bot appears in the panel's menu


class DiagView(ui.View):
    """Buttons under /devpannel: Self-test, Test voice message, Test TTS, Refresh, Add bot token — and a menu to switch bot. Admins only."""

    def __init__(self, control: "ControlBot", origin: discord.Interaction, *, clip: Optional[VoiceClip],
                 roster: Optional[list[RosterItem]] = None, age_ms: int = 0) -> None:
        super().__init__(timeout=BUILDER_TIMEOUT)
        self.control = control
        self.origin = origin
        self.clip = clip
        self.age_ms = age_ms
        self.roster: list[RosterItem] = roster or []
        self._menu: Optional[ui.Select] = None
        self.set_roster(self.roster)

    def set_roster(self, roster: list[RosterItem]) -> None:
        """(Re)build the "switch bot" menu: shown only when there is more than one bot to choose from."""
        self.roster = roster
        if self._menu is not None:
            self.remove_item(self._menu)
            self._menu = None
        if len(roster) < 2:
            return
        options = []
        for n, item in enumerate(roster[:MAX_BOTS], start=1):
            if item.info is not None:
                label = f"{'🟢 ' if item.active else ''}{item.info.name}"[:100]
                desc = f"{'Active · ' if item.active else ''}commands start with {item.prefix}"[:100]
            else:
                label = f"⚠️ Bot {n}"
                desc = ("Token rejected by Discord" if item.problem == "rejected" else "Couldn't check it right now")[:100]
            options.append(discord.SelectOption(label=label, value=item.entry.key, description=desc))
        menu = ui.Select(placeholder="Switch the active bot…", options=options, row=1)

        async def picked(interaction: discord.Interaction, menu=menu) -> None:
            item = next((r for r in self.roster if r.entry.key == menu.values[0]), None)
            if item is None:
                return await reply_private(interaction, t("troll_switch_unknown"))
            if item.active:
                return await reply_private(interaction, t("troll_switch_same"))
            view = SwitchConfirmView(self, item)
            name = safe_name(item.info.name) if item.info else "?"
            await interaction.response.send_message(
                t("troll_switch_confirm", name=name, prefix=item.prefix or "…"), view=view, ephemeral=True)
            view.source = interaction

        menu.callback = picked
        self._menu = menu
        self.add_item(menu)

    async def reload(self, age_ms: Optional[int] = None, *, force: bool = False) -> None:
        """Re-read the bot list and redraw the panel message (best effort: the panel's token lasts 15 minutes)."""
        if age_ms is not None:
            self.age_ms = age_ms
        roster = await self.control.host.roster(force=force)
        self.set_roster(roster)
        try:
            await self.origin.edit_original_response(
                embed=await diag_embed(self.control, self.origin, self.age_ms, roster), view=self)
        except discord.HTTPException:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return not await refuse_not_admin(self.control, interaction)

    async def on_timeout(self) -> None:
        try:
            await self.origin.edit_original_response(view=None)
        except discord.HTTPException:
            pass

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: ui.Item) -> None:
        await self.control.report_error(interaction, error, "/devpannel · panel", sid=session_id(self.origin))

    @ui.button(label="Self-test", emoji="🧪", row=0)
    async def on_selftest(self, interaction: discord.Interaction, button: ui.Button) -> None:
        age = interaction_age_ms(interaction)
        await interaction.response.defer(ephemeral=True)
        lines = await run_self_test(self.control, interaction, age)
        await interaction.followup.send("\n".join(lines)[:2000], ephemeral=True)

    @ui.button(label="Test voice message", emoji="🎙️", row=0)
    async def on_voice(self, interaction: discord.Interaction, button: ui.Button) -> None:
        if self.clip is None:
            return await reply_private(interaction, t("troll_test_voice_no_clip"))
        if missing := missing_to_post(interaction, voice=True):
            return await reply_private(interaction, describe_missing(missing))
        sid = session_id(self.origin)
        tlog = self.control.host.tlog
        try:
            # Same path /voice uses: the answer to this button press is the voice message itself.
            took = await post_voice_message(interaction, self.clip, self.control.host.http())
        except VoiceSendError as e:
            tlog.record("fail", "/devpannel · voice test failed", interaction, sid=sid, summary=str(e))
            await reply_private(interaction, t("troll_voice_failed", error=inline(str(e), 300)))
        else:
            tlog.record("ok", "/devpannel · voice test sent", interaction, sid=sid, summary=f"Upload accepted in {took} ms.")

    @ui.button(label="Test TTS", emoji="🔊", row=0)
    async def on_tts_test(self, interaction: discord.Interaction, button: ui.Button) -> None:
        if missing := missing_to_post(interaction):
            return await reply_private(interaction, describe_missing(missing))
        await interaction.response.defer()                # silent; the test message goes out as a follow-up
        perms, app = interaction.permissions, interaction.app_permissions
        in_guild = interaction.guild_id is not None and bool(perms.value)
        try:
            message = await interaction.followup.send(
                t("troll_test_tts_text"), tts=True, ephemeral=False, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException as e:
            return await interaction.followup.send(
                t("troll_test_tts_rejected", error=inline(e.text or str(e), 300)), ephemeral=True)
        # Discord answers with the message it actually created: its `tts` flag says whether it was kept.
        self.control.host.tlog.record("ok", "/devpannel · TTS test sent", interaction, sid=session_id(self.origin),
                                      summary="Discord kept the TTS flag." if message.tts else "Discord dropped the TTS flag.")
        await interaction.followup.send(t(
            "troll_test_tts_kept" if message.tts else "troll_test_tts_dropped",
            you=("✅" if perms.administrator or perms.send_tts_messages else "❌") if in_guild else "n/a",
            app="✅" if app.send_tts_messages else "❌"), ephemeral=True)

    @ui.button(label="Refresh", emoji="🔄", row=0)
    async def on_refresh(self, interaction: discord.Interaction, button: ui.Button) -> None:
        age = interaction_age_ms(interaction)
        await interaction.response.defer()
        await self.reload(age, force=True)

    @ui.button(label="Add bot token", emoji="➕", row=0)
    async def on_add_token(self, interaction: discord.Interaction, button: ui.Button) -> None:
        if len(self.control.host.entries) >= MAX_BOTS:
            return await reply_private(interaction, t("troll_token_limit", limit=MAX_BOTS))
        await interaction.response.send_modal(AddTokenModal(self))


# ─────────────────────────────────────────────────────────────────────────────
# The commands
# ─────────────────────────────────────────────────────────────────────────────

class ControlTree(app_commands.CommandTree):
    """Guild-install only, and every command is checked against the control server and the staff lists."""

    def __init__(self, client: "ControlBot") -> None:
        super().__init__(
            client,
            allowed_installs=app_commands.AppInstallationType(guild=True, user=False),
            allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=False, private_channel=False),
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        control: ControlBot = self.client      # type: ignore[assignment]
        interaction.extras["arrived_ms"] = interaction_age_ms(interaction)
        if interaction.guild_id != control.settings.guild_id:
            control.note_refusal(interaction, "wrong server")
            return False                         # from anywhere else: no answer at all
        if control.level_of(interaction.user.id) is None:
            control.note_refusal(interaction, "not staff")
            try:
                await reply_private(interaction, t("troll_no_permission"))
            except discord.HTTPException:
                pass
            return False
        return True

    async def on_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, app_commands.CheckFailure):
            return
        cause = error.original if isinstance(error, app_commands.CommandInvokeError) else error
        name = interaction.command.qualified_name if interaction.command else "?"
        await self.client.report_error(interaction, cause, f"/{name}")      # type: ignore[attr-defined]


class ControlCommands(commands.Cog):
    """Ban management and the dev panel. Registered as guild commands of the control server only."""

    def __init__(self, control: "ControlBot") -> None:
        self.control = control

    # ── helpers ──────────────────────────────────────────────────────────────
    def _target_guard(self, interaction: discord.Interaction, target: int, *, admin_only_key: str) -> Optional[str]:
        """The reason (a message) why this staff member may not act on `target`, or None."""
        control = self.control
        if control.level_of(target) == ADMIN:
            return t("troll_ctl_ban_is_admin")
        if control.level_of(target) == MOD and control.level_of(interaction.user.id) != ADMIN:
            return t(admin_only_key)
        return None

    async def _lookup(self, uid: int) -> tuple[Optional[discord.User], bool]:
        """(user, exists). exists is False only when Discord says there is no such user."""
        try:
            return await self.control.fetch_user(uid), True
        except discord.NotFound:
            return None, False
        except discord.HTTPException:
            return None, True                  # couldn't check — don't block the action over it

    def _db_failed(self, interaction: discord.Interaction, where: str, error: Exception) -> str:
        self.control.tlog.record("fail", f"{where} · database error", interaction, sid=session_id(interaction), error=error,
                                 summary=f"{type(error).__name__}: {inline(str(error), 200)}")
        return t("troll_ctl_db_error", error=type(error).__name__)

    # ── /ban ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="ban", description="Ban a user from using Trollenator.")
    @app_commands.describe(
        user="The user's ID, or an @mention",
        notify="Show them the reason when they try to use Trollenator",
        duration="30m, 1h, 7d, 2w … (at most 5 years) — leave empty for a permanent ban",
        reason="Why (kept with the ban; shown to them only if notify is on)",
    )
    @app_commands.choices(notify=[app_commands.Choice(name="yes", value="yes")])
    async def ban(
        self, interaction: discord.Interaction, user: app_commands.Range[str, 1, 64],
        notify: Optional[str] = None,
        duration: Optional[app_commands.Range[str, 1, 12]] = None,
        reason: Optional[app_commands.Range[str, 1, REASON_MAX]] = None,
    ) -> None:
        control = self.control
        uid = parse_user_ref(user)
        if uid is None:
            return await reply_private(interaction, t("troll_ctl_bad_user"))
        if uid == interaction.user.id:
            return await reply_private(interaction, t("troll_ctl_ban_self"))
        if blocked := self._target_guard(interaction, uid, admin_only_key="troll_ctl_ban_mod_admin_only"):
            return await reply_private(interaction, blocked)
        expires_at: Optional[int] = None
        if duration:
            try:
                expires_at = int(time.time()) + parse_ban_duration(duration)
            except ValueError:
                return await reply_private(interaction, t("troll_ctl_bad_duration"))

        await interaction.response.defer(ephemeral=True)         # the user lookup below is a web request
        found, exists = await self._lookup(uid)
        if not exists:
            return await reply_private(interaction, t("troll_ctl_user_not_found", id=uid))
        try:
            ban = await control.host.store.add_ban(
                uid, reason=reason or "", banned_by=interaction.user.id, expires_at=expires_at, notify=notify == "yes")
        except (sqlite3.Error, RuntimeError) as e:
            return await reply_private(interaction, self._db_failed(interaction, "/ban", e))
        if ban is None:
            return await reply_private(interaction, t("troll_ctl_ban_already", id=uid))
        control.tlog.record("ok", "/ban · user banned", interaction, sid=session_id(interaction),
                            summary=f"Banned `{uid}` until {('<t:%d:f>' % ban.expires_at) if ban.expires_at else 'forever'} · notify {'on' if ban.notify else 'off'}",
                            details=f"Reason: {ban.reason or '(none)'}")
        await reply_private(interaction, t(
            "troll_ctl_ban_success", name=safe_name(found.name) if found else "?", id=uid, duration=when(ban.expires_at),
            notify="Yes 🔔" if ban.notify else "No", reason=shown_reason(ban.reason)))

    # ── /unban ───────────────────────────────────────────────────────────────
    @app_commands.command(name="unban", description="Let a banned user use Trollenator again.")
    @app_commands.describe(user="The user's ID, or an @mention")
    async def unban(self, interaction: discord.Interaction, user: app_commands.Range[str, 1, 64]) -> None:
        uid = parse_user_ref(user)
        if uid is None:
            return await reply_private(interaction, t("troll_ctl_bad_user"))
        if self.control.level_of(uid) == MOD and self.control.level_of(interaction.user.id) != ADMIN:
            return await reply_private(interaction, t("troll_ctl_unban_mod_admin_only"))
        try:
            removed = await self.control.host.store.remove_ban(uid)
        except (sqlite3.Error, RuntimeError) as e:
            return await reply_private(interaction, self._db_failed(interaction, "/unban", e))
        if not removed:
            return await reply_private(interaction, t("troll_ctl_unban_not_banned", id=uid))
        self.control.tlog.record("ok", "/unban · user unbanned", interaction, sid=session_id(interaction), summary=f"Unbanned `{uid}`.")
        await reply_private(interaction, t("troll_ctl_unban_success", id=uid))

    # ── /bans ────────────────────────────────────────────────────────────────
    @app_commands.command(name="bans", description="List the active bans.")
    @app_commands.describe(page="Which page (15 bans per page)")
    async def bans(self, interaction: discord.Interaction, page: app_commands.Range[int, 1, 10000] = 1) -> None:
        bans = self.control.host.store.list_bans()
        if not bans:
            return await reply_private(interaction, t("troll_ctl_bans_none"))
        pages = math.ceil(len(bans) / BANS_PER_PAGE)
        if page > pages:
            return await reply_private(interaction, t("troll_ctl_bans_bad_page", pages=pages))
        lines = []
        for ban in bans[(page - 1) * BANS_PER_PAGE: page * BANS_PER_PAGE]:
            until = t("troll_ctl_permanent") if ban.expires_at is None else f"<t:{ban.expires_at}:R>"
            lines.append(f"• <@{ban.user_id}> `{ban.user_id}` · {until}{' · 🔔' if ban.notify else ''}\n"
                         f"  {inline(shown_reason(ban.reason), 90)}")
        embed = discord.Embed(title=t("troll_ctl_bans_title", count=len(bans)), description="\n".join(lines), colour=discord.Colour.red())
        embed.set_footer(text=t("troll_ctl_bans_footer", page=page, pages=pages))
        await interaction.response.send_message(embed=embed, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    # ── /baninfo ─────────────────────────────────────────────────────────────
    @app_commands.command(name="baninfo", description="Show everything about one user's ban.")
    @app_commands.describe(user="The user's ID, or an @mention")
    async def baninfo(self, interaction: discord.Interaction, user: app_commands.Range[str, 1, 64]) -> None:
        uid = parse_user_ref(user)
        if uid is None:
            return await reply_private(interaction, t("troll_ctl_bad_user"))
        ban = self.control.host.store.active_ban(uid)
        if ban is None:
            return await reply_private(interaction, t("troll_ctl_baninfo_not_found", id=uid))
        await interaction.response.defer(ephemeral=True)         # fetching the user is a web request
        found, _ = await self._lookup(uid)
        embed = discord.Embed(title=t("troll_ctl_baninfo_title"), colour=discord.Colour.red())
        if found is not None:
            embed.set_thumbnail(url=found.display_avatar.url)
        embed.add_field(name="User", value=f"{safe_name(found.name) if found else 'Unknown'} (`{uid}`)", inline=False)
        embed.add_field(name="Reason", value=shown_reason(ban.reason), inline=False)
        embed.add_field(name="Expires", value=when(ban.expires_at), inline=True)
        embed.add_field(name="Notify", value="Yes 🔔" if ban.notify else "No", inline=True)
        embed.add_field(name="Banned by", value=f"<@{ban.banned_by}> (`{ban.banned_by}`)", inline=True)
        embed.add_field(name="Banned", value=when(ban.banned_at), inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    # ── /banedit ─────────────────────────────────────────────────────────────
    @app_commands.command(name="banedit", description="Change the reason of an existing ban.")
    @app_commands.describe(user="The user's ID, or an @mention", reason="The new reason")
    async def banedit(
        self, interaction: discord.Interaction, user: app_commands.Range[str, 1, 64],
        reason: app_commands.Range[str, 1, REASON_MAX],
    ) -> None:
        uid = parse_user_ref(user)
        if uid is None:
            return await reply_private(interaction, t("troll_ctl_bad_user"))
        if self.control.level_of(uid) == MOD and self.control.level_of(interaction.user.id) != ADMIN:
            return await reply_private(interaction, t("troll_ctl_banedit_mod_admin_only"))
        try:
            ban: Optional[Ban] = await self.control.host.store.set_reason(uid, reason)
        except (sqlite3.Error, RuntimeError) as e:
            return await reply_private(interaction, self._db_failed(interaction, "/banedit", e))
        if ban is None:
            return await reply_private(interaction, t("troll_ctl_baninfo_not_found", id=uid))
        self.control.tlog.record("ok", "/banedit · reason changed", interaction, sid=session_id(interaction),
                                 summary=f"Changed the reason for `{uid}`.", details=f"New reason: {ban.reason}")
        await reply_private(interaction, t("troll_ctl_banedit_success", id=uid, reason=shown_reason(ban.reason)))

    # ── /devpannel ───────────────────────────────────────────────────────────
    @app_commands.command(name="devpannel", description="Admins only: diagnostics, switch bot, add a bot token.")
    async def devpannel(self, interaction: discord.Interaction) -> None:
        control = self.control
        if await refuse_not_admin(control, interaction):
            return
        age = interaction_age_ms(interaction)          # measured first: the rest takes time
        await interaction.response.defer(ephemeral=True)       # the diagnostics run ffmpeg and web requests
        try:
            clip = await make_test_clip()              # for the "Test voice message" button
        except AudioError:
            clip = None
        roster = await control.host.roster()
        view = DiagView(control, interaction, clip=clip, roster=roster, age_ms=age)
        await interaction.followup.send(embed=await diag_embed(control, interaction, age, roster), view=view, ephemeral=True)
        control.tlog.record("ok", "/devpannel · panel opened", interaction, sid=session_id(interaction))


# ─────────────────────────────────────────────────────────────────────────────
# The bot
# ─────────────────────────────────────────────────────────────────────────────

class ControlBot(ReportMixin, commands.Bot):
    """
    The control bot. Intents: only `guilds` (non-privileged) — slash commands are interactions and need nothing else,
    and `guilds` lets it notice (and leave) servers it was added to by mistake.
    """

    def __init__(self, host: TrollenatorHost, settings: ControlSettings) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents, help_command=None, tree_cls=ControlTree)
        self.host = host
        self.settings = settings
        self.tlog = host.tlog
        self.online = asyncio.Event()
        self.started_at = time.monotonic()
        self._announced = False
        self._refusal_logged: dict[int, float] = {}

    def level_of(self, user_id: int) -> Optional[str]:
        return self.settings.level_of(user_id)

    def note_refusal(self, interaction: discord.Interaction, why: str) -> None:
        """Log a refused attempt — at most once a minute per person, so it can't be used to flood the log."""
        uid = interaction.user.id
        now = time.monotonic()
        if now - self._refusal_logged.get(uid, float("-inf")) < 60:
            return
        self._refusal_logged[uid] = now
        if len(self._refusal_logged) > 1000:
            self._refusal_logged = {u: ts for u, ts in self._refusal_logged.items() if now - ts < 60}
        name = interaction.command.qualified_name if interaction.command else f"component:{interaction.type.name}"
        self.tlog.record("warn", f"Control · refused ({why})", interaction, sid=session_id(interaction),
                         summary=f"Tried to use `{inline(name, 60)}`.")

    # ── startup ──────────────────────────────────────────────────────────────
    async def setup_hook(self) -> None:
        guild = discord.Object(id=self.settings.guild_id)
        await self.add_cog(ControlCommands(self), guild=guild)
        await self._sync_commands(guild)

    def _fingerprint(self, guild: discord.abc.Snowflake) -> str:
        payload = [cmd.to_dict(self.tree) for cmd in self.tree.get_commands(guild=guild)]
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        return f"{self.application_id}:{guild.id}:{digest}"

    async def _sync_commands(self, guild: discord.abc.Snowflake) -> None:
        """Push the control commands to the control server — only when their definitions changed."""
        fingerprint = self._fingerprint(guild)
        if load_data(STATE_FILE).get("control_synced") == fingerprint:
            log.info("Control bot: slash commands unchanged — skipping sync.")
            return
        try:
            synced = await self.tree.sync(guild=guild)
        except discord.HTTPException as e:
            log.error(f"Control bot: slash command sync failed: {e}")
            self.tlog.record("fail", "Control · slash command sync failed", error=e,
                             summary=f"HTTP {e.status}, code {e.code}: {inline(e.text or str(e), 300)}")
            return
        state = load_data(STATE_FILE)               # read AGAIN: the state may have changed while we were waiting on Discord
        state["control_synced"] = fingerprint
        save_data(STATE_FILE, state)
        log.info(f"Control bot: synced {len(synced)} slash command(s) to the control server.")
        self.tlog.record("ok", "Control · slash commands synced", summary=", ".join(f"/{c.name}" for c in synced))

    # ── events ───────────────────────────────────────────────────────────────
    async def on_ready(self) -> None:
        self.online.set()
        self.host.control_app_id = self.application_id or 0
        for guild in list(self.guilds):
            if guild.id != self.settings.guild_id:
                await self._leave(guild)
        if self.get_guild(self.settings.guild_id) is None:
            log.warning("Control bot: it is not in the control server yet — open its Install Link and add it to server "
                        f"{self.settings.guild_id}.")
            self.tlog.record("warn", "Control · not in the control server",
                             summary=f"Add the control bot to server {self.settings.guild_id} (guild install).")
        if not self._announced:
            self._announced = True
            log.info(f"Control bot online as {self.user} (ID: {self.user.id})")
            self.tlog.record("ok", "Control bot online", summary=f"Logged in as {self.user} (ID {self.user.id}) · "
                             f"{len(self.settings.admins)} admin(s), {len(self.settings.mods)} mod(s).")

    async def on_guild_join(self, guild: discord.Guild) -> None:
        if guild.id != self.settings.guild_id:
            await self._leave(guild)

    async def _leave(self, guild: discord.Guild) -> None:
        """The control bot belongs to ONE server. Anywhere else it has no business — and no commands — so it leaves."""
        try:
            await guild.leave()
        except discord.HTTPException as e:
            log.error(f"Control bot: could not leave server {guild.id}: {e}")
            self.tlog.record("fail", "Control · could not leave a foreign server", error=e, summary=f"Server `{guild.id}`.")
            return
        log.warning(f"Control bot was added to a server other than the control server and left it ({guild.id}).")
        self.tlog.record("warn", "Control · left a foreign server",
                         summary=f"It was added to `{guild.id}` ({inline(guild.name, 60)}) and left at once.")

    async def on_disconnect(self) -> None:
        self.tlog.record("warn", "Control bot: gateway disconnected", summary="discord.py reconnects by itself.")

    async def on_resumed(self) -> None:
        self.tlog.record("info", "Control bot: gateway session resumed")


async def run_control(control: ControlBot) -> None:
    """Log the control bot in and keep it connected. A bad token is logged loudly; Trollenator itself keeps running."""
    try:
        await control.start(control.settings.token, reconnect=True)
    except discord.LoginFailure:
        log.critical("Control bot login failed — Discord rejected control_token. Bans and the dev panel are unavailable.")
        control.tlog.record("fail", "Control bot login failed", summary="Discord rejected control_token.")
    except asyncio.CancelledError:
        raise
    except discord.PrivilegedIntentsRequired:
        log.critical("Control bot: Discord says it needs a privileged intent it doesn't ask for — this should not happen.")
    except Exception as e:
        log.exception("Control bot stopped unexpectedly")
        control.tlog.record("fail", "Control bot stopped unexpectedly", error=e, summary=f"{type(e).__name__}")
