from argparse import Namespace

from hierarchy import cli
from hierarchy.config import ConfigError


def test_run_forwards_bootstrap_repetitions(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "cmd_fetch", lambda args: calls.append(("fetch", args.allow_missing)))
    monkeypatch.setattr(
        cli, "cmd_aggregate", lambda args: calls.append(("aggregate", args.reps)) or 0
    )

    assert cli.cmd_run(Namespace(reps=321)) == 0
    assert calls == [("fetch", True), ("aggregate", 321)]


def test_validate_reports_config_error_without_traceback(monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_config", lambda: (_ for _ in ()).throw(ConfigError("bad weights")))

    assert cli.cmd_validate(Namespace()) == 1
    captured = capsys.readouterr()
    assert captured.err.strip() == "config ERROR: bad weights"
    assert captured.out == ""


def test_fetch_strict_reports_failure_without_traceback(monkeypatch):
    monkeypatch.setattr(cli, "fetch_all", lambda *a, **k: ([], []))
    monkeypatch.setattr(cli, "fetch_boards", lambda *a, **k: ([], [("arena_text", "unavailable")]))
    assert cli.cmd_fetch(Namespace(allow_missing=False)) == 1
    assert cli.cmd_fetch(Namespace(allow_missing=True)) == 0
