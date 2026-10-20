import logging
import subprocess
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import discord

import strings as strings_mod
from main import QuietDiscordNoise
from trollenator import ReportMixin

ROOT = Path(__file__).resolve().parent.parent


def rec(name, msg):
    return logging.LogRecord(name, logging.WARNING, __file__, 1, msg, (), None)


def test_quiet_filter_drops_only_the_three_known_warnings():
    f = QuietDiscordNoise()
    assert not f.filter(rec("discord.client", "PyNaCl is not installed, voice will NOT be supported"))
    assert not f.filter(rec("discord.client", "davey is not installed, voice will NOT be supported"))
    assert not f.filter(rec("discord.state", "Guilds intent seems to be disabled. This may cause state related issues."))
    assert f.filter(rec("discord.client", "Shard ID None has connected to Gateway"))
    assert f.filter(rec("discord.gateway", "PyNaCl is not installed"))          # same words, other logger: kept
    assert f.filter(rec("trollenator", "anything else"))


def test_second_copy_refuses_to_start(tmp_path):
    code = textwrap.dedent(f"""
        import sys; sys.path.insert(0, {str(ROOT)!r})
        import appconfig; appconfig.DATA_DIR = __import__("pathlib").Path({str(tmp_path)!r})
        import main; main.DATA_DIR = appconfig.DATA_DIR
        h = main.acquire_instance_lock()
        print("LOCKED" if h else "NOLOCK", flush=True)
        sys.stdin.readline()
    """)
    first = subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    assert first.stdout.readline().strip() == "LOCKED"
    second = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, input="\n")
    assert second.returncode == 3
    first.communicate("\n")
    third = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, input="\n")
    assert third.returncode == 0 and "LOCKED" in third.stdout           # released when the first one exited


def _reporter():
    r = SimpleNamespace(tlog=MagicMock(), latency=0.05)
    r._report_expired = ReportMixin._report_expired.__get__(r)
    return r


def test_expired_report_tells_the_cases_apart():
    strings_mod.load_strings()
    for done, needle in ((True, "already answered"), (False, "same token")):
        r = _reporter()
        i = MagicMock()
        i.extras = {"arrived_ms": 150}
        i.created_at = discord.utils.utcnow()
        i.response.is_done.return_value = done
        r._report_expired(i, "/say", "abc", 10062)
        kw = r.tlog.record.call_args.kwargs
        assert needle in kw["summary"] and kw["fields"]["Answered by this process"] == ("yes" if done else "no")
    r = _reporter()
    i = MagicMock(); i.extras = {}; i.created_at = discord.utils.utcnow(); i.response.is_done.return_value = False
    r._report_expired(i, "/say", "abc", 40060)
    assert "already been acknowledged" in r.tlog.record.call_args.kwargs["summary"]


def test_terms_file_is_read_from_the_configs_folder(tmp_path, monkeypatch):
    import trollenator
    (tmp_path / "terms.txt").write_text("# comment\nbadword\n")
    monkeypatch.setattr(trollenator, "CONFIG_DIR", tmp_path)
    pattern = trollenator.load_terms({"tos_terms_file": "terms.txt"})
    assert pattern is not None and pattern.search("you badword")
