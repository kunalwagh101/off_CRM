"""Every command-line tool that opens the workspace holds its lease (D-134, D-139).

A restore swaps the whole data directory under an exclusive lease. Web requests
and the email worker take the shared lease, so a restore waits for them and
they wait for it. The command-line tools took nothing: a write made mid-restore
landed in the generation being swapped out and was lost with it.

Each case is one harmless command of one entry point, run through the tool's
real `main`, that opens a store under the data directory.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from test_agent_artifacts import _trace
from test_audit_wp1 import _settings
from test_workspace_lock import _pending_restore

from offsetx_apollo_builder import artifact_cli, db_cli, notebook_cli, outreach_cli
from offsetx_apollo_builder.agent.artifacts import XLSX_FILENAME
from offsetx_apollo_builder.ai import eval_cli, tool_cli
from offsetx_apollo_builder.outreach.engine import OutreachEngine
from offsetx_apollo_builder.outreach.workspace_lock import WorkspaceLock


def _outreach(settings, monkeypatch):
    return outreach_cli.main, ["create-campaign", "Lease check"], settings.database_path


def _gmail_authorize(settings, monkeypatch):
    def authorize(*, token_path, **_):
        # What the real consent flow leaves behind; the flow itself needs a person.
        Path(token_path).parent.mkdir(parents=True, exist_ok=True)
        Path(token_path).write_text("{}")

    monkeypatch.setattr(outreach_cli, "authorize_interactive", authorize)
    return (
        outreach_cli.main,
        ["gmail-authorize", "--no-browser"],
        settings.data_dir / "gmail_token.json",
    )


def _notebook(settings, monkeypatch):
    engine = OutreachEngine(settings.database_path)
    try:
        campaign_id = engine.create_campaign(name="Lease check")
    finally:
        engine.close()
    return notebook_cli.main, ["plan", "--campaign", str(campaign_id)], settings.database_path


def _evals(settings, monkeypatch):
    return eval_cli.main, ["champion", "--suite", "lease_check"], settings.data_dir / "ai_evals.db"


def _tools(settings, monkeypatch):
    return tool_cli.main, ["list"], settings.data_dir / "ai_tools.db"


def _db(settings, monkeypatch):
    return db_cli.main, ["check"], settings.data_dir / "ai_egress.db"


def _artifacts(settings, monkeypatch):
    # The app keeps agent runs under the data directory; so does this one.
    trace = _trace(settings.data_dir)
    return (
        artifact_cli.main,
        ["--run-dir", str(trace.directory), "--format", "xlsx"],
        trace.directory / XLSX_FILENAME,
    )


COMMANDS = [
    pytest.param(_outreach, id="offsetx-outreach"),
    pytest.param(_gmail_authorize, id="offsetx-outreach-gmail-authorize"),
    pytest.param(_notebook, id="offsetx-notebook"),
    pytest.param(_evals, id="offsetx-evals"),
    pytest.param(_tools, id="offsetx-tools"),
    pytest.param(_db, id="offsetx-db"),
    pytest.param(_artifacts, id="offsetx-artifacts"),
]


def _point_at(settings, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OFFSETX_DATA_DIR", str(settings.data_dir))
    monkeypatch.setenv("OFFSETX_OUTREACH_DB", str(settings.database_path))
    for name in ("OFFSETX_GMAIL_TOKEN", "OFFSETX_DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)


def _state(path: Path):
    """Enough to tell whether a file was created or written."""
    if not path.exists():
        return None
    status = path.stat()
    return status.st_size, status.st_mtime_ns


@pytest.mark.parametrize("command", COMMANDS)
def test_a_tool_refuses_while_a_restore_holds_the_workspace(command, tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _point_at(settings, tmp_path, monkeypatch)
    run, argv, store = command(settings, monkeypatch)
    before = _state(store)

    # A backup takes the same exclusive lease, so the sentence names both.
    with (
        WorkspaceLock(settings.data_dir, exclusive=True),
        pytest.raises(SystemExit, match="backing up or restoring the workspace"),
    ):
        run(argv)

    assert _state(store) == before


@pytest.mark.parametrize("command", COMMANDS)
def test_a_tool_refuses_while_a_restore_waits_to_be_rolled_back(command, tmp_path, monkeypatch):
    """No process holds the workspace, but the journal says a swap never
    committed: whatever a tool wrote now could be rolled back under it."""
    settings = _pending_restore(tmp_path)
    _point_at(settings, tmp_path, monkeypatch)
    run, argv, store = command(settings, monkeypatch)
    before = _state(store)

    with pytest.raises(SystemExit, match="interrupted and has not been rolled back"):
        run(argv)

    assert _state(store) == before


@pytest.mark.parametrize("command", COMMANDS)
def test_a_tool_lets_a_restore_in_once_it_finishes(command, tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _point_at(settings, tmp_path, monkeypatch)
    run, argv, store = command(settings, monkeypatch)

    assert run(argv) == 0
    assert store.exists()  # it opened the file the web app would have
    with WorkspaceLock(settings.data_dir, exclusive=True):
        pass


@pytest.mark.parametrize(
    "run, argv",
    [
        pytest.param(outreach_cli.main, ["campaign-kinds"], id="offsetx-outreach-campaign-kinds"),
        pytest.param(notebook_cli.main, ["targets"], id="offsetx-notebook-targets"),
        pytest.param(eval_cli.main, ["list"], id="offsetx-evals-list"),
    ],
)
def test_a_command_that_opens_nothing_still_runs_during_a_restore(run, argv, tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _point_at(settings, tmp_path, monkeypatch)

    with WorkspaceLock(settings.data_dir, exclusive=True):
        assert run(argv) == 0

    assert not settings.database_path.exists()


def test_offsetx_db_still_checks_postgres_during_a_restore(tmp_path, monkeypatch, capsys):
    """Checking the Postgres target is what an operator does while a restore is
    stuck; nothing a restore swaps is open, so nothing is refused."""
    settings = _settings(tmp_path)
    _point_at(settings, tmp_path, monkeypatch)

    with WorkspaceLock(settings.data_dir, exclusive=True):
        answer = db_cli.main(["check", "--target", "postgresql://probe@127.0.0.1:1/none"])

    assert answer == 2  # unreachable, and said so
    assert "Reachable: no" in capsys.readouterr().err


def test_offsetx_db_still_checks_a_file_outside_the_workspace_during_a_restore(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _point_at(settings, tmp_path, monkeypatch)
    outside = tmp_path / "elsewhere" / "egress.db"
    outside.parent.mkdir()

    with WorkspaceLock(settings.data_dir, exclusive=True):
        assert db_cli.main(["check", "--target", str(outside)]) == 0

    assert outside.exists()


def test_offsetx_artifacts_still_renders_a_run_kept_outside_the_workspace(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _point_at(settings, tmp_path, monkeypatch)
    trace = _trace(tmp_path / "copied")

    with WorkspaceLock(settings.data_dir, exclusive=True):
        assert artifact_cli.main(["--run-dir", str(trace.directory), "--format", "xlsx"]) == 0

    assert (trace.directory / XLSX_FILENAME).exists()
