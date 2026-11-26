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


def _fake_to_matrix(received):
    """Stub that computes `skipped` exactly like hierarchy.data.to_matrix does."""
    def to_matrix(snaps, cfg):
        received["snaps"] = snaps
        skipped = set(snaps) - set(cfg.bench_ids())
        return {}, {}, {}, skipped, {}, {}
    return to_matrix


def test_aggregate_drops_context_sources_without_unknown_benchmark_noise(monkeypatch, capsys):
    """Usage is context-only (§4): it must not reach the composite nor emit noise."""
    received = {}
    monkeypatch.setattr(cli, "cmd_boards", lambda args: 0)
    monkeypatch.setattr(cli, "load_snapshots", lambda *a, **k: {
        "openrouter_usage": {"benchmark": "openrouter_usage", "as_of": "2026-01-01", "values": {}}})
    monkeypatch.setattr(cli, "load_manual_csv", lambda *a, **k: {})
    monkeypatch.setattr(cli, "merge_snapshots", lambda *dicts: {k: v for d in dicts for k, v in d.items()})
    monkeypatch.setattr(cli, "to_matrix", _fake_to_matrix(received))
    monkeypatch.setattr(cli, "_run_matrix", lambda *a, **k: 0)

    assert cli.cmd_aggregate(Namespace(reps=None)) == 0
    assert "openrouter_usage" not in received["snaps"]
    assert "skipping unregistered benchmarks" not in capsys.readouterr().out


def test_aggregate_still_warns_about_genuinely_unknown_benchmarks(monkeypatch, capsys):
    received = {}
    monkeypatch.setattr(cli, "cmd_boards", lambda args: 0)
    monkeypatch.setattr(cli, "load_snapshots", lambda *a, **k: {})
    monkeypatch.setattr(cli, "load_manual_csv", lambda *a, **k: {
        "totally_unknown_bench": {"benchmark": "totally_unknown_bench", "as_of": "2026-01-01", "values": {}}})
    monkeypatch.setattr(cli, "merge_snapshots", lambda *dicts: {k: v for d in dicts for k, v in d.items()})
    monkeypatch.setattr(cli, "to_matrix", _fake_to_matrix(received))
    monkeypatch.setattr(cli, "_run_matrix", lambda *a, **k: 0)

    assert cli.cmd_aggregate(Namespace(reps=None)) == 0
    assert "totally_unknown_bench" in capsys.readouterr().out


def test_validate_reports_board_config_error_without_traceback(monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_board_config",
                        lambda: (_ for _ in ()).throw(ValueError("default_board must be registered")))
    assert cli.cmd_validate(Namespace()) == 1
    assert "board config ERROR: default_board must be registered" in capsys.readouterr().err


def test_validate_fails_when_the_methodology_version_drifts(monkeypatch, capsys):
    monkeypatch.setattr(cli, "methodology_version", lambda: "9.9.9")
    assert cli.cmd_validate(Namespace()) == 1
    assert "METHODOLOGY.md states v9.9.9" in capsys.readouterr().err
