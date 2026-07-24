from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Iterable

from ..outreach.provider_profiles import ProviderProfileStore
from ..outreach.providers import (
    ProviderError,
    ProviderUnavailableError,
    create_provider,
    normalize_generation_output,
)
from .policy import EgressPolicy, PolicyViolation
from .store import OffAIStore


@dataclass(slots=True)
class BrokerResult:
    text: str
    call_id: str
    profile_id: str
    provider_type: str
    model: str
    trust_tier: str
    attempts: list[dict[str, Any]]


def _estimate_tokens(value: str) -> int:
    return max(1, (len(value) + 3) // 4)


class EgressBroker:
    """The only runtime path from OFF_CRM to an AI provider."""

    def __init__(
        self,
        *,
        store: OffAIStore,
        profiles: ProviderProfileStore,
        owner_domains: Iterable[str] = (),
    ):
        self.store = store
        self.profiles = profiles
        self.policy = EgressPolicy(owner_domains=owner_domains)

    def list_models(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        task_types = (
            "public_general",
            "outreach_draft",
            "template_rewrite",
            "masked_parse_fallback",
            "health_check",
        )
        for profile in self.profiles.list():
            usage = self.store.usage_for_profile(str(profile.get("id", "")))
            item = dict(profile)
            item["effective_trust_tier"] = self.policy.effective_tier(profile)
            item["usage"] = usage
            blockers = {
                task_type: self.policy.provider_reasons(
                    profile,
                    task_type=task_type,
                    data_class=self.policy.rule(task_type).data_class,
                    explicit_selection=True,
                    is_failover=False,
                )
                for task_type in task_types
            }
            item["task_eligibility"] = {
                task_type: not reasons
                for task_type, reasons in blockers.items()
            }
            item["task_blockers"] = blockers
            item["ai_eligible"] = item["task_eligibility"]["public_general"]
            result.append(item)
        return result

    def _quota_reasons(
        self, profile: dict[str, Any], *, estimated_input_tokens: int
    ) -> list[str]:
        usage = self.store.usage_for_profile(str(profile.get("id", "")))
        reasons: list[str] = []
        rpm_limit = int(profile.get("rpm_limit") or 0)
        rpd_limit = int(profile.get("rpd_limit") or 0)
        if rpm_limit and usage["last_minute_requests"] >= rpm_limit:
            reasons.append(f"RPM limit reached ({rpm_limit})")
        if rpd_limit and usage["today"]["requests"] >= rpd_limit:
            reasons.append(f"daily request limit reached ({rpd_limit})")
        input_cost = float(profile.get("input_cost_per_million") or 0)
        estimated_request_cost = estimated_input_tokens / 1_000_000 * input_cost
        daily_cap = float(profile.get("daily_cost_cap") or 0)
        monthly_cap = float(profile.get("monthly_cost_cap") or 0)
        if daily_cap and usage["today"]["estimated_cost"] + estimated_request_cost > daily_cap:
            reasons.append(f"daily cost cap reached ({daily_cap:g})")
        if monthly_cap and usage["month"]["estimated_cost"] + estimated_request_cost > monthly_cap:
            reasons.append(f"monthly cost cap reached ({monthly_cap:g})")
        return reasons

    def _candidate_profiles(
        self,
        *,
        task_type: str,
        data_class: str,
        selected_profile_id: str,
        allow_failover: bool,
        estimated_input_tokens: int,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        profiles = self.profiles.list()
        by_id = {str(item.get("id", "")): item for item in profiles}
        rejected: list[str] = []
        if selected_profile_id:
            selected = by_id.get(selected_profile_id)
            if not selected:
                return [], ["selected provider profile does not exist"]
            reasons = self.policy.provider_reasons(
                selected,
                task_type=task_type,
                data_class=data_class,
                explicit_selection=True,
                is_failover=False,
            )
            reasons.extend(
                self._quota_reasons(
                    selected, estimated_input_tokens=estimated_input_tokens
                )
            )
            if reasons:
                return [], reasons
            candidates = [selected]
            tier = self.policy.effective_tier(selected)
            if allow_failover and tier != "C":
                for fallback_id in selected.get("fallback_profile_ids", []):
                    fallback = by_id.get(str(fallback_id))
                    if not fallback:
                        rejected.append(f"fallback profile {fallback_id} is missing")
                        continue
                    if self.policy.effective_tier(fallback) != tier:
                        rejected.append(
                            f"fallback {fallback_id} crosses trust tier {tier}"
                        )
                        continue
                    fallback_reasons = self.policy.provider_reasons(
                        fallback,
                        task_type=task_type,
                        data_class=data_class,
                        explicit_selection=True,
                        is_failover=True,
                    )
                    fallback_reasons.extend(
                        self._quota_reasons(
                            fallback, estimated_input_tokens=estimated_input_tokens
                        )
                    )
                    if fallback_reasons:
                        rejected.extend(
                            f"fallback {fallback_id}: {reason}"
                            for reason in fallback_reasons
                        )
                    else:
                        candidates.append(fallback)
            return candidates, rejected

        eligible: list[dict[str, Any]] = []
        for profile in profiles:
            reasons = self.policy.provider_reasons(
                profile,
                task_type=task_type,
                data_class=data_class,
                explicit_selection=False,
                is_failover=False,
            )
            reasons.extend(
                self._quota_reasons(
                    profile, estimated_input_tokens=estimated_input_tokens
                )
            )
            if reasons:
                rejected.extend(
                    f"{profile.get('name', profile.get('id'))}: {reason}"
                    for reason in reasons
                )
            else:
                eligible.append(profile)
        eligible.sort(
            key=lambda item: (
                float(item.get("input_cost_per_million") or 0)
                + float(item.get("output_cost_per_million") or 0),
                int(item.get("priority") or 100),
                str(item.get("name", "")),
            )
        )
        if not eligible:
            return [], rejected
        primary_tier = self.policy.effective_tier(eligible[0])
        same_tier = [
            item
            for item in eligible
            if self.policy.effective_tier(item) == primary_tier
        ]
        return (same_tier if allow_failover else same_tier[:1]), rejected

    @staticmethod
    def _synthetic_profile(profile_id: str = "") -> dict[str, Any]:
        return {
            "id": profile_id,
            "name": "Unresolved provider",
            "provider_type": "",
            "model": "",
            "host_origin": "",
            "model_origin": "",
            "jurisdiction": "Unknown",
            "retention_policy": "unknown",
            "trust_tier": "D",
        }

    def dispatch(
        self,
        *,
        task_type: str,
        fields: dict[str, Any],
        selected_profile_id: str = "",
        allow_failover: bool = True,
        conversation_id: str = "",
        message_id: str = "",
    ) -> BrokerResult:
        rule = self.policy.rule(task_type)
        constructed_payload = self.policy.build_payload(task_type, fields)
        constructed_exact_payload = {
            "system_prompt": rule.system_prompt,
            "input": constructed_payload,
        }
        scan_reasons = self.policy.scan(constructed_exact_payload)
        if scan_reasons:
            profile = (
                self.profiles.get(selected_profile_id)
                if selected_profile_id
                else self._synthetic_profile()
            )
            audit = self.store.begin_egress(
                conversation_id=conversation_id,
                message_id=message_id,
                profile=profile,
                task_type=task_type,
                data_class=rule.data_class,
                payload=constructed_exact_payload,
                status="blocked",
                blocked_reasons=scan_reasons,
            )
            raise PolicyViolation(
                f"Provider call {audit['id']} blocked by pre-flight scan",
                reasons=scan_reasons,
            )
        payload, _redactions = self.policy.redact(constructed_payload)
        exact_payload = {
            "system_prompt": rule.system_prompt,
            "input": payload,
        }

        serialized = json.dumps(exact_payload, ensure_ascii=False)
        estimated_input_tokens = _estimate_tokens(serialized)
        candidates, rejected = self._candidate_profiles(
            task_type=task_type,
            data_class=rule.data_class,
            selected_profile_id=selected_profile_id,
            allow_failover=allow_failover,
            estimated_input_tokens=estimated_input_tokens,
        )
        if not candidates:
            profile = (
                self.profiles.get(selected_profile_id)
                if selected_profile_id
                else self._synthetic_profile()
            )
            reasons = rejected or ["no eligible provider is configured"]
            audit = self.store.begin_egress(
                conversation_id=conversation_id,
                message_id=message_id,
                profile=profile,
                task_type=task_type,
                data_class=rule.data_class,
                payload=exact_payload,
                status="blocked",
                blocked_reasons=reasons,
            )
            raise PolicyViolation(
                f"Provider call {audit['id']} denied by trust or quota policy",
                reasons=reasons,
            )

        attempts: list[dict[str, Any]] = []
        for profile in candidates:
            profile_id = str(profile.get("id", ""))
            audit = self.store.begin_egress(
                conversation_id=conversation_id,
                message_id=message_id,
                profile=profile,
                task_type=task_type,
                data_class=rule.data_class,
                payload=exact_payload,
            )
            started = time.monotonic()
            output = ""
            try:
                runtime_profile, config, environ = self.profiles.runtime_material(
                    profile_id
                )
                provider = create_provider(config, environ=environ)
                system_prompt, user_prompt = self.policy.serialise_for_provider(
                    system_prompt=rule.system_prompt, payload=payload
                )
                output = provider.generate(
                    system_prompt=system_prompt, user_prompt=user_prompt
                ).strip()
                if not output:
                    raise ProviderError("AI provider returned an empty response")
                if task_type == "outreach_draft":
                    output = normalize_generation_output(output)
                elif task_type == "masked_parse_fallback":
                    parsed = json.loads(output)
                    if not isinstance(parsed, dict) or not isinstance(
                        parsed.get("rows"), list
                    ):
                        raise ProviderError(
                            "Masked parse fallback must return a JSON object with rows"
                        )
                    output = json.dumps(parsed, ensure_ascii=False)
                duration_ms = int((time.monotonic() - started) * 1000)
                output_tokens = _estimate_tokens(output)
                estimated_cost = (
                    estimated_input_tokens
                    / 1_000_000
                    * float(runtime_profile.get("input_cost_per_million") or 0)
                    + output_tokens
                    / 1_000_000
                    * float(runtime_profile.get("output_cost_per_million") or 0)
                )
                self.store.finish_egress(
                    str(audit["id"]),
                    status="succeeded",
                    response_text=output,
                    input_tokens=estimated_input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost=estimated_cost,
                    duration_ms=duration_ms,
                )
                self.store.record_usage(
                    profile_id,
                    input_tokens=estimated_input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost=estimated_cost,
                )
                attempts.append(
                    {
                        "profile_id": profile_id,
                        "call_id": audit["id"],
                        "status": "used",
                    }
                )
                return BrokerResult(
                    text=output,
                    call_id=str(audit["id"]),
                    profile_id=profile_id,
                    provider_type=str(profile.get("provider_type", "")),
                    model=str(profile.get("model", "")),
                    trust_tier=self.policy.effective_tier(profile),
                    attempts=attempts,
                )
            except PolicyViolation:
                raise
            except Exception as exc:
                duration_ms = int((time.monotonic() - started) * 1000)
                self.store.finish_egress(
                    str(audit["id"]),
                    status="failed",
                    response_text="",
                    error=str(exc),
                    input_tokens=estimated_input_tokens,
                    output_tokens=0,
                    estimated_cost=0,
                    duration_ms=duration_ms,
                )
                self.store.record_usage(
                    profile_id,
                    input_tokens=estimated_input_tokens,
                    output_tokens=0,
                    estimated_cost=0,
                )
                attempts.append(
                    {
                        "profile_id": profile_id,
                        "call_id": audit["id"],
                        "status": "failed",
                        "error": str(exc)[:500],
                    }
                )
                continue
        details = "; ".join(
            f"{item['profile_id']}: {item.get('error', item['status'])}"
            for item in attempts
        )
        raise ProviderUnavailableError(f"All same-tier AI providers failed. {details}")

    def health(self, profile_id: str, *, live_probe: bool = False) -> dict[str, Any]:
        profile = self.profiles.get(profile_id)
        if profile.get("credential_source") == "none":
            updated = self.profiles.set_health(
                profile_id, status="unhealthy", error="No provider credential configured"
            )
            return {
                "status": "unhealthy",
                "profile_id": profile_id,
                "error": updated["last_error"],
            }
        if not live_probe:
            self.profiles.set_health(profile_id, status="configured")
            return {"status": "configured", "profile_id": profile_id}
        try:
            self.dispatch(
                task_type="health_check",
                fields={},
                selected_profile_id=profile_id,
                allow_failover=False,
            )
        except Exception as exc:
            self.profiles.set_health(
                profile_id, status="unhealthy", error=str(exc)
            )
            return {
                "status": "unhealthy",
                "profile_id": profile_id,
                "error": str(exc)[:1000],
            }
        self.profiles.set_health(profile_id, status="healthy")
        return {"status": "healthy", "profile_id": profile_id}

    def email_provider(
        self,
        *,
        profile_ids: Iterable[str] = (),
        sender_positioning: str = "",
    ) -> "BrokeredEmailProvider":
        return BrokeredEmailProvider(
            broker=self,
            profile_ids=list(profile_ids),
            sender_positioning=sender_positioning,
        )


class BrokeredEmailProvider:
    """Compatibility adapter for the existing CRM draft engine."""

    def __init__(
        self,
        *,
        broker: EgressBroker,
        profile_ids: list[str],
        sender_positioning: str,
    ):
        self.broker = broker
        self.profile_ids = list(dict.fromkeys(profile_ids))
        self.sender_positioning = sender_positioning
        self.last_run: dict[str, Any] = {}

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        try:
            source = json.loads(user_prompt)
        except json.JSONDecodeError as exc:
            raise ProviderError(
                "Existing draft engine produced an invalid structured prompt"
            ) from exc
        if not isinstance(source, dict):
            raise ProviderError("Existing draft engine prompt must be an object")
        recipient = source.get("recipient")
        blueprint = source.get("template_blueprint")
        if not isinstance(recipient, dict) or not isinstance(blueprint, dict):
            raise ProviderError("Draft prompt is missing recipient or template data")
        public_profile = {
            "name": recipient.get("full_name") or recipient.get("first_name"),
            "first_name": recipient.get("first_name"),
            "company": recipient.get("company"),
            "title": recipient.get("title"),
            "category": recipient.get("category"),
            "route": recipient.get("route"),
            "public_hook": recipient.get("public_hook"),
            "hook_source": recipient.get("hook_source"),
        }
        template_text = json.dumps(
            {
                "subject": str(blueprint.get("subject", "")),
                "body": str(blueprint.get("body", "")),
            },
            ensure_ascii=False,
        )
        selected = self.profile_ids[0] if self.profile_ids else ""
        result = self.broker.dispatch(
            task_type="outreach_draft",
            fields={
                "public_profile": public_profile,
                "template_text": template_text,
                "sender_positioning": self.sender_positioning,
                "instructions": (
                    "Keep the supplied stage and campaign structure. "
                    "Return subject and body only."
                ),
            },
            selected_profile_id=selected,
            allow_failover=True,
        )
        self.last_run = {
            "selected_profile_id": result.profile_id,
            "attempts": result.attempts,
            "egress_call_id": result.call_id,
        }
        return result.text
