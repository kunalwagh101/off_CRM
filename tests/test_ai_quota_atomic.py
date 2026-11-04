"""A11: quota checks must reserve before transport across independent workers."""
from __future__ import annotations

import multiprocessing
import os
import time
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from offsetx_apollo_builder.ai.broker import EgressBroker, WorkspaceEgressSettings
from offsetx_apollo_builder.ai.payload import EgressRequest
from offsetx_apollo_builder.ai.quota import QuotaLimits, QuotaTracker
from offsetx_apollo_builder.ai.registry import ProviderRegistry
from offsetx_apollo_builder.ai.tiers import DataClass
from offsetx_apollo_builder.db.hosted import HostedStorage


class _WireProvider:
    """A fake transport whose shared count proves actual egress, not selection."""

    def __init__(self, counter):
        self.counter = counter
        self.last_usage = {"tokens_in": 1, "tokens_out": 1}

    def generate(self, *, system_prompt, user_prompt):
        with self.counter.get_lock():
            self.counter.value += 1
        time.sleep(0.20)
        return "done"


def _attempt_from_process(path, use_hosted, key, limits_name, start, wire, results, hosted_target=""):
    data_dir = Path(path)
    quota = QuotaTracker(
        data_dir / "quota",
        hosted=HostedStorage(hosted_target or str(data_dir / "hosted.db"), key) if use_hosted else None,
    )
    broker = EgressBroker(
        registry=ProviderRegistry(Path(__file__).resolve().parents[1] / "config" / "providers.yaml"),
        credential_resolver=lambda provider: "test-key-only",
        quota=quota,
        max_retries=0,
    )
    broker._instantiate = lambda candidate: _WireProvider(wire)
    limits = QuotaLimits(**{limits_name: 1})
    settings = WorkspaceEgressSettings(
        workspace_id="test-workspace",
        enabled_provider_ids=("mistral",),
        quota_limits={"mistral": limits},
    )
    start.wait(timeout=20)
    try:
        broker.call(
            EgressRequest(task_type="t", data_class=DataClass.PUBLIC),
            settings,
            system_prompt="answer with done",
        )
        results.put("sent")
    except Exception as exc:
        results.put(type(exc).__name__)


@pytest.mark.parametrize("use_hosted", [False, True], ids=["local-file", "hosted-sqlite"])
@pytest.mark.parametrize("limit_name", ["requests_per_day", "requests_per_minute"])
def test_A11_two_processes_can_send_only_one_provider_request(tmp_path, use_hosted, limit_name):
    """A11: atomic reservation gates the actual provider, even in separate processes."""
    ctx = multiprocessing.get_context("spawn")
    start, wire, results = ctx.Event(), ctx.Value("i", 0), ctx.Queue()
    key = Fernet.generate_key().decode()
    workers = [
        ctx.Process(
            target=_attempt_from_process,
            args=(str(tmp_path), use_hosted, key, limit_name, start, wire, results),
        )
        for _ in range(2)
    ]
    for worker in workers:
        worker.start()
    start.set()
    for worker in workers:
        worker.join(timeout=35)
        if worker.is_alive():
            worker.terminate()
            worker.join()
            pytest.fail("A11 worker stuck: quota reservation must not deadlock.")
        assert worker.exitcode == 0
    outcomes = [results.get(timeout=5) for _ in workers]
    assert wire.value == 1, f"Two workers reached the provider: {outcomes}"
    assert outcomes.count("sent") == 1
    assert any(value in {"NoPermittedProvider", "EgressBlocked"} for value in outcomes)


def test_A11_corrupt_local_quota_must_refuse_a_new_call(tmp_path):
    data_dir = tmp_path / "quota"
    data_dir.mkdir()
    (data_dir / "ai_quota.json").write_text("{destroyed-json", encoding="utf-8")
    tracker = QuotaTracker(data_dir)
    with pytest.raises(Exception, match="quota|counter|ledger|corrupt|repair"):
        tracker.prepare()


def test_A11_hosted_counter_does_not_silently_reset_on_malformed_json(tmp_path):
    hosted = HostedStorage(str(tmp_path / "hosted.db"), Fernet.generate_key().decode())
    hosted.write("ai_quota", "{destroyed-json")
    tracker = QuotaTracker(tmp_path / "quota", hosted=hosted)
    with pytest.raises(Exception, match="quota|counter|ledger|corrupt|repair"):
        tracker.prepare()


def test_A11_reservation_spend_is_idempotent_and_crash_safe(tmp_path):
    tracker = QuotaTracker(tmp_path)
    limits = QuotaLimits(requests_per_day=2, max_spend_usd_per_day=0.001)
    ticket = tracker.reserve("mistral", limits, worst_case_usd=0.0007)
    assert ticket
    other = QuotaTracker(tmp_path)
    allowed, reason = other.try_reserve("mistral", limits, worst_case_usd=0.0007)
    assert not allowed and "spend" in reason
    assert other.reconcile("mistral", ticket, spend_usd=0.0003)
    assert not other.reconcile("mistral", ticket, spend_usd=0.0003)
    restarted = QuotaTracker(tmp_path)
    assert restarted.usage("mistral", limits)["day_used"] == 1
    assert restarted.usage("mistral", limits)["day_spend_usd"] == pytest.approx(0.0003, abs=0.0001)


def test_A11_reserved_attempt_survives_crash_without_replay(tmp_path):
    tracker = QuotaTracker(tmp_path)
    limits = QuotaLimits(requests_per_day=1)
    assert tracker.reserve("mistral", limits)
    restarted = QuotaTracker(tmp_path)
    assert restarted.try_reserve("mistral", limits)[0] is None
    assert restarted.usage("mistral", limits)["day_used"] == 1


def test_A11_two_separate_accounts_keep_independent_spend_and_request_ledgers(tmp_path):
    tracker = QuotaTracker(tmp_path)
    limits = QuotaLimits(requests_per_day=1, max_spend_usd_per_day=0.80)
    ticket_a = tracker.reserve("mistral", limits, worst_case_usd=0.60, scope_id="account-a")
    assert ticket_a
    assert tracker.try_reserve("mistral", limits, scope_id="account-a")[0] is None
    ticket_b = tracker.reserve("mistral", limits, worst_case_usd=0.60, scope_id="account-b")
    assert ticket_b != ticket_a
    assert tracker.usage("mistral", limits, scope_id="account-a")["day_used"] == 1
    assert tracker.usage("mistral", limits, scope_id="account-b")["day_used"] == 1
    assert tracker.reconcile("mistral", ticket_a, spend_usd=0.15, scope_id="account-a")
    assert tracker.usage("mistral", limits, scope_id="account-a")["day_spend_usd"] == pytest.approx(0.15)
    assert tracker.usage("mistral", limits, scope_id="account-b")["day_spend_usd"] == pytest.approx(0.60)


def test_A11_corrupt_ledger_refuses_broker_with_one_safe_reference(tmp_path, capsys):
    import json
    from offsetx_apollo_builder.ai.errors import NoPermittedProvider

    counter = []
    (tmp_path / "ai_quota.json").write_text('{"x":{"day_spend_usd":-7}}', encoding="utf-8")
    broker = EgressBroker(
        registry=ProviderRegistry(Path(__file__).resolve().parents[1] / "config" / "providers.yaml"),
        credential_resolver=lambda _: "super-sensitive-provider-key",
        quota=QuotaTracker(tmp_path),
    )
    broker._instantiate = lambda _: counter.append("sent")
    settings = WorkspaceEgressSettings(
        workspace_id="test-workspace", enabled_provider_ids=("mistral",),
        quota_limits={"mistral": QuotaLimits(requests_per_day=1)},
    )
    with pytest.raises(NoPermittedProvider, match="Reference: E-") as caught:
        broker.call(EgressRequest(task_type="t", data_class=DataClass.PUBLIC),
                    settings, system_prompt="test")
    assert not counter
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()
             if line.startswith('{"event":"failure"')]
    assert len(lines) == 1
    assert lines[0]["error_id"] in str(caught.value)
    assert "super-sensitive-provider-key" not in json.dumps(lines)
    assert "super-sensitive-provider-key" not in str(caught.value)


def test_A11_spend_cap_requires_bounded_priced_model_before_transport(tmp_path):
    from offsetx_apollo_builder.ai.errors import NoPermittedProvider

    called = []
    broker = EgressBroker(
        registry=ProviderRegistry(Path(__file__).resolve().parents[1] / "config" / "providers.yaml"),
        credential_resolver=lambda _: "key",
        quota=QuotaTracker(tmp_path),
    )
    broker._instantiate = lambda _: called.append("sent")
    settings = WorkspaceEgressSettings(
        workspace_id="x", enabled_provider_ids=("mistral",),
        quota_limits={"mistral": QuotaLimits(max_spend_usd_per_day=0.001)},
    )
    with pytest.raises(NoPermittedProvider):
        broker.call(EgressRequest(task_type="t", data_class=DataClass.PUBLIC),
                    settings, system_prompt="test")
    # The model's full context costs more than $0.001, so it cannot fit an
    # enforceable cap unless output is bounded more tightly.
    assert not called


def test_A11_legacy_provider_usage_is_not_ignored_during_account_migration(tmp_path):
    tracker = QuotaTracker(tmp_path)
    tracker.record("mistral", spend_usd=0.20)
    account = QuotaTracker(tmp_path)
    limits = QuotaLimits(requests_per_day=1, max_spend_usd_per_day=0.30)
    assert account.try_reserve("mistral", limits, scope_id="new-account")[0] is None
    assert account.try_reserve("mistral", QuotaLimits(max_spend_usd_per_day=0.25),
                               worst_case_usd=0.10, scope_id="new-account")[0] is None



def test_A11_postgres_two_processes_reserve_one_actual_provider_call(tmp_path):
    """A11: real PostgreSQL advisory transaction, not just SQLite or a Python lock."""
    url = os.getenv("OFF_CRM_TEST_POSTGRES_URL", "").strip()
    if not url:
        pytest.skip("set OFF_CRM_TEST_POSTGRES_URL for disposable PostgreSQL")
    import uuid
    import psycopg

    schema = "a11_" + uuid.uuid4().hex[:12]
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(f'CREATE SCHEMA "{schema}"')
    target = url + ("&" if "?" in url else "?") + f"options=-csearch_path%3D{schema}"
    key = Fernet.generate_key().decode()
    try:
        hosted = HostedStorage(target, key)
        hosted.probe()  # Initialise the schema once, before the race.
        hosted.close()
        ctx = multiprocessing.get_context("spawn")
        start, wire, results = ctx.Event(), ctx.Value("i", 0), ctx.Queue()
        workers = [
            ctx.Process(
                target=_attempt_from_process,
                args=(str(tmp_path), True, key, "requests_per_day", start,
                      wire, results, target),
            ) for _ in range(2)
        ]
        for worker in workers:
            worker.start()
        start.set()
        for worker in workers:
            worker.join(timeout=40)
            if worker.is_alive():
                worker.terminate()
                worker.join()
                pytest.fail("The PostgreSQL quota reservation deadlocked.")
            assert worker.exitcode == 0
        outcomes = [results.get(timeout=5) for _ in workers]
        assert wire.value == 1, f"A11 sent twice on real PostgreSQL: {outcomes}"
        assert outcomes.count("sent") == 1
        assert "NoPermittedProvider" in outcomes
        # The reservation survives both workers closing and an independent reader.
        new_hosted = HostedStorage(target, key)
        assert QuotaTracker(tmp_path / "second", hosted=new_hosted).prepare() is None
        new_hosted.close()
    finally:
        with psycopg.connect(url, autocommit=True) as admin:
            admin.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')


def test_A11_storage_write_failure_refuses_transport_and_logs_once(tmp_path, monkeypatch, capsys):
    import json
    from offsetx_apollo_builder.ai.errors import NoPermittedProvider

    hosted = HostedStorage(str(tmp_path / "hosted.db"), Fernet.generate_key().decode())
    hosted.probe()

    def deny_write(_name, _body):
        raise OSError("SECRET_LEDGER_WRITE_DATA")

    monkeypatch.setattr(hosted, "write", deny_write)
    broker = EgressBroker(
        registry=ProviderRegistry(Path(__file__).resolve().parents[1] / "config" / "providers.yaml"),
        credential_resolver=lambda _: "secret-account",
        quota=QuotaTracker(tmp_path / "quota", hosted=hosted),
    )
    reached_provider = []
    broker._instantiate = lambda _: reached_provider.append("sent")
    settings = WorkspaceEgressSettings(
        workspace_id="test-workspace", enabled_provider_ids=("mistral",),
        quota_limits={"mistral": QuotaLimits(requests_per_day=1)},
    )
    with pytest.raises(NoPermittedProvider, match="Reference: E-") as caught:
        broker.call(EgressRequest(task_type="t", data_class=DataClass.PUBLIC),
                    settings, system_prompt="test")
    assert not reached_provider
    log_lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()
                 if line.startswith('{"event":"failure"')]
    assert len(log_lines) == 1
    assert log_lines[0]["error_id"] in str(caught.value)
    assert "SECRET_LEDGER_WRITE_DATA" not in str(caught.value)
    assert "SECRET_LEDGER_WRITE_DATA" not in json.dumps(log_lines)
    hosted.close()
