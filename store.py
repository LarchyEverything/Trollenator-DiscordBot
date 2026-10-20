"""
store.py — the ban list.

Design: every ACTIVE ban is held in memory and written through to SQLite. Checking whether a user is banned
(done before every command and button press, inside Discord's 3-second window) is therefore a dictionary lookup:
no database round-trip, nothing to time out, and no "let them through if the database is slow" fallback.
That is safe because exactly one process owns the database — the control bot and the user app run in the same
process, so there is no second writer to fall out of sync with. (Edit the database by hand only while it is stopped.)

Writes go to the database FIRST and to memory only after they succeeded, so memory never claims more than disk.
Times are Unix seconds (UTC) — no time-zone strings to get wrong. Every query is parameterised.
"""

import asyncio
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import aiosqlite

log = logging.getLogger("trollenator.store")

REASON_MAX = 300
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Ban:
    user_id: int
    reason: str
    banned_by: int
    banned_at: int                  # Unix seconds
    expires_at: Optional[int]       # Unix seconds; None = permanent
    notify: bool

    def active(self, now: Optional[float] = None) -> bool:
        return self.expires_at is None or self.expires_at > (time.time() if now is None else now)


def clean_reason(raw: Optional[str]) -> str:
    """Single-line, trimmed, length-capped, control characters removed — safe to store and to show."""
    text = "".join(ch for ch in (raw or "") if ch.isprintable() or ch.isspace())     # drop control characters (NUL, bells …)
    return " ".join(text.split())[:REASON_MAX]                                     # one line, single spaces


def _row_to_ban(row: tuple) -> Ban:
    user_id, reason, banned_by, banned_at, expires_at, notify = row
    return Ban(int(user_id), str(reason or ""), int(banned_by), int(banned_at),
               None if expires_at is None else int(expires_at), bool(notify))


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._conn: Optional[aiosqlite.Connection] = None
        self._bans: dict[int, Ban] = {}
        self._lock = asyncio.Lock()          # one write at a time: "check, then write" can't interleave

    # ── lifecycle ────────────────────────────────────────────────────────────
    async def init(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existed = self.path.exists()
        self._conn = await aiosqlite.connect(self.path)
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA synchronous=NORMAL")      # safe with WAL; far fewer SD-card syncs
        await self._conn.execute("PRAGMA busy_timeout=5000")
        await self._conn.execute(
            "CREATE TABLE IF NOT EXISTS user_bans ("
            " user_id INTEGER PRIMARY KEY,"
            " reason TEXT NOT NULL DEFAULT '',"
            " banned_by INTEGER NOT NULL,"
            " banned_at INTEGER NOT NULL,"
            " expires_at INTEGER,"
            " notify INTEGER NOT NULL DEFAULT 0)")
        async with self._conn.execute("PRAGMA user_version") as cur:
            version = (await cur.fetchone())[0]
        if version > SCHEMA_VERSION:
            raise RuntimeError(f"{self.path} was made by a newer Trollenator (schema {version}) — refusing to use it.")
        await self._conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        await self._conn.execute("DELETE FROM user_bans WHERE expires_at IS NOT NULL AND expires_at <= ?", (int(time.time()),))
        await self._conn.commit()
        if not existed:
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
        async with self._conn.execute(
                "SELECT user_id, reason, banned_by, banned_at, expires_at, notify FROM user_bans") as cur:
            self._bans = {ban.user_id: ban for ban in map(_row_to_ban, await cur.fetchall())}
        log.info(f"Ban list ready: {len(self._bans)} active ban(s).")

    async def close(self) -> None:
        conn, self._conn = self._conn, None
        if conn is not None:
            try:
                await conn.close()
            except Exception:
                log.exception("Closing the database failed")

    def _db(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("the database is not open")
        return self._conn

    # ── reading (memory only — no I/O, never blocks) ─────────────────────────
    def active_ban(self, user_id: int) -> Optional[Ban]:
        ban = self._bans.get(user_id)
        return ban if ban is not None and ban.active() else None

    def list_bans(self) -> list[Ban]:
        """Active bans, newest first."""
        now = time.time()
        return sorted((b for b in self._bans.values() if b.active(now)), key=lambda b: b.banned_at, reverse=True)

    # ── writing (database first, memory second) ──────────────────────────────
    async def add_ban(self, user_id: int, *, reason: str, banned_by: int, expires_at: Optional[int], notify: bool) -> Optional[Ban]:
        """Ban a user. Returns the new Ban, or None if they were already banned (nothing is changed then)."""
        ban = Ban(user_id, clean_reason(reason), banned_by, int(time.time()), expires_at, bool(notify))
        async with self._lock:
            db = self._db()
            now = int(time.time())
            try:
                await db.execute("DELETE FROM user_bans WHERE expires_at IS NOT NULL AND expires_at <= ?", (now,))
                cur = await db.execute(
                    "INSERT OR IGNORE INTO user_bans (user_id, reason, banned_by, banned_at, expires_at, notify) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (ban.user_id, ban.reason, ban.banned_by, ban.banned_at, ban.expires_at, int(ban.notify)))
                inserted = cur.rowcount == 1
                await db.commit()
            except sqlite3.Error:
                await db.rollback()
                raise
            for uid in [u for u, b in self._bans.items() if not b.active(now)]:
                del self._bans[uid]                      # forget bans that have run out
            if not inserted:
                return None
            self._bans[user_id] = ban
            return ban

    async def remove_ban(self, user_id: int) -> bool:
        """Lift a ban. False if the user had no (active) ban."""
        async with self._lock:
            db = self._db()
            try:
                cur = await db.execute("DELETE FROM user_bans WHERE user_id = ?", (user_id,))
                removed = cur.rowcount > 0
                await db.commit()
            except sqlite3.Error:
                await db.rollback()
                raise
            was_active = self.active_ban(user_id) is not None
            self._bans.pop(user_id, None)
            return removed and was_active

    async def set_reason(self, user_id: int, reason: str) -> Optional[Ban]:
        """Change the reason of an active ban; everything else about it is kept. None if there is no such ban."""
        new_reason = clean_reason(reason)
        async with self._lock:
            ban = self.active_ban(user_id)
            if ban is None:
                return None
            db = self._db()
            try:
                await db.execute("UPDATE user_bans SET reason = ? WHERE user_id = ?", (new_reason, user_id))
                await db.commit()
            except sqlite3.Error:
                await db.rollback()
                raise
            updated = Ban(ban.user_id, new_reason, ban.banned_by, ban.banned_at, ban.expires_at, ban.notify)
            self._bans[user_id] = updated
            return updated

    async def ping_ms(self) -> int:
        """How long a trivial query takes — for the diagnostics."""
        started = time.monotonic()
        async with self._db().execute("SELECT 1") as cur:
            await cur.fetchone()
        return round((time.monotonic() - started) * 1000)
