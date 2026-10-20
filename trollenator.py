"""
trollenator.py — Trollenator: a user-installed Discord app (its own program, no bot-Bot needed).

What this is
────────────
Trollenator is a Discord application that people install to their own *account* ("user install"), so its slash
commands follow them into any server, DM or group DM — even servers where the app was never added.

Two Discord applications run inside this one process (see main.py):
  • the USER APP (this file) — the commands below. Several bot tokens can be configured; ONE runs at a time.
  • the CONTROL BOT (control.py) — a private bot installed to ONE server of yours. It is the only place where bans,
    unbans, the dev panel, switching the active bot and adding bot tokens live. This file never changes who may
    use it; it only asks the shared ban list (store.py) whether a user is banned.

Commands of the user app (slash only, user-install only)
────────────────────────────────────────────────────────
  /say [text] [repeat-amount] [ping] [tts] [media]
                                      Private plain-text editor (every option is optional): change the text /
                                      repeat amount (typed: any number, decimals ignored, 0 or less = 1; "max",
                                      "all" … or a number too big for one message = as many lines as fit), attach
                                      a file of any kind
                                      (right in the command with `media`; more with the editor's Media button),
                                      toggle TTS and Pings, then Send. No embeds.
  /embed [ping] [tts] [media]   Private embed builder: edit with buttons + forms, add files outside the
                                      embed (`media` or the Media button), toggle TTS and Pings, then Send.
  /voice [audio]                Private editor for a Discord voice message: upload any audio file (it is
                                      converted to Ogg/Opus with ffmpeg), then Send.
  /poll [question] [ping] [tts] Private poll editor: question, answers, duration, multiple choice;
                                      TTS and Pings apply to the message above the poll.
  /permcheck                          Private report of what you and the app can do in this channel.

  Every command name starts with the first letters of the running bot's name — "/trolle-say" for a bot
  called "Trollenator" — so apps installed side by side never share command names. (The names above are the
  base names; messages and the activity log show them with the prefix where users see them.)

One-time setup
──────────────
  1. discord.com/developers/applications → New Application.  (One application per bot token you want.)
  2. Installation tab → turn ON "User Install" and OFF "Guild Install".
  3. Bot tab → Reset Token → paste it into Configs/trollenator_config.json ("token").
  4. pip install -r requirements.txt       (discord.py 2.7+: file uploads inside forms need it)
  5. sudo apt install ffmpeg               (only /voice needs it)
  6. Create the CONTROL BOT the same way but turn ON "Guild Install" and OFF "User Install", set its token and
     your private server's ID ("control_token", "control_guild_id") and the people allowed to use it ("admins",
     "mods") — see README.md.
  7. python3 main.py, then open the user app's Install Link and add it to your account.

Config  (Configs/trollenator_config.json)
─────────────────────────────────────────
  enabled           true/false — kill switch for the USER app (the control bot still runs, so bans stay manageable)
  token             bot token of a Trollenator user app
  tokens            more bots — a list of token strings, or of {"token": "...", "prefix": "optional"} (the
                    optional "prefix" replaces the bot's name when making the command prefix, up to 16 letters or
                    digits; useful if two bots' names start with the same 6 letters). ONE bot runs at a time:
                    the one last chosen in /devpannel, else the first listed (token, then tokens). Up to 25.
  control_token     bot token of the CONTROL bot (must be a different application from every user app)
  control_guild_id  ID of the private server the control bot lives in. REQUIRED when control_token is set: the
                    control bot answers nobody anywhere else and leaves any other server it is added to.
  admins            user IDs: may do everything — bans (including of mods), the dev panel, switching bots,
                    adding bot tokens.
  mods              user IDs: may ban, unban and look at bans (not the dev panel, not other staff).
  cooldown_seconds  pause between a user's posts — /say, /embed, /poll and /voice (0 = off)
  tos_warnings      true/false — the ToS warning (see "ToS warning" below). Default true.
  tos_terms         list of words/phrases to flag as hateful/abusive (nothing is hard-coded — you choose)
  tos_terms_file    optional text file of such terms, one per line (path relative to Configs/, or absolute)
  log_webhook_url   Discord webhook that receives the activity log (see "Activity log" below). Empty = no
                    webhook log (errors are then only in Data/trollenator.log).

Data  (Data/)
─────────────
  trollenator.db           the ban list (SQLite). Owned by this process — don't edit it while Trollenator runs.
  trollenator_state.json   per application, a fingerprint of the registered slash commands so they are only
                           re-synced with Discord when they actually change (switching bots back and forth doesn't
                           re-sync), and which bot was active ("active", a fingerprint of its token — not the
                           token). Delete the file to force a re-sync.
  trollenator.log          the program's own log (rotated, secrets removed).

Switching bots
──────────────
  /devpannel (control bot, admins) → "Switch the active bot…" (shown when two or more bots are configured) → confirm.
  The new token is checked with Discord first; then the running bot is stopped and the new one started. If it can't
  come online the previous bot is started again. "Add bot token" checks a pasted token, appends it to "tokens" in
  Configs/trollenator_config.json (atomic write, file readable by its owner only) and offers to switch.
  The token you paste travels through Discord like any modal input; if you'd rather it didn't, edit the config
  file by hand instead. It is never logged, shown or kept in the editor.
  The control bot keeps running while user apps are swapped, so you can always switch back from your private
  server — even to or from an app that isn't installed on your own account. Open editors of the old bot stop
  working when it goes offline.

How permissions work for a user-installed app
─────────────────────────────────────────────
  Two separate sets of permissions matter, and Discord hands us both in every interaction:
    • The USER's permissions in that channel (interaction.permissions). "Use External Apps"
      decides whether the app may post publicly there; without it Discord only allows
      private (ephemeral) replies. "Send Messages" is needed to post at all.
    • The APP's permissions in that channel (interaction.app_permissions). For an app that
      isn't a member of the server this mirrors what @everyone can do, limited to Embed
      Links, Attach Files, Mention Everyone and Use External Emojis.
  Both are checked BEFORE posting; if something is missing the user gets a private
  message naming exactly what. /permcheck shows the full picture.

Pings
─────
  `ping` defaults to ON. Choosing "no" sends allowed_mentions=none, so nothing pings. The editors'
  Pings button flips it before you press Send (green = pings on, red = off).
  When ON, user mentions always work; @everyone/@here need the app to have Mention Everyone
  in that channel (rare outside DMs/group DMs) and role pings need a mentionable role or
  Mention Everyone. If a ping can't work the message is still sent and the user gets a
  private note saying why.

TTS
───
  The `tts` slash option starts the editor with text-to-speech ON; the editor's TTS button toggles it
  (red = off, green = on). Discord reports the APP's Send TTS Messages permission separately from
  yours — /permcheck shows both. /voice has no TTS (a voice message carries no text).

Voice messages
──────────────
  Discord shows a message as a voice message when it carries the IS_VOICE_MESSAGE flag and ONE
  Ogg/Opus attachment with a duration and a waveform. The audio is converted (and its waveform
  computed) when it is uploaded; Send then answers the button press with the voice message itself.
  Such a message can't hold text, embeds, other files or a poll.

Banned users
────────────
  Anyone on the ban list (store.py) is rejected with a private message before every command and button press.
  Active bans live in memory (written through to the database), so the check is instant and a ban made with the
  control bot applies to the very next press.

Activity log (webhook)
──────────────────────
  Everything Trollenator does is reported to the webhook in `log_webhook_url` (class TrollLog): who ran
  which command, where and when, the options / message / embed / poll / voice details that were involved,
  and how it ended — sent, blocked (and why: permission, cooldown, ban …), failed (with Discord's error),
  cancelled or expired — plus errors with tracebacks, start-up/shut-down, command sync, gateway
  disconnects, event-loop stalls and "Unknown interaction" (10062) timing breakdowns. Control-bot actions (bans,
  switches, token additions) are logged the same way. Entries from one command share a short session id so they
  can be followed from start to finish.
  The log text is built so it can't hurt: webhook mentions are disabled (a logged @everyone never pings),
  user text is code-fenced, and tokens (bot token, interaction tokens, webhook URLs) are redacted.
  The log contains what users typed and the names of files they attached, so treat that channel as private.

ToS warning
───────────
  When a public post looks like it could break Discord's rules (spam-like repeats, mass pings, threats or
  self-harm taunts, doxxing, scams / IP-grabbing / lookalike links, impersonating Discord, risky file types,
  words from your own list …) the editor is replaced by a warning with two buttons: Acknowledge (cancels the
  command) or Ignore (sends as normal). It never blocks anyone. See the "ToS risk check" section below, and
  every warning and every choice is in the activity log. Voice messages can't be read, so they aren't checked.

Voice conversion
────────────────
  Only audio formats on an allow-list (mp3, wav, ogg, flac, aac, m4a/mp4, webm/mkv, wma, aiff, amr, caf) are
  handed to ffmpeg, and ffmpeg may only read the one local file (-protocol_whitelist file), so a crafted
  "audio" file can't make it fetch URLs or read other files. A file that is already Ogg/Opus is sent as it
  is (no re-encoding); everything else is decoded once, at low priority and one at a time.
"""
import array
import asyncio
import base64
import collections
import dataclasses
import hashlib
import io
import ipaddress
import json
import logging
import math
import os
import re
import shutil
import sys
import tempfile
import time
import traceback
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import aiohttp
import discord
from discord import app_commands, ui
from discord.ext import commands

import strings as strings_mod
from appconfig import CONFIG_DIR, CONFIG_PATH, STATE_FILE, atomic_write, load_data, save_data
from store import Store

if discord.version_info < (2, 7):
    raise RuntimeError(
        f"Trollenator needs discord.py 2.7 or newer (found {discord.__version__}). "
        'Run:  pip install -U "discord.py>=2.7"'
    )

log = logging.getLogger("trollenator")

# ── Discord limits & our own caps ────────────────────────────────────────────
MAX_MESSAGE_LEN   = 2000                 # characters in one message
EMBED_TOTAL_LIMIT = 6000                 # characters across all parts of an embed
MAX_FIELDS        = 25
MAX_IMAGE_BYTES   = 8 * 1024 * 1024      # per uploaded image (our cap, below Discord's)
FALLBACK_UPLOAD   = 10 * 1024 * 1024     # used if Discord doesn't tell us the channel's limit
BUILDER_TIMEOUT   = 14 * 60              # interaction tokens last 15 min; stay inside that
REPEAT_CEILING    = (MAX_MESSAGE_LEN + 1) // 2   # most lines Discord could ever fit (1-character text) = what "max" means
REPEAT_INPUT_MAX  = 100                  # characters the repeat-amount box accepts
MAX_ATTACHMENTS   = 10                   # Discord's limit of files per message
MAX_MEDIA_BYTES   = 25 * 1024 * 1024     # most file data ONE editor may hold in memory (our cap, whatever Discord allows)
MAX_OPEN_EDITORS  = 3                    # editors one user may have open at once — the oldest closes (memory cap)
MAX_AUDIO_BYTES   = 25 * 1024 * 1024     # biggest audio file /voice will convert (our cap)
MAX_VOICE_SECONDS = 20 * 60              # longest clip /voice will convert (our cap)
AUDIO_TIMEOUT     = 120                  # seconds ffmpeg may spend on one clip
AUDIO_MAX_PENDING = 3                    # conversions running + waiting; more are refused as "busy" (the Pi has few cores)
LOOP_LAG_WARN     = 0.75                 # seconds of event-loop stall worth reporting
LOG_QUEUE_MAX     = 500                  # log entries kept while the webhook is slow/unreachable (oldest dropped)
LOG_EMBED_BUDGET  = 5600                 # characters per webhook message (Discord allows 6000 across its embeds)
VOICE_FLAG        = 1 << 13              # Discord's IS_VOICE_MESSAGE message flag
WAVEFORM_BUCKETS  = 256                  # amplitude samples in a voice message's waveform
WAVEFORM_RATE     = 4000                 # Hz we decode at to measure that waveform (and the duration)
POLL_MAX_ANSWERS  = 10
POLL_QUESTION_MAX = 300
POLL_ANSWER_MAX   = 55
POLL_MIN_HOURS    = 1
POLL_MAX_HOURS    = 32 * 24              # Discord: polls stay open up to 32 days
DISCORD_API       = "https://discord.com/api/v10"   # base URL of the one raw request (voice messages)

IMAGE_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp"}
IMAGE_EXTS  = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".gif": "image/gif", ".webp": "image/webp"}
IMAGE_SLOTS = ("author_icon", "footer_icon", "thumbnail", "image")

THREAD_TYPES = (
    discord.ChannelType.public_thread,
    discord.ChannelType.private_thread,
    discord.ChannelType.news_thread,
)

NAMED_COLOURS = {
    "red": 0xED4245, "orange": 0xE67E22, "yellow": 0xFEE75C, "green": 0x57F287,
    "blue": 0x3498DB, "blurple": 0x5865F2, "purple": 0x9B59B6, "pink": 0xEB459E,
    "fuchsia": 0xEB459E, "teal": 0x1ABC9C, "white": 0xFFFFFF, "black": 0x010101,
    "grey": 0x95A5A6, "gray": 0x95A5A6,
}


# ─────────────────────────────────────────────────────────────────────────────
# Pure helpers (no Discord calls — easy to test)
# ─────────────────────────────────────────────────────────────────────────────

# Words that mean "as many lines as fit" (compared case-insensitively). Anything else that isn't a number is rejected.
REPEAT_MAX_WORDS = frozenset({
    "max", "maximum", "all", "everything", "full", "fill", "limit", "unlimited", "inf", "infinity",
})
# [sign] whole number (optionally written with thousands commas: 1,000) [.decimals] — ASCII digits only.
_RE_REPEAT_NUMBER = re.compile(r"([+-]?)([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)?(?:\.([0-9]*))?")


def parse_repeat(raw: Optional[str]) -> tuple[int, bool]:
    """
    Parse the repeat-amount text → (requested lines, was_max).

      empty                      → 1
      a number                   → that many lines; decimals are ignored ("3.9" → 3, "1,000" → 1000)
      0, a negative, or < 1      → 1
      bigger than any message
      could hold (> REPEAT_CEILING) → treated exactly like max
      "max", "all", "full" …     → max (see REPEAT_MAX_WORDS)
      anything else              → ValueError

    "max" is returned as REPEAT_CEILING, which build_repeated() then clamps to what actually fits.
    The number is never converted until it is known to be short, so a pasted 5,000-digit value can't hit
    Python's int-conversion limit or burn CPU.
    """
    s = (raw or "").strip().casefold()
    if not s:
        return 1, False
    if s in REPEAT_MAX_WORDS:
        return REPEAT_CEILING, True
    m = _RE_REPEAT_NUMBER.fullmatch(s)
    if m is None or not (m.group(2) or m.group(3)):       # not a number, or no digits at all ("-", ".")
        raise ValueError(raw)
    sign, whole = m.group(1), (m.group(2) or "").replace(",", "").lstrip("0")
    if sign == "-" or not whole:                          # negative, zero, or only decimals ("0.7")
        return 1, False
    if len(whole) > len(str(REPEAT_CEILING)) or int(whole) > REPEAT_CEILING:
        return REPEAT_CEILING, True
    return int(whole), False


def build_repeated(text: str, requested: int) -> tuple[str, int]:
    """
    Repeat `text` on `requested` lines without ever exceeding Discord's message limit.
    Whole lines only — we stop at the last one that fits. Returns (message, lines_used).
    """
    fits  = max(1, (MAX_MESSAGE_LEN + 1) // (len(text) + 1))   # n*len + (n-1) <= 2000
    lines = min(max(1, requested), fits)
    return "\n".join([text] * lines), lines


def parse_colour(raw: str) -> int:
    """'#5865F2', '5865f2', '0x5865F2', '#f00' or a name from NAMED_COLOURS → int."""
    s = raw.strip().lower().replace(" ", "")
    if s in NAMED_COLOURS:
        return NAMED_COLOURS[s]
    m = re.fullmatch(r"(?:#|0x)?([0-9a-f]{6}|[0-9a-f]{3})", s)
    if not m:
        raise ValueError(raw)
    digits = m.group(1)
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    return int(digits, 16)


def parse_timestamp(raw: str) -> tuple[bool, Optional[datetime]]:
    """
    'now' → (True, None)   [resolved when the embed is actually sent]
    unix seconds/ms or an ISO date ('2026-10-02 18:30', assumed UTC) → (False, datetime)
    """
    s = raw.strip()
    if s.lower() == "now":
        return True, None
    try:
        if s.isascii() and s.isdigit():
            n = int(s)
            if n > 10 ** 11:            # looks like milliseconds
                n //= 1000
            return False, datetime.fromtimestamp(n, tz=timezone.utc)
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, OverflowError, OSError):
        raise ValueError(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return False, dt


def clean_url(raw: str) -> str:
    """Accept only http(s) links (what embeds support). Raises ValueError otherwise."""
    s = raw.strip()
    if len(s) > 2000 or not re.fullmatch(r"https?://\S+", s, re.IGNORECASE):
        raise ValueError(raw)
    return s


def safe_filename(original: str, mime: str) -> str:
    """A tame filename for re-uploading (embeds reference it as attachment://name)."""
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(original).stem).strip("_")[:40] or "image"
    return f"{stem}.{IMAGE_TYPES[mime]}"


def fmt_mb(n: int) -> str:
    return f"{n / 1048576:.1f}"


def inline(text: str, limit: int = 40) -> str:
    """Make user text safe to drop inside `backticks` in a message."""
    return text.replace("`", "'").replace("\n", " ")[:limit]


def allowed_mentions(pings_on: bool) -> discord.AllowedMentions:
    return discord.AllowedMentions.all() if pings_on else discord.AllowedMentions.none()


def ping_notes(message: str, app_perms: discord.Permissions) -> list[str]:
    """Private notes explaining pings that can't work with the app's permissions here."""
    if app_perms.mention_everyone:
        return []
    notes = []
    if re.search(r"@(?:everyone|here)\b", message):
        notes.append(t("troll_ping_everyone"))
    if re.search(r"<@&\d+>", message):
        notes.append(t("troll_ping_roles"))
    return notes


def safe_media_filename(original: str) -> str:
    """A tame filename for re-uploading ANY kind of file (the extension is kept)."""
    p = Path(original)
    stem = re.sub(r"[^\w-]+", "_", p.stem).strip("_")[:60] or "file"     # \w keeps letters of any language
    ext = re.sub(r"[^a-z0-9]", "", p.suffix.lower())[:10]
    return f"{stem}.{ext}" if ext else stem


def unique_names(names: list[str], taken: Optional[set[str]] = None) -> list[str]:
    """Make every name unique (a.png, a-2.png, a-3.png …) without touching names that are already fine."""
    used = set(taken or ())
    out: list[str] = []
    for name in names:
        candidate, n = name, 1
        while candidate in used:
            n += 1
            p = Path(name)
            candidate = f"{p.stem}-{n}{p.suffix}"
        used.add(candidate)
        out.append(candidate)
    return out


# ── polls ────────────────────────────────────────────────────────────────────
_CUSTOM_EMOJI = re.compile(r"<a?:\w{2,32}:\d{15,25}>")
_UNICODE_EMOJI = re.compile(
    "(?:[\U0001F1E6-\U0001F1FF]{2}"                                 # flags
    "|[0-9#*]\uFE0F?\u20E3"                                         # keycaps
    "|(?:[\U0001F300-\U0001FAFF"                                    # pictographs, faces, objects …
    "\u2705\u274C\u274E\u2753-\u2755\u2757\u2764\u2B50\u2728\u26A1\u2600-\u2604\u260E\u2611"
    "\u2614\u2615\u2648-\u2653\u267F\u2693\u26A0\u26AA\u26AB\u26BD\u26BE\u26C4\u26C5\u26CE"
    "\u26D4\u26EA\u26F2\u26F3\u26F5\u26FA\u26FD\u2702\u2708\u2709\u270A-\u270D\u270F\u2712"
    "\u2714\u2716\u271D\u2721\u2733\u2734\u2744\u2747\u2795-\u2797\u27A1\u27B0\u27BF\u2934"
    "\u2935\u2B05-\u2B07\u2B1B\u2B1C\u2B55\u231A\u231B\u23E9-\u23F3\u23F8-\u23FA]"
    "[\uFE0F\U0001F3FB-\U0001F3FF]?"
    "(?:\u200D[\U0001F300-\U0001FAFF\u2640\u2642\u2695\u2696\u2708\u2764]\uFE0F?[\U0001F3FB-\U0001F3FF]?)*))"
)


class PollInputError(ValueError):
    """A poll form problem: kind is 'too_many' | 'too_long' | 'no_text'; line is the 1-based answer line."""

    def __init__(self, kind: str, line: int = 0) -> None:
        super().__init__(kind)
        self.kind = kind
        self.line = line


def split_emoji(line: str) -> tuple[Optional[str], str]:
    """'🍕 Pizza' → ('🍕', 'Pizza') · '<:blob:123…> Hi' → ('<:blob:123…>', 'Hi') · 'Plain' → (None, 'Plain')."""
    s = line.strip()
    m = _CUSTOM_EMOJI.match(s) or _UNICODE_EMOJI.match(s)
    if not m:
        return None, s
    return m.group(0), s[m.end():].strip()


def parse_poll_answers(raw: str) -> list[tuple[Optional[str], str]]:
    """
    One answer per line (blank lines are skipped), each optionally starting with an emoji.
    Returns [(emoji or None, text)]. Raises PollInputError for >10 answers, an answer over
    55 characters, or an answer that is only an emoji.
    """
    answers: list[tuple[Optional[str], str]] = []
    for n, line in enumerate((ln for ln in raw.splitlines() if ln.strip()), start=1):
        emoji, text = split_emoji(line)
        if not text:
            raise PollInputError("no_text", n)
        if len(text) > POLL_ANSWER_MAX:
            raise PollInputError("too_long", n)
        answers.append((emoji, text))
    if len(answers) > POLL_MAX_ANSWERS:
        raise PollInputError("too_many")
    return answers


def format_answers(answers: list[tuple[Optional[str], str]]) -> str:
    """The inverse of parse_poll_answers — used to pre-fill the form."""
    return "\n".join(f"{emoji} {text}" if emoji else text for emoji, text in answers)


def parse_duration(raw: str) -> int:
    """'24h' · '3d' · '2w' · '36' (hours) → whole hours, 1 hour … 32 days. Raises ValueError otherwise."""
    m = re.fullmatch(
        r"(\d+(?:\.\d+)?)(h|hr|hrs|hour|hours|d|day|days|w|wk|wks|week|weeks)?",
        raw.strip().lower().replace(" ", ""))
    if not m:
        raise ValueError(raw)
    per_unit = {"h": 1, "d": 24, "w": 168}
    hours = round(float(m.group(1)) * per_unit[(m.group(2) or "h")[0]])
    if not POLL_MIN_HOURS <= hours <= POLL_MAX_HOURS:
        raise ValueError(raw)
    return hours


def format_duration(hours: int) -> str:
    if hours % 168 == 0:
        return f"{hours // 168}w"
    if hours % 24 == 0:
        return f"{hours // 24}d"
    return f"{hours}h"


# ── voice messages ───────────────────────────────────────────────────────────
# Discord shows a message as a voice message when it has the IS_VOICE_MESSAGE flag and ONE
# Ogg/Opus attachment that carries a duration and a waveform. So an uploaded audio file is
# converted to Ogg/Opus with ffmpeg and we work the duration + waveform out ourselves.

class AudioError(Exception):
    """Why a file couldn't become a voice message: no_ffmpeg | unsupported | unreadable | timeout | too_long | busy."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class VoiceClip:
    data: bytes          # Ogg/Opus bytes, ready to upload
    duration: float      # seconds
    waveform: str        # base64 of 256 amplitude bytes (0-255)
    source_name: str     # the file it came from (for the editor)
    mode: str = "converted"    # "as-is" = it already was Ogg/Opus and is sent untouched · "converted" = re-encoded
    convert_ms: int = 0        # how long the work took (for the activity log)
    source_bytes: int = 0      # size of the file that was uploaded


def waveform_from_pcm(pcm: bytes, rate: int) -> tuple[float, str]:
    """
    Mono signed 16-bit little-endian PCM → (duration in seconds, Discord waveform).
    The waveform is WAVEFORM_BUCKETS peak amplitudes, scaled so the loudest one is 255.
    """
    samples = array.array("h")
    samples.frombytes(pcm[: len(pcm) // 2 * 2])
    if sys.byteorder == "big":
        samples.byteswap()
    n = len(samples)
    duration = n / rate
    if n == 0:
        return 0.0, base64.b64encode(bytes(WAVEFORM_BUCKETS)).decode()
    size = n / WAVEFORM_BUCKETS
    peaks: list[int] = []
    for i in range(WAVEFORM_BUCKETS):
        lo = int(i * size)
        hi = max(lo + 1, int((i + 1) * size))
        chunk = samples[lo:hi:max(1, (hi - lo) // 64)]       # ≤ ~64 looks per bucket is plenty
        peaks.append(max(abs(s) for s in chunk) if len(chunk) else 0)
    loudest = max(peaks) or 1
    return duration, base64.b64encode(bytes(round(p * 255 / loudest) for p in peaks)).decode()


_NICE = shutil.which("nice")          # lets ffmpeg yield the CPU to the bot (the host is a small board)
AS_IS_MAX_BITRATE = 96_000            # an Ogg/Opus file above this is re-encoded anyway: smaller = faster upload
_audio_slot: Optional[asyncio.Semaphore] = None    # at most ONE conversion runs at a time …
_audio_pending = 0                                 # … and at most AUDIO_MAX_PENDING may be running or waiting


async def _ffmpeg(ffmpeg: str, *args: str) -> bytes:
    """Run ffmpeg (lowest-ish priority), return its stdout. Raises AudioError on failure or timeout."""
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", *args]
    if _NICE:
        cmd = [_NICE, "-n", "15", *cmd]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), AUDIO_TIMEOUT)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise AudioError("timeout")
    except asyncio.CancelledError:          # plugin unloaded mid-conversion: don't leave ffmpeg running
        proc.kill()
        raise
    if proc.returncode != 0:
        log.info(f"Trollenator: ffmpeg could not read the audio: {err.decode(errors='replace')[:300]}")
        raise AudioError("unreadable")
    return out


def sniff_audio_format(head: bytes) -> Optional[str]:
    """
    The ffmpeg demuxer for an audio file, decided from its first bytes — or None if it isn't a format we accept.

    Security: ffmpeg is told this format explicitly (-f), so it never auto-detects things like playlists
    (HLS, concat …) that can point at other files or at network addresses.
    """
    if head[:4] == b"OggS":
        return "ogg"
    if head[:4] == b"fLaC":
        return "flac"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav"
    if head[:4] == b"FORM" and head[8:12] in (b"AIFF", b"AIFC"):
        return "aiff"
    if head[:4] == b"caff":
        return "caf"
    if head[4:8] == b"ftyp":
        return "mov"                                     # mp4 / m4a / 3gp / mov
    if head[:4] == b"\x1aE\xdf\xa3":
        return "matroska"                                # mkv / webm
    if head[:16] == bytes.fromhex("3026b2758e66cf11a6d900aa0062ce6c"):
        return "asf"                                     # wma
    if head[:9] == b"#!AMR-WB\n":
        return "amrwb"
    if head[:6] == b"#!AMR\n":
        return "amr"
    if head[:3] == b"ID3":
        return "mp3"
    if len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0:
        return "aac" if (head[1] & 0x06) == 0 else "mp3"     # ADTS AAC has layer bits 00, mp3 doesn't
    return None


def is_ogg_opus(data: bytes) -> bool:
    """
    True if `data` is already a mono Ogg/Opus file (what a voice message is made of): the first Ogg page
    must be an OpusHead packet with a plain channel layout. Pure Python — no subprocess, no decoding.
    """
    if len(data) < 47 or data[:4] != b"OggS" or data[4] != 0 or not data[5] & 0x02:
        return False
    start = 27 + data[26]                       # 27-byte page header + the segment table
    head = data[start:start + 19]
    return (len(head) == 19 and head[:8] == b"OpusHead" and head[8] >> 4 == 0
            and head[9] == 1 and head[18] == 0)


async def _ffmpeg_run(ffmpeg: str, src: Path, fmt: str, *, opus_out: Optional[Path], pcm: bool) -> bytes:
    """
    ONE ffmpeg run that reads `src` once and produces what is asked: Ogg/Opus into `opus_out`
    and/or mono 4 kHz PCM (for the waveform + duration) on stdout.
    """
    args = [
        "-threads", "1",                        # one decoder thread: don't starve the bot
        "-protocol_whitelist", "file",          # the input may only be this local file — no URLs, no other protocols
        "-t", str(MAX_VOICE_SECONDS + 1),       # +1 so "too long" can be told from "exactly the limit"
        "-f", fmt, "-i", str(src),
    ]
    if opus_out is not None:
        args += ["-map", "0:a:0", "-c:a", "libopus", "-b:a", "32k", "-ar", "48000", "-ac", "1",
                 "-threads", "1", "-f", "ogg", str(opus_out)]
    if pcm:
        args += ["-map", "0:a:0", "-ac", "1", "-ar", str(WAVEFORM_RATE), "-f", "s16le", "pipe:1"]
    return await _ffmpeg(ffmpeg, *args)


async def _convert(ffmpeg: str, fmt: str, data: bytes, filename: str) -> VoiceClip:
    started = time.monotonic()
    as_is = fmt == "ogg" and is_ogg_opus(data)
    with tempfile.TemporaryDirectory(prefix="trollenator-audio-") as tmp:
        src, out = Path(tmp) / "input", Path(tmp) / "voice.ogg"
        await asyncio.to_thread(src.write_bytes, data)
        # Already Ogg/Opus → only decode (for the waveform); anything else → decode ONCE and encode in the same run.
        pcm = await _ffmpeg_run(ffmpeg, src, fmt, opus_out=None if as_is else out, pcm=True)
        duration, waveform = await asyncio.to_thread(waveform_from_pcm, pcm, WAVEFORM_RATE)
        if as_is and duration > 0 and len(data) * 8 / duration > AS_IS_MAX_BITRATE:
            as_is = False                       # a heavy Opus file: shrinking it is worth one encode pass
            await _ffmpeg_run(ffmpeg, src, fmt, opus_out=out, pcm=False)
        ogg = data if as_is else await asyncio.to_thread(out.read_bytes)
    if not ogg or not pcm:
        raise AudioError("unreadable")
    if duration > MAX_VOICE_SECONDS:
        raise AudioError("too_long")
    return VoiceClip(
        data=ogg, duration=round(duration, 3), waveform=waveform, source_name=Path(filename).name,
        mode="as-is" if as_is else "converted", convert_ms=round((time.monotonic() - started) * 1000),
        source_bytes=len(data))


async def convert_to_voice(data: bytes, filename: str) -> VoiceClip:
    """Any supported audio (or a video's soundtrack) → a ready-to-send voice message clip."""
    global _audio_slot, _audio_pending
    fmt = sniff_audio_format(data[:64])
    if fmt is None:
        raise AudioError("unsupported")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise AudioError("no_ffmpeg")
    if _audio_pending >= AUDIO_MAX_PENDING:
        raise AudioError("busy")
    if _audio_slot is None:
        _audio_slot = asyncio.Semaphore(1)
    _audio_pending += 1
    try:
        async with _audio_slot:
            return await _convert(ffmpeg, fmt, data, filename)
    finally:
        _audio_pending -= 1


class VoiceSendError(Exception):
    """Discord (or the network) refused the voice message."""


async def post_voice_message(interaction: discord.Interaction, clip: VoiceClip, session: aiohttp.ClientSession) -> int:
    """
    Answer `interaction` with a public voice message. Returns how many milliseconds the request took.

    `interaction` is the press of the editor's Send button — so, exactly like /say and /embed
    posts, the voice message answers the PRIVATE editor message, never the /voice command itself.

    discord.py can't set the voice-message flag or an attachment's waveform/duration, so this
    makes the interaction-callback request itself (no token needed — the interaction token
    is the credential). It MUST be the interaction's first response, which is why the clip is
    converted beforehand: there is no time to run ffmpeg inside Discord's 3-second window. For the same
    reason the request goes over the bot's long-lived `session` (no new TLS handshake per send) and is
    retried once at once if the kept-alive connection turns out to have been closed by the other side.
    Raises VoiceSendError if Discord says no — the interaction is then still unanswered (or already expired).
    """
    payload = {
        "type": 4,                                       # CHANNEL_MESSAGE_WITH_SOURCE
        "data": {
            "flags": VOICE_FLAG,
            "attachments": [{
                "id": 0, "filename": "voice-message.ogg",
                "duration_secs": clip.duration, "waveform": clip.waveform,
            }],
        },
    }

    def make_form() -> aiohttp.FormData:                 # a FormData can only be sent once
        form = aiohttp.FormData()
        form.add_field("payload_json", json.dumps(payload), content_type="application/json")
        form.add_field("files[0]", clip.data, filename="voice-message.ogg", content_type="audio/ogg")
        return form

    url = f"{DISCORD_API}/interactions/{interaction.id}/{interaction.token}/callback"
    started = time.monotonic()
    status, body = 0, ""
    for attempt in (1, 2):
        try:
            async with session.post(url, data=make_form(), timeout=aiohttp.ClientTimeout(total=10)) as resp:
                status = resp.status
                if status < 300:
                    # Tell discord.py this interaction has been answered, so error paths that
                    # check is_done() use a follow-up instead of a second first-response.
                    try:
                        interaction.response._response_type = discord.InteractionResponseType.channel_message
                    except Exception:
                        pass
                    return round((time.monotonic() - started) * 1000)
                body = await resp.text()
            break
        except (aiohttp.ServerDisconnectedError, aiohttp.ClientOSError) as e:
            if attempt == 1 and time.monotonic() - started < 1.5:
                continue
            raise VoiceSendError(redact(f"network error: {type(e).__name__}: {e}"))
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            raise VoiceSendError(redact(f"network error: {type(e).__name__}: {e}"))
    try:
        message = json.loads(body).get("message") or body
    except (ValueError, AttributeError):
        message = body
    raise VoiceSendError(redact(f"{status}: {message}")[:300])


def toggle_style(on: bool) -> discord.ButtonStyle:
    """On/off buttons (TTS, Pings): red while off, green while on."""
    return discord.ButtonStyle.success if on else discord.ButtonStyle.danger



# ─────────────────────────────────────────────────────────────────────────────
# Multiple bots — tokens, the command prefix, the `t` wrapper
# ─────────────────────────────────────────────────────────────────────────────
# Several Discord applications ("bots") can be listed in the config; ONE of them runs at a time and a bot admin
# switches between them in /devpannel. Their slash commands would otherwise share names, so every command gets
# the first letters of its bot's name in front of it ("/trolle-say").

MAX_BOTS          = 25                   # a select menu holds 25 options
PREFIX_LETTERS    = 6                    # letters of the bot's name put in front of each command
PREFIX_OVERRIDE_MAX = 16                 # longest "prefix" a config entry may set itself
PREFIX_SEPARATOR  = "-"                  # between the letters and the command ("trolle-say")
STARTUP_TIMEOUT   = 45.0                 # seconds a bot gets to come online during a switch
PROBE_TIMEOUT     = 8                    # seconds one token check (GET /users/@me) may take
PROBE_TTL_OK      = 600.0                # a bot's name is remembered this long …
PROBE_TTL_BAD     = 30.0                 # … and a failed check this long
BASE_COMMANDS     = ("say", "embed", "voice", "poll", "permcheck")
COMMAND_NAME_RE   = re.compile(r"[a-z0-9_-]{1,32}")      # what this plugin produces (a safe subset of Discord's rule)
_RE_TOKEN_SHAPE   = re.compile(r"[A-Za-z0-9_-]{18,32}\.[A-Za-z0-9_-]{5,8}\.[A-Za-z0-9_-]{25,100}")


class CommandNames:
    """
    The prefix of the bot that is running right now, and the one place that turns "/say" in a message into
    "/trolle-say". Only one bot runs at a time, so a single shared value is enough.
    """

    prefix = ""
    _pattern = re.compile(r"(?<![\w/-])/(" + "|".join(BASE_COMMANDS) + r")(?![\w-])")

    @classmethod
    def localize(cls, text: str) -> str:
        if not cls.prefix:
            return text
        return cls._pattern.sub(lambda m: f"/{cls.prefix}{m.group(1)}", text)


def t(key: str, **kwargs: Any) -> str:
    """
    strings.json message with its values filled in. Command names written as `/say` in a string show the running
    bot's prefix — applied to the template BEFORE the values go in, so text typed by a user is never rewritten.
    """
    return strings_mod.render(key, kwargs, CommandNames.localize)


def clean_token(raw: object) -> str:
    """Tidy a pasted token: surrounding spaces/quotes and a leading "Bot " are removed."""
    s = str(raw or "").strip().strip("\"'`").strip()
    return re.sub(r"^bot\s+", "", s, flags=re.IGNORECASE).strip()


def token_key(token: str) -> str:
    """A stable id for a token that is safe to store and show (a SHA-256 fragment — it can't be turned back into the token)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


def sanitize_prefix(raw: str, limit: int) -> str:
    """Letters and digits only (ASCII, lower-case), at most `limit` of them — what a command name can safely start with."""
    folded = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", folded)[:limit]


def make_prefix(name: str, override: str = "", app_id: int = 0) -> str:
    """
    "Trollenator" → "trolle-". A config "prefix" replaces the name. A name with no usable letters (all emoji, or a
    script Discord's lower-case rule doesn't cover) falls back to "bot" + the last digits of the application id.
    """
    letters = sanitize_prefix(override, PREFIX_OVERRIDE_MAX) if override else sanitize_prefix(name, PREFIX_LETTERS)
    if not letters:
        letters = "bot" + (str(app_id)[-3:] if app_id else "")
    return letters + PREFIX_SEPARATOR


@dataclass
class BotEntry:
    """One configured bot. The token is a secret: it is excluded from repr() so a traceback can't print it."""
    token: str = field(repr=False)
    key: str
    prefix: str = ""            # optional config override for the command prefix


@dataclass(frozen=True)
class BotInfo:
    id: int
    name: str


@dataclass
class RosterItem:
    entry: BotEntry
    info: Optional[BotInfo]     # None = couldn't be checked (see `problem`)
    active: bool
    prefix: str                 # the command prefix this bot uses ("" if unknown)
    problem: str = ""           # "" | "rejected" | "unreachable"


TOKEN_PROBLEM_KEYS = {          # TokenProblem.kind → message (full keys, so the string check in the self-test can find them)
    "rejected": "troll_token_rejected",
    "unreachable": "troll_token_unreachable",
    "not_a_bot": "troll_token_not_a_bot",
}


class TokenProblem(Exception):
    """A token check failed. kind: rejected | unreachable | not_a_bot"""

    def __init__(self, kind: str) -> None:
        super().__init__(kind)
        self.kind = kind


def parse_bot_entries(cfg: dict, exclude: frozenset[str] = frozenset()) -> list[BotEntry]:
    """
    Every token in the config, in order, without duplicates: the legacy "token" first, then "tokens" — a list whose
    items are either a token string or {"token": "...", "prefix": "optional"}. A token whose key is in `exclude`
    (the control bot's) is skipped: the control bot and a user app must be different applications.
    """
    raw: list[object] = [cfg.get("token")]
    tokens = cfg.get("tokens")
    if isinstance(tokens, (str, dict)):
        tokens = [tokens]
    if isinstance(tokens, list):
        raw.extend(tokens)
    entries: list[BotEntry] = []
    seen: set[str] = set()
    for item in raw:
        override = ""
        if isinstance(item, dict):
            override = str(item.get("prefix") or "")
            item = item.get("token")
        if not isinstance(item, str):
            continue
        token = clean_token(item)
        if not token or len(token) > 200 or not re.fullmatch(r"[\x21-\x7e]+", token):     # printable ASCII, no spaces/newlines
            continue
        key = token_key(token)
        if key in seen or key in exclude:
            continue
        seen.add(key)
        register_secret(token)
        entries.append(BotEntry(token=token, key=key, prefix=sanitize_prefix(override, PREFIX_OVERRIDE_MAX)))
        if len(entries) >= MAX_BOTS:
            break
    return entries


def write_config_token(path: Path, token: str) -> None:
    """
    Add `token` to the "tokens" list of the config file (blocking — call it with asyncio.to_thread).
    The file is read fresh, changed, written to a private temporary file in the same folder, flushed to disk and
    swapped in with os.replace (appconfig.atomic_write), so a crash can never leave a half-written config; the new file is readable by its
    owner only (it holds bot tokens). Raises ValueError if the file isn't a JSON object or "tokens" isn't a list —
    nothing is written then.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("the config file is not a JSON object")
    tokens = data.get("tokens")
    if tokens is None:
        tokens = data["tokens"] = []
    if not isinstance(tokens, list):
        raise ValueError('"tokens" in the config file is not a list')
    tokens.append(token)
    atomic_write(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


async def probe_token(session: aiohttp.ClientSession, token: str) -> BotInfo:
    """
    Ask Discord who a token belongs to (GET /users/@me) without logging in to the gateway. Raises TokenProblem.
    The token only ever travels in the Authorization header: it is never part of a URL, a log line or an error.
    """
    headers = {"Authorization": f"Bot {token}", "User-Agent": f"DiscordBot (Trollenator, {discord.__version__})"}
    try:
        async with session.get(f"{DISCORD_API}/users/@me", headers=headers,
                               timeout=aiohttp.ClientTimeout(total=PROBE_TIMEOUT)) as resp:
            if resp.status in (401, 403):
                raise TokenProblem("rejected")
            if resp.status != 200:
                raise TokenProblem("unreachable")          # includes 429 and 5xx
            data = await resp.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
        raise TokenProblem("unreachable")
    if not isinstance(data, dict) or data.get("bot") is not True or not str(data.get("id", "")).isdigit():
        raise TokenProblem("not_a_bot")
    return BotInfo(id=int(data["id"]), name=str(data.get("username") or "?"))


def safe_name(name: str) -> str:
    """A bot name made harmless to show inside a message (no markdown, no mentions)."""
    return discord.utils.escape_mentions(discord.utils.escape_markdown(name))[:80]


# ─────────────────────────────────────────────────────────────────────────────
# Activity log — everything Trollenator does, reported to a Discord webhook
# ─────────────────────────────────────────────────────────────────────────────
# A queue that can never block a command, 429 / rate-limit-header handling, rich embeds, up to 10 entries per
# request, retries that survive a Wi-Fi drop, and a flush on shutdown.

_known_secrets: set[str] = set()     # exact strings that must never appear in a log entry or a user-facing error
_SECRET_PATTERNS = (
    re.compile(r"/webhooks/\d+/[A-Za-z0-9._-]+"),                    # a webhook URL (its token is the password)
    re.compile(r"/interactions/\d+/[A-Za-z0-9._-]+"),                # an interaction callback URL (token inside)
    re.compile(r"\b[A-Za-z0-9_-]{23,28}\.[A-Za-z0-9_-]{6,7}\.[A-Za-z0-9_-]{27,}\b"),   # the shape of a bot token
)
_WEBHOOK_URL = re.compile(
    r"https://(?:(?:ptb|canary)\.)?discord(?:app)?\.com/api(?:/v\d+)?/webhooks/\d+/[A-Za-z0-9._-]+")
LOG_STYLES = {                       # level → (embed colour, emoji)
    "ok":   (0x57F287, "✅"),
    "info": (0x5865F2, "ℹ️"),
    "warn": (0xFEE75C, "⚠️"),
    "fail": (0xED4245, "❌"),
}


def register_secret(value: str) -> None:
    """Remember a secret so redact() can strip it from anything that gets logged or shown."""
    if value and len(value) >= 8:
        _known_secrets.add(value)


def redact(text: object) -> str:
    """`text` with every known secret (bot token, webhook URL) and any token-bearing Discord URL blanked out."""
    out = str(text)
    for secret in _known_secrets:
        out = out.replace(secret, "[redacted]")
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub("[redacted]", out)
    return out


class RedactFilter(logging.Filter):
    """Scrubs known secrets (bot tokens, webhook URLs) from every record this plugin writes — messages AND tracebacks."""

    _trollenator = True

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact(record.getMessage())
            record.args = ()
            if record.exc_info:
                record.exc_text = redact("".join(traceback.format_exception(*record.exc_info)).rstrip())
                record.exc_info = None
            elif record.exc_text:
                record.exc_text = redact(record.exc_text)
        except Exception:
            pass
        return True


log.filters = [f for f in log.filters if not getattr(f, "_trollenator", False)]    # a plugin reload must not stack filters
log.addFilter(RedactFilter())


def clip(text: object, limit: int) -> str:
    out = str(text)
    return out if len(out) <= limit else out[:max(0, limit - 1)] + "…"


def fence(text: object, limit: int = 1700) -> str:
    """User text as a code block it can't break out of (and that never pings anyone)."""
    body = redact(text).replace("```", "`\u200b``")
    return f"```\n{clip(body, limit)}\n```"


def fmt_size(n: int) -> str:
    return f"{n / 1024:.0f} KB" if n < 1048576 else f"{n / 1048576:.1f} MB"


def session_id(interaction: discord.Interaction) -> str:
    """A short id shared by every log entry of one command (derived from the command's interaction)."""
    return hashlib.sha1(str(interaction.id).encode()).hexdigest()[:6]


def log_user(interaction: discord.Interaction) -> str:
    user = interaction.user
    return f"<@{user.id}> `{inline(user.name, 40)}` (`{user.id}`)"


def install_kind(interaction: discord.Interaction) -> str:
    try:
        user, guild = interaction.is_user_integration(), interaction.is_guild_integration()
    except Exception:
        return "?"
    return "user + server" if user and guild else "user install" if user else "server install" if guild else "?"


def log_where(interaction: discord.Interaction) -> str:
    channel = interaction.channel
    name = getattr(channel, "name", None)
    kind = getattr(getattr(channel, "type", None), "name", None)
    if interaction.guild_id is not None:
        where = f"server `{interaction.guild_id}` · channel `{interaction.channel_id}`"
        if name:
            where += f" (#{inline(name, 40)})"
    else:
        dm_with_bot = getattr(getattr(interaction, "context", None), "dm_channel", False)
        where = ("DM with the bot" if dm_with_bot else "DM / group DM") + f" · channel `{interaction.channel_id}`"
    if kind:
        where += f" · {kind}"
    return f"{where} · {install_kind(interaction)}"


def describe_attachment(att: discord.Attachment) -> str:
    return f"{inline(att.filename, 80)} · {fmt_size(att.size)} · {att.content_type or 'unknown type'}"


def describe_options(interaction: discord.Interaction) -> str:
    """The options the user filled in on a slash command, one per line."""
    lines = []
    try:
        for name, value in interaction.namespace:
            if isinstance(value, discord.Attachment):
                lines.append(f"{name}: [file] {describe_attachment(value)}")
            else:
                lines.append(f"{name}: {value}")
    except Exception:
        pass
    return "\n".join(lines) or "(no options)"


def describe_refs(refs: "list[FileRef]") -> str:
    return "\n".join(f"{ref.filename} · {fmt_size(len(ref.data))}" for ref in refs) or "(none)"


class TrollLog:
    """
    Non-blocking activity log. `record()` never waits and never raises: entries go into a bounded queue and a
    background task posts them (batched, up to 10 per request) to the webhook. With no valid webhook URL it
    still writes a one-line summary to the normal Python log.
    """

    def __init__(self, url: str) -> None:
        url = (url or "").strip()
        self.url = url if _WEBHOOK_URL.fullmatch(url) else ""
        self.url_rejected = bool(url) and not self.url      # something was configured but it isn't a Discord webhook
        register_secret(self.url)
        self._pending: collections.deque[tuple[int, dict]] = collections.deque()   # (size in characters, embed dict)
        self._wake = asyncio.Event()
        self._task: Optional[asyncio.Task] = None
        self._closing = False
        self._dead = False                                   # Discord said the webhook doesn't exist (any more)
        self.app_label = ""                                   # name of the bot that is running (shown in each entry's footer)
        self._dropped = 0

    @property
    def enabled(self) -> bool:
        return bool(self.url) and not self._dead

    # ── lifecycle ────────────────────────────────────────────────────────────
    def start(self) -> None:
        if self.url and self._task is None:
            self._task = asyncio.create_task(self._worker(), name="trollenator-log")

    async def stop(self, timeout: float = 8.0) -> None:
        """Deliver what is still queued (up to `timeout` seconds), then stop."""
        self._closing = True
        self._wake.set()
        task, self._task = self._task, None
        if task is not None:
            try:
                await asyncio.wait_for(task, timeout)
            except asyncio.TimeoutError:
                pass                                         # wait_for already cancelled the worker
            except Exception:
                pass

    # ── writing entries ──────────────────────────────────────────────────────
    def record(
        self, level: str, event: str, interaction: Optional[discord.Interaction] = None, *,
        sid: str = "", summary: str = "", details: str = "", fields: Optional[dict[str, str]] = None,
        error: Optional[BaseException] = None,
    ) -> None:
        """
        level   "ok" | "info" | "warn" | "fail"
        event   short headline, e.g. "/say · sent"
        summary one safe sentence (reasons, numbers) — also goes to the normal Python log
        details raw user content (message text, poll answers …) — webhook only, always code-fenced
        fields  extra small facts shown as embed fields
        """
        try:
            who = f" user={interaction.user.id}" if interaction is not None else ""
            log.log({"fail": logging.ERROR, "warn": logging.WARNING}.get(level, logging.INFO),
                    "Trollenator [%s] %s%s%s", sid or "-", redact(event), who, f" — {redact(summary)}" if summary else "")
            if not self.enabled or self._closing and self._task is None:
                return
            colour, emoji = LOG_STYLES[level]
            now = discord.utils.utcnow()
            parts = []
            if summary:
                parts.append(clip(redact(summary), 700))
            if details:
                parts.append(fence(details, 2800 if error is None else 1600))
            if error is not None:
                trace = "".join(traceback.format_exception(type(error), error, error.__traceback__))
                parts.append(fence(trace[-1300:], 1300))
            embed = discord.Embed(
                title=clip(f"{emoji} {redact(event)}", 250), description=clip("\n".join(parts), 3900) or None,
                colour=colour, timestamp=now)
            if interaction is not None:
                embed.add_field(name="User", value=log_user(interaction), inline=True)
                embed.add_field(name="Where", value=clip(log_where(interaction), 600), inline=True)
            for name, value in list((fields or {}).items())[:6]:
                embed.add_field(name=clip(name, 60), value=clip(redact(value), 300) or "—", inline=True)
            embed.set_footer(text=clip(" · ".join(filter(None, [self.app_label, f"session {sid}" if sid else "",
                                                              f"{now:%Y-%m-%d %H:%M:%S} UTC"])), 2000))
            while len(embed) > LOG_EMBED_BUDGET and embed.description:        # keep one entry inside Discord's limit
                embed.description = embed.description[:max(0, len(embed.description) - (len(embed) - LOG_EMBED_BUDGET) - 20)] + "…"
            self._push(len(embed), embed.to_dict())
        except Exception:
            log.exception("Trollenator: could not build a log entry")

    def _push(self, size: int, embed: dict) -> None:
        if len(self._pending) >= LOG_QUEUE_MAX:
            self._pending.popleft()
            self._dropped += 1
        self._pending.append((size, embed))
        self._wake.set()

    # ── delivery ─────────────────────────────────────────────────────────────
    def _take_batch(self) -> list[dict]:
        batch, size = [], 0
        while self._pending and len(batch) < 10:
            n, embed = self._pending[0]
            if batch and size + n > LOG_EMBED_BUDGET:
                break
            self._pending.popleft()
            batch.append(embed)
            size += n
        return batch

    async def _post(self, session: aiohttp.ClientSession, batch: list[dict]) -> tuple[str, float]:
        """One request → ("ok" | "retry" | "net" | "drop" | "dead", seconds to wait before the next request)."""
        payload = {
            "username": "Trollenator log", "embeds": batch,
            "allowed_mentions": {"parse": []},               # a logged @everyone / @role must never ping anyone
            "flags": 4096,                                   # SUPPRESS_NOTIFICATIONS
        }
        try:
            async with session.post(self.url, json=payload) as resp:
                if resp.status in (200, 204):
                    try:
                        remaining = int(resp.headers.get("x-ratelimit-remaining", "1"))
                        reset_after = float(resp.headers.get("x-ratelimit-reset-after", "1"))
                    except ValueError:
                        remaining, reset_after = 0, 1.0
                    return "ok", (reset_after + 0.3 if remaining <= 1 else 0.3)
                if resp.status == 429:
                    try:
                        wait = float((await resp.json(content_type=None)).get("retry_after", 5))
                    except Exception:
                        wait = 5.0
                    return "retry", min(wait, 60.0) + 0.5
                if resp.status in (401, 403, 404):
                    log.error(f"Trollenator: the log webhook answered HTTP {resp.status} — it was deleted or is "
                              "invalid. Webhook logging is off until the plugin is reloaded.")
                    return "dead", 0.0
                if resp.status >= 500:
                    return "retry", 5.0
                log.error(f"Trollenator: the log webhook rejected a batch (HTTP {resp.status}): "
                          f"{redact((await resp.text())[:200])}")
                return "drop", 0.0
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            log.warning(f"Trollenator: log webhook unreachable ({type(e).__name__}) — will keep retrying.")
            return "net", 0.0

    async def _worker(self) -> None:
        pause = 0.0
        failures = 0
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            while True:
                if not self._pending:
                    if self._closing:
                        return
                    self._wake.clear()
                    await self._wake.wait()
                    continue
                batch = self._take_batch()
                while True:                                  # until this batch is delivered or given up on
                    if pause > 0:
                        await asyncio.sleep(pause)
                    outcome, pause = await self._post(session, batch)
                    if outcome == "ok":
                        failures = 0
                        break
                    if outcome == "dead":
                        self._dead = True
                        self._pending.clear()
                        return
                    if outcome == "drop":
                        break
                    if outcome == "net":                     # Wi-Fi down: back off, keep the entries, deliver later
                        failures += 1
                        pause = min(30.0, 2.0 ** min(failures, 5))
                if self._dropped:
                    count, self._dropped = self._dropped, 0
                    self.record("warn", "Log entries were lost",
                                summary=f"{count} log entries were dropped because the webhook was slow or unreachable.")


# ─────────────────────────────────────────────────────────────────────────────
# ToS risk check — a warning, never a block
# ─────────────────────────────────────────────────────────────────────────────
# Before a public post goes out, the text of the message / embed / poll, the attached file names and a few
# behaviour signals are checked against rules drawn from Discord's own policies (Community Guidelines, the
# Bullying/Harassment/Threats, Doxxing, Hateful Conduct, Platform Manipulation and Deceptive Practices
# explainers, and the Developer Policy). If something looks risky the editor is replaced by a warning; the user
# either acknowledges it (the command is cancelled) or ignores it (the post goes out exactly as if nothing had
# happened). Nobody is ever stopped from using the bot — and the post, the warning and the choice are all logged.
#
# Deliberately local: no message text leaves this machine for a third-party classifier (Discord's Developer Policy
# restricts how API Data may be used and shared, and Google's Perspective API shuts down on 2026-12-31 anyway).
# A rule list is not a judge — it misses things and sometimes flags harmless text. That's why it only warns.
# Slurs are NOT hard-coded: put the terms you want flagged in `tos_terms` / `tos_terms_file` of the config.

TOS_WARN_SCORE   = 2                 # findings add up to this → warn (one "low" finding on its own doesn't)
TOS_REPEAT_LINES = 10                # /say repeated on this many lines or more = spam-like
TOS_MANY_MENTIONS = 5                # this many different users pinged in one message
TOS_RAPID_POSTS  = 8                 # this many posts …
TOS_RAPID_WINDOW = 600.0             # … within this many seconds
TOS_IGNORED_WINDOW = 86400.0         # how long an ignored warning counts in the log's "ignored warnings" number
TOS_MAX_TERMS    = 5000
TOS_MAX_SCAN     = 30000             # characters looked at (a message is at most 6000 + file names)
TOS_WARN_TIMEOUT = 300               # seconds the warning waits for a choice
TOS_CODES = (
    "mass_ping", "many_mentions", "spam_repeat", "tts_spam", "rapid_use", "threat", "self_harm", "ip_address",
    "personal_info", "scam", "ip_logger", "lookalike_link", "short_link", "invite_link", "impersonation",
    "hate_term", "risky_file",
)

_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i", "|": "i"})


def fold_text(text: str, *, leet: bool = False) -> str:
    """Lower-case, NFKC-normalised, with invisible / combining characters removed (and, with `leet`, l33t undone)."""
    out = unicodedata.normalize("NFKC", text[:TOS_MAX_SCAN])
    out = "".join(ch for ch in out if unicodedata.category(ch) not in ("Cf", "Mn", "Me")).casefold()
    return out.translate(_LEET) if leet else out


_RE_EVERYONE = re.compile(r"@(?:everyone|here)\b")
_RE_USER_MENTION = re.compile(r"<@!?(\d{15,25})>")
_RE_ROLE_MENTION = re.compile(r"<@&\d{15,25}>")
_RE_SELF_HARM = re.compile(
    r"\b(?:kys|k\s*y\s*s)\b|\bkill\s*(?:your|ur)\s*self\b|\bhang\s*(?:your|ur)\s*self\b|\bunalive\s*(?:your|ur)\s*self\b"
    r"|\b(?:you|u)\s*should\s*(?:just\s*)?(?:die|kill)\b|\b(?:go|just)\s*die\b|\bhope\s*(?:you|u)\s*(?:die|get\s*cancer)\b")
_RE_THREAT = re.compile(
    r"\b(?:i|im|i'm)\s*(?:'?ll|will|gonna|am\s*going\s*to|going\s*to|'?m\s*going\s*to|want\s*to|wanna)?\s*"
    r"(?:find\s*(?:you\s*)?(?:and\s*)?)?(?:kill|murder|stab|shoot|rape|beat\s*up|hurt)\s*(?:you|u|ur\s*family|your\s*family)\b"
    r"|\bi\s*know\s*where\s*(?:you|u)\s*live\b|\bswat(?:ting)?\s*(?:you|u|him|her|them)\b")
_RE_IPV4 = re.compile(r"(?<![\d.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\d.])")
_RE_PHONE = re.compile(r"(?<![\w+])(?:\+\d[\d\s().-]{8,}\d|\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4})(?![\w])")
_RE_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]{2,}\b")
_RE_DOX_WORDS = re.compile(r"\b(?:dox+(?:ed|ing|x?er)?|d0x+|ddos(?:ed|ing)?|swatting)\b")
_RE_SCAM = re.compile(
    r"free\s*nitro|nitro\s*(?:gift|giveaway|for\s*free)|claim\s*(?:your\s*)?(?:free\s*)?(?:nitro|gift|reward|prize)"
    r"|(?:steam|cs2|csgo)\s*(?:gift|giveaway|trade\s*link)|\bairdrop\b|seed\s*phrase|recovery\s*phrase"
    r"|verify\s*your\s*(?:account|identity)|your\s*account\s*(?:has\s*been|will\s*be|is)\s*(?:suspended|disabled|banned|terminated)"
    r"|(?:send|give|dm)\s*(?:me\s*)?(?:your\s*)?(?:password|token)\b|token\s*grabber")
_RE_INVITE = re.compile(r"(?:discord(?:app)?\.gg|dsc\.gg|discord(?:app)?\.com/invite)/[\w-]+")
_RE_URL_HOST = re.compile(r"(?<![\w@.-])((?:[a-z0-9-]+\.)+[a-z]{2,})(?![\w-])", re.IGNORECASE)   # any host-like token, with or without http://
_RE_IMPERSONATE_NAME = re.compile(
    r"\b(?:discord|trust\s*(?:&|and)\s*safety)\s*(?:staff|team|support|moderators?|admins?|system|security|safety|official)\b"
    r"|\bsystem\s*message\b|\bofficial\s*discord\b")
_RE_IMPERSONATE_TEXT = re.compile(r"\bmessage\s*from\s*discord\b|\bofficial\s*(?:warning|notice)\s*(?:from|by)\s*discord\b")
# Known address-grabbing / tracking domains (not exhaustive) and common link shorteners.
_IP_LOGGERS = ("grabify.link", "iplogger.org", "iplogger.com", "iplogger.ru", "2no.co", "yip.su", "ipgrabber.ru",
               "ipgraber.ru", "leancoding.co", "stopify.co", "spottyfly.com", "freegiftcards.co", "joinmy.site",
               "curiouscat.club", "catsnthing.com", "bmwforum.co", "blasze.tk")
_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "cutt.ly", "rb.gy", "is.gd", "v.gd", "goo.gl", "ow.ly", "shorturl.at", "tiny.cc")
_LEGIT_DISCORD = {"discord.com", "discordapp.com", "discord.gg", "discord.gift", "discordapp.net", "discord.media",
                  "discordstatus.com", "dis.gd", "discord.new", "discord.dev"}
_DISCORD_LOOKALIKE = re.compile(
    r"^(?:dlscord|d1scord|discrod|dicsord|disocrd|discorcl|discorb|disc0rd|dlscorcl|discordd|dsicord|discoord)\w*$"
    r"|^d[i1l]sc[o0]r[dcl][\w-]*(?:nitro|gift|free|promo|drop|claim|verify|login|steam)[\w-]*$"
    r"|^[\w-]*(?:nitro|gift|free|promo|claim|verify|login)[\w-]*d[i1l]sc[o0]r[dcl][\w-]*$")
_RISKY_EXTENSIONS = {".exe", ".scr", ".bat", ".cmd", ".com", ".msi", ".js", ".jse", ".vbs", ".vbe", ".wsf", ".ps1",
                     ".jar", ".apk", ".lnk", ".dll", ".hta", ".cpl", ".reg", ".pif"}


@dataclass(frozen=True)
class Finding:
    code: str        # one of TOS_CODES — also the suffix of the explanation string "troll_tos_<code>"
    weight: int      # 1 low · 2 medium · 3 high


@dataclass
class ScanInput:
    """Everything the check looks at; each editor fills one in at Send time."""
    ping_text: str = ""                                          # the message text that can actually ping people
    texts: list = field(default_factory=list)                    # every typed text + link field that will be posted
    names: list = field(default_factory=list)                    # author / title / footer — checked for impersonation
    filenames: list = field(default_factory=list)                # attached file names
    lines: int = 1                                               # /say repeat count
    tts: bool = False
    pings_on: bool = True
    recent_posts: int = 0                                        # this user's posts in the last TOS_RAPID_WINDOW seconds

    def fingerprint(self) -> str:
        """Identifies the content (not the behaviour signals): the same content is never warned about twice."""
        blob = json.dumps([self.ping_text, self.texts, self.names, self.filenames, self.lines, self.tts, self.pings_on],
                          ensure_ascii=False)
        return hashlib.sha256(blob.encode()).hexdigest()[:16]


def registered_domain(host: str) -> str:
    parts = host.lower().strip(".").split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host.lower()


def scan_content(inp: ScanInput, terms: Optional["re.Pattern[str]"] = None) -> list[Finding]:
    """The rule check. Pure function; returns findings sorted most serious first."""
    found: dict[str, int] = {}

    def add(code: str, weight: int) -> None:
        found[code] = max(found.get(code, 0), weight)

    blob = "\n".join([*map(str, inp.texts), *map(str, inp.names), *map(str, inp.filenames)])
    plain, leet = fold_text(blob), fold_text(blob, leet=True)

    # ── pings & spam ─────────────────────────────────────────────────────────
    if inp.pings_on:
        raw = inp.ping_text[:TOS_MAX_SCAN]
        if _RE_EVERYONE.search(raw):
            add("mass_ping", 2)
        elif _RE_ROLE_MENTION.search(raw):
            add("mass_ping", 1)
        if len(set(_RE_USER_MENTION.findall(raw))) >= TOS_MANY_MENTIONS:
            add("many_mentions", 2)
    if inp.lines >= TOS_REPEAT_LINES:
        add("spam_repeat", 3 if inp.lines >= 50 else 2)
    if inp.tts and (inp.lines >= 3 or (inp.pings_on and _RE_EVERYONE.search(inp.ping_text))):
        add("tts_spam", 2)
    if inp.recent_posts >= TOS_RAPID_POSTS:
        add("rapid_use", 2)

    # ── harassment, threats, self-harm, hate ─────────────────────────────────
    if _RE_SELF_HARM.search(leet):
        add("self_harm", 3)
    if _RE_THREAT.search(leet):
        add("threat", 3)
    if terms is not None and terms.search(leet):
        add("hate_term", 3)

    # ── personal information (doxxing) ───────────────────────────────────────
    for m in _RE_IPV4.finditer(plain):
        try:
            if ipaddress.ip_address(m.group(0)).is_global:
                add("ip_address", 2)
                break
        except ValueError:
            pass
    if _RE_PHONE.search(plain) or _RE_EMAIL.search(plain) or _RE_DOX_WORDS.search(plain):
        add("personal_info", 1)

    # ── scams, tracking links, lookalikes, invites ───────────────────────────
    if _RE_SCAM.search(plain):
        add("scam", 2)
    for bad in _IP_LOGGERS:
        if re.search(r"(?<![\w.-])" + re.escape(bad) + r"(?![\w-])", plain):
            add("ip_logger", 3)
            break
    for short in _SHORTENERS:
        if re.search(r"(?<![\w.-])" + re.escape(short) + r"/", plain):
            add("short_link", 1)
            break
    for host in _RE_URL_HOST.findall(plain):
        dom = registered_domain(host)
        label = dom.split(".")[0]
        if dom not in _LEGIT_DISCORD and _DISCORD_LOOKALIKE.match(label):
            add("lookalike_link", 3)
            break
    if _RE_INVITE.search(plain):
        add("invite_link", 1)

    # ── impersonation ────────────────────────────────────────────────────────
    if any(_RE_IMPERSONATE_NAME.search(fold_text(str(n))) for n in inp.names) or _RE_IMPERSONATE_TEXT.search(plain):
        add("impersonation", 2)

    # ── files ────────────────────────────────────────────────────────────────
    for name in inp.filenames:
        lowered = str(name).lower()
        if any(lowered.endswith(ext) for ext in _RISKY_EXTENSIONS):
            add("risky_file", 2)
        elif any(ch in str(name) for ch in "\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"):
            add("risky_file", 2)          # right-to-left tricks that disguise a file's real extension

    return sorted((Finding(c, w) for c, w in found.items()), key=lambda f: -f.weight)


def should_warn(findings: list[Finding]) -> bool:
    return sum(f.weight for f in findings) >= TOS_WARN_SCORE


def load_terms(cfg: dict) -> Optional["re.Pattern[str]"]:
    """
    The owner's list of terms to flag (config `tos_terms` and/or a file `tos_terms_file`, one term per line,
    `#` comments) as one compiled pattern, or None. Terms are matched as whole words, plurals included,
    after the same normalisation as the text — so "l33t" spellings of a listed word match too.
    """
    raw: list[str] = [str(x) for x in (cfg.get("tos_terms") or []) if isinstance(x, (str, int))]
    path = str(cfg.get("tos_terms_file") or "").strip()
    if path:
        file = Path(path)
        if not file.is_absolute():
            file = CONFIG_DIR / path
        try:
            raw += file.read_text(encoding="utf-8").splitlines()
        except OSError as e:
            log.warning(f"Trollenator: could not read tos_terms_file {file}: {e}")
    cleaned = {fold_text(x, leet=True).strip() for x in raw if x.strip() and not x.strip().startswith("#")}
    terms = sorted((x for x in cleaned if 2 <= len(x) <= 60), key=len, reverse=True)[:TOS_MAX_TERMS]
    if not terms:
        return None
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(x) for x in terms) + r")(?:s|es)?(?![a-z0-9])")


def tos_warning_text(findings: list[Finding]) -> str:
    lines = [t("troll_tos_header")]
    lines += [t(f"troll_tos_{f.code}") for f in findings]
    lines.append(t("troll_tos_footer"))
    return "\n".join(lines)


class WarnView(ui.View):
    """
    Replaces an editor's message with the ToS warning. Two choices:
      Acknowledge — the editor is closed, nothing is posted.
      Ignore      — the editor comes back and the post goes out as if Send had been pressed.
    """

    def __init__(self, editor: "EditorMixin", findings: list[Finding], fingerprint: str) -> None:
        super().__init__(timeout=TOS_WARN_TIMEOUT)
        self.editor = editor
        self.findings = findings
        self.fingerprint = fingerprint
        self.settled = False
        self.flags = ", ".join(f"{f.code}({f.weight})" for f in findings)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if getattr(self.editor, "done", False):
            await reply_private(interaction, t("troll_tos_gone"))
            return False
        return await self.editor.bot.guard(interaction)

    async def on_timeout(self) -> None:
        ed = self.editor
        if not self.settled and not getattr(ed, "done", False):
            ed.note("info", "ToS warning timed out — nothing was sent", ed.anchor, summary=f"Flags: {self.flags}")
            await ed.close_message(t("troll_tos_expired"))

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: ui.Item) -> None:
        await self.editor.bot.report_error(interaction, error, f"/{self.editor.cmd} · ToS warning", sid=self.editor.sid)

    @ui.button(label="Acknowledge — cancel", emoji="✅", style=discord.ButtonStyle.primary, row=0)
    async def on_acknowledge(self, interaction: discord.Interaction, button: ui.Button) -> None:
        if self.settled:
            return await interaction.response.defer()
        self.settled = True
        self.stop()
        ed = self.editor
        ed.note("info", "ToS warning acknowledged — command cancelled", interaction, summary=f"Flags: {self.flags}")
        ed.done = True
        ed.stop()
        await interaction.response.edit_message(content=t("troll_tos_cancelled"), embeds=[], view=None)

    @ui.button(label="Ignore — send anyway", emoji="⚠️", style=discord.ButtonStyle.danger, row=0)
    async def on_ignore(self, interaction: discord.Interaction, button: ui.Button) -> None:
        if self.settled:
            return await interaction.response.defer()
        self.settled = True
        self.stop()
        ed = self.editor
        ed.tos_ack, ed.tos_flags = self.fingerprint, self.flags
        ignored = ed.bot.note_ignored_warning(interaction.user.id)
        ed.note("warn", "ToS warning ignored — sending anyway", interaction, summary=f"Flags: {self.flags}",
                fields={"Ignored warnings (24 h)": str(ignored)})
        # Acknowledge, put the editor back on the message (so it is there if Send is then refused for another
        # reason, e.g. a missing permission), and send exactly as a normal press of Send would.
        await interaction.response.defer()
        await interaction.edit_original_response(view=ed, **ed.render())
        await ed.send(interaction)


# ─────────────────────────────────────────────────────────────────────────────
# Permission helpers
# ─────────────────────────────────────────────────────────────────────────────

def in_thread(interaction: discord.Interaction) -> bool:
    return getattr(interaction.channel, "type", None) in THREAD_TYPES


def missing_to_post(
    interaction: discord.Interaction, *,
    embeds: bool = False, files: bool = False, polls: bool = False, voice: bool = False,
) -> list[tuple[str, str]]:
    """
    Everything that would stop a PUBLIC post right now, as (permission name, "user"|"app").
    Empty list = good to go. `embeds`/`files` add the app-side needs of that kind of post;
    `polls`/`voice` add the user-side permission those two need.
    """
    missing: list[tuple[str, str]] = []

    if interaction.guild_id is not None:
        perms = interaction.permissions
        # An EMPTY set means Discord didn't send the member's permissions (anyone who can run a
        # command can at least view the channel). Don't block anyone on missing data.
        if perms.value and not perms.administrator:
            if not interaction.is_guild_integration() and not perms.use_external_apps:
                missing.append(("Use External Apps", "user"))
            can_send = perms.send_messages_in_threads if in_thread(interaction) else perms.send_messages
            if not can_send:
                missing.append(("Send Messages", "user"))
            if polls and not perms.send_polls:
                missing.append(("Send Polls", "user"))
            if voice and not perms.send_voice_messages:
                missing.append(("Send Voice Messages", "user"))

    app = interaction.app_permissions
    if embeds and not app.embed_links:
        missing.append(("Embed Links", "app"))
    if files and not app.attach_files:
        missing.append(("Attach Files", "app"))
    return missing


def describe_missing(missing: list[tuple[str, str]]) -> str:
    lines = []
    for perm, who in missing:
        if perm == "Use External Apps":
            lines.append(t("troll_perm_external_apps"))
        elif who == "user":
            lines.append(t("troll_perm_user", perm=perm))
        else:
            lines.append(t("troll_perm_app", perm=perm))
    return t("troll_missing_perms", details="\n".join(lines))


async def reply_private(interaction: discord.Interaction, content: Optional[str] = None, **kwargs):
    """Ephemeral reply that works whether or not the interaction was already answered."""
    if interaction.response.is_done():
        return await interaction.followup.send(content, ephemeral=True, **kwargs)
    return await interaction.response.send_message(content, ephemeral=True, **kwargs)


def missing_text(missing: list[tuple[str, str]]) -> str:
    """Plain-English list of missing permissions, for the activity log."""
    return ", ".join(f"{perm} ({'you' if who == 'user' else 'the app'})" for perm, who in missing)


async def open_editor(interaction: discord.Interaction, view: Any, *, deferred: bool = False) -> None:
    """Show a private editor and start counting it against the user's open-editor cap."""
    try:
        if deferred:
            await interaction.followup.send(**view.render(), view=view, ephemeral=True)
        else:
            await interaction.response.send_message(**view.render(), view=view, ephemeral=True)
    except BaseException:
        view.stop()                     # it was never shown: don't leave it counted or holding files
        raise
    view.bot.track_editor(interaction.user.id, view)


async def open_editor_with_media(interaction: discord.Interaction, view: Any, attachments: list[discord.Attachment]) -> None:
    """
    Open an editor, first loading files given in the slash command's `media` option (any file type — only
    /voice looks at what kind of file it gets). Downloading can outlast Discord's 3-second window, so with
    files the command is acknowledged first and the editor arrives as the follow-up. Same limits as the
    editor's Media button.
    """
    if not attachments:
        return await open_editor(interaction, view)
    await interaction.response.defer(ephemeral=True)
    warnings: list[str] = []
    try:
        await ingest_media(view, attachments, interaction.filesize_limit or FALLBACK_UPLOAD, warnings)
    except BaseException:
        view.stop()
        raise
    view.note("info" if view.media else "warn", "file from the command's media option", interaction,
              summary=f"{len(view.media)} of {len(attachments)} accepted" + (f" · {' | '.join(warnings)}" if warnings else ""),
              details=describe_refs(view.media))
    await open_editor(interaction, view, deferred=True)
    if warnings:
        await interaction.followup.send("\n".join(warnings), ephemeral=True)


class EditorMixin:
    """
    What every private editor (BuilderView, EchoView, VoiceView, PollView) shares: its session id and the
    activity-log helpers, the cap on open editors, and the common "post it publicly" routine.
    Put it FIRST in the bases: `class EchoView(EditorMixin, ui.View)`.
    """

    cmd = "?"                           # command name, for the log
    sid = "-"                           # session id: ties together the log entries of one command
    bot: "TrollenatorBot"
    tts: bool
    pings_on: bool
    sending = False                     # True while a Send is in flight, and after it succeeded
    tos_ack = ""                        # fingerprint of the content whose ToS warning was ignored (never warned twice)
    tos_flags = ""                      # the flags of that warning, for the log

    def note(self, level: str, event: str, interaction: Optional[discord.Interaction] = None, **kw: Any) -> None:
        self.bot.tlog.record(level, f"/{self.cmd} · {event}", interaction, sid=self.sid, **kw)

    def stop(self) -> None:
        self.bot.untrack_editor(self)
        if hasattr(self, "media"):
            self.media = []             # free the files (the cap on open editors keeps total memory bounded)
        if hasattr(self, "clip"):
            self.clip = None
        super().stop()                  # type: ignore[misc]  (ui.View.stop)

    async def evict(self) -> None:
        """The user opened more editors than MAX_OPEN_EDITORS — this, their oldest, is closed."""
        self.note("info", "closed — replaced by a newer editor")
        await self.close_message(t("troll_editor_replaced", limit=MAX_OPEN_EDITORS))   # type: ignore[attr-defined]

    async def warn_if_risky(self, interaction: discord.Interaction, scan: ScanInput, details: str) -> bool:
        """
        Run the ToS check on what is about to be posted. If it finds something, the editor is replaced by a warning
        (a WarnView) and True is returned — the caller must then stop; the WarnView carries on or cancels. The same
        content is never warned about twice, so "Ignore" really means "send as normal".
        """
        if not self.bot.host.tos_enabled:
            return False
        scan.recent_posts = self.bot.recent_posts(interaction.user.id)
        fingerprint = scan.fingerprint()
        if fingerprint == self.tos_ack:
            return False
        self.tos_ack = self.tos_flags = ""
        findings = scan_content(scan, self.bot.host.tos_terms)
        if not should_warn(findings):
            return False
        flags = ", ".join(f"{f.code}({f.weight})" for f in findings)
        self.note("warn", "ToS warning shown", interaction, summary=f"Flags: {flags}", details=details)
        await interaction.response.edit_message(
            content=tos_warning_text(findings), embeds=[], view=WarnView(self, findings, fingerprint),
            allowed_mentions=discord.AllowedMentions.none())
        return True

    async def refuse(self, interaction: discord.Interaction, why: str, text: str, *, summary: str = "") -> None:
        """Send did nothing: tell the user privately why, and log it."""
        self.note("warn", f"not sent — {why}", interaction, summary=summary)
        await reply_private(interaction, text)

    async def publish(self, interaction: discord.Interaction, payload: dict, *, details: str, ping_text: str) -> None:
        """
        Post `payload` publicly as a follow-up to this Send press — silently acknowledged first, so Discord shows no
        "<user> used /…" line above it — then close the editor. Claims the cooldown, guards against a double press,
        and logs the outcome. Everything that can be checked BEFORE posting has been checked by the caller.
        """
        uid = interaction.user.id
        if wait := self.bot.claim_cooldown(uid):
            return await self.refuse(interaction, "cooldown", t("troll_cooldown", seconds=f"{wait:.1f}"),
                                     summary=f"{wait:.1f} s left")
        self.sending = True
        age = interaction_age_ms(interaction)
        started = time.monotonic()
        acked = False
        try:
            if not interaction.response.is_done():          # (already answered when coming back from a ToS warning)
                await interaction.response.defer()
            acked = True
            message = await interaction.followup.send(**payload)
        except discord.HTTPException as e:
            self.sending = False
            self.bot.release_cooldown(uid)
            if not acked:
                raise                   # never got as far as posting (e.g. the press expired): report_error explains
            self.note("fail", "send failed", interaction, details=details,
                      summary=f"Discord refused the message: HTTP {e.status}, code {e.code}: {inline(e.text or str(e), 300)}")
            return await interaction.followup.send(
                t("troll_send_failed", error=inline(e.text or str(e), 300)), ephemeral=True)
        except BaseException:
            self.sending = False
            self.bot.release_cooldown(uid)
            raise

        self.bot.note_post(uid)
        mid = getattr(message, "id", None)
        link = f"https://discord.com/channels/{interaction.guild_id or '@me'}/{interaction.channel_id}/{mid}" if mid else "—"
        self.note("ok", "sent", interaction, details=details,
                  summary=f"Posted in {round((time.monotonic() - started) * 1000)} ms (the Send press was {age} ms old when it arrived).",
                  fields={"Message": link, "TTS": "on" if self.tts else "off", "Pings": "on" if self.pings_on else "off",
                          **({"ToS warning": f"ignored — {self.tos_flags}"} if self.tos_ack and self.tos_flags else {})})
        await self.close_message(t("troll_embed_sent"), interaction)         # type: ignore[attr-defined]
        if self.pings_on and ping_text:
            if notes := ping_notes(ping_text, interaction.app_permissions):
                await interaction.followup.send("\n".join(notes), ephemeral=True)


def describe_where(interaction: discord.Interaction) -> str:
    if interaction.guild_id is not None:
        return t("troll_pc_where_guild")
    if interaction.context.dm_channel:
        return t("troll_pc_where_bot_dm")
    return t("troll_pc_where_private")


# ─────────────────────────────────────────────────────────────────────────────
# Embed draft — everything the builder edits
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ImageRef:
    url: str                          # what the live preview shows
    data: Optional[bytes] = None      # bytes of an uploaded image (None = plain link)
    filename: Optional[str] = None    # tame name used when re-uploading

    @property
    def uploaded(self) -> bool:
        return self.data is not None


@dataclass
class FileRef:
    """A file of ANY kind that goes on a message as an ordinary attachment."""
    data: bytes
    filename: str


@dataclass
class EmbedDraft:
    content: str = ""
    title: str = ""
    title_url: str = ""
    description: str = ""
    colour: Optional[int] = None
    timestamp: Optional[datetime] = None
    timestamp_now: bool = False                 # "use the moment of sending"
    author_name: str = ""
    author_url: str = ""
    author_icon: Optional[ImageRef] = None
    footer_text: str = ""
    footer_icon: Optional[ImageRef] = None
    thumbnail: Optional[ImageRef] = None
    image: Optional[ImageRef] = None
    fields: list = field(default_factory=list)  # [{"name", "value", "inline"}]

    def has_embed(self) -> bool:
        return bool(
            self.title or self.description or self.fields or self.author_name
            or self.footer_text or self.thumbnail or self.image
        )

    def uploads(self) -> list[tuple[str, ImageRef]]:
        return [(slot, ref) for slot in IMAGE_SLOTS
                if (ref := getattr(self, slot)) is not None and ref.uploaded]

    def upload_bytes(self) -> int:
        return sum(len(ref.data) for _, ref in self.uploads())

    @staticmethod
    def attachment_name(slot: str, ref: ImageRef) -> str:
        return f"{slot}_{ref.filename}"          # slot prefix keeps names unique

    def files(self) -> list[discord.File]:
        return [
            discord.File(io.BytesIO(ref.data), filename=self.attachment_name(slot, ref))
            for slot, ref in self.uploads()
        ]

    def build(self, *, final: bool) -> Optional[discord.Embed]:
        """
        The embed, or None if there's nothing embed-worthy yet.
        final=False → live preview (images use their CDN/link URL).
        final=True  → real send (uploaded images become attachment:// references).
        """
        if not self.has_embed():
            return None

        def img(slot: str) -> Optional[str]:
            ref = getattr(self, slot)
            if ref is None:
                return None
            if final and ref.uploaded:
                return f"attachment://{self.attachment_name(slot, ref)}"
            return ref.url

        embed = discord.Embed(
            title=self.title or None,
            url=self.title_url or None,
            description=self.description or None,
            colour=self.colour,
        )
        if self.timestamp_now:
            embed.timestamp = discord.utils.utcnow()
        elif self.timestamp:
            embed.timestamp = self.timestamp
        if self.author_name:
            embed.set_author(name=self.author_name, url=self.author_url or None, icon_url=img("author_icon"))
        if self.footer_text:
            embed.set_footer(text=self.footer_text, icon_url=img("footer_icon"))
        if url := img("thumbnail"):
            embed.set_thumbnail(url=url)
        if url := img("image"):
            embed.set_image(url=url)
        for fld in self.fields:
            embed.add_field(name=fld["name"], value=fld["value"], inline=fld["inline"])
        return embed


def describe_embed_draft(d: EmbedDraft, media: list[FileRef]) -> str:
    """What an embed message contains, for the activity log (text only — never image bytes)."""
    def img(ref: Optional[ImageRef]) -> str:
        return "—" if ref is None else (f"uploaded {ref.filename}" if ref.uploaded else ref.url)

    lines = []
    if d.content:
        lines.append(f"Message: {d.content}")
    if d.title:
        lines.append(f"Title: {d.title}" + (f"  → {d.title_url}" if d.title_url else ""))
    if d.description:
        lines.append(f"Description: {clip(d.description, 700)}")
    if d.author_name:
        lines.append(f"Author: {d.author_name}" + (f"  → {d.author_url}" if d.author_url else "")
                     + (f"  icon: {img(d.author_icon)}" if d.author_icon else ""))
    if d.footer_text:
        lines.append(f"Footer: {clip(d.footer_text, 200)}" + (f"  icon: {img(d.footer_icon)}" if d.footer_icon else ""))
    if d.thumbnail:
        lines.append(f"Thumbnail: {img(d.thumbnail)}")
    if d.image:
        lines.append(f"Image: {img(d.image)}")
    if d.colour is not None:
        lines.append(f"Colour: #{d.colour:06X}")
    if d.timestamp_now or d.timestamp:
        lines.append("Timestamp: now" if d.timestamp_now else f"Timestamp: {d.timestamp:%Y-%m-%d %H:%M} UTC")
    for i, fld in enumerate(d.fields[:8], start=1):
        lines.append(f"Field {i}{' (inline)' if fld['inline'] else ''}: {clip(fld['name'], 60)} = {clip(fld['value'], 120)}")
    if len(d.fields) > 8:
        lines.append(f"… and {len(d.fields) - 8} more fields")
    if media:
        lines.append("Files:\n" + describe_refs(media))
    return "\n".join(lines) or "(empty)"


# ─────────────────────────────────────────────────────────────────────────────
# Embed builder UI — forms (modals)
# ─────────────────────────────────────────────────────────────────────────────
# A Discord form holds at most 5 inputs, so one form can't hold a whole embed.
# The builder is a private message with buttons; each button opens a small form for
# one part of the embed. Chrome (button/form labels) stays plain English constants,
# like the other plugins; real messages go through strings.json.

def text_field(
    label: str, *, default: str = "", paragraph: bool = False, required: bool = False,
    max_length: Optional[int] = None, placeholder: Optional[str] = None,
    description: Optional[str] = None,
) -> tuple[ui.TextInput, ui.Label]:
    inp = ui.TextInput(
        style=discord.TextStyle.paragraph if paragraph else discord.TextStyle.short,
        default=default or None, required=required, max_length=max_length, placeholder=placeholder,
    )
    return inp, ui.Label(text=label, component=inp, description=description)


def upload_field(label: str, *, description: Optional[str] = None) -> tuple[ui.FileUpload, ui.Label]:
    up = ui.FileUpload(required=False, min_values=0, max_values=1)
    return up, ui.Label(text=label, component=up, description=description)


def link_default(ref: Optional[ImageRef]) -> str:
    """Pre-fill a link box only when the current image IS a plain link."""
    return ref.url if ref is not None and not ref.uploaded else ""


class DraftModal(ui.Modal):
    """Base for every builder form: shared validation helpers + finishing logic."""

    def __init__(self, builder: "BuilderView", *, title: str) -> None:
        super().__init__(title=title, timeout=900)
        self.builder = builder
        self.warnings: list[str] = []

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Acknowledge FIRST (a silent "deferred update" of the builder message). The ban check hits
        # the database and some forms download images — either can outlast Discord's 3-second window
        # (error 10062). Every on_submit below can therefore assume the interaction is already answered.
        await interaction.response.defer()
        return await self.builder.bot.guard(interaction)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await self.builder.bot.report_error(
            interaction, error, f"/{self.builder.cmd} · form {type(self).__name__}", sid=self.builder.sid)

    # ── input helpers ────────────────────────────────────────────────────────
    def keep_url(self, raw: Optional[str], label: str, current: str) -> str:
        """A link box → cleaned URL, "" if emptied, or `current` (+ warning) if invalid."""
        raw = (raw or "").strip()
        if not raw:
            return ""
        try:
            return clean_url(raw)
        except ValueError:
            self.warnings.append(t("troll_warn_bad_url", field=label))
            return current

    async def read_upload(self, att: discord.Attachment, label: str) -> Optional[ImageRef]:
        """Validate + download an uploaded image. Adds a warning and returns None on failure."""
        mime = (att.content_type or "").split(";")[0].strip().lower()
        if mime in ("", "application/octet-stream"):
            mime = IMAGE_EXTS.get(Path(att.filename.lower()).suffix, "")
        if mime not in IMAGE_TYPES:
            self.warnings.append(t("troll_warn_not_image", field=label, filename=inline(att.filename)))
            return None
        if att.size > MAX_IMAGE_BYTES:
            self.warnings.append(t("troll_warn_too_large", field=label, filename=inline(att.filename),
                                   size=fmt_mb(att.size), limit=fmt_mb(MAX_IMAGE_BYTES)))
            return None
        try:
            data = await att.read()
        except discord.HTTPException:
            self.warnings.append(t("troll_warn_download", field=label))
            return None
        return ImageRef(url=att.url, data=data, filename=safe_filename(att.filename, mime))

    async def resolve_image(
        self, current: Optional[ImageRef], label: str, upload: ui.FileUpload,
        link_text: Optional[str], remove: bool,
    ) -> Optional[ImageRef]:
        """
        What an image slot should hold after this form is submitted:
          new upload → wins · "remove" ticked → cleared · link typed → that link ·
          link box emptied (it was pre-filled with the old link) → cleared · else unchanged.
        """
        if upload.values:
            ref = await self.read_upload(upload.values[0], label)
            return ref if ref is not None else current      # rejected upload keeps the old one
        if remove:
            return None
        text = (link_text or "").strip()
        if text:
            try:
                return ImageRef(url=clean_url(text))
            except ValueError:
                self.warnings.append(t("troll_warn_bad_url", field=f"{label} link"))
                return current
        if current is not None and not current.uploaded:
            return None
        return current

    async def finish(self, interaction: discord.Interaction) -> None:
        """Redraw the builder, then show any warnings collected while applying the input."""
        await self.builder.refresh(interaction)
        if self.warnings:
            await interaction.followup.send("\n".join(self.warnings), ephemeral=True)


async def ingest_media(
    view: Any, attachments: list[discord.Attachment], limit: int, warnings: list[str], label: str = "Media",
) -> None:
    """
    Download `attachments` onto `view.media`, keeping to Discord's file-count and upload limits AND to
    MAX_MEDIA_BYTES (so one editor can't hold an unbounded amount of memory). Anything skipped adds a warning.
    Sizes are checked BEFORE downloading, so memory stays bounded. Shared by the Media form and /say's options.
    """
    cap = min(limit, MAX_MEDIA_BYTES)
    used = view.other_bytes() + sum(len(ref.data) for ref in view.media)
    slots = MAX_ATTACHMENTS - view.other_count() - len(view.media)
    for att in attachments:
        if slots <= 0:
            warnings.append(t("troll_warn_too_many_files", field=label, limit=MAX_ATTACHMENTS))
            break
        if used + att.size > cap:
            warnings.append(t("troll_warn_file_too_large", field=label, filename=inline(att.filename),
                              size=fmt_mb(att.size), limit=fmt_mb(cap)))
            continue
        try:
            data = await att.read()
        except discord.HTTPException:
            warnings.append(t("troll_warn_download", field=label))
            continue
        view.media.append(FileRef(data=data, filename=safe_media_filename(att.filename)))
        used += len(data)
        slots -= 1


class MediaModal(DraftModal):
    """
    Add files of ANY kind (posted as ordinary attachments) and/or remove ones already attached.
    Shared by /say and /embed — whichever view opens it provides:
      .media            list[FileRef] already attached          .media_room()   how many more fit
      .other_count()    attachments that aren't media (embed images)   .other_bytes()  their size
    """

    def __init__(self, builder) -> None:
        super().__init__(builder, title="Media")
        self.up: Optional[ui.FileUpload] = None
        room = builder.media_room()
        if room > 0:
            self.up = ui.FileUpload(required=False, min_values=0, max_values=min(room, MAX_ATTACHMENTS))
            self.add_item(ui.Label(
                text="Add files", component=self.up,
                description=f"Any file type, up to {room} more. They are posted as normal attachments."))
        self.rm: Optional[ui.CheckboxGroup] = None
        if builder.media:
            options = [
                discord.CheckboxGroupOption(label=f"{i + 1}. {ref.filename}"[:100], value=str(i))
                for i, ref in enumerate(builder.media)
            ]
            self.rm = ui.CheckboxGroup(required=False, min_values=0, max_values=len(options), options=options)
            self.add_item(ui.Label(text="Remove files", component=self.rm))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        b = self.builder
        removing = set(self.rm.values) if self.rm is not None else set()
        b.media = [ref for i, ref in enumerate(b.media) if str(i) not in removing]
        await ingest_media(b, self.up.values if self.up is not None else [],
                           interaction.filesize_limit or FALLBACK_UPLOAD, self.warnings)
        await self.finish(interaction)


class TextModal(DraftModal):
    def __init__(self, builder: "BuilderView") -> None:
        super().__init__(builder, title="Message & text")
        d = builder.draft
        self.in_content, l1 = text_field(
            "Message above the embed", default=d.content, paragraph=True, max_length=MAX_MESSAGE_LEN,
            description="Plain text sent together with the embed. Optional.")
        self.in_title, l2 = text_field("Title", default=d.title, max_length=256)
        self.in_title_url, l3 = text_field(
            "Title link (URL)", default=d.title_url, max_length=500, placeholder="https://…")
        # Discord forms cap a paragraph at 4000 characters (an embed allows 4096).
        self.in_desc, l4 = text_field(
            "Description", default=d.description, paragraph=True, max_length=4000,
            description="Discord markdown works here.")
        for item in (l1, l2, l3, l4):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        d = self.builder.draft
        trial = dataclasses.replace(
            d,
            content=self.in_content.value.strip(),
            title=self.in_title.value.strip(),
            title_url=self.keep_url(self.in_title_url.value, "Title link", d.title_url),
            description=self.in_desc.value.strip(),
        )
        if await self.builder.commit(interaction, trial):
            await self.finish(interaction)


class AuthorModal(DraftModal):
    def __init__(self, builder: "BuilderView") -> None:
        super().__init__(builder, title="Author")
        d = builder.draft
        self.in_name, l1 = text_field(
            "Author name", default=d.author_name, max_length=256,
            description="Empty this to remove the whole author line.")
        self.in_url, l2 = text_field(
            "Author link (URL)", default=d.author_url, max_length=500, placeholder="https://…")
        self.up_icon, l3 = upload_field(
            "Author icon — upload", description="Optional. Leave empty to keep the current icon.")
        self.in_icon, l4 = text_field(
            "Author icon — link", default=link_default(d.author_icon), max_length=500,
            placeholder="https://… (used when nothing is uploaded)")
        for item in (l1, l2, l3, l4):
            self.add_item(item)
        self.rm_icon: Optional[ui.Checkbox] = None
        if d.author_icon is not None:
            self.rm_icon = ui.Checkbox()
            self.add_item(ui.Label(text="Remove the current icon", component=self.rm_icon))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        d = self.builder.draft
        name = self.in_name.value.strip()
        if not name:
            if self.up_icon.values:
                return await reply_private(interaction, t("troll_err_author_name"))
            trial = dataclasses.replace(d, author_name="", author_url="", author_icon=None)
        else:
            icon = await self.resolve_image(
                d.author_icon, "Author icon", self.up_icon, self.in_icon.value,
                bool(self.rm_icon and self.rm_icon.value))
            trial = dataclasses.replace(
                d, author_name=name, author_icon=icon,
                author_url=self.keep_url(self.in_url.value, "Author link", d.author_url))
        if await self.builder.commit(interaction, trial):
            await self.finish(interaction)


class FooterModal(DraftModal):
    def __init__(self, builder: "BuilderView") -> None:
        super().__init__(builder, title="Footer")
        d = builder.draft
        self.in_text, l1 = text_field(
            "Footer text", default=d.footer_text, paragraph=True, max_length=2048,
            description="Empty this to remove the footer.")
        self.up_icon, l2 = upload_field(
            "Footer icon — upload", description="Optional. Leave empty to keep the current icon.")
        self.in_icon, l3 = text_field(
            "Footer icon — link", default=link_default(d.footer_icon), max_length=500,
            placeholder="https://… (used when nothing is uploaded)")
        for item in (l1, l2, l3):
            self.add_item(item)
        self.rm_icon: Optional[ui.Checkbox] = None
        if d.footer_icon is not None:
            self.rm_icon = ui.Checkbox()
            self.add_item(ui.Label(text="Remove the current icon", component=self.rm_icon))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        d = self.builder.draft
        text = self.in_text.value.strip()
        if not text:
            if self.up_icon.values:
                return await reply_private(interaction, t("troll_err_footer_text"))
            trial = dataclasses.replace(d, footer_text="", footer_icon=None)
        else:
            icon = await self.resolve_image(
                d.footer_icon, "Footer icon", self.up_icon, self.in_icon.value,
                bool(self.rm_icon and self.rm_icon.value))
            trial = dataclasses.replace(d, footer_text=text, footer_icon=icon)
        if await self.builder.commit(interaction, trial):
            await self.finish(interaction)


class ImagesModal(DraftModal):
    def __init__(self, builder: "BuilderView") -> None:
        super().__init__(builder, title="Thumbnail & main image")
        d = builder.draft
        self.up_thumb, l1 = upload_field(
            "Thumbnail — upload", description="Small image in the corner. Leave empty to keep the current one.")
        self.in_thumb, l2 = text_field(
            "Thumbnail — link", default=link_default(d.thumbnail), max_length=500, placeholder="https://…")
        self.up_image, l3 = upload_field(
            "Main image — upload", description="Large image under the text. Leave empty to keep the current one.")
        self.in_image, l4 = text_field(
            "Main image — link", default=link_default(d.image), max_length=500, placeholder="https://…")
        for item in (l1, l2, l3, l4):
            self.add_item(item)
        self.rm: Optional[ui.CheckboxGroup] = None
        options = []
        if d.thumbnail is not None:
            options.append(discord.CheckboxGroupOption(label="Remove the thumbnail", value="thumbnail"))
        if d.image is not None:
            options.append(discord.CheckboxGroupOption(label="Remove the main image", value="image"))
        if options:
            self.rm = ui.CheckboxGroup(required=False, min_values=0, max_values=len(options), options=options)
            self.add_item(ui.Label(text="Remove current images", component=self.rm))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        d = self.builder.draft
        removing = set(self.rm.values) if self.rm is not None else set()
        thumb = await self.resolve_image(
            d.thumbnail, "Thumbnail", self.up_thumb, self.in_thumb.value, "thumbnail" in removing)
        image = await self.resolve_image(
            d.image, "Main image", self.up_image, self.in_image.value, "image" in removing)
        trial = dataclasses.replace(d, thumbnail=thumb, image=image)
        if await self.builder.commit(interaction, trial):
            await self.finish(interaction)


class StyleModal(DraftModal):
    def __init__(self, builder: "BuilderView") -> None:
        super().__init__(builder, title="Colour & timestamp")
        d = builder.draft
        if d.timestamp_now:
            stamp = "now"
        else:
            stamp = d.timestamp.strftime("%Y-%m-%d %H:%M") if d.timestamp else ""
        self.in_colour, l1 = text_field(
            "Colour", default=f"#{d.colour:06X}" if d.colour is not None else "", max_length=20,
            placeholder="#5865F2, or red / blue / green / blurple …",
            description="The stripe on the left. Empty = none.")
        self.in_time, l2 = text_field(
            "Timestamp", default=stamp, max_length=40,
            placeholder="now · 2026-10-02 18:30 · a Unix timestamp",
            description="Shown in the footer. 'now' = the moment you press Send (UTC dates). Empty = none.")
        self.add_item(l1)
        self.add_item(l2)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        d = self.builder.draft
        colour, ts_now, ts = d.colour, d.timestamp_now, d.timestamp

        raw = self.in_colour.value.strip()
        if not raw:
            colour = None
        else:
            try:
                colour = parse_colour(raw)
            except ValueError:
                self.warnings.append(t("troll_warn_bad_colour", value=inline(raw)))

        raw = self.in_time.value.strip()
        if not raw:
            ts_now, ts = False, None
        else:
            try:
                ts_now, ts = parse_timestamp(raw)
            except ValueError:
                self.warnings.append(t("troll_warn_bad_time", value=inline(raw)))

        trial = dataclasses.replace(d, colour=colour, timestamp_now=ts_now, timestamp=ts)
        if await self.builder.commit(interaction, trial):
            await self.finish(interaction)


class FieldModal(DraftModal):
    """Add a field (index=None) or edit/delete an existing one."""

    def __init__(self, builder: "BuilderView", index: Optional[int]) -> None:
        super().__init__(builder, title="Add field" if index is None else f"Edit field {index + 1}")
        self.index = index
        cur = builder.draft.fields[index] if index is not None else None
        self.in_name, l1 = text_field(
            "Field name", default=cur["name"] if cur else "", required=True, max_length=256)
        self.in_value, l2 = text_field(
            "Field value", default=cur["value"] if cur else "", paragraph=True, required=True, max_length=1024)
        self.in_inline = ui.Checkbox(default=bool(cur["inline"]) if cur else False)
        l3 = ui.Label(text="Show inline (side by side with other fields)", component=self.in_inline)
        for item in (l1, l2, l3):
            self.add_item(item)
        self.rm_field: Optional[ui.Checkbox] = None
        if cur is not None:
            self.rm_field = ui.Checkbox()
            self.add_item(ui.Label(text="Delete this field", component=self.rm_field))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        d = self.builder.draft
        fields = list(d.fields)
        if self.rm_field is not None and self.rm_field.value:
            del fields[self.index]
        else:
            name, value = self.in_name.value.strip(), self.in_value.value.strip()
            if not name or not value:
                return await reply_private(interaction, t("troll_err_field_blank"))
            entry = {"name": name, "value": value, "inline": bool(self.in_inline.value)}
            if self.index is None:
                if len(fields) >= MAX_FIELDS:
                    return await reply_private(interaction, t("troll_embed_too_many_fields"))
                fields.append(entry)
            else:
                fields[self.index] = entry
        if await self.builder.commit(interaction, dataclasses.replace(d, fields=fields)):
            await self.finish(interaction)


# ─────────────────────────────────────────────────────────────────────────────
# Embed builder UI — the private control panel
# ─────────────────────────────────────────────────────────────────────────────

class BuilderView(EditorMixin, ui.View):
    """Private (ephemeral) message: live preview + buttons. Created by /embed."""

    cmd = "embed"

    def __init__(
        self, bot: "TrollenatorBot", origin: discord.Interaction, *, pings_on: bool, tts: bool = False
    ) -> None:
        super().__init__(timeout=BUILDER_TIMEOUT)
        self.bot = bot
        self.sid = session_id(origin)
        self.anchor = origin        # latest interaction whose "original response" is the builder message
        self.pings_on = pings_on
        self.tts = tts
        self.draft = EmbedDraft()
        self.media: list[FileRef] = []      # files posted OUTSIDE the embed (any type)
        self.done = False
        self.rebuild()

    # ── layout ───────────────────────────────────────────────────────────────
    def _button(self, label, emoji, handler, row, style=discord.ButtonStyle.secondary, disabled=False):
        btn = ui.Button(label=label, emoji=emoji, style=style, row=row, disabled=disabled)
        btn.callback = handler
        return btn

    def rebuild(self) -> None:
        """(Re)create every control — cheap, and keeps the field picker in step with the draft."""
        self.clear_items()
        for label, emoji, handler in (
            ("Text",   "📝", self.on_text),
            ("Author", "👤", self.on_author),
            ("Footer", "🔻", self.on_footer),
            ("Images", "🖼️", self.on_images),
            ("Style",  "🎨", self.on_style),
        ):
            self.add_item(self._button(label, emoji, handler, 0))

        fields = self.draft.fields
        if fields:
            picker = ui.Select(
                placeholder="Edit or delete a field…", row=1,
                options=[
                    discord.SelectOption(
                        label=f"{i + 1}. {fld['name']}"[:100], value=str(i),
                        description=fld["value"].replace("\n", " ")[:100] or None)
                    for i, fld in enumerate(fields)
                ],
            )

            async def picked(interaction: discord.Interaction, picker=picker) -> None:
                await interaction.response.send_modal(FieldModal(self, int(picker.values[0])))

            picker.callback = picked
            self.add_item(picker)

        self.add_item(self._button("Add field", "➕", self.on_add_field, 2,
                                   disabled=len(fields) >= MAX_FIELDS))
        self.add_item(self._button("Media", "📎", self.on_media, 2))
        self.add_item(self._button("TTS", "🔊", self.on_tts, 2, style=toggle_style(self.tts)))
        self.add_item(self._button("Pings", "🔔", self.on_pings, 2, style=toggle_style(self.pings_on)))
        self.add_item(self._button("Reset", "🔄", self.on_reset, 2))
        self.add_item(self._button("Send", "✅", self.on_send, 3, style=discord.ButtonStyle.success))
        self.add_item(self._button("Cancel", "✖️", self.on_cancel, 3, style=discord.ButtonStyle.danger))

    def render(self) -> dict:
        """kwargs for send_message / edit_message: header + status line, and the preview embed."""
        d = self.draft
        embed = d.build(final=False)
        lines = [t("troll_embed_header")]
        tail = [t("troll_embed_status", chars=len(embed) if embed else 0,
                  fields=len(d.fields), uploads=len(d.uploads()))]
        tail += [t("troll_echo_attachment", n=i + 1, name=inline(ref.filename, 60), size=fmt_mb(len(ref.data)))
                 for i, ref in enumerate(self.media)]
        if d.content:                    # the message preview gets whatever room the other lines leave
            room = max(80, min(1500, 1990 - len("\n".join(lines + tail)) - 40))
            preview = d.content if len(d.content) <= room else d.content[:room] + "…"
            lines.append(t("troll_embed_message", content=preview))
        lines += tail
        if embed is None:
            embed = discord.Embed(description=t("troll_embed_placeholder"), colour=discord.Colour.blurple())
        return {
            "content": "\n".join(lines),
            "embeds": [embed],
            "allowed_mentions": discord.AllowedMentions.none(),   # a preview must never ping
        }

    async def refresh(self, interaction: discord.Interaction) -> None:
        """Redraw the builder message after a change (`interaction` came from one of its controls)."""
        self.rebuild()
        if interaction.response.is_done():
            await interaction.edit_original_response(view=self, **self.render())
        else:
            await interaction.response.edit_message(view=self, **self.render())
        self.anchor = interaction

    async def commit(self, interaction: discord.Interaction, trial: EmbedDraft) -> bool:
        """Adopt `trial` as the new draft unless it breaks Discord's embed size limit."""
        embed = trial.build(final=False)
        if embed is not None and len(embed) > EMBED_TOTAL_LIMIT:
            await reply_private(interaction, t("troll_embed_too_big", chars=len(embed)))
            return False
        self.draft = trial
        return True

    async def close_message(self, content: str, interaction: Optional[discord.Interaction] = None) -> None:
        """
        Replace the builder with a one-liner and drop the buttons (best effort: tokens expire).
        `interaction` must be one whose original response IS the builder message — i.e. a
        component/form interaction that did not post a new message of its own.
        """
        self.done = True
        self.stop()
        try:
            await (interaction or self.anchor).edit_original_response(content=content, embeds=[], view=None)
        except discord.HTTPException:
            pass

    # ── view plumbing ────────────────────────────────────────────────────────
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await self.bot.guard(interaction)

    async def on_timeout(self) -> None:
        if not self.done:
            self.note("info", "expired — nothing was sent", self.anchor)
            await self.close_message(t("troll_embed_expired"))

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: ui.Item) -> None:
        await self.bot.report_error(interaction, error, f"/{self.cmd} · embed builder", sid=self.sid)

    # ── buttons ──────────────────────────────────────────────────────────────
    async def on_text(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(TextModal(self))

    async def on_author(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(AuthorModal(self))

    async def on_footer(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(FooterModal(self))

    async def on_images(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(ImagesModal(self))

    async def on_style(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(StyleModal(self))

    async def on_add_field(self, interaction: discord.Interaction) -> None:
        if len(self.draft.fields) >= MAX_FIELDS:
            return await reply_private(interaction, t("troll_embed_too_many_fields"))
        await interaction.response.send_modal(FieldModal(self, None))

    # what the shared Media form asks every editor for
    def media_room(self) -> int:
        return MAX_ATTACHMENTS - len(self.draft.uploads()) - len(self.media)

    def other_count(self) -> int:
        return len(self.draft.uploads())

    def other_bytes(self) -> int:
        return self.draft.upload_bytes()

    def extra_files(self) -> list[discord.File]:
        taken = {EmbedDraft.attachment_name(slot, ref) for slot, ref in self.draft.uploads()}
        names = unique_names([ref.filename for ref in self.media], taken)
        return [discord.File(io.BytesIO(ref.data), filename=name) for ref, name in zip(self.media, names)]

    async def on_media(self, interaction: discord.Interaction) -> None:
        if self.media_room() <= 0 and not self.media:
            return await reply_private(interaction, t("troll_too_many_files", limit=MAX_ATTACHMENTS))
        await interaction.response.send_modal(MediaModal(self))

    async def on_tts(self, interaction: discord.Interaction) -> None:
        self.tts = not self.tts
        await self.refresh(interaction)

    async def on_pings(self, interaction: discord.Interaction) -> None:
        self.pings_on = not self.pings_on
        await self.refresh(interaction)

    async def on_reset(self, interaction: discord.Interaction) -> None:
        self.draft = EmbedDraft()
        self.media = []
        await self.refresh(interaction)

    async def on_cancel(self, interaction: discord.Interaction) -> None:
        self.note("info", "cancelled", interaction)
        self.done = True
        self.stop()
        await interaction.response.edit_message(
            content=t("troll_embed_cancelled"), embeds=[], view=None)

    async def on_send(self, interaction: discord.Interaction) -> None:
        await self.send(interaction)

    async def send(self, interaction: discord.Interaction) -> None:
        """Send was pressed (or the user chose to ignore the ToS warning): check, then post."""
        if self.sending:                                  # a second tap while the first is in flight
            return await interaction.response.defer()
        d = self.draft
        embed = d.build(final=True)
        if embed is None and not d.content.strip() and not self.media:
            return await self.refuse(interaction, "nothing to send", t("troll_embed_nothing"))
        if embed is not None and len(embed) > EMBED_TOTAL_LIMIT:
            return await self.refuse(interaction, "embed too big", t("troll_embed_too_big", chars=len(embed)),
                                     summary=f"{len(embed)} characters")

        files = d.files() + self.extra_files()
        if len(files) > MAX_ATTACHMENTS:
            return await self.refuse(interaction, "too many files", t("troll_too_many_files", limit=MAX_ATTACHMENTS),
                                     summary=f"{len(files)} files")
        if missing := missing_to_post(interaction, embeds=embed is not None, files=bool(files)):
            return await self.refuse(interaction, "missing permission", describe_missing(missing),
                                     summary=missing_text(missing))

        limit = interaction.filesize_limit or FALLBACK_UPLOAD
        total = d.upload_bytes() + sum(len(ref.data) for ref in self.media)
        if total > limit:
            return await self.refuse(interaction, "files too big", t(
                "troll_files_too_big", size=fmt_mb(total), limit=fmt_mb(limit)),
                summary=f"{fmt_mb(total)} MB over the {fmt_mb(limit)} MB limit")

        payload = {"allowed_mentions": allowed_mentions(self.pings_on), "ephemeral": False}
        if d.content:
            payload["content"] = d.content
        if embed:
            payload["embeds"] = [embed]
        if files:
            payload["files"] = files
        if self.tts:
            payload["tts"] = True
        details = describe_embed_draft(d, self.media)
        links = [ref.url for ref in (d.author_icon, d.footer_icon, d.thumbnail, d.image) if ref is not None and not ref.uploaded]
        scan = ScanInput(
            ping_text=d.content, tts=self.tts, pings_on=self.pings_on, filenames=[r.filename for r in self.media],
            texts=[d.content, d.title, d.title_url, d.description, d.author_name, d.author_url, d.footer_text, *links,
                   *(f"{f['name']}\n{f['value']}" for f in d.fields)],
            names=[d.author_name, d.title, d.footer_text])
        if await self.warn_if_risky(interaction, scan, details):
            return
        await self.publish(interaction, payload, details=details, ping_text=d.content)


# ─────────────────────────────────────────────────────────────────────────────
# /say editor — plain text + optional files of any kind (deliberately NO embeds)
# ─────────────────────────────────────────────────────────────────────────────
# A file on a plain-text message is just an attachment: Discord shows images and video inline,
# gives audio a player and anything else a download — the post stays an ordinary message.
# Text and files are each optional, but a message needs at least one of them.

class EchoTextModal(DraftModal):
    """Edit the text and the repeat amount."""

    def __init__(self, builder: "EchoView") -> None:
        super().__init__(builder, title="Text & repeat")
        self.in_text, l1 = text_field(
            "Text", default=builder.text, paragraph=True, max_length=MAX_MESSAGE_LEN,
            description="Leave empty to send only files.")
        self.in_repeat, l2 = text_field(
            "Repeat amount", default=builder.repeat_raw, max_length=REPEAT_INPUT_MAX, placeholder="a number, or max / all",
            description="How many lines to repeat the text on. Decimals are ignored, 0 or less = 1. Empty = 1.")
        self.add_item(l1)
        self.add_item(l2)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        b = self.builder
        b.text = self.in_text.value.strip()
        raw = self.in_repeat.value.strip()
        try:
            parse_repeat(raw)
            b.repeat_raw = raw or "1"
        except ValueError:
            self.warnings.append(t("troll_bad_repeat"))
        await self.finish(interaction)


class EchoView(EditorMixin, ui.View):
    """Private (ephemeral) editor for /say: preview of the text + Text / Media / TTS / Pings / Send / Cancel."""

    cmd = "say"

    def __init__(
        self, bot: "TrollenatorBot", origin: discord.Interaction, *,
        text: str, repeat_raw: str, pings_on: bool, tts: bool,
    ) -> None:
        super().__init__(timeout=BUILDER_TIMEOUT)
        self.bot = bot
        self.sid = session_id(origin)
        self.anchor = origin
        self.pings_on = pings_on
        self.tts = tts
        self.text = text
        self.repeat_raw = repeat_raw
        self.media: list[FileRef] = []
        self.done = False
        self.on_tts.style = toggle_style(tts)
        self.on_pings.style = toggle_style(pings_on)

    # ── state ────────────────────────────────────────────────────────────────
    def message(self) -> tuple[str, int, int]:
        """(final message text, lines actually used, lines requested). No text → ("", 0, requested)."""
        requested, _ = parse_repeat(self.repeat_raw)
        if not self.text:
            return "", 0, requested
        message, lines = build_repeated(self.text, requested)
        return message, lines, requested

    def files(self) -> list[discord.File]:
        names = unique_names([ref.filename for ref in self.media])
        return [discord.File(io.BytesIO(ref.data), filename=name) for ref, name in zip(self.media, names)]

    # what the shared Media form asks every editor for
    def media_room(self) -> int:
        return MAX_ATTACHMENTS - len(self.media)

    def other_count(self) -> int:
        return 0

    def other_bytes(self) -> int:
        return 0

    def render(self) -> dict:
        message, lines, requested = self.message()
        _, was_max = parse_repeat(self.repeat_raw)
        head = t("troll_echo_header")
        if message:
            head += "\n" + t("troll_echo_status", lines=lines, chars=len(message), limit=MAX_MESSAGE_LEN)
            if requested > lines and not was_max:
                head += "\n" + t("troll_repeat_capped", lines=lines)
        else:
            head += "\n" + t("troll_echo_no_text")
        if self.media:
            head += "\n" + "\n".join(
                t("troll_echo_attachment", n=i + 1, name=inline(ref.filename, 60), size=fmt_mb(len(ref.data)))
                for i, ref in enumerate(self.media))
        if not message:
            return {"content": head, "allowed_mentions": discord.AllowedMentions.none()}
        room = 1990 - len(head) - 5                      # Discord caps the preview message at 2000
        preview = message if len(message) <= room else message[:max(0, room - 1)] + "…"
        return {"content": f"{head}\n>>> {preview}",
                "allowed_mentions": discord.AllowedMentions.none()}   # a preview must never ping

    async def refresh(self, interaction: discord.Interaction) -> None:
        """Redraw after a form (which has already been acknowledged by DraftModal.interaction_check)."""
        await interaction.edit_original_response(view=self, **self.render())
        self.anchor = interaction

    async def close_message(self, content: str, interaction: Optional[discord.Interaction] = None) -> None:
        self.done = True
        self.stop()
        try:
            await (interaction or self.anchor).edit_original_response(content=content, view=None)
        except discord.HTTPException:
            pass

    # ── view plumbing ────────────────────────────────────────────────────────
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await self.bot.guard(interaction)

    async def on_timeout(self) -> None:
        if not self.done:
            self.note("info", "expired — nothing was sent", self.anchor)
            await self.close_message(t("troll_echo_expired"))

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: ui.Item) -> None:
        await self.bot.report_error(interaction, error, f"/{self.cmd} · editor", sid=self.sid)

    # ── buttons ──────────────────────────────────────────────────────────────
    @ui.button(label="Text & repeat", emoji="📝", row=0)
    async def on_text(self, interaction: discord.Interaction, button: ui.Button) -> None:
        await interaction.response.send_modal(EchoTextModal(self))

    @ui.button(label="Media", emoji="📎", row=0)
    async def on_media(self, interaction: discord.Interaction, button: ui.Button) -> None:
        await interaction.response.send_modal(MediaModal(self))

    @ui.button(label="TTS", emoji="🔊", style=discord.ButtonStyle.danger, row=0)
    async def on_tts(self, interaction: discord.Interaction, button: ui.Button) -> None:
        self.tts = not self.tts
        button.style = toggle_style(self.tts)
        await interaction.response.edit_message(view=self)

    @ui.button(label="Pings", emoji="🔔", style=discord.ButtonStyle.danger, row=0)
    async def on_pings(self, interaction: discord.Interaction, button: ui.Button) -> None:
        self.pings_on = not self.pings_on
        button.style = toggle_style(self.pings_on)
        await interaction.response.edit_message(view=self)

    @ui.button(label="Send", emoji="✅", style=discord.ButtonStyle.success, row=1)
    async def on_send(self, interaction: discord.Interaction, button: ui.Button) -> None:
        await self.send(interaction)

    async def send(self, interaction: discord.Interaction) -> None:
        """Send was pressed (or the user chose to ignore the ToS warning): check, then post."""
        if self.sending:                                  # a second tap while the first is in flight
            return await interaction.response.defer()
        message, lines, requested = self.message()
        files = self.files()
        if not message and not files:
            return await self.refuse(interaction, "nothing to send", t("troll_echo_nothing"))
        if missing := missing_to_post(interaction, files=bool(files)):
            return await self.refuse(interaction, "missing permission", describe_missing(missing),
                                     summary=missing_text(missing))
        limit = interaction.filesize_limit or FALLBACK_UPLOAD
        total = sum(len(ref.data) for ref in self.media)
        if total > limit:
            return await self.refuse(interaction, "files too big", t(
                "troll_files_too_big", size=fmt_mb(total), limit=fmt_mb(limit)),
                summary=f"{fmt_mb(total)} MB over the {fmt_mb(limit)} MB limit")

        payload = {"allowed_mentions": allowed_mentions(self.pings_on), "ephemeral": False}
        if message:
            payload["content"] = message
        if files:
            payload["files"] = files
        if self.tts:
            payload["tts"] = True
        details = f"Text: {self.text or '(none)'}\nRepeated on {lines} line(s) (asked for {self.repeat_raw}) → {len(message)} characters posted"
        if self.media:
            details += "\nFiles:\n" + describe_refs(self.media)
        scan = ScanInput(ping_text=message, texts=[self.text], filenames=[r.filename for r in self.media],
                         lines=lines, tts=self.tts, pings_on=self.pings_on)
        if await self.warn_if_risky(interaction, scan, details):
            return
        await self.publish(interaction, payload, details=details, ping_text=message)

    @ui.button(label="Cancel", emoji="✖️", style=discord.ButtonStyle.danger, row=1)
    async def on_cancel(self, interaction: discord.Interaction, button: ui.Button) -> None:
        self.note("info", "cancelled", interaction)
        self.done = True
        self.stop()
        await interaction.response.edit_message(content=t("troll_echo_cancelled"), view=None)


# ─────────────────────────────────────────────────────────────────────────────
# /voice editor — one audio file, posted as a real Discord voice message
# ─────────────────────────────────────────────────────────────────────────────
# The editor only ever holds ONE thing: the audio. It is converted to Ogg/Opus the moment it is
# uploaded (so Send is instant), and Send answers the button press with the voice message itself.
# A voice message can't carry text, embeds, other files or a poll — that's Discord's rule.

async def load_voice_clip(att: discord.Attachment) -> tuple[Optional[VoiceClip], Optional[str], str]:
    """
    Download + convert an uploaded audio file → (clip, None, "ok"), or (None, a warning to show, why).
    `why` is a short code for the activity log: too_large | download_failed | unsupported | unreadable | …
    """
    name = inline(att.filename, 60)
    if att.size > MAX_AUDIO_BYTES:
        return None, t("troll_audio_too_large", filename=name, size=fmt_mb(att.size), limit=fmt_mb(MAX_AUDIO_BYTES)), "too_large"
    try:
        data = await att.read()
    except discord.HTTPException:
        return None, t("troll_warn_download", field="Audio"), "download_failed"
    try:
        return await convert_to_voice(data, att.filename), None, "ok"
    except AudioError as e:
        key = {"no_ffmpeg": "troll_audio_no_ffmpeg", "timeout": "troll_audio_timeout",
               "too_long": "troll_audio_too_long", "unsupported": "troll_audio_unsupported",
               "busy": "troll_audio_busy"}.get(e.code, "troll_audio_unreadable")
        return None, t(key, filename=name, minutes=MAX_VOICE_SECONDS // 60), e.code


class VoiceAudioModal(DraftModal):
    """Upload (or replace) the audio."""

    def __init__(self, builder: "VoiceView") -> None:
        super().__init__(builder, title="Voice message")
        self.up = ui.FileUpload(required=True, min_values=1, max_values=1)
        self.add_item(ui.Label(
            text="Audio file", component=self.up,
            description="Any audio (mp3, wav, m4a, ogg, flac …) — it is converted to a voice message."))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        att = self.up.values[0]
        clip, warning, outcome = await load_voice_clip(att)
        if clip is not None:
            self.builder.clip = clip
        self.builder.note_audio(interaction, att, clip, outcome)
        if warning:
            self.warnings.append(warning)
        await self.finish(interaction)


class VoiceView(EditorMixin, ui.View):
    """Private (ephemeral) editor for /voice: the current audio + Change audio / Send / Cancel."""

    cmd = "voice"
    tts = False                 # a voice message carries no text, so these two never apply
    pings_on = False

    def __init__(self, bot: "TrollenatorBot", origin: discord.Interaction, *, clip: Optional[VoiceClip]) -> None:
        super().__init__(timeout=BUILDER_TIMEOUT)
        self.bot = bot
        self.sid = session_id(origin)
        self.anchor = origin
        self.clip = clip
        self.done = False
        self.sending = False

    def render(self) -> dict:
        lines = [t("troll_voice_header")]
        if self.clip is None:
            lines.append(t("troll_voice_no_audio"))
        else:
            key = "troll_voice_clip_asis" if self.clip.mode == "as-is" else "troll_voice_clip"
            lines.append(t(key, name=inline(self.clip.source_name, 60),
                           seconds=f"{self.clip.duration:.1f}", size=f"{len(self.clip.data) / 1024:.0f}"))
        return {"content": "\n".join(lines)}

    def note_audio(self, interaction: discord.Interaction, att: discord.Attachment,
                   clip: Optional[VoiceClip], outcome: str) -> None:
        """Log the result of loading an audio file (used by the command and by the Change-audio form)."""
        if clip is not None:
            self.note("info", "audio ready", interaction, fields={"File": describe_attachment(att)},
                      summary=(f"{clip.mode} · {clip.duration:.1f} s · {fmt_size(len(clip.data))} to upload "
                               f"(source {fmt_size(clip.source_bytes)}) · took {clip.convert_ms} ms"))
        else:
            self.note("warn", "audio rejected", interaction, fields={"File": describe_attachment(att)},
                      summary=f"Could not make a voice message from it: {outcome}")

    async def refresh(self, interaction: discord.Interaction) -> None:
        await interaction.edit_original_response(view=self, **self.render())
        self.anchor = interaction

    async def close_message(self, content: str, interaction: Optional[discord.Interaction] = None) -> None:
        self.done = True
        self.stop()
        try:
            await (interaction or self.anchor).edit_original_response(content=content, view=None)
        except discord.HTTPException:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await self.bot.guard(interaction)

    async def on_timeout(self) -> None:
        if not self.done:
            self.note("info", "expired — nothing was sent", self.anchor)
            await self.close_message(t("troll_voice_expired"))

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: ui.Item) -> None:
        await self.bot.report_error(interaction, error, f"/{self.cmd} · editor", sid=self.sid)

    @ui.button(label="Change audio", emoji="🎵", row=0)
    async def on_audio(self, interaction: discord.Interaction, button: ui.Button) -> None:
        await interaction.response.send_modal(VoiceAudioModal(self))

    @ui.button(label="Send", emoji="✅", style=discord.ButtonStyle.success, row=0)
    async def on_send(self, interaction: discord.Interaction, button: ui.Button) -> None:
        if self.sending:                                  # a second tap while the first is in flight
            return await interaction.response.defer()
        clip = self.clip
        if clip is None:
            return await self.refuse(interaction, "no audio", t("troll_voice_nothing"))
        if missing := missing_to_post(interaction, voice=True):
            return await self.refuse(interaction, "missing permission", describe_missing(missing),
                                     summary=missing_text(missing))
        limit = interaction.filesize_limit or FALLBACK_UPLOAD
        if len(clip.data) > limit:
            return await self.refuse(interaction, "file too big", t(
                "troll_files_too_big", size=fmt_mb(len(clip.data)), limit=fmt_mb(limit)),
                summary=f"{fmt_mb(len(clip.data))} MB over the {fmt_mb(limit)} MB limit")
        uid = interaction.user.id
        if wait := self.bot.claim_cooldown(uid):
            return await self.refuse(interaction, "cooldown", t("troll_cooldown", seconds=f"{wait:.1f}"),
                                     summary=f"{wait:.1f} s left")

        self.sending = True
        age = interaction_age_ms(interaction)
        details = (f"Source: {clip.source_name}\n{clip.mode} · {clip.duration:.1f} s · {fmt_size(len(clip.data))} "
                   f"(source {fmt_size(clip.source_bytes)}, prepared in {clip.convert_ms} ms)")
        try:
            # `interaction` is the press of Send on THIS private editor, so the voice message answers
            # the editor message — not the /voice command. It can't be deferred first: the voice
            # message has to be this interaction's first response (the clip is already converted), and the
            # whole upload has to fit in the 3 seconds Discord gives a button press.
            took = await post_voice_message(interaction, clip, self.bot.http_session())
        except VoiceSendError as e:
            self.sending = False
            self.bot.release_cooldown(uid)
            self.note("fail", "send failed", interaction, details=details, fields={"Upload": fmt_size(len(clip.data))},
                      summary=f"{e} — the press was already {age} ms old when the upload began.")
            text = t("troll_voice_too_slow" if "Unknown interaction" in str(e) else "troll_voice_failed",
                     error=inline(str(e), 300))
            try:
                return await reply_private(interaction, text)
            except discord.HTTPException:
                # This press has expired, but the editor's own interaction token is good for 15 minutes.
                try:
                    return await self.anchor.followup.send(text, ephemeral=True)
                except discord.HTTPException:
                    return
        except BaseException:
            self.sending = False
            self.bot.release_cooldown(uid)
            raise

        self.bot.note_post(uid)
        self.note("ok", "sent", interaction, details=details,
                  summary=f"Upload accepted in {took} ms (the press was {age} ms old when it arrived; Discord allows 3000).")
        # `interaction`'s own response is now the voice message, so the editor is closed through
        # the anchor (the interaction whose original response IS the editor).
        await self.close_message(t("troll_embed_sent"))

    @ui.button(label="Cancel", emoji="✖️", style=discord.ButtonStyle.danger, row=0)
    async def on_cancel(self, interaction: discord.Interaction, button: ui.Button) -> None:
        self.note("info", "cancelled", interaction)
        self.done = True
        self.stop()
        await interaction.response.edit_message(content=t("troll_voice_cancelled"), view=None)


# ─────────────────────────────────────────────────────────────────────────────
# /poll editor — a native Discord poll (its own editor: question, answers, duration)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PollDraft:
    content: str = ""                                   # optional message above the poll
    question: str = ""
    answers: list = field(default_factory=list)         # [(emoji or None, text)]
    hours: int = 24
    multiple: bool = False


class PollModal(DraftModal):
    """One form for the whole poll: message, question, answers (one per line) and duration."""

    def __init__(self, builder: "PollView") -> None:
        super().__init__(builder, title="Poll")
        d = builder.draft
        self.in_content, l1 = text_field(
            "Message above the poll", default=d.content, paragraph=True, max_length=MAX_MESSAGE_LEN,
            description="Plain text sent together with the poll. Optional.")
        self.in_question, l2 = text_field(
            "Question", default=d.question, max_length=POLL_QUESTION_MAX)
        self.in_answers, l3 = text_field(
            "Answers — one per line", default=format_answers(d.answers), paragraph=True, max_length=1500,
            description=f"Up to {POLL_MAX_ANSWERS}, each up to {POLL_ANSWER_MAX} characters. "
                        "Start a line with an emoji to give that answer one.")
        self.in_duration, l4 = text_field(
            "Open for", default=format_duration(d.hours), max_length=12, placeholder="24h, 3d, 2w …",
            description="From 1 hour to 32 days.")
        for item in (l1, l2, l3, l4):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        d = self.builder.draft
        answers = d.answers
        try:
            answers = parse_poll_answers(self.in_answers.value)
        except PollInputError as e:
            self.warnings.append(t(f"troll_poll_warn_{e.kind}", n=e.line, max=POLL_MAX_ANSWERS if e.kind == "too_many" else POLL_ANSWER_MAX))
        hours = d.hours
        raw = self.in_duration.value.strip()
        if raw:
            try:
                hours = parse_duration(raw)
            except ValueError:
                self.warnings.append(t("troll_poll_warn_duration", value=inline(raw, 20)))
        self.builder.draft = dataclasses.replace(
            d, content=self.in_content.value.strip(), question=self.in_question.value.strip(),
            answers=answers, hours=hours)
        await self.finish(interaction)


class PollView(EditorMixin, ui.View):
    """Private (ephemeral) editor for /poll: preview + Edit poll / Multiple choice / TTS / Pings / Send / Cancel."""

    cmd = "poll"

    def __init__(
        self, bot: "TrollenatorBot", origin: discord.Interaction, *, question: str, pings_on: bool, tts: bool
    ) -> None:
        super().__init__(timeout=BUILDER_TIMEOUT)
        self.bot = bot
        self.sid = session_id(origin)
        self.anchor = origin
        self.pings_on = pings_on
        self.tts = tts
        self.draft = PollDraft(question=question)
        self.done = False
        self.sending = False
        self.on_tts.style = toggle_style(tts)
        self.on_pings.style = toggle_style(pings_on)

    def render(self) -> dict:
        d = self.draft
        lines = [t("troll_poll_header")]
        lines.append(t("troll_poll_question", question=d.question) if d.question else t("troll_poll_no_question"))
        for i, (emoji, text) in enumerate(d.answers, start=1):
            lines.append(t("troll_poll_answer", n=i, answer=f"{emoji} {text}" if emoji else text))
        lines.append(t("troll_poll_status", answers=len(d.answers), max=POLL_MAX_ANSWERS,
                       duration=format_duration(d.hours), multiple="on" if d.multiple else "off"))
        if d.content:                                     # the message text gets whatever room is left
            room = 1990 - len("\n".join(lines)) - 20
            if room > 40:
                preview = d.content if len(d.content) <= min(500, room) else d.content[:min(500, room)] + "…"
                lines.insert(1, t("troll_embed_message", content=preview))
        return {"content": "\n".join(lines), "allowed_mentions": discord.AllowedMentions.none()}

    async def refresh(self, interaction: discord.Interaction) -> None:
        await interaction.edit_original_response(view=self, **self.render())
        self.anchor = interaction

    async def close_message(self, content: str, interaction: Optional[discord.Interaction] = None) -> None:
        self.done = True
        self.stop()
        try:
            await (interaction or self.anchor).edit_original_response(content=content, view=None)
        except discord.HTTPException:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await self.bot.guard(interaction)

    async def on_timeout(self) -> None:
        if not self.done:
            self.note("info", "expired — nothing was sent", self.anchor)
            await self.close_message(t("troll_poll_expired"))

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: ui.Item) -> None:
        await self.bot.report_error(interaction, error, f"/{self.cmd} · editor", sid=self.sid)

    @ui.button(label="Edit poll", emoji="📝", row=0)
    async def on_edit(self, interaction: discord.Interaction, button: ui.Button) -> None:
        await interaction.response.send_modal(PollModal(self))

    @ui.button(label="Multiple choice", emoji="☑️", row=0)
    async def on_multiple(self, interaction: discord.Interaction, button: ui.Button) -> None:
        self.draft = dataclasses.replace(self.draft, multiple=not self.draft.multiple)
        button.style = discord.ButtonStyle.success if self.draft.multiple else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self, **self.render())

    @ui.button(label="TTS", emoji="🔊", style=discord.ButtonStyle.danger, row=0)
    async def on_tts(self, interaction: discord.Interaction, button: ui.Button) -> None:
        self.tts = not self.tts
        button.style = toggle_style(self.tts)
        await interaction.response.edit_message(view=self)

    @ui.button(label="Pings", emoji="🔔", style=discord.ButtonStyle.danger, row=0)
    async def on_pings(self, interaction: discord.Interaction, button: ui.Button) -> None:
        self.pings_on = not self.pings_on
        button.style = toggle_style(self.pings_on)
        await interaction.response.edit_message(view=self)

    @ui.button(label="Send", emoji="✅", style=discord.ButtonStyle.success, row=1)
    async def on_send(self, interaction: discord.Interaction, button: ui.Button) -> None:
        await self.send(interaction)

    async def send(self, interaction: discord.Interaction) -> None:
        """Send was pressed (or the user chose to ignore the ToS warning): check, then post."""
        if self.sending:
            return await interaction.response.defer()
        d = self.draft
        if not d.question or not d.answers:
            return await self.refuse(interaction, "poll incomplete", t("troll_poll_nothing"))
        if missing := missing_to_post(interaction, polls=True):
            return await self.refuse(interaction, "missing permission", describe_missing(missing),
                                     summary=missing_text(missing))

        poll = discord.Poll(question=d.question, duration=timedelta(hours=d.hours), multiple=d.multiple)
        for emoji, text in d.answers:
            poll.add_answer(text=text, emoji=emoji)
        payload = {"poll": poll, "allowed_mentions": allowed_mentions(self.pings_on), "ephemeral": False}
        if d.content:
            payload["content"] = d.content
        if self.tts:
            payload["tts"] = True
        details = "\n".join(filter(None, [
            f"Message: {d.content}" if d.content else "",
            f"Question: {d.question}",
            *(f"  {i}. {format_answers([a])}" for i, a in enumerate(d.answers, start=1)),
            f"Open for {format_duration(d.hours)} · multiple choice {'on' if d.multiple else 'off'}",
        ]))
        scan = ScanInput(ping_text=d.content, texts=[d.content, d.question, *(text for _, text in d.answers)],
                         tts=self.tts, pings_on=self.pings_on)
        if await self.warn_if_risky(interaction, scan, details):
            return
        await self.publish(interaction, payload, details=details, ping_text=d.content)

    @ui.button(label="Cancel", emoji="✖️", style=discord.ButtonStyle.danger, row=1)
    async def on_cancel(self, interaction: discord.Interaction, button: ui.Button) -> None:
        self.note("info", "cancelled", interaction)
        self.done = True
        self.stop()
        await interaction.response.edit_message(content=t("troll_poll_cancelled"), view=None)


# ─────────────────────────────────────────────────────────────────────────────
# Shared by both bots: timing + error reporting
# ─────────────────────────────────────────────────────────────────────────────

def interaction_age_ms(interaction: discord.Interaction) -> int:
    """≈ how long ago Discord created the interaction (includes any clock difference with this machine)."""
    return round((discord.utils.utcnow() - interaction.created_at).total_seconds() * 1000)


class ReportMixin:
    """
    Error reporting for a bot (the user app AND the control bot). Needs `self.tlog` and `self.latency`
    (the latter comes from discord.Client).
    """

    tlog: "TrollLog"

    async def report_error(
        self, interaction: discord.Interaction, error: BaseException, where: str, *, sid: str = ""
    ) -> None:
        sid = sid or session_id(interaction)
        if isinstance(error, discord.HTTPException) and error.code in (10062, 40060):
            return self._report_expired(interaction, where, sid, error.code)
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        log.error(f"Trollenator error in {where} (user={interaction.user.id})\n{redact(tb)}")
        self.tlog.record("fail", f"{where} · error", interaction, sid=sid, error=error,
                         summary=f"{type(error).__name__}: {inline(redact(error), 300)}")
        try:
            await reply_private(interaction, t("troll_error"))
        except discord.HTTPException:
            pass

    def _report_expired(self, interaction: discord.Interaction, where: str, sid: str, code: int = 10062) -> None:
        """
        Discord error 10062 "Unknown interaction" (the answer came too late, or the interaction was already used up) or
        40060 "already acknowledged" (something else answered first). The entry says WHERE the time went and — the
        part that tells these cases apart — whether THIS process ever managed to answer.
        """
        arrived = interaction.extras.get("arrived_ms")
        now_age = interaction_age_ms(interaction)
        answered = interaction.response.is_done()          # True only after one of OUR calls was accepted by Discord
        if arrived is not None and arrived > 2000:
            verdict = ("It was already that old when the bot first saw it, so the delay happened BEFORE the bot: "
                       "network / gateway lag — or this machine's clock being off (the age is measured against it).")
        elif answered:
            verdict = ("This process had already answered the interaction, so the call that failed came after the user "
                       "got their reply. Nothing was lost.")
        else:
            verdict = ("It reached the bot quickly, yet this process never got an answer accepted. If the user DID see a "
                       "reply, another copy of the bot logged in with the same token answered first (an old host still "
                       "running, a second process) — look for it, or reset the token. If the user saw nothing, the bot's "
                       "event loop was stalled (look for \"Event loop stalled\" entries) or the answer was slow to leave.")
        what = "Unknown interaction" if code == 10062 else "Interaction has already been acknowledged"
        self.tlog.record(
            "warn", f"{where} · interaction expired ({code})", interaction, sid=sid,
            summary=f"Discord answered '{what}'. " + verdict,
            fields={
                "Reached the bot": f"{arrived} ms after Discord made it" if arrived is not None else "?",
                "Age at the failed answer": f"{now_age} ms (limit 3000)",
                "Answered by this process": "yes" if answered else "no",
                "Process": f"pid {os.getpid()}",
                "Gateway latency": f"{round(self.latency * 1000)} ms" if math.isfinite(self.latency) else "?",
            })


# ─────────────────────────────────────────────────────────────────────────────
# The Trollenator user app (one of possibly several bots; only one runs at a time)
# ─────────────────────────────────────────────────────────────────────────────

class TrollTree(app_commands.CommandTree):
    """Command tree for the Trollenator app: user-install only, ban check on every command."""

    def __init__(self, client: "TrollenatorBot") -> None:
        super().__init__(
            client,
            # New commands inherit these unless they say otherwise → user install only,
            # usable in servers, DMs with the bot, and DMs/group DMs between users.
            allowed_installs=app_commands.AppInstallationType(guild=False, user=True),
            allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        ok = await self.client.guard(interaction)
        if ok and interaction.type is discord.InteractionType.application_command:   # autocomplete keystrokes aren't logged
            ex = interaction.extras
            name = self.client.base_name(interaction.command.qualified_name) if interaction.command else "?"
            self.client.tlog.record(
                "info", f"/{name} · invoked", interaction, sid=session_id(interaction),
                summary=(f"Reached the bot {ex.get('arrived_ms', '?')} ms after Discord created it; the ban check took "
                         f"{ex.get('guard_ms', '?')} ms (Discord allows 3000 ms to answer)."),
                details=describe_options(interaction))
        return ok

    async def on_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, app_commands.CheckFailure):
            return      # guard() already told the user why
        cause = error.original if isinstance(error, app_commands.CommandInvokeError) else error
        name = self.client.base_name(interaction.command.qualified_name) if interaction.command else "?"
        await self.client.report_error(interaction, cause, f"/{name}")


class TrollCommands(commands.Cog):
    """The slash commands. Registered on the user app's own tree."""

    def __init__(self, bot: "TrollenatorBot") -> None:
        self.bot = bot

    # ── /say ────────────────────────────────────────────────────────────────
    @app_commands.command(name="say", description="Say something — text, files, or both. Optionally repeated on several lines.")
    @app_commands.describe(
        text="What to say (you can also type or change it in the editor)",
        repeat_amount="Lines to repeat it on: type a number, or max / all (default 1)",
        ping="Pings work by default — pick no to turn every ping off",
        tts="Send it as a text-to-speech message (needs Send TTS Messages)",
        media="A file to attach — any type (you can add more in the editor)",
    )
    @app_commands.rename(repeat_amount="repeat-amount")
    @app_commands.choices(
        ping=[app_commands.Choice(name="no", value="no")],
        tts=[app_commands.Choice(name="yes", value="yes")],
    )
    async def echo(
        self,
        interaction: discord.Interaction,
        text: Optional[app_commands.Range[str, 1, MAX_MESSAGE_LEN]] = None,
        repeat_amount: app_commands.Range[str, 1, REPEAT_INPUT_MAX] = "1",
        ping: Optional[str] = None,
        tts: Optional[str] = None,
        media: Optional[discord.Attachment] = None,
    ) -> None:
        try:
            parse_repeat(repeat_amount)
        except ValueError:
            self.bot.tlog.record("warn", "/say · rejected — bad repeat-amount", interaction,
                                 sid=session_id(interaction), summary=f"repeat-amount was {inline(repeat_amount, 20)!r}")
            return await reply_private(interaction, t("troll_bad_repeat"))

        # The reply to the command is PRIVATE: an editor where you can change the text / repeat
        # amount, attach files and toggle TTS, then press Send. Every option is optional — with none
        # you just get an empty editor. The public post goes out as a follow-up, so nobody sees
        # "<user> used /say". Cooldown and permission checks happen at Send time.
        view = EchoView(self.bot, interaction, text=text or "", repeat_raw=repeat_amount.strip() or "1",
                        pings_on=ping != "no", tts=tts == "yes")
        await open_editor_with_media(interaction, view, [media] if media is not None else [])

    # ── /embed ───────────────────────────────────────────────────────────────
    @app_commands.command(name="embed", description="Build a custom embed (with images, and files outside it) and post it.")
    @app_commands.describe(
        ping="Pings in your message work by default — pick no to turn every ping off",
        tts="Send it as a text-to-speech message (needs Send TTS Messages)",
        media="A file to attach beside the embed — any type (images INSIDE the embed: use the editor's Images button)",
    )
    @app_commands.choices(
        ping=[app_commands.Choice(name="no", value="no")],
        tts=[app_commands.Choice(name="yes", value="yes")],
    )
    async def embed(
        self, interaction: discord.Interaction, ping: Optional[str] = None, tts: Optional[str] = None,
        media: Optional[discord.Attachment] = None,
    ) -> None:
        builder = BuilderView(self.bot, interaction, pings_on=ping != "no", tts=tts == "yes")
        await open_editor_with_media(interaction, builder, [media] if media is not None else [])

    # ── /voice ───────────────────────────────────────────────────────────────
    @app_commands.command(name="voice", description="Send an audio file as a Discord voice message.")
    @app_commands.describe(audio="The audio file (you can also add or change it in the editor)")
    async def voice(self, interaction: discord.Interaction, audio: Optional[discord.Attachment] = None) -> None:
        if audio is None:
            return await open_editor(interaction, VoiceView(self.bot, interaction, clip=None))
        # Converting the audio can take longer than Discord's 3-second window, so acknowledge first.
        await interaction.response.defer(ephemeral=True)
        clip, warning, outcome = await load_voice_clip(audio)
        view = VoiceView(self.bot, interaction, clip=clip)
        view.note_audio(interaction, audio, clip, outcome)
        await open_editor(interaction, view, deferred=True)
        if warning:
            await interaction.followup.send(warning, ephemeral=True)

    # ── /poll ────────────────────────────────────────────────────────────────
    @app_commands.command(name="poll", description="Create a Discord poll, with an editor for the question, answers and duration.")
    @app_commands.describe(
        question="The poll question (you can also type or change it in the editor)",
        ping="Pings in the message above the poll work by default — pick no to turn them off",
        tts="Send the message above the poll as text-to-speech (needs Send TTS Messages)",
    )
    @app_commands.choices(
        ping=[app_commands.Choice(name="no", value="no")],
        tts=[app_commands.Choice(name="yes", value="yes")],
    )
    async def poll(
        self,
        interaction: discord.Interaction,
        question: Optional[app_commands.Range[str, 1, POLL_QUESTION_MAX]] = None,
        ping: Optional[str] = None,
        tts: Optional[str] = None,
    ) -> None:
        view = PollView(self.bot, interaction, question=question or "", pings_on=ping != "no", tts=tts == "yes")
        await open_editor(interaction, view)

    # ── /permcheck ───────────────────────────────────────────────────────────
    @app_commands.command(name="permcheck", description="Privately show what I can and can't do in this channel.")
    async def permcheck(self, interaction: discord.Interaction) -> None:
        def line(label: str, ok: bool) -> str:
            return t("troll_pc_line_ok", what=label) if ok else t("troll_pc_perm_no", perm=label)

        def verdict(what: str, missing: list[tuple[str, str]]) -> str:
            if not missing:
                return t("troll_pc_line_ok", what=what)
            # Name WHOSE permission is missing: yours, or the app's (which you can't change in a server
            # the app isn't installed to).
            owners: dict[str, list[str]] = {}
            for name, who in missing:
                owners.setdefault(name, []).append(t("troll_pc_who_you") if who == "user" else t("troll_pc_who_app"))
            perms = ", ".join(f"**{name}** ({' + '.join(whos)})" for name, whos in owners.items())
            return t("troll_pc_line_no", what=what, perms=perms)

        app = interaction.app_permissions

        if interaction.guild_id is None:
            you = t("troll_pc_you_na")
        elif not interaction.permissions.value:
            you = t("troll_pc_you_unknown")
        else:
            perms = interaction.permissions
            can_send = perms.send_messages_in_threads if in_thread(interaction) else perms.send_messages
            you = "\n".join((
                line("Send Messages", perms.administrator or can_send),
                line("Use External Apps", perms.administrator or perms.use_external_apps),
                line("Send Polls", perms.administrator or perms.send_polls),
                line("Send Voice Messages", perms.administrator or perms.send_voice_messages),
                line("Send TTS Messages", perms.administrator or perms.send_tts_messages),
            ))

        app_lines = "\n".join((
            line("Embed Links", app.embed_links),
            line("Attach Files", app.attach_files),
            line("Mention @everyone, @here and all roles", app.mention_everyone),
            line("Use External Emojis", app.external_emojis),
            line("Send TTS Messages", app.send_tts_messages),
        ))
        # TTS depends on two separate permissions: YOURS (listed above) and the APP's. Discord reports the
        # app's as missing in servers it isn't installed to; whether it still speaks the message anyway only
        # a real send shows — that is what `/devpannel` → Test TTS does.
        user_tts = (interaction.guild_id is None or not interaction.permissions.value
                    or interaction.permissions.administrator or interaction.permissions.send_tts_messages)
        if user_tts and not app.send_tts_messages:
            tts_line = t("troll_pc_tts_unsure", what=t("troll_pc_what_tts"))
        else:
            tts_line = verdict(t("troll_pc_what_tts"),
                               ([] if user_tts else [("Send TTS Messages", "user")])
                               + ([] if app.send_tts_messages else [("Send TTS Messages", "app")]))
        works = "\n".join((
            verdict(t("troll_pc_what_public"), missing_to_post(interaction)),
            verdict(t("troll_pc_what_embed"), missing_to_post(interaction, embeds=True)),
            verdict(t("troll_pc_what_upload"), missing_to_post(interaction, embeds=True, files=True)),
            verdict(t("troll_pc_what_everyone"),
                    [] if app.mention_everyone else [("Mention Everyone", "app")]),
            verdict(t("troll_pc_what_poll"), missing_to_post(interaction, polls=True)),
            verdict(t("troll_pc_what_voice"), missing_to_post(interaction, voice=True)),
            tts_line,
        ))

        embed = discord.Embed(title=t("troll_pc_title"), colour=discord.Colour.blurple())
        embed.add_field(name=t("troll_pc_where_label"), value=describe_where(interaction), inline=False)
        embed.add_field(name=t("troll_pc_you_label"), value=you, inline=True)
        embed.add_field(name=t("troll_pc_app_label"), value=app_lines, inline=True)
        embed.add_field(name=t("troll_pc_result_label"), value=works, inline=False)
        embed.set_footer(text=t("troll_pc_footer"))
        await interaction.response.send_message(embed=embed, ephemeral=True)
        self.bot.tlog.record("ok", "/permcheck · report shown", interaction, sid=session_id(interaction))


class TrollenatorBot(ReportMixin, commands.Bot):
    """
    The second Discord app. Gateway intents are NONE: slash commands arrive as
    interactions, which need no intents (and no privileged-intent approval).
    """

    def __init__(self, host: "TrollenatorHost", entry: BotEntry) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned,     # required by commands.Bot; never used
            intents=discord.Intents.none(),
            help_command=None,
            tree_cls=TrollTree,
        )
        self.host = host
        self.entry = entry                  # which configured bot this is (its token stays inside the entry)
        self.cmd_prefix = ""                # "trolle-" — known once logged in (see setup_hook)
        self.online = asyncio.Event()       # set when the gateway is ready
        self.run_error = ""                 # why start() ended, in words (never contains a secret)
        self.tlog: TrollLog = host.tlog
        self.started_at = time.monotonic()
        self._last_use: dict[int, float] = {}
        self._announced = False
        self._last_blocked_log: dict[int, float] = {}                  # user id → when a "banned user" log entry was last written
        self._editors: dict[int, list] = {}                            # user id → their open editors, oldest first
        self._posts: dict[int, collections.deque] = {}                 # user id → times of their recent posts
        self._ignored: dict[int, collections.deque] = {}               # user id → times they ignored a ToS warning
        self._session: Optional[aiohttp.ClientSession] = None
        self._background: set[asyncio.Task] = set()
        self._watch_task: Optional[asyncio.Task] = None

    # ── startup / shutdown ───────────────────────────────────────────────────
    async def setup_hook(self) -> None:
        # Logged in by now (discord.py does that before setup_hook), so the bot's name is known.
        self.cmd_prefix = make_prefix(getattr(self.user, "name", ""), self.entry.prefix, self.application_id or 0)
        CommandNames.prefix = self.cmd_prefix
        self.tlog.app_label = f"{getattr(self.user, 'name', '?')}"
        await self.add_cog(TrollCommands(self))
        self._apply_command_prefix()
        await self._sync_commands()
        self._watch_task = asyncio.create_task(self._watch_loop(), name="trollenator-loop-watch")

    async def close(self) -> None:
        for task in (self._watch_task, *self._background):
            if task is not None:
                task.cancel()
        self._watch_task = None
        try:
            await super().close()
        finally:
            if self._session is not None and not self._session.closed:
                await self._session.close()

    def _apply_command_prefix(self) -> None:
        """
        Put the prefix in front of every slash command. The cog's commands are this bot's own copies, so renaming
        them touches nothing shared; each is taken out of the tree and put back under its new name (the tree is
        keyed by name). Base names contain no "-", so a name that already starts with the prefix is never prefixed twice.
        """
        for cmd in list(self.tree.get_commands()):
            if cmd.name.startswith(self.cmd_prefix):
                continue
            self.tree.remove_command(cmd.name)
            cmd.name = self.cmd_prefix + cmd.name
            self.tree.add_command(cmd)

    def base_name(self, name: str) -> str:
        """"trolle-say" → "say" (the name the code and the activity log use)."""
        return name[len(self.cmd_prefix):] if self.cmd_prefix and name.startswith(self.cmd_prefix) else name

    def spawn(self, coro) -> None:
        """Run `coro` in the background, keeping a reference so it isn't garbage-collected mid-flight."""
        task = asyncio.create_task(coro)
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    def http_session(self) -> aiohttp.ClientSession:
        """One long-lived HTTP session (kept-alive connection to Discord) for the time-critical voice upload."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(keepalive_timeout=60, ttl_dns_cache=300),
                timeout=aiohttp.ClientTimeout(total=15))
        return self._session

    def command_fingerprint(self) -> str:
        """Identifies the current slash command definitions (names included, so a new prefix changes it too)."""
        payload = [cmd.to_dict(self.tree) for cmd in self.tree.get_commands()]
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        return f"{self.application_id}:{digest}"

    def is_synced(self) -> bool:
        """Were the current command definitions already pushed to Discord for THIS application?"""
        synced = load_data(STATE_FILE).get("synced")
        return isinstance(synced, dict) and synced.get(str(self.application_id)) == self.command_fingerprint()

    async def _sync_commands(self) -> None:
        """
        Push slash commands to Discord only when their definitions changed for this application. Creating commands is
        rate limited per day, so switching back and forth between bots must not re-sync each time: the last synced
        fingerprint is remembered per application id.
        """
        fingerprint = self.command_fingerprint()
        if self.is_synced():
            log.info("Trollenator: slash commands unchanged — skipping sync.")
            self.tlog.record("info", "Slash commands unchanged", summary="No sync with Discord was needed.")
            return
        try:
            synced = await self.tree.sync()
        except discord.HTTPException as e:
            log.error(f"Trollenator: slash command sync failed: {e}")
            self.tlog.record("fail", "Slash command sync failed", error=e,
                             summary=f"HTTP {e.status}, code {e.code}: {inline(e.text or str(e), 300)}")
            return
        state = load_data(STATE_FILE)               # read AGAIN: the state may have changed while we were waiting on Discord
        known = state.get("synced")
        if not isinstance(known, dict):             # older versions stored a single string
            known = {}
        known[str(self.application_id)] = fingerprint
        state["synced"] = known
        save_data(STATE_FILE, state)
        log.info(f"Trollenator: synced {len(synced)} slash command(s).")
        self.tlog.record("ok", "Slash commands synced", summary=f"{len(synced)} command(s): "
                         + ", ".join(f"/{c.name}" for c in synced))

    # ── gateway events (a flapping Wi-Fi connection shows up here) ───────────
    async def on_ready(self) -> None:
        self.online.set()
        if not self._announced:
            self._announced = True
            log.info(f"Trollenator online as {self.user} (ID: {self.user.id})")
            self.tlog.record("ok", "Trollenator online", summary=f"Logged in as {self.user} (ID {self.user.id}), "
                             f"gateway latency {round(self.latency * 1000) if math.isfinite(self.latency) else '?'} ms.")

    async def on_disconnect(self) -> None:
        self.tlog.record("warn", "Gateway disconnected", summary="Connection to Discord was lost; discord.py reconnects by itself.")

    async def on_resumed(self) -> None:
        self.tlog.record("info", "Gateway session resumed", summary="Connection to Discord is back; no events were lost.")

    async def _watch_loop(self) -> None:
        """
        Reports when the event loop stalls. Trollenator shares bot-Bot's event loop, so anything that blocks it
        (slow code in any plugin, a starved CPU) delays Discord's interactions — and Discord only waits 3 seconds.
        """
        last_report = 0.0
        while True:
            before = time.monotonic()
            await asyncio.sleep(1.0)
            now = time.monotonic()
            lag = now - before - 1.0
            if lag >= LOOP_LAG_WARN and now - last_report > 30:
                last_report = now
                self.tlog.record(
                    "warn", "Event loop stalled",
                    summary=f"Something blocked the bot's event loop for about {lag:.1f} s. Interactions that arrive "
                            "during a stall can expire (Discord allows 3 s) — this is process-wide, not only Trollenator.",
                    fields={"Gateway latency": f"{round(self.latency * 1000)} ms" if math.isfinite(self.latency) else "?"})

    # ── per-user cooldown (shared by every posting command) ──────────────────
    def claim_cooldown(self, user_id: int) -> float:
        """
        0.0 and the cooldown starts NOW, or the seconds still left. Check-and-start is one step with no `await`
        in between, so two quick presses (or two open editors) can't both get through. Call release_cooldown()
        if the post then fails.
        """
        now = time.monotonic()
        left = self.host.cooldown - (now - self._last_use.get(user_id, float("-inf")))
        if left > 0:
            return left
        self._last_use[user_id] = now
        if len(self._last_use) > 2000:      # keep the dict from growing forever
            cutoff = now - max(self.host.cooldown, 1.0)
            self._last_use = {u: ts for u, ts in self._last_use.items() if ts > cutoff}
        return 0.0

    def release_cooldown(self, user_id: int) -> None:
        self._last_use.pop(user_id, None)

    # ── behaviour signals for the ToS check (in memory only; gone on restart) ──
    def note_post(self, user_id: int) -> None:
        self._posts.setdefault(user_id, collections.deque(maxlen=50)).append(time.monotonic())
        if len(self._posts) > 5000:
            cutoff = time.monotonic() - TOS_RAPID_WINDOW
            self._posts = {u: d for u, d in self._posts.items() if d and d[-1] > cutoff}

    def recent_posts(self, user_id: int) -> int:
        cutoff = time.monotonic() - TOS_RAPID_WINDOW
        return sum(1 for ts in self._posts.get(user_id, ()) if ts > cutoff)

    def note_ignored_warning(self, user_id: int) -> int:
        """Record that this user chose to ignore a ToS warning; returns how many they ignored in the last 24 h."""
        now = time.monotonic()
        times = self._ignored.setdefault(user_id, collections.deque(maxlen=100))
        times.append(now)
        return sum(1 for ts in times if ts > now - TOS_IGNORED_WINDOW)

    # ── open editors: each can hold uploaded files in memory, so a user gets only a few ──
    def track_editor(self, user_id: int, view: Any) -> None:
        views = self._editors.setdefault(user_id, [])
        views.append(view)
        while len(views) > MAX_OPEN_EDITORS:
            self.spawn(views.pop(0).evict())

    def untrack_editor(self, view: Any) -> None:
        anchor = getattr(view, "anchor", None)
        views = self._editors.get(anchor.user.id) if anchor is not None else None
        if views and view in views:
            views.remove(view)
            if not views:
                del self._editors[anchor.user.id]

    # ── ban check ────────────────────────────────────────────────────────────
    async def guard(self, interaction: discord.Interaction) -> bool:
        """True if this user may use Trollenator. Banned users get a private rejection."""
        uid = interaction.user.id
        # Timing breakdown for "Unknown interaction" (10062) reports: how old was this when the bot first saw it?
        interaction.extras["arrived_ms"] = interaction_age_ms(interaction)
        started = time.monotonic()
        ban = self.host.store.active_ban(uid)              # a dictionary lookup: no I/O, can't be slow
        interaction.extras["guard_ms"] = round((time.monotonic() - started) * 1000)
        if ban is None:
            return True
        now = time.monotonic()
        if now - self._last_blocked_log.get(uid, float("-inf")) > 60:      # a hammering banned user mustn't flood the log
            self._last_blocked_log[uid] = now
            if len(self._last_blocked_log) > 2000:
                self._last_blocked_log = {u: ts for u, ts in self._last_blocked_log.items() if now - ts <= 60}
            self.tlog.record("warn", "Blocked — banned user", interaction, sid=session_id(interaction),
                             summary=f"Interaction type: {interaction.type.name}. Ban reason: {ban.reason or 'none given'}.")
        if interaction.type is discord.InteractionType.autocomplete:
            return False                # autocomplete can't carry a message; just offer nothing
        reason = discord.utils.escape_mentions(ban.reason)
        text = t("troll_banned_reason", reason=reason) if ban.notify and reason else t("troll_banned")
        try:
            await reply_private(interaction, text)
        except discord.HTTPException:
            pass
        return False


# ─────────────────────────────────────────────────────────────────────────────
# THE HOST — starts / stops / swaps the user app
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SwitchResult:
    """How a switch ended. status: ok | same | busy | unknown | unavailable | is_control | rejected | unreachable | not_a_bot | failed"""
    status: str
    name: str = ""              # the bot that was asked for
    prefix: str = ""            # its command prefix (ok)
    reason: str = ""            # why it failed (failed) — plain words, never a secret
    restored: bool = False      # failed: the previous bot is running again
    previous: str = ""          # failed: the previous bot's name


class TrollenatorHost:
    """
    Runs the Trollenator user app inside this process.

    It owns the list of configured bots, starts the active one, and swaps it for another on request. Only one runs at a
    time. A swap checks the new token first, stops the old bot, starts the new one and — if that fails — starts the old
    one again, so a typo'd or disabled token can't take Trollenator down. The control bot (control.py) is a separate
    client that keeps running throughout, which is why a swap can always be undone from the control server.
    """

    def __init__(self, cfg: dict, store: Store, *, control_key: str = "") -> None:
        self.cfg = cfg
        self.store = store
        self.enabled: bool = bool(cfg.get("enabled", True))
        self.control_key = control_key                       # key of the control bot's token: never a user app
        self.control_app_id = 0                              # set by the control bot once it is logged in
        self.entries: list[BotEntry] = parse_bot_entries(cfg, frozenset({control_key}) if control_key else frozenset())
        try:
            self.cooldown: float = max(0.0, float(cfg.get("cooldown_seconds", 3)))
        except (TypeError, ValueError):
            self.cooldown = 3.0
        self.tlog = TrollLog(str(cfg.get("log_webhook_url") or ""))
        self.tos_enabled: bool = bool(cfg.get("tos_warnings", True))
        self.tos_terms = load_terms(cfg)
        self.troll: Optional[TrollenatorBot] = None       # the running bot
        self.active: Optional[BotEntry] = None            # its config entry
        self._task: Optional[asyncio.Task] = None
        self._switch_lock = asyncio.Lock()
        self._config_lock = asyncio.Lock()
        self._names: dict[str, tuple[float, object]] = {}   # token key → (valid until, BotInfo | problem kind)
        self._http: Optional[aiohttp.ClientSession] = None
        self._stopping = False
        self._stop_event = asyncio.Event()                   # set when the program is shutting down

    # ── plumbing ─────────────────────────────────────────────────────────────
    def http(self) -> aiohttp.ClientSession:
        """The host's own HTTP session (token checks, and the control bot's voice-message test)."""
        if self._http is None or self._http.closed:
            self._http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
        return self._http

    def _initial_entry(self) -> Optional[BotEntry]:
        """The bot that was active last time (remembered by token fingerprint), else the first one in the config."""
        if not self.entries:
            return None
        wanted = load_data(STATE_FILE).get("active")
        return next((e for e in self.entries if e.key == wanted), self.entries[0])

    def _remember_active(self, key: str) -> None:
        state = load_data(STATE_FILE)
        state["active"] = key
        save_data(STATE_FILE, state)

    def _launch(self, entry: BotEntry) -> TrollenatorBot:
        troll = TrollenatorBot(self, entry)
        self.troll, self.active = troll, entry
        self._task = asyncio.create_task(self._run(troll), name="trollenator-client")
        return troll

    async def _launch_and_wait(self, entry: BotEntry) -> tuple[bool, str]:
        """Start `entry` and wait until it is online, or has failed, or STARTUP_TIMEOUT passed → (ok, reason)."""
        troll = self._launch(entry)
        task = self._task
        waiter = asyncio.ensure_future(troll.online.wait())
        stopper = asyncio.ensure_future(self._stop_event.wait())
        try:
            done, _ = await asyncio.wait({waiter, stopper, task}, timeout=STARTUP_TIMEOUT, return_when=asyncio.FIRST_COMPLETED)
        finally:
            waiter.cancel()
            stopper.cancel()
        if waiter in done:
            return True, ""
        if stopper in done:
            return False, "Trollenator is shutting down"
        if task in done:
            return False, troll.run_error or "it stopped right after starting"
        return False, f"it didn't come online within {STARTUP_TIMEOUT:.0f} s"

    async def _stop_bot(self) -> None:
        troll, task = self.troll, self._task
        self.troll = self._task = None
        CommandNames.prefix = ""                         # the next bot to log in sets its own
        self.tlog.app_label = ""
        if troll is not None and not troll.is_closed():
            try:
                await troll.close()
            except Exception:
                log.exception("Trollenator did not close cleanly")
        if task is not None:
            done, _ = await asyncio.wait({task}, timeout=10)
            if task not in done:
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)      # collects the result; our own cancellation still propagates

    async def _run(self, troll: TrollenatorBot) -> None:
        try:
            await troll.start(troll.entry.token, reconnect=True)
        except discord.LoginFailure:
            troll.run_error = "login failed — Discord rejected the token (wrong, reset, or the bot is disabled)"
            log.error("Trollenator login failed — Discord rejected a token from Configs/trollenator_config.json.")
            self.tlog.record("fail", "Trollenator login failed", summary="Discord rejected the token of the bot that was being started.")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            troll.run_error = f"{type(e).__name__}: {inline(redact(e), 200)}"
            log.exception("Trollenator stopped unexpectedly")
            self.tlog.record("fail", "Trollenator stopped unexpectedly", error=e, summary=f"{type(e).__name__}: {inline(redact(e), 300)}")

    # ── checking tokens ──────────────────────────────────────────────────────
    async def probe(self, token: str) -> BotInfo:
        """Who does this token belong to? (HTTP only — no gateway login.) Raises TokenProblem."""
        return await probe_token(self.http(), token)

    async def _info_for(self, entry: BotEntry, force: bool) -> object:
        """A BotInfo, or the problem kind ("rejected" / "unreachable" / "not_a_bot"). Remembered for a while."""
        live = self.troll
        if live is not None and entry is self.active and live.online.is_set() and live.user is not None:
            return BotInfo(id=live.user.id, name=live.user.name)
        hit = self._names.get(entry.key)
        if hit is not None and hit[0] > time.monotonic() and not force:
            return hit[1]
        try:
            result: object = await self.probe(entry.token)
            ttl = PROBE_TTL_OK
        except TokenProblem as e:
            result, ttl = e.kind, PROBE_TTL_BAD
        self._names[entry.key] = (time.monotonic() + ttl, result)
        return result

    async def roster(self, *, force: bool = False) -> list[RosterItem]:
        """Every configured bot with its name, prefix and whether it is the running one."""
        gate = asyncio.Semaphore(5)

        async def one(entry: BotEntry) -> RosterItem:
            async with gate:
                found = await self._info_for(entry, force)
            active = entry is self.active and self.troll is not None
            if isinstance(found, BotInfo):
                return RosterItem(entry, found, active, make_prefix(found.name, entry.prefix, found.id))
            return RosterItem(entry, None, active, "", str(found))

        return list(await asyncio.gather(*(one(e) for e in self.entries)))

    def remember(self, entry: BotEntry, info: BotInfo) -> None:
        """Remember a bot's name for a while (so the panel needn't ask Discord again straight away)."""
        self._names[entry.key] = (time.monotonic() + PROBE_TTL_OK, info)

    # ── adding a token from the dev panel ────────────────────────────────────
    async def add_token(self, token: str) -> BotEntry:
        """
        Save a new token to the config file and the in-memory list (the caller has already checked it with probe()).
        Raises ValueError (limit / duplicate / control), OSError or json.JSONDecodeError (the file couldn't be updated —
        then nothing was changed).
        """
        async with self._config_lock:
            key = token_key(token)
            if key == self.control_key:
                raise ValueError("control")
            if any(e.key == key for e in self.entries):
                raise ValueError("duplicate")
            if len(self.entries) >= MAX_BOTS:
                raise ValueError("limit")
            await asyncio.to_thread(write_config_token, CONFIG_PATH, token)
            register_secret(token)
            entry = BotEntry(token=token, key=key)
            self.entries.append(entry)
            self._names.pop(key, None)
            return entry

    # ── switching ────────────────────────────────────────────────────────────
    async def switch_to(self, key: str) -> SwitchResult:
        if self._stopping or not self.enabled:
            return SwitchResult("unavailable")
        if self._switch_lock.locked():
            return SwitchResult("busy")
        async with self._switch_lock:
            entry = next((e for e in self.entries if e.key == key), None)
            if entry is None:
                return SwitchResult("unknown")
            running = self.troll
            if entry is self.active and running is not None and running.online.is_set() and not running.is_closed():
                return SwitchResult("same", name=running.user.name if running.user else "")
            try:                                            # a bad token is caught BEFORE anything is stopped
                info = await self.probe(entry.token)
            except TokenProblem as e:
                self._names[entry.key] = (time.monotonic() + PROBE_TTL_BAD, e.kind)
                return SwitchResult(e.kind)
            if self.control_app_id and info.id == self.control_app_id:
                return SwitchResult("is_control", name=info.name)
            self._names[entry.key] = (time.monotonic() + PROBE_TTL_OK, info)

            previous = self.active
            previous_name = running.user.name if running is not None and running.user is not None else ""
            await self._stop_bot()
            ok, reason = await self._launch_and_wait(entry)
            if ok:
                self._remember_active(entry.key)
                return SwitchResult("ok", name=info.name, prefix=self.troll.cmd_prefix if self.troll else "")
            await self._stop_bot()
            restored = False
            if self._stopping:                              # shutting down: don't start anything new
                return SwitchResult("unavailable")
            if previous is not None:
                restored, _ = await self._launch_and_wait(previous)
                if not restored:
                    await self._stop_bot()
            return SwitchResult("failed", name=info.name, reason=reason, restored=restored, previous=previous_name)

    def switch_text(self, result: SwitchResult) -> str:
        name = safe_name(result.name)
        if result.status == "ok":
            return t("troll_switch_ok", name=name, prefix=result.prefix)
        if result.status == "failed":
            if result.restored:
                return t("troll_switch_failed_restored", name=name, reason=result.reason, previous=safe_name(result.previous))
            return t("troll_switch_failed_offline", name=name, reason=result.reason)
        return t({"same": "troll_switch_same", "busy": "troll_switch_busy", "unknown": "troll_switch_unknown",
                  "unavailable": "troll_switch_unavailable", "is_control": "troll_switch_is_control",
                  "rejected": "troll_switch_rejected", "unreachable": "troll_switch_unreachable",
                  "not_a_bot": "troll_switch_not_a_bot"}[result.status])

    # ── lifecycle ────────────────────────────────────────────────────────────
    async def start(self) -> None:
        self.tlog.start()
        if self.tlog.url_rejected:
            log.warning("Trollenator: \"log_webhook_url\" in Configs/trollenator_config.json isn't a Discord webhook "
                        "URL — the activity log is off.")
        if not self.enabled:
            log.info("Trollenator is disabled in Configs/trollenator_config.json — not starting the user app.")
            self.tlog.record("info", "Trollenator disabled", summary="\"enabled\" is false in trollenator_config.json.")
            return
        entry = self._initial_entry()
        if entry is None:
            log.warning(
                "Trollenator has no user-app token — set \"token\" (or \"tokens\") in Configs/trollenator_config.json. "
                "The user app is idle; the control bot can still add one."
            )
            self.tlog.record("warn", "Trollenator has no token", summary="Set \"token\" or \"tokens\" in trollenator_config.json. The user app is idle.")
            return
        self._launch(entry)
        log.info("Trollenator starting…")
        self.tlog.record("info", "Trollenator starting",
                         summary=f"discord.py {discord.__version__} · {len(self.entries)} bot token(s) configured · cooldown {self.cooldown:g} s · "
                                 f"ffmpeg {'found' if shutil.which('ffmpeg') else 'NOT found'} · "
                                 f"ToS warning {'on' if self.tos_enabled else 'off'}"
                                 f"{' (custom term list loaded)' if self.tos_terms is not None else ''}")

    async def stop(self) -> None:
        self._stopping = True
        self._stop_event.set()                           # an unfinished swap gives up instead of starting another bot
        try:
            await asyncio.wait_for(self._switch_lock.acquire(), 30)     # …and has a moment to wind down
        except asyncio.TimeoutError:
            log.warning("Trollenator: a bot switch was still running at shutdown — stopping anyway.")
        async with self._config_lock:                    # let a token being saved finish writing its file
            pass
        await self._stop_bot()
        if self._http is not None and not self._http.closed:
            await self._http.close()
        CommandNames.prefix = ""
        log.info("Trollenator stopped.")
        self.tlog.record("info", "Trollenator stopped")
        await self.tlog.stop()                           # deliver the last entries before the program exits
