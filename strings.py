"""
strings.py — every user-facing message lives in Configs/strings.json (a flat {"key": "text"} file).

Keys starting with "_" are comments and are ignored. Templates use str.format placeholders ({name}); the values
that are filled in are never treated as templates, so user text can't inject anything into a message.
"""

import json
import logging
from typing import Callable, Optional

from appconfig import CONFIG_DIR

log = logging.getLogger("trollenator.strings")

STRINGS_PATH = CONFIG_DIR / "strings.json"
_strings: dict[str, str] = {}


def load_strings() -> int:
    """(Re)load strings.json. On a bad file the previous strings stay in use and the error is raised to the caller."""
    global _strings
    data = json.loads(STRINGS_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("strings.json must be a JSON object")
    fresh = {k: v for k, v in data.items() if not k.startswith("_") and isinstance(v, str)}
    _strings = fresh
    return len(fresh)


def known_keys() -> set[str]:
    return set(_strings)


def render(key: str, kwargs: dict, transform: Optional[Callable[[str], str]] = None) -> str:
    """
    The message for `key`. `transform` (if given) is applied to the TEMPLATE before the values are filled in, so it
    can never alter user text that is inserted afterwards. A missing key shows as «key»; a template/values mismatch
    is logged and the unformatted template is shown — neither can crash a command.
    """
    template = _strings.get(key)
    if template is None:
        log.error(f"Missing string: {key}")
        return f"«{key}»"
    if transform is not None:
        template = transform(template)
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError) as e:
        log.error(f"String {key} could not be formatted ({type(e).__name__}: {e})")
        return template
