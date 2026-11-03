"""A12/A13: cache must never change factual evidence or model provenance.

Real ResponseCache storage is exercised. No provider credentials or network calls.
"""
from __future__ import annotations

from offsetx_apollo_builder.ai import DataClass, DataPolicy
from offsetx_apollo_builder.ai.cache import ResponseCache


def _payload(fact: str) -> dict[str, object]:
    context = " ".join(
        f"Evidence paragraph {n} confirms the audited accounting records for this period."
        for n in range(50)
    )
    return {"schema_version": 1, "text": f"{context} The recorded fact is {fact}. {context}"}


def _arguments(payload: dict[str, object]) -> dict[str, object]:
    return {
        "payload": payload,
        "data_class": DataClass.PUBLIC,
        "policy": DataPolicy.STANDARD,
        "task_type": "summarise",
        "provider_id": "mistral",
    }


def test_A12_changed_numeric_evidence_cannot_reuse_near_cache(tmp_path):
    cache = ResponseCache(tmp_path / "factual.db")
    old, new = _payload("42 million"), _payload("420 million")
    assert cache.put(**_arguments(old), response="The amount is 42 million.")
    assert cache.get(**_arguments(new)) is None
    assert cache.get(**_arguments(old)).response == "The amount is 42 million."


def test_A12_changed_negation_cannot_reuse_near_cache(tmp_path):
    cache = ResponseCache(tmp_path / "factual.db")
    old, new = _payload("is approved"), _payload("is not approved")
    assert cache.put(**_arguments(old), response="Approved.")
    assert cache.get(**_arguments(new)) is None


def test_A13_model_id_partitions_identical_payload(tmp_path):
    cache = ResponseCache(tmp_path / "models.db")
    payload = _payload("verified")
    assert cache.put(**_arguments(payload), response="Model A", model_id="model-a")
    assert cache.get(**_arguments(payload), model_id="model-b") is None
    hit = cache.get(**_arguments(payload), model_id="model-a")
    assert hit is not None and hit.response == "Model A" and hit.model_id == "model-a"


def test_A13_system_instructions_partition_identical_payload(tmp_path):
    cache = ResponseCache(tmp_path / "prompts.db")
    payload = _payload("verified")
    assert cache.put(
        **_arguments(payload), response="First instructions",
        model_id="model-a", system_prompt="Answer in English",
    )
    assert cache.get(
        **_arguments(payload), model_id="model-a", system_prompt="Answer in Hindi",
    ) is None
    assert cache.get(
        **_arguments(payload), model_id="model-a", system_prompt="Answer in English",
    ) is not None


def test_A13_generation_options_invalidate_cache(tmp_path):
    """Changed sampling configuration must run the selected model again."""
    cache = ResponseCache(tmp_path / "options.db")
    payload = _payload("same evidence")
    assert cache.put(
        **_arguments(payload), response="Temperature 0 result", model_id="model-a",
        generation_options={"temperature": 0, "max_tokens": 1024},
    )
    assert cache.get(
        **_arguments(payload), model_id="model-a",
        generation_options={"temperature": 0.8, "max_tokens": 1024},
    ) is None
    assert cache.get(
        **_arguments(payload), model_id="model-a",
        generation_options={"temperature": 0, "max_tokens": 1024},
    ) is not None


def test_A13_raw_system_prompt_is_never_written_to_cache_index(tmp_path):
    """Partition keys must not contain sensitive instructions."""
    cache = ResponseCache(tmp_path / "private-index.db")
    payload = _payload("stable")
    prompt = "Internal system text PRIVATE_UNIQUE_PROBE_92837"
    assert cache.put(
        **_arguments(payload), response="done", model_id="model-a",
        system_prompt=prompt,
    )
    with cache.connection() as conn:
        row = conn.execute(
            "SELECT cache_key, partition_key, normalised, shingles FROM ai_response_cache"
        ).fetchone()
    assert row is not None
    for column in ("cache_key", "partition_key", "normalised", "shingles"):
        assert prompt not in row[column]
        assert "PRIVATE_UNIQUE_PROBE_92837" not in row[column]


def test_A12_changed_units_dates_and_entities_all_miss(tmp_path):
    """Changed units, dates and entities must never reuse the old fact."""
    cache = ResponseCache(tmp_path / "entities.db")
    changes = [
        ("42 kilograms", "42 tonnes"),
        ("2 January 2024", "2 January 2025"),
        ("Company Alpha", "Company Beta"),
        ("USD 1,000", "INR 1,000"),
    ]
    for n, (before, after) in enumerate(changes):
        original = _payload(f"reference {n}: {before}")
        edited = _payload(f"reference {n}: {after}")
        assert cache.put(**_arguments(original), response=before)
        assert cache.get(**_arguments(edited)) is None


def test_cache_partition_rejects_delimiter_collision():
    """A model or registry field containing a separator cannot alias another scope."""
    from offsetx_apollo_builder.ai.cache import partition_key

    base = {"workspace_id": "local", "data_class": DataClass.PUBLIC,
            "policy": DataPolicy.STANDARD, "system_prompt": "instructions"}
    left = partition_key(
        **base, task_type="extract|summarise", provider_id="mistral",
        model_id="example-model",
    )
    right = partition_key(
        **base, task_type="extract", provider_id="summarise|mistral",
        model_id="example-model",
    )
    assert left != right


def test_A12_A13_restart_keeps_fact_and_model_provenance_isolated(tmp_path):
    """A12/A13: closing and reopening storage cannot bypass cache boundaries."""
    database = tmp_path / "restart-integrity.db"
    original = _payload("42 tonnes in 2026")
    changed = _payload("420 tonnes in 2026")
    settings = {
        **_arguments(original),
        "model_id": "verified-model",
        "system_prompt": "Report the exact value",
        "generation_options": {"temperature": 0, "expect_json": True},
    }
    writer = ResponseCache(database, near_match=True)
    try:
        assert writer.put(**settings, response="42 tonnes")
    finally:
        writer.close()

    reader = ResponseCache(database, near_match=True)
    try:
        hit = reader.get(**settings)
        assert hit is not None
        assert hit.response == "42 tonnes"
        assert hit.model_id == "verified-model"
        assert reader.get(**{**settings, "payload": changed}) is None
        assert reader.get(**{**settings, "model_id": "different-model"}) is None
        assert reader.get(**{**settings, "system_prompt": "Ignore the earlier value"}) is None
        assert reader.get(**{
            **settings,
            "generation_options": {"temperature": 0, "expect_json": False},
        }) is None
        assert reader.get(**{**settings, "workspace_id": "other-workspace"}) is None
        stats = reader.stats()
        assert stats["exact_hits"] == 1
        assert stats["misses"] == 4
        assert stats["near_hits"] == 0
    finally:
        reader.close()
