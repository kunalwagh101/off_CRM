"""Every command-line tool that opens the workspace holds its lease (D-134, D-139).

A restore swaps the whole data directory under an exclusive lease. Web requests
and the email worker take the shared lease, so a restore waits for them and
they wait for it. The command-line tools took nothing: a write made mid-restore
landed in the generation being swapped out and was lost with it.

Each case is one harmless command of one entry point, run through the tool's
real `main`, that opens a store under the data directory.
"""
from __future__ import annotations

import json
import os
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

    with pytest.raises(SystemExit, match="has not finished"):
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


@pytest.fixture(autouse=True)
def _no_dotenv(monkeypatch):
    """`offsetx-outreach` loads `.env` into the process; a developer's own file
    must not decide what these tests see, nor leak into the tests after them."""
    monkeypatch.setattr(outreach_cli, "load_dotenv", lambda *args, **kwargs: False)


def test_a_lock_file_this_process_cannot_write_still_locks(tmp_path, monkeypatch):
    """A tool run as root first left a root-owned 0600 lock file; the app's own
    user then failed to open it and answered 500 to every request."""
    from offsetx_apollo_builder.outreach import workspace_lock

    real_open = os.open

    def owned_by_someone_else(path, flags, *args):
        if str(path).endswith(".lock") and flags & os.O_RDWR:
            raise PermissionError(13, "Permission denied", str(path))
        return real_open(path, flags, *args)

    data = tmp_path / "data"
    WorkspaceLock(data).__enter__().__exit__()  # the file exists, made by "root"
    monkeypatch.setattr(workspace_lock.os, "open", owned_by_someone_else)

    with WorkspaceLock(data), WorkspaceLock(data):
        pass  # shared leases still share
    with WorkspaceLock(data, exclusive=True), pytest.raises(workspace_lock.WorkspaceBusy):
        WorkspaceLock(data).__enter__()


@pytest.mark.parametrize("run", [eval_cli.main, tool_cli.main], ids=["offsetx-evals", "offsetx-tools"])
def test_a_refused_tool_writes_nothing_into_the_workspace(run, tmp_path, monkeypatch):
    """Working out the data directory went through the web app's settings, which
    write an API token into it — before the lease was taken."""
    settings = _settings(tmp_path)
    _point_at(settings, tmp_path, monkeypatch)
    monkeypatch.delenv("OFFSETX_LOCAL_API_TOKEN", raising=False)
    argv = ["champion", "--suite", "x"] if run is eval_cli.main else ["list"]

    with (
        WorkspaceLock(settings.data_dir, exclusive=True),
        pytest.raises(SystemExit, match="backing up or restoring"),
    ):
        run(argv)

    assert not settings.data_dir.exists()


def test_a_restore_left_committed_is_not_called_interrupted(tmp_path, monkeypatch):
    """A cleanup failure leaves a committed journal in a running, healthy app:
    nothing will be rolled back, and the app needs a restart, not a start."""
    from offsetx_apollo_builder.outreach import backup

    settings = _pending_restore(tmp_path)
    journal_path = backup._journal_path(settings.data_dir.resolve())
    journal = json.loads(journal_path.read_text())
    journal["state"] = "committed"
    journal_path.write_text(json.dumps(journal))
    _point_at(settings, tmp_path, monkeypatch)

    with pytest.raises(SystemExit) as refused:
        tool_cli.main(["list"])
    assert "rolled back" not in str(refused.value)
    assert "Restart the web app" in str(refused.value)


def test_a_data_dir_given_as_dot_locks_the_web_apps_lease(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    settings.data_dir.mkdir(parents=True)
    _point_at(settings, tmp_path, monkeypatch)
    monkeypatch.chdir(settings.data_dir)

    with (
        WorkspaceLock(settings.data_dir, exclusive=True),
        pytest.raises(SystemExit, match="backing up or restoring"),
    ):
        tool_cli.main(["--data-dir", ".", "list"])


def test_copy_log_locks_when_it_would_write_into_the_workspace(tmp_path, monkeypatch):
    """`--to` was not looked at: a mistyped path made a SQLite file in the
    workspace while a restore held it."""
    settings = _settings(tmp_path)
    _point_at(settings, tmp_path, monkeypatch)
    source = tmp_path / "elsewhere.db"

    with (
        WorkspaceLock(settings.data_dir, exclusive=True),
        pytest.raises(SystemExit, match="backing up or restoring"),
    ):
        db_cli.main(["copy-log", "--from", str(source), "--to", str(settings.data_dir / "typo.db")])
    assert not (settings.data_dir / "typo.db").exists()


def test_check_locks_the_crm_database_even_outside_the_data_dir(tmp_path, monkeypatch):
    """A backup covers the CRM database wherever it lives, so a restore swaps it."""
    settings = _settings(tmp_path)
    _point_at(settings, tmp_path, monkeypatch)
    outside = tmp_path / "crm" / "outreach.db"
    monkeypatch.setenv("OFFSETX_OUTREACH_DB", str(outside))

    with (
        WorkspaceLock(settings.data_dir, exclusive=True),
        pytest.raises(SystemExit, match="backing up or restoring"),
    ):
        db_cli.main(["check", "--target", str(outside)])


def test_a_lock_file_is_readable_by_the_apps_own_user(tmp_path):
    """The read-only fallback only helps if another user can open the file: it
    holds no data, so a 0600 file made by root stopped the app for nothing."""
    lock = WorkspaceLock(tmp_path / "data")
    lock.__enter__().__exit__()
    assert lock.path.stat().st_mode & 0o044 == 0o044


def test_a_lock_that_cannot_be_opened_says_which_file(tmp_path, monkeypatch):
    from offsetx_apollo_builder.outreach import workspace_lock

    def denied(path, flags, *args):
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr(workspace_lock.os, "open", denied)
    with pytest.raises(PermissionError, match=r"\.data\.workspace\.lock"):
        WorkspaceLock(tmp_path / "data").__enter__()
