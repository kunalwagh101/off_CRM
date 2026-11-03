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
