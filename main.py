"""
main.py — Trollenator's entry point:  python3 main.py

Starts, in one process / one event loop:
  • the ban list (store.py)
  • the user app host (trollenator.py) — the user-installed app people actually use
  • the control bot (control.py) — the private server bot for bans, the dev panel, switching bots and adding tokens
Stops cleanly on Ctrl+C or SIGTERM (what systemd sends).
"""

import asyncio
import faulthandler
import logging
import os
import signal
import sys
from logging.handlers import RotatingFileHandler

if sys.version_info < (3, 10):
    sys.exit("Trollenator needs Python 3.10 or newer.")

os.umask(0o077)                       # everything this program creates (database, log, config rewrites) is private to its owner

from appconfig import DATA_DIR, DB_FILE, load_config
from store import Store
import strings as strings_mod

log = logging.getLogger("trollenator.main")

LOCK_FILE = ".trollenator.lock"
EXIT_ALREADY_RUNNING = 3


class QuietDiscordNoise(logging.Filter):
    """
    Drops three discord.py start-up warnings that don't apply here, and nothing else:
      • "PyNaCl / davey is not installed" — they are for talking in voice CHANNELS. Trollenator never joins one;
        a voice MESSAGE is an ordinary file upload (see /voice), so it needs neither.
      • "Guilds intent seems to be disabled" — the user app asks for no gateway intents on purpose.
    """

    _MUTED = {
        "discord.client": ("PyNaCl is not installed", "davey is not installed"),
        "discord.state": ("Guilds intent seems to be disabled",),
    }

    def filter(self, record: logging.LogRecord) -> bool:
        prefixes = self._MUTED.get(record.name)
        return not (prefixes and record.getMessage().startswith(prefixes))


def setup_logging() -> None:
    from trollenator import RedactFilter       # imported late: it needs discord.py, and a clear error beats a traceback
    DATA_DIR.mkdir(exist_ok=True)
    handlers: list[logging.Handler] = [
        RotatingFileHandler(DATA_DIR / "trollenator.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"),
    ]
    # Only print to the terminal when there is one. Under supervisor.sh stdout is a file (Data/stdout.log) that
    # nothing rotates — duplicating the whole log there would slowly fill the phone's storage.
    if sys.stdout is not None and sys.stdout.isatty():
        handlers.append(logging.StreamHandler(sys.stdout))
    fmt = logging.Formatter("[%(asctime)s] [%(levelname)-8s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    for handler in handlers:
        handler.setFormatter(fmt)
        handler.addFilter(RedactFilter())      # on the HANDLERS, so even discord.py's and aiohttp's lines are scrubbed
        handler.addFilter(QuietDiscordNoise())
    logging.basicConfig(level=logging.INFO, handlers=handlers)


def acquire_instance_lock():
    """
    Make sure only ONE Trollenator runs from this folder. Two copies logged in with the same bot token both receive
    every interaction; one answers first and the other gets "Unknown interaction" / "already acknowledged" errors.
    The lock is released by the operating system when the process ends — however it ends — so it can't go stale.
    Returns the open lock file (keep a reference to it for the life of the process), or None where file locks
    aren't available (Windows). A copy on ANOTHER machine can't be detected from here.
    """
    try:
        import fcntl
    except ImportError:
        return None
    DATA_DIR.mkdir(exist_ok=True)
    handle = open(DATA_DIR / LOCK_FILE, "a+")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        log.critical("Another Trollenator is already running from this folder — not starting a second copy. "
                     "(Check with: pgrep -af main.py)")
        sys.exit(EXIT_ALREADY_RUNNING)
    return handle


async def amain() -> int:
    from control import ControlBot, ControlSettings, run_control
    from trollenator import TrollenatorHost, token_key

    cfg = load_config()
    try:
        count = strings_mod.load_strings()
    except (OSError, ValueError) as e:
        log.critical(f"Could not load Configs/strings.json: {type(e).__name__}: {e}")
        return 1
    log.info(f"Loaded {count} strings.")

    settings, problems = ControlSettings.from_config(cfg)
    for problem in problems:
        (log.error if settings is None else log.warning)(problem)

    store = Store(DATA_DIR / DB_FILE)
    try:
        await store.init()
    except Exception as e:
        log.critical(f"Could not open the ban database: {type(e).__name__}: {e}")
        return 1

    host = TrollenatorHost(cfg, store, control_key=token_key(settings.token) if settings else "")
    control = ControlBot(host, settings) if settings else None

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            pass                              # Windows: Ctrl+C then arrives as KeyboardInterrupt (see main())

    control_task = None
    try:
        await host.start()
        if control is not None:
            control_task = asyncio.create_task(run_control(control), name="trollenator-control")
        log.info("Trollenator is running. Press Ctrl+C to stop.")
        await stop.wait()
    finally:
        log.info("Shutting down…")
        if control is not None:
            try:
                await control.close()
            except Exception:
                log.exception("Control bot did not close cleanly")
        if control_task is not None:
            control_task.cancel()
            await asyncio.gather(control_task, return_exceptions=True)
        await host.stop()
        await store.close()
        log.info("Shutdown complete.")
    return 0


def main() -> None:
    faulthandler.enable()                 # a hard crash (segfault, out-of-memory kill of a thread) leaves a trace in stderr
    setup_logging()
    lock = acquire_instance_lock()        # noqa: F841 — must stay referenced until the process exits
    try:
        code = asyncio.run(amain())
    except KeyboardInterrupt:
        code = 0
    sys.exit(code)


if __name__ == "__main__":
    main()
