"""The response cache.

Two things are being protected, and the second matters more than the first.

**Correctness of the saving.** A hit must be an answer to the question actually
asked, not to one that looked similar.

**The policy boundary.** A response can travel back out as ``prior_drafts`` on a
later call, so a cache that blurred policy boundaries would be a slow path for
material derived from a tier A payload to reach a tier C provider. The key
includes the constructed payload, which encodes the policy, so that crossing is
structurally impossible rather than merely avoided — and these tests prove it
rather than trusting it.
"""
from __future__ import annotations

import ast
import time
from pathlib import Path

import pytest

from offsetx_apollo_builder.ai import DataClass, DataPolicy
from offsetx_apollo_builder.ai.cache import (
    DEFAULT_SIMILARITY,
    NEVER_CACHE,
    ResponseCache,
    cache_key,
    canonical_payload,
    partition_key,
    similarity,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "offsetx_apollo_builder"

PAYLOAD = {
    "schema_version": 1,
    "task": "draft_email",
    "instructions": "Write a warm first email about customs software.",
}


@pytest.fixture()
def cache(tmp_path) -> ResponseCache:
    return ResponseCache(tmp_path / "cache.sqlite3")


def _put(cache: ResponseCache, **overrides) -> bool:
    kwargs = {
        "payload": PAYLOAD,
        "response": "Subject: Hi\n\nA draft.",
        "data_class": DataClass.PUBLIC,
        "policy": DataPolicy.STANDARD,
        "task_type": "draft_email",
        "provider_id": "mistral",
    }
    kwargs.update(overrides)
    return cache.put(**kwargs)


def _get(cache: ResponseCache, **overrides):
    kwargs = {
        "payload": PAYLOAD,
        "data_class": DataClass.PUBLIC,
        "policy": DataPolicy.STANDARD,
        "task_type": "draft_email",
        "provider_id": "mistral",
    }
    kwargs.update(overrides)
    return cache.get(**kwargs)


# ── the policy boundary ────────────────────────────────────────────────────


def test_a_response_from_one_policy_is_never_served_for_another(cache):
    """The property the whole key design exists for."""
    _put(cache, policy=DataPolicy.FULL, response="written with everything")
    assert _get(cache, policy=DataPolicy.PSEUDONYMOUS) is None
    assert _get(cache, policy=DataPolicy.MINIMAL) is None
    assert _get(cache, policy=DataPolicy.STANDARD) is None
    assert _get(cache, policy=DataPolicy.FULL) is not None


def test_a_response_from_one_data_class_is_never_served_for_another(cache):
    _put(cache, data_class=DataClass.CAMPAIGN)
    assert _get(cache, data_class=DataClass.PUBLIC) is None
    assert _get(cache, data_class=DataClass.PERSON_PUBLIC) is None


def test_one_workspace_never_sees_another_ones_answers(cache):
    _put(cache, workspace_id="alice", response="alice's draft")
    assert _get(cache, workspace_id="bob") is None
    assert _get(cache, workspace_id="alice") is not None


def test_a_response_from_one_provider_is_not_attributed_to_another(cache):
    """"What did DeepSeek say" must stay answerable."""
    _put(cache, provider_id="deepseek", response="deepseek's draft")
    assert _get(cache, provider_id="mistral") is None


def test_near_matching_cannot_cross_a_policy_boundary_either(cache):
    """Fuzzy comparison is confined to one partition, so however similar two
    texts look they cannot meet across policies."""
    _put(cache, policy=DataPolicy.FULL, response="rich answer")
    almost = dict(PAYLOAD, instructions=PAYLOAD["instructions"] + " ")
    assert cache.get(
        payload=almost,
        data_class=DataClass.PUBLIC,
        policy=DataPolicy.PSEUDONYMOUS,
        task_type="draft_email",
        provider_id="mistral",
    ) is None


def test_mailbox_class_is_never_cached_in_either_direction(cache):
    assert DataClass.MAILBOX in NEVER_CACHE
    assert _put(cache, data_class=DataClass.MAILBOX) is False
    assert _get(cache, data_class=DataClass.MAILBOX) is None


# ── exact hits ─────────────────────────────────────────────────────────────


def test_the_same_payload_hits(cache):
    _put(cache)
    hit = _get(cache)
    assert hit is not None
    assert hit.kind == "exact"
    assert hit.response == "Subject: Hi\n\nA draft."
    assert hit.provider_id == "mistral"


def test_a_different_payload_misses(cache):
    _put(cache)
    other = dict(PAYLOAD, instructions="Something else entirely, about invoices.")
    assert _get(cache, payload=other) is None


def test_key_ordering_does_not_affect_the_hit(cache):
    """Two payloads differing only in dict order must hash the same, or the hit
    rate would depend on iteration order."""
    _put(cache)
    reordered = {k: PAYLOAD[k] for k in reversed(list(PAYLOAD))}
    assert _get(cache, payload=reordered) is not None
    assert canonical_payload(PAYLOAD) == canonical_payload(reordered)


def test_storing_the_same_key_twice_replaces_rather_than_duplicates(cache):
    _put(cache, response="first")
    _put(cache, response="second")
    assert _get(cache).response == "second"
    assert cache.stats()["entries"] == 1


# ── near matches, and their limits ─────────────────────────────────────────


def test_whitespace_and_case_differences_still_hit(cache):
    _put(cache)
    noisy = dict(PAYLOAD, instructions="write a WARM first email about customs software.")
    hit = _get(cache, payload=noisy)
    assert hit is not None
    assert hit.kind == "near"
    assert hit.similarity >= DEFAULT_SIMILARITY


def test_a_genuinely_different_question_does_not_near_hit(cache):
    """The failure that would make a cache worse than useless: answering the
    wrong question because it shared vocabulary."""
    _put(cache)
    different = dict(
        PAYLOAD,
        instructions="Write an angry final notice about an overdue customs invoice.",
    )
    assert _get(cache, payload=different) is None


def test_near_matching_can_be_switched_off(tmp_path):
    strict = ResponseCache(tmp_path / "c.db", near_match=False)
    _put(strict)
    noisy = dict(PAYLOAD, instructions=PAYLOAD["instructions"].upper())
    assert _get(strict, payload=noisy) is None
    assert _get(strict) is not None


def test_the_default_threshold_is_high_enough_to_be_conservative():
    """Serving a stale answer to a different request is a worse failure than
    missing a hit, so the threshold errs towards missing."""
    assert DEFAULT_SIMILARITY >= 0.9


def test_similarity_is_symmetric_and_bounded():
    a, b = ["x y z", "y z w"], ["y z w", "z w v"]
    assert similarity(a, b) == similarity(b, a)
    assert 0.0 <= similarity(a, b) <= 1.0
    assert similarity(a, a) == 1.0
    assert similarity([], []) == 1.0
    assert similarity(a, []) == 0.0


def test_word_triples_rather_than_single_words(cache):
    """Single-word overlap would call two different questions about the same
    subject similar. Triples require the phrasing to line up."""
    _put(cache, payload={"instructions": "customs software for exporters in europe"})
    shuffled = {"instructions": "europe exporters for software customs in"}
    assert _get(cache, payload=shuffled) is None


# ── freshness and size ─────────────────────────────────────────────────────


def test_an_expired_entry_is_not_served(tmp_path):
    quick = ResponseCache(tmp_path / "c.db", ttl_seconds=1)
    _put(quick)
    assert _get(quick) is not None
    time.sleep(1.1)
    assert _get(quick) is None


def test_expired_entries_can_be_purged(tmp_path):
    quick = ResponseCache(tmp_path / "c.db", ttl_seconds=1)
    _put(quick)
    time.sleep(1.1)
    assert quick.purge_expired() == 1
    assert quick.stats()["entries"] == 0


def test_a_zero_ttl_means_never_expire(tmp_path):
    forever = ResponseCache(tmp_path / "c.db", ttl_seconds=0)
    _put(forever)
    assert _get(forever) is not None
    assert forever.purge_expired() == 0


def test_the_oldest_entries_are_evicted_past_the_cap(tmp_path):
    small = ResponseCache(tmp_path / "c.db", max_rows=5, near_match=False)
    for index in range(12):
        small.put(
            payload={"n": index},
            response=f"answer {index}",
            data_class=DataClass.PUBLIC,
            policy=DataPolicy.STANDARD,
        )
    assert small.stats()["entries"] == 5
    # The newest survived; the oldest did not.
    assert small.get(
        payload={"n": 11}, data_class=DataClass.PUBLIC, policy=DataPolicy.STANDARD
    ) is not None
    assert small.get(
        payload={"n": 0}, data_class=DataClass.PUBLIC, policy=DataPolicy.STANDARD
    ) is None


def test_clearing_is_scoped_to_a_workspace_when_asked(cache):
    _put(cache, workspace_id="alice")
    _put(cache, workspace_id="bob")
    assert cache.clear(workspace_id="alice") == 1
    assert _get(cache, workspace_id="bob") is not None


# ── what must never be stored ──────────────────────────────────────────────


def test_an_empty_response_is_not_stored(cache):
    """Caching "the provider returned nothing" turns one transient failure into
    a week of them."""
    assert _put(cache, response="") is False
    assert _put(cache, response="   ") is False
    assert _get(cache) is None


# ── measurement, because the headline numbers do not apply here ────────────


def test_the_hit_rate_is_reported_rather_than_assumed(cache):
    """Published 60-90% figures come from chat systems. On personalised outreach
    the only honest answer is to measure it."""
    assert cache.stats()["hit_rate"] == 0.0
    _get(cache)                      # miss
    _put(cache)
    _get(cache)                      # exact hit
    stats = cache.stats()
    assert stats["exact_hits"] == 1
    assert stats["misses"] == 1
    assert stats["lookups"] == 2
    assert stats["hit_rate"] == 0.5
    assert stats["calls_avoided"] == 1


def test_near_hits_are_counted_separately_from_exact_ones(cache):
    """They carry different risk, so they are worth telling apart."""
    _put(cache)
    _get(cache, payload=dict(PAYLOAD, instructions=PAYLOAD["instructions"].upper()))
    stats = cache.stats()
    assert stats["near_hits"] == 1
    assert stats["exact_hits"] == 0


def test_per_entry_hit_counts_are_kept(cache):
    _put(cache)
    _get(cache)
    _get(cache)
    with cache.connection() as conn:
        row = conn.execute("SELECT hits, last_hit_at FROM ai_response_cache").fetchone()
    assert row["hits"] == 2
    assert row["last_hit_at"]


# ── key construction ───────────────────────────────────────────────────────


def test_the_partition_covers_every_boundary_that_matters():
    base = dict(
        workspace_id="local",
        data_class=DataClass.PUBLIC,
        policy=DataPolicy.STANDARD,
        task_type="draft_email",
        provider_id="mistral",
    )
    reference = partition_key(**base)
    for field, value in [
        ("workspace_id", "other"),
        ("data_class", DataClass.CAMPAIGN),
        ("policy", DataPolicy.FULL),
        ("task_type", "summarise"),
        ("provider_id", "deepseek"),
    ]:
        assert partition_key(**{**base, field: value}) != reference, field


def test_the_key_changes_with_the_payload():
    partition = "p"
    assert cache_key(partition=partition, payload={"a": 1}) != cache_key(
        partition=partition, payload={"a": 2}
    )


# ── structural ─────────────────────────────────────────────────────────────


def test_the_cache_reaches_no_provider():
    """A cache that could call a model would defeat its own purpose."""
    source = (PACKAGE_ROOT / "ai" / "cache.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            imported.update(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    banned = {"requests", "httpx", "openai", "socket", "urllib"}
    assert not (imported & banned)
    assert not any("create_provider" in name for name in imported)


def test_the_cache_exposes_no_retrieval_interface_to_a_model(cache):
    for attribute in ("query", "search", "tools", "functions", "retrieve", "generate"):
        assert not hasattr(cache, attribute)


# ── wired into the broker ──────────────────────────────────────────────────


def _broker(tmp_path, cache_obj, calls):
    from offsetx_apollo_builder.ai import (
        EgressBroker,
        EgressLog,
        ProviderRegistry,
        QuotaTracker,
    )

    class Counter:
        def generate(self, *, system_prompt, user_prompt):
            calls.append(user_prompt)
            return f"answer {len(calls)}"

    broker = EgressBroker(
        registry=ProviderRegistry(PACKAGE_ROOT.parent / "config" / "providers.yaml"),
        credential_resolver=lambda provider_id: "k",
        quota=QuotaTracker(tmp_path),
        logger=EgressLog(tmp_path / "e.db").record,
        cache=cache_obj,
    )
    broker._instantiate = lambda candidate: Counter()
    return broker


def _settings():
    from offsetx_apollo_builder.ai import WorkspaceEgressSettings

    return WorkspaceEgressSettings(
        workspace_id="local",
        enabled_provider_ids=("mistral",),
        owner_domains=("offsetx.example",),
    )


def _public_request():
    from offsetx_apollo_builder.ai import EgressRequest

    return EgressRequest(
        task_type="write_code",
        data_class=DataClass.PUBLIC,
        public_text="Write a Python function that reverses a list.",
    )


def test_a_second_identical_call_does_not_reach_the_provider(tmp_path):
    calls: list[str] = []
    cache_obj = ResponseCache(tmp_path / "cache.db")
    broker = _broker(tmp_path, cache_obj, calls)

    first = broker.call(_public_request(), _settings(), system_prompt="w")
    second = broker.call(_public_request(), _settings(), system_prompt="w")

    assert len(calls) == 1, "the second call should have been served from cache"
    assert second.text == first.text
    assert cache_obj.stats()["calls_avoided"] == 1


def test_a_cache_hit_is_logged_as_a_hit_not_as_a_send(tmp_path):
    """Nothing left the machine. An audit trail showing this as a send would be
    a lie, and the egress log is the one thing that must never lie."""
    from offsetx_apollo_builder.ai import EgressLog

    calls: list[str] = []
    cache_obj = ResponseCache(tmp_path / "cache.db")
    log = EgressLog(tmp_path / "e.db")
    broker = _broker(tmp_path, cache_obj, calls)
    broker.logger = log.record

    broker.call(_public_request(), _settings(), system_prompt="w")
    broker.call(_public_request(), _settings(), system_prompt="w")

    rows, _ = log.list(limit=10)
    statuses = [row["status"] for row in rows]
    assert "succeeded" in statuses
    assert any(status.startswith("cache_") for status in statuses)


def test_the_cache_is_consulted_after_the_scanner_not_before(tmp_path):
    """A lookup must never become a way around the checks that precede it. If
    the payload is blocked, nothing is served and nothing is stored."""
    from offsetx_apollo_builder.ai import EgressBlocked
    from offsetx_apollo_builder.ai import broker as broker_module

    calls: list[str] = []
    cache_obj = ResponseCache(tmp_path / "cache.db")
    broker = _broker(tmp_path, cache_obj, calls)

    def leaky(request, policy, **kwargs):
        return {"schema_version": 1, "leaky": "ana.silva@acme.example"}

    original = broker_module.build_payload
    broker_module.build_payload = leaky
    try:
        with pytest.raises(EgressBlocked):
            broker.call(_public_request(), _settings(), system_prompt="w")
    finally:
        broker_module.build_payload = original

    assert calls == []
    assert cache_obj.stats()["entries"] == 0


def test_a_failed_call_is_not_cached(tmp_path):
    """Otherwise one transient outage becomes a week of them."""
    calls: list[str] = []
    cache_obj = ResponseCache(tmp_path / "cache.db")
    broker = _broker(tmp_path, cache_obj, calls)

    class Broken:
        def generate(self, *, system_prompt, user_prompt):
            raise RuntimeError("provider is down")

    broker._instantiate = lambda candidate: Broken()
    with pytest.raises(Exception):
        broker.call(_public_request(), _settings(), system_prompt="w")
    assert cache_obj.stats()["entries"] == 0


def test_a_broker_without_a_cache_still_works(tmp_path):
    calls: list[str] = []
    broker = _broker(tmp_path, None, calls)
    broker.call(_public_request(), _settings(), system_prompt="w")
    broker.call(_public_request(), _settings(), system_prompt="w")
    assert len(calls) == 2, "no cache means no sharing"
