"""S-06.02.38: errors reported through supported application boundaries."""
from __future__ import annotations

import json
import importlib
import asyncio
import subprocess
import sys
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.db import DatabaseError
from offsetx_apollo_builder.observability import FailureReporter, FailureMiddleware, ReportedFailure, failure_boundary, failure_summary, report_failure, traced_command
from offsetx_apollo_builder.outreach.workspace_lock import WorkspaceLock


def settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        project_root=tmp_path, database_path=tmp_path / "data" / "crm.db",
        data_dir=tmp_path / "data", export_dir=tmp_path / "data" / "exports",
        frontend_dist=tmp_path / "frontend", allow_unauthenticated=True,
    )


def records(output: str) -> list[dict]:
    return [json.loads(line) for line in output.splitlines() if line.startswith("{")]


def test_customer_labels_cannot_turn_a_successful_cycle_into_a_failure():
    reference = "E-0123456789ABCDEF01234567"
    assert failure_summary([{"campaign_name": reference, "campaign_id": reference, "sent_count": 1}]) == ""
    assert reference in failure_summary([{"failed": [{"draft_id": "d1", "error": "Reference: " + reference}]}])


@pytest.mark.parametrize("kind,status", [("unexpected", 500), ("database", 503), ("explicit", 503)])
def test_api_failure_matches_one_secret_safe_record(tmp_path, capsys, kind, status):
    app = create_app(settings(tmp_path))

    @app.get("/api/v1/fault/{item}")
    def fault(item: str):
        secret = "CUSTOMER-CONTENT-and-cookie-secret"
        if kind == "database":
            raise DatabaseError(secret)
        if kind == "explicit":
            raise HTTPException(503, secret)
        raise RuntimeError(secret)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/fault/private-customer?token=hidden-query")
    assert response.status_code == status
    assert response.headers.get("x-error-id", "").startswith("E-")
    payload = response.json()
    assert payload["error_id"] in payload["detail"]
    failures = [row for row in records(capsys.readouterr().out) if row.get("event") == "failure"]
    assert len(failures) == 1
    assert failures[0]["error_id"] == payload["error_id"]
    assert failures[0]["route"] == "/api/v1/fault/{item}"
    encoded = json.dumps(failures) + response.text
    for forbidden in ("CUSTOMER-CONTENT", "cookie-secret", "private-customer", "hidden-query"):
        assert forbidden not in encoded


def test_success_and_client_refusals_never_log_bodies_or_raw_urls(tmp_path, capsys):
    app = create_app(settings(tmp_path))
    with TestClient(app) as client:
        assert client.get("/health/live?password=secret-query").status_code == 200
        assert client.get("/api/v1/no-such-private-customer").status_code == 404
    lines = records(capsys.readouterr().out)
    assert [row["event"] for row in lines] == ["access", "access"]
    assert lines[1]["route"] == "unmatched"
    assert "secret-query" not in json.dumps(lines)
    assert "private-customer" not in json.dumps(lines)


def test_session_lookup_failure_records_the_route_before_dispatch(tmp_path, monkeypatch, capsys):
    module = importlib.import_module("offsetx_apollo_builder.api.app")
    def unavailable(*_):
        raise DatabaseError("private database detail")
    monkeypatch.setattr(module.WorkspaceAuthStore, "verify", unavailable)
    with TestClient(create_app(settings(tmp_path))) as client:
        response = client.get("/api/v1/campaigns?token=secret-query")
    assert response.status_code == 503
    assert "cannot reach its database" in response.json()["detail"]
    failures = [row for row in records(capsys.readouterr().out) if row["event"] == "failure"]
    assert len(failures) == 1 and failures[0]["route"] == "/api/v1/campaigns"
    assert failures[0]["error_id"] == response.json()["error_id"]


def test_an_exception_reused_in_two_requests_gets_two_references(tmp_path, capsys):
    app = create_app(settings(tmp_path))
    error = RuntimeError("private content")

    @app.get("/api/v1/reused-failure")
    def fault():
        raise error

    with TestClient(app, raise_server_exceptions=False) as client:
        first = client.get("/api/v1/reused-failure").json()["error_id"]
        second = client.get("/api/v1/reused-failure").json()["error_id"]
    failures = [row for row in records(capsys.readouterr().out) if row["event"] == "failure"]
    assert {row["error_id"] for row in failures} == {first, second}
    assert first != second


def test_nested_reporting_emits_once_but_a_new_cycle_emits_again(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OFFSETX_DATA_DIR", str(tmp_path))
    error = RuntimeError("private")

    @failure_boundary
    def cycle():
        first = report_failure(error, operation="worker.inner")
        second = report_failure(error, operation="worker.outer")
        assert first == second
        return first

    first, second = cycle(), cycle()
    assert first != second
    assert len(records(capsys.readouterr().out)) == 2


def test_chained_errors_never_include_secrets_customer_text_or_source(tmp_path, capsys):
    reporter = FailureReporter(tmp_path)
    try:
        try:
            raise ValueError("email-body with Bearer private-token and cookie private-cookie")
        except ValueError as exc:
            raise RuntimeError("postgresql://owner:private-password@host/db?password=other-secret") from exc
    except RuntimeError as exc:
        reference = reporter.failure(exc, operation="worker.cycle", workspace="123-workspace")
    row = records(capsys.readouterr().out)[0]
    assert row["error_id"] == reference and row["workspace"] == "123-workspace"
    assert {frame.get("exception") for frame in row["traceback"]} >= {"RuntimeError", "ValueError"}
    assert "private-" not in json.dumps(row) and "email-body" not in json.dumps(row)
    assert "other-secret" not in (tmp_path / "logs/failures.jsonl").read_text()


def test_local_logs_survive_restart_and_rotate_within_the_cap(tmp_path, capsys):
    reporter = FailureReporter(tmp_path, max_bytes=1024, backup_count=2)
    for _ in range(20):
        reporter.failure(None, operation="rotation.test")
    restarted = FailureReporter(tmp_path, max_bytes=1024, backup_count=2)
    reference = restarted.failure(None, operation="rotation.after_restart")
    paths = sorted((tmp_path / "logs").glob("failures.jsonl*"))
    assert 1 < len(paths) <= 3
    assert all(path.stat().st_size <= 1024 for path in paths)
    rows = [row for path in paths for row in records(path.read_text())]
    assert reference in {row["error_id"] for row in rows}
    assert len(records(capsys.readouterr().out)) == 21


def test_threaded_failures_have_unique_intact_records(tmp_path, capsys):
    reporter = FailureReporter(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        references = list(pool.map(lambda _: reporter.failure(None, operation="parallel.test"), range(50)))
    stdout_rows = records(capsys.readouterr().out)
    file_rows = records((tmp_path / "logs/failures.jsonl").read_text())
    assert len(set(references)) == len(stdout_rows) == len(file_rows) == 50
    assert {row["error_id"] for row in file_rows} == set(references)


def test_processes_share_bounded_rotation_without_corrupting_records(tmp_path):
    program = (
        "from offsetx_apollo_builder.observability import FailureReporter\n"
        "import sys\n"
        "reporter = FailureReporter(sys.argv[1], hosted=False, max_bytes=1024, backup_count=3)\n"
        "for _ in range(30): reporter.failure(None, operation='process.test')\n"
    )
    processes = [subprocess.Popen([sys.executable, "-c", program, str(tmp_path)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                 for _ in range(4)]
    output = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=30)
        assert process.returncode == 0, stderr
        output.extend(records(stdout))
    references = {row["error_id"] for row in output}
    assert len(references) == len(output) == 120
    paths = list((tmp_path / "logs").glob("failures.jsonl*"))
    assert 1 <= len(paths) <= 4
    retained = []
    for path in paths:
        assert path.stat().st_size <= 1024
        retained.extend(records(path.read_text()))
    assert retained and {row["error_id"] for row in retained} <= references
    assert len(retained) == len({row["error_id"] for row in retained})


def test_broken_stdout_does_not_mask_failure_or_prevent_local_retention(tmp_path, monkeypatch):
    class BrokenOutput:
        def write(self, _):
            raise OSError("broken stream")
        def flush(self):
            raise OSError("broken stream")
    monkeypatch.setattr(sys, "stdout", BrokenOutput())
    reference = FailureReporter(tmp_path, hosted=False).failure(RuntimeError("private"), operation="sink.test")
    assert records((tmp_path / "logs/failures.jsonl").read_text())[0]["error_id"] == reference


def test_cancelling_a_job_preserves_cancellation_and_does_not_report_success(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OFFSETX_DATA_DIR", str(tmp_path))
    @failure_boundary
    async def job(ready):
        ready.set()
        await asyncio.Event().wait()
    async def scenario():
        ready = asyncio.Event()
        task = asyncio.create_task(job(ready))
        await ready.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert task.cancelled()
    asyncio.run(scenario())
    assert records(capsys.readouterr().out) == []


def test_hosted_mode_keeps_only_stdout(tmp_path, capsys):
    reference = FailureReporter(tmp_path, hosted=True).failure(None, operation="render.test")
    assert records(capsys.readouterr().out)[0]["error_id"] == reference
    assert not tmp_path.exists() or not list(tmp_path.iterdir())


@pytest.mark.parametrize("password", ["E", "%22"])
def test_a_short_database_password_cannot_corrupt_structured_references(tmp_path, monkeypatch, capsys, password):
    monkeypatch.setenv("OFFSETX_DATABASE_URL", f"postgresql://synthetic:{password}@localhost/synthetic")
    reference = FailureReporter(tmp_path, hosted=True).failure(RuntimeError("private"), operation="test.failure")
    record = records(capsys.readouterr().out)[0]
    assert record["error_id"] == reference
    assert record["exception"] == "RuntimeError"


def test_unwritable_log_root_still_reports_to_stdout(tmp_path, capsys):
    root = tmp_path / "not-a-directory"
    root.write_text("unchanged")
    reference = FailureReporter(root).failure(None, operation="disk.failed")
    assert records(capsys.readouterr().out)[0]["error_id"] == reference
    assert root.read_text() == "unchanged"


def test_reporting_during_restore_does_not_create_the_data_directory(tmp_path, capsys):
    root = tmp_path / "data"
    with WorkspaceLock(root, exclusive=True):
        reference = FailureReporter(root).failure(None, operation="restore.refusal")
        assert not root.exists()
    assert records(capsys.readouterr().out)[0]["error_id"] == reference


@pytest.mark.parametrize("module", [
    "cli", "outreach_cli", "db_cli", "artifact_cli", "notebook_cli",
    "codegraph_cli", "web_cli", "email_worker_cli", "ai.eval_cli", "ai.tool_cli",
])
def test_installed_command_failure_exposes_the_matching_reference(module, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OFFSETX_DATA_DIR", str(tmp_path / "data"))
    main = importlib.import_module("offsetx_apollo_builder." + module).main
    with pytest.raises(SystemExit) as raised:
        main(["--not-a-real-option"])
    assert raised.value.code == 2
    output = capsys.readouterr()
    failures = [row for row in records(output.out) if row["event"] == "failure"]
    assert len(failures) == 1
    assert failures[0]["error_id"] in output.err
    assert failures[0]["traceback"]


def test_failed_email_cycle_keeps_a_safe_reference_in_status(tmp_path, capsys):
    from offsetx_apollo_builder.outreach.automation import AutomationService

    def broken_engine():
        raise RuntimeError("customer body and private-token")

    service = AutomationService(
        tmp_path / "automation.json", engine_factory=broken_engine,
        mail_provider_factory=lambda *_: None, own_email_factory=lambda: "",
    )
    with pytest.raises(RuntimeError):
        service.run_once()
    failures = [row for row in records(capsys.readouterr().out) if row["event"] == "failure"]
    assert len(failures) == 1
    assert failures[0]["error_id"] in service.last_error
    assert "private-token" not in service.last_error


def test_lifespan_protocol_never_forwards_a_raw_traceback(tmp_path, capsys):
    from starlette.applications import Starlette

    @asynccontextmanager
    async def lifespan(_):
        raise RuntimeError("private-lifespan-secret and customer prompt")
        yield

    events = []
    async def receive():
        return {"type": "lifespan.startup"}
    async def send(event):
        events.append(event)
    middleware = FailureMiddleware(Starlette(lifespan=lifespan), reporter=FailureReporter(tmp_path, hosted=True))
    with pytest.raises(ReportedFailure):
        asyncio.run(middleware({"type": "lifespan", "state": {}}, receive, send))
    assert events[0]["type"] == "lifespan.startup.failed"
    assert "private-lifespan-secret" not in json.dumps(events)
    assert "customer prompt" not in json.dumps(events)
    assert records(capsys.readouterr().out)[0]["error_id"] in events[0]["message"]


@pytest.mark.parametrize("kind", ["email", "content"])
def test_failed_timer_preserves_its_reference_through_lifespan_shutdown(tmp_path, capsys, kind):
    from starlette.applications import Starlette
    from offsetx_apollo_builder.outreach.automation import AutomationService
    from offsetx_apollo_builder.distribution.automation import ContentAutomationService
    if kind == "email":
        service = AutomationService(tmp_path / "automation.json", engine_factory=lambda: None,
                                    mail_provider_factory=lambda *_: None, own_email_factory=lambda: "")
    else:
        service = ContentAutomationService(tmp_path / "content.json", trends_factory=lambda: None,
                                           pipeline_factory=lambda *_: None, distribution_factory=lambda: None)
    def failed_config():
        raise RuntimeError("private-timer-secret")
    service.config = failed_config
    @asynccontextmanager
    async def lifespan(_):
        await service.start()
        await asyncio.sleep(0)
        yield
        await service.stop()
    pending = iter([{"type": "lifespan.startup"}, {"type": "lifespan.shutdown"}])
    events = []
    async def receive():
        return next(pending)
    async def send(event):
        events.append(event)
    middleware = FailureMiddleware(Starlette(lifespan=lifespan), reporter=FailureReporter(tmp_path, hosted=True))
    with pytest.raises(ReportedFailure):
        asyncio.run(middleware({"type": "lifespan", "state": {}}, receive, send))
    failures = records(capsys.readouterr().out)
    assert len(failures) == 1
    assert failures[0]["error_id"] in service.last_error
    assert failures[0]["error_id"] in events[-1]["message"]
    assert "private-timer-secret" not in json.dumps(events)


def test_command_cycles_reset_deduplication_and_release_exception_context(tmp_path, monkeypatch, capsys):
    from offsetx_apollo_builder.observability import _BOUNDARY
    monkeypatch.setenv("OFFSETX_DATA_DIR", str(tmp_path))
    error = RuntimeError("private")
    references = []

    @failure_boundary
    def cycle():
        references.append(report_failure(error, operation="worker.cycle"))

    @traced_command("worker.watch")
    def watch():
        for _ in range(100):
            cycle()
        assert not (_BOUNDARY.get() or {}).get("exceptions")
        return 0

    assert watch() == 0
    assert len(set(references)) == len(records(capsys.readouterr().out)) == 100


def test_nested_job_failure_already_has_request_metadata(tmp_path, capsys):
    app = create_app(settings(tmp_path))
    @failure_boundary
    def job():
        raise RuntimeError("private")
    @app.get("/api/v1/nested-job/{item}")
    def fault(item: str):
        job()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/nested-job/private-customer")
    assert response.status_code == 500
    failures = [row for row in records(capsys.readouterr().out) if row["event"] == "failure"]
    assert len(failures) == 1
    assert failures[0]["error_id"] == response.json()["error_id"]
    assert failures[0]["route"] == "/api/v1/nested-job/{item}"
    assert failures[0]["workspace"] == "local"


def test_routine_scheduler_reference_is_readable_during_a_history_outage(tmp_path, monkeypatch, capsys):
    app = create_app(settings(tmp_path))
    with TestClient(app) as client:
        service = app.state.agent_routines
        async def failed_poll():
            service._stop.set()
            raise DatabaseError("private-routine-store-detail")
        monkeypatch.setattr(service, "run_due_once", failed_poll)
        client.portal.call(service._loop)
        def failed_history(**kwargs):
            raise DatabaseError("private-routine-store-detail")
        monkeypatch.setattr(app.state.agent_routine_store, "runs", failed_history)
        assert client.get("/api/v1/agent-routine-runs").status_code == 503
        status = client.get("/api/v1/agent-routine-status")
        assert status.status_code == 200
        failures = [row for row in records(capsys.readouterr().out) if row["event"] == "failure"
                    and row["operation"] == "routine.scheduler"]
        assert len(failures) == 1
        assert failures[0]["error_id"] in status.json()["last_error"]


def test_an_escaping_routine_failure_is_recorded_once_for_its_workspace(capsys):
    from types import SimpleNamespace
    from offsetx_apollo_builder.agent.routines import RoutineService
    routine = SimpleNamespace(next_due_at=10, interval_seconds=1, id="r1", workspace_id="synthetic-workspace")
    class Store:
        def claim_due(self, **kwargs):
            return [routine]
        def begin_run(self, *args, **kwargs):
            service._stop.set()
            raise RuntimeError("private-routine-content")
    service = RoutineService(Store(), runner=lambda *_: None)
    asyncio.run(service._loop())
    failures = records(capsys.readouterr().out)
    assert len(failures) == 1
    assert failures[0]["error_id"] in service.last_error
    assert failures[0]["workspace"] == routine.workspace_id


def test_hidden_crm_refusal_has_one_reference(tmp_path, monkeypatch, capsys):
    from offsetx_apollo_builder import outreach_cli
    from offsetx_apollo_builder.outreach import store_copy
    from offsetx_apollo_builder.db.hosted import HostedStorageError
    monkeypatch.setenv("OFFSETX_DATA_DIR", str(tmp_path))
    def refusal(*_):
        raise HostedStorageError("Run offsetx-db import-crm --yes or --skip")
    monkeypatch.setattr(store_copy, "refuse_a_hidden_local_crm", refusal)
    @traced_command("crm.hidden")
    def main():
        outreach_cli._refuse_a_hidden_local_crm("unused")
    with pytest.raises(SystemExit):
        main()
    output = capsys.readouterr()
    failures = [row for row in records(output.out) if row["event"] == "failure"]
    assert len(failures) == 1 and failures[0]["error_id"] in output.err


def test_recovered_failure_with_a_client_status_still_exposes_its_reference(tmp_path, capsys):
    app = create_app(settings(tmp_path))
    @app.post("/api/v1/recovered-failure")
    def recovered():
        try:
            raise RuntimeError("private")
        except RuntimeError as exc:
            report_failure(exc, operation="workspace.restore")
            raise HTTPException(422, "Restore was rejected; the previous workspace is available.") from exc
    with TestClient(app) as client:
        response = client.post("/api/v1/recovered-failure")
    assert response.status_code == 422
    failures = [row for row in records(capsys.readouterr().out) if row["event"] == "failure"]
    assert failures[0]["error_id"] == response.json()["error_id"]
    assert response.json()["error_id"] in response.json()["detail"]


def test_caught_artifact_command_error_never_prints_customer_text(tmp_path, monkeypatch, capsys):
    from offsetx_apollo_builder import artifact_cli
    monkeypatch.setenv("OFFSETX_DATA_DIR", str(tmp_path / "data"))
    def broken(*_):
        raise artifact_cli.ArtifactError("private-customer-content and secret-key")
    monkeypatch.setattr(artifact_cli, "_trace", broken)
    assert artifact_cli.main(["--run-dir", str(tmp_path / "run")]) == 2
    output = capsys.readouterr()
    assert "private-customer-content" not in output.out + output.err
    assert "secret-key" not in output.out + output.err
    failures = [row for row in records(output.out) if row["event"] == "failure"]
    assert len(failures) == 1 and failures[0]["error_id"] in output.err


def test_automation_preserves_individual_send_failure_references(tmp_path, monkeypatch, capsys):
    from offsetx_apollo_builder.outreach.automation import AutomationService
    from offsetx_apollo_builder.outreach.engine import OutreachEngine
    from offsetx_apollo_builder.outreach.gmail import LocalOutboxProvider
    from offsetx_apollo_builder.outreach import engine as engine_module
    monkeypatch.setenv("OFFSETX_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(engine_module, "campaign_send_window", lambda *_: {"allowed": True})
    contacts = tmp_path / "contacts.csv"
    contacts.write_text("Full Name,Email,Company,Title,Category,Public Hook,Hook Source,Tension\n"
                        "Anita Rao,anita@example.com,Example,Lead,CBAM,Published brief,https://example.com,Supplier handoff\n")
    engine = OutreachEngine(tmp_path / "crm.db")
    campaign = engine.create_campaign(name="Logging")
    engine.import_contacts(campaign, contacts)
    engine.generate_drafts(campaign, stages=["initial"])
    assert engine.approve_drafts(campaign, stages=["initial"])["approved"] == 1
    class BrokenMail(LocalOutboxProvider):
        def send_message(self, **kwargs):
            raise RuntimeError("private-mail-body and secret-mail-token")
    service = AutomationService(
        tmp_path / "automation.json", engine_factory=lambda: engine,
        mail_provider_factory=lambda *_: BrokenMail(tmp_path / "mail"),
        own_email_factory=lambda: "owner@example.com",
    )
    result = service.run_once()[0]
    assert result["failed_count"] == 1 and result["sent_count"] == 0
    failures = [row for row in records(capsys.readouterr().out) if row["event"] == "failure"]
    assert len(failures) == 1
    assert failures[0]["error_id"] in json.dumps(result)
    assert failures[0]["error_id"] in service.status()["last_error"]
    assert "private-mail-body" not in json.dumps(result)
    assert "secret-mail-token" not in json.dumps(result)
