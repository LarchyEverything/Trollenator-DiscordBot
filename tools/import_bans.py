"""
tools/import_bot_bans.py — copy the USER bans out of bot-Bot's database into Trollenator's ban list.

    python3 tools/import_bot_bans.py /path/to/bot-Bot/Data/<its>.db

Stop Trollenator first (it owns Data/trollenator.db). The bot database is opened READ-ONLY and never changed.
Only user bans (target_type 'user') are copied — Trollenator never looked at server bans. Expired bans are skipped, and
users that are already banned here are left alone. Promoted bot staff are NOT copied: put their IDs in "mods" in
Configs/trollenator_config.json instead.
"""

import asyncio
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from appconfig import DATA_DIR, DB_FILE, parse_snowflake      # noqa: E402
from store import Store                                        # noqa: E402


def to_epoch(value) -> int | None:
    """bot stored ISO strings; accept those and plain numbers."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    dt = datetime.fromisoformat(str(value))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


async def run(source: Path) -> None:
    uri = f"file:{source.resolve().as_posix()}?mode=ro"
    src = sqlite3.connect(uri, uri=True)
    src.row_factory = sqlite3.Row
    rows = src.execute("SELECT * FROM bot_bans WHERE target_type = 'user'").fetchall()
    store = Store(DATA_DIR / DB_FILE)
    await store.init()
    now, copied, skipped = time.time(), 0, 0
    try:
        for row in rows:
            uid = parse_snowflake(row["target_id"])
            expires = to_epoch(row["expires_at"])
            banned_by = parse_snowflake(row["banned_by"]) or 1
            if uid is None or (expires is not None and expires <= now):
                skipped += 1
                continue
            ban = await store.add_ban(uid, reason=row["reason"] or "", banned_by=banned_by, expires_at=expires,
                                      notify=bool(row["notify"]))
            copied, skipped = (copied + 1, skipped) if ban else (copied, skipped + 1)
    finally:
        await store.close()
        src.close()
    print(f"Copied {copied} ban(s); skipped {skipped} (expired, invalid or already banned).")


if __name__ == "__main__":
    if len(sys.argv) != 2 or not Path(sys.argv[1]).is_file():
        sys.exit(__doc__)
    asyncio.run(run(Path(sys.argv[1])))
