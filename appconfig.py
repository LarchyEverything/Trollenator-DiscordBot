"""
appconfig.py — paths, the config file and the small state file.

Everything here is blocking file I/O on tiny files; it is only used at start-up and for the rare state update.
"""

import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

log = logging.getLogger("trollenator.config")

BASE_DIR    = Path(__file__).resolve().parent
CONFIG_DIR  = BASE_DIR / "Configs"
DATA_DIR    = BASE_DIR / "Data"
CONFIG_FILE = "trollenator_config.json"
CONFIG_PATH = CONFIG_DIR / CONFIG_FILE
STATE_FILE  = "trollenator_state.json"
DB_FILE     = "trollenator.db"

MAX_SNOWFLAKE = 2 ** 63 - 1          # Discord IDs fit a signed 64-bit integer (and so does SQLite's INTEGER)


def parse_snowflake(raw: object) -> int | None:
    """An ID written as an int or as ASCII digits ("123…") → int, else None. Bools, floats, '²' and '-5' are refused."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        value = raw
    elif isinstance(raw, str) and raw.isascii() and raw.isdigit() and len(raw) <= 20:
        value = int(raw)
    else:
        return None
    return value if 0 < value <= MAX_SNOWFLAKE else None


def parse_id_list(raw: object, name: str) -> frozenset[int]:
    """A config list of user IDs. Bad entries are reported (never silently dropped) and ignored."""
    if raw is None:
        return frozenset()
    if not isinstance(raw, list):
        log.error(f'"{name}" in {CONFIG_FILE} must be a list of user IDs — ignoring it.')
        return frozenset()
    ids: set[int] = set()
    for item in raw:
        value = parse_snowflake(item)
        if value is None:
            log.error(f'"{name}" in {CONFIG_FILE} contains an entry that is not a valid Discord ID — ignored.')
        else:
            ids.add(value)
    return frozenset(ids)


def load_config() -> dict:
    """Read Configs/trollenator_config.json. Exits with a clear message if it is missing or isn't a JSON object."""
    if not CONFIG_PATH.exists():
        log.critical(f"{CONFIG_PATH} not found. Copy Configs/trollenator_config.example.json to that name and fill it in.")
        sys.exit(1)
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        log.critical(f"Could not read {CONFIG_PATH}: {type(e).__name__}: {e}")
        sys.exit(1)
    if not isinstance(data, dict):
        log.critical(f"{CONFIG_PATH} must contain a JSON object.")
        sys.exit(1)
    return data


def atomic_write(path: Path, text: str) -> None:
    """Write `text` to `path` so a crash can't leave a half-written file; the new file is readable by its owner only."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.stem}.", suffix=".tmp")     # created with mode 0600
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def load_data(name: str) -> dict[str, Any]:
    """Data/<name> as a dict. A missing or damaged file gives {} (the state is only a cache of what was synced)."""
    path = DATA_DIR / name
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as e:
        log.warning(f"Could not read {path} ({type(e).__name__}) — starting from an empty state.")
        return {}
    return data if isinstance(data, dict) else {}


def save_data(name: str, data: dict[str, Any]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    atomic_write(DATA_DIR / name, json.dumps(data, indent=2, sort_keys=True) + "\n")
