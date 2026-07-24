from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable


TRUST_TIERS = {"A", "B", "C", "D"}
DATA_CLASSES = {
    "public",
    "person_public",
    "owner_template",
    "internal_private",
    "mailbox_private",
}

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
CREDENTIAL_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bAIza[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{12,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{12,}", re.IGNORECASE),
    re.compile(r"\bpostgres(?:ql)?://[^\s]+", re.IGNORECASE),
)
FILE_PATH_PATTERNS = (
    re.compile(r"(?:^|\s)/(?:workspace|home|root|Users?)/[^\s]+", re.IGNORECASE),
    re.compile(r"\b[A-Z]:\\Users\\[^\s]+", re.IGNORECASE),
)
PII_REDACTION_PATTERNS = (
    (
        "phone",
        re.compile(
            r"(?<!\w)(?:\+\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)|\d{2,4})"
            r"[\s.-]\d{3,4}[\s.-]\d{4}(?!\w)"
        ),
        "[PHONE_REDACTED]",
    ),
    (
        "india_mobile",
        re.compile(r"(?<!\d)(?:\+91[\s.-]?)?[6-9]\d{4}[\s.-]?\d{5}(?!\d)"),
        "[PHONE_REDACTED]",
    ),
    (
        "aadhaar_like",
        re.compile(r"(?<!\d)\d{4}\s?\d{4}\s?\d{4}(?!\d)"),
        "[NATIONAL_ID_REDACTED]",
    ),
    (
        "india_pan_like",
        re.compile(r"(?<![A-Z0-9])[A-Z]{5}\d{4}[A-Z](?![A-Z0-9])"),
        "[NATIONAL_ID_REDACTED]",
    ),
    (
        "ipv4",
        re.compile(
            r"(?<!\d)(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}"
            r"(?:25[0-5]|2[0-4]\d|1?\d?\d)(?!\d)"
        ),
        "[IP_ADDRESS_REDACTED]",
    ),
)
MAILBOX_MARKERS = (
    re.compile(r"\bMessage-ID\s*:", re.IGNORECASE),
    re.compile(r"\bIn-Reply-To\s*:", re.IGNORECASE),
    re.compile(r"\bX-GM-(?:MSGID|THRID|LABELS)\b", re.IGNORECASE),
    re.compile(r"\bsearch\s+(?:my\s+)?(?:gmail|mailbox|inbox)\b", re.IGNORECASE),
    re.compile(r"\b(?:read|open|retrieve|fetch)\s+(?:my\s+)?(?:gmail|mailbox|inbox)\b", re.IGNORECASE),
    re.compile(r"\bget\s+(?:the\s+)?(?:email|reply)\s+(?:from|sent by)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:read|open|retrieve|fetch|search|query)\s+(?:my\s+)?"
        r"(?:crm|database|context\s+(?:store|layer)|memory\s+(?:store|layer))\b",
        re.IGNORECASE,
    ),
)

FORBIDDEN_KEYS = {
    "email",
    "email_address",
    "recipient_email",
    "owner_email",
    "to_email",
    "from_email",
    "phone",
    "phone_number",
    "mailbox",
    "inbox",
    "reply_body",
    "received_subject",
    "received_headers",
    "gmail_token",
    "oauth_token",
    "api_key",
    "credential",
    "credentials",
    "connection_string",
    "database_path",
    "file_path",
    "storage_path",
    "context_state",
    "memory_store",
    "evidence_store",
    "crm_record",
    "pipeline_data",
    "deal_value",
    "projection",
}

PUBLIC_PROFILE_FIELDS = {
    "name",
    "first_name",
    "role",
    "title",
    "company",
    "category",
    "route",
    "public_hook",
    "hook_source",
    "public_professional_details",
    "public_claims",
}
CHINA_JURISDICTION_MARKERS = {
    "china",
    "chinese",
    "people's republic of china",
    "prc",
    "cn",
}
AGGREGATOR_MARKERS = {
    "openrouter",
    "kilo code",
    "llm7",
    "hugging face routing",
    "huggingface routing",
    "ollama cloud",
    "aggregator",
    "opaque router",
}


class PolicyViolation(RuntimeError):
    def __init__(self, message: str, *, reasons: Iterable[str] = ()):
        self.reasons = list(dict.fromkeys(str(reason) for reason in reasons if reason))
        detail = message
        if self.reasons:
            detail += ": " + "; ".join(self.reasons)
        super().__init__(detail)


@dataclass(slots=True, frozen=True)
class TaskRule:
    task_type: str
    data_class: str
    permitted_tiers: frozenset[str]
    system_prompt: str


TASK_RULES: dict[str, TaskRule] = {
    "public_general": TaskRule(
        task_type="public_general",
        data_class="public",
        permitted_tiers=frozenset({"A", "B", "C"}),
        system_prompt=(
            "Answer only from the public, non-personal material supplied in this request. "
            "You have no tools, connectors, files, mailbox, CRM, memory, database or web access. "
            "Do not ask the application to retrieve private data. State uncertainty plainly."
        ),
    ),
    "outreach_draft": TaskRule(
        task_type="outreach_draft",
        data_class="person_public",
        permitted_tiers=frozenset({"A"}),
        system_prompt=(
            "Write one outbound message using only the supplied public professional facts, "
            "sender positioning and template. Do not invent facts or relationships. "
            "Return strict JSON with non-empty subject and body strings."
        ),
    ),
    "template_rewrite": TaskRule(
        task_type="template_rewrite",
        data_class="owner_template",
        permitted_tiers=frozenset({"A"}),
        system_prompt=(
            "Rewrite the supplied outbound template using only its text and numeric performance. "
            "Do not infer reply content. Return only the revised template."
        ),
    ),
    "masked_parse_fallback": TaskRule(
        task_type="masked_parse_fallback",
        data_class="owner_template",
        permitted_tiers=frozenset({"A"}),
        system_prompt=(
            "Extract a table from the already-masked text. Personal identifiers are tokens. "
            "Return JSON rows and do not guess values that are absent."
        ),
    ),
    "health_check": TaskRule(
        task_type="health_check",
        data_class="public",
        permitted_tiers=frozenset({"A", "B", "C"}),
        system_prompt="Return exactly: connected",
    ),
}


def _text_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _text_values(item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _text_values(item)


class EgressPolicy:
    """Default-deny policy used before every provider call."""

    def __init__(self, *, owner_domains: Iterable[str] = ()):
        self.owner_domains = {
            str(item).strip().lower().lstrip("@")
            for item in owner_domains
            if str(item).strip()
        }

    def rule(self, task_type: str) -> TaskRule:
        try:
            return TASK_RULES[task_type]
        except KeyError as exc:
            raise PolicyViolation(
                "Unknown AI task type is denied",
                reasons=[f"task_type={task_type or 'empty'}"],
            ) from exc

    def effective_tier(self, profile: dict[str, Any]) -> str:
        tier = str(profile.get("trust_tier") or "D").upper()
        if tier not in TRUST_TIERS:
            return "D"
        jurisdiction = str(profile.get("jurisdiction") or "").strip().lower()
        jurisdiction_tokens = set(re.findall(r"[a-z]+", jurisdiction))
        if (
            jurisdiction in CHINA_JURISDICTION_MARKERS
            or "china" in jurisdiction_tokens
            or "chinese" in jurisdiction_tokens
        ):
            return "C"
        host_identity = " ".join(
            [
                str(profile.get("name", "")),
                str(profile.get("host_origin", "")),
                str(profile.get("base_url", "")),
            ]
        ).lower()
        if any(marker in host_identity for marker in AGGREGATOR_MARKERS):
            return "D"
        if tier in {"A", "B"} and jurisdiction in {"", "unknown", "unassigned"}:
            return "D"
        model_origin = " ".join(
            [
                str(profile.get("model_origin", "")),
                str(profile.get("model_origin_jurisdiction", "")),
            ]
        ).lower()
        model_origin_tokens = set(re.findall(r"[a-z]+", model_origin))
        model_origin_is_china = (
            "china" in model_origin_tokens
            or "chinese" in model_origin_tokens
            or "prc" in model_origin_tokens
            or "cn" in model_origin_tokens
        )
        verified = bool(profile.get("model_origin_input_isolation_verified", False))
        if tier == "A" and model_origin_is_china and not verified:
            return "B"
        return tier

    def provider_reasons(
        self,
        profile: dict[str, Any],
        *,
        task_type: str,
        data_class: str,
        explicit_selection: bool,
        is_failover: bool,
    ) -> list[str]:
        reasons: list[str] = []
        rule = self.rule(task_type)
        tier = self.effective_tier(profile)
        if str(profile.get("provider_type") or "").strip().lower() == "local_command":
            reasons.append(
                "legacy local-command profiles cannot run through OFF_AI; "
                "use a networkless sandboxed tool or an API endpoint"
            )
        if not bool(profile.get("enabled", True)):
            reasons.append("provider is disabled")
        if tier not in rule.permitted_tiers:
            reasons.append(
                f"Tier {tier} is not permitted for {task_type}/{data_class}"
            )
        if data_class not in DATA_CLASSES:
            reasons.append("unknown data class")
        if data_class in {"internal_private", "mailbox_private"}:
            reasons.append(f"{data_class} cannot leave OFF_CRM")
        if tier == "A":
            retention = str(profile.get("retention_policy") or "unknown")
            if retention != "no_training_no_retention":
                reasons.append(
                    "Tier A requires verified no-training and no-retention terms"
                )
            if not str(profile.get("terms_checked_at") or ""):
                reasons.append("provider terms have not been checked")
        if tier == "B" and data_class != "public":
            reasons.append("Tier B accepts fully public, non-personal tasks only")
        if tier == "C":
            allowed = {
                str(item)
                for item in profile.get("allowed_task_types", [])
                if str(item)
            }
            if not explicit_selection:
                reasons.append("Tier C requires explicit owner selection")
            if not bool(profile.get("public_tasks_enabled", False)):
                reasons.append("Tier C public tasks are off")
            if task_type not in allowed:
                reasons.append(f"Tier C is not enabled for task type {task_type}")
            if is_failover:
                reasons.append("Tier C cannot participate in failover")
            if data_class != "public":
                reasons.append("Tier C accepts public, non-personal tasks only")
        if tier == "D":
            reasons.append("untrusted/default-deny provider")
        allowed_tasks = {
            str(item)
            for item in profile.get("allowed_task_types", [])
            if str(item)
        }
        if allowed_tasks and task_type not in allowed_tasks:
            reasons.append(f"provider is not configured for task type {task_type}")
        return list(dict.fromkeys(reasons))

    def scan(self, payload: dict[str, Any]) -> list[str]:
        reasons: list[str] = []

        def inspect(value: Any, path: str = "payload") -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    canonical = re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")
                    if canonical in FORBIDDEN_KEYS:
                        reasons.append(f"forbidden field at {path}.{key}")
                    inspect(item, f"{path}.{key}")
                return
            if isinstance(value, (list, tuple)):
                for index, item in enumerate(value):
                    inspect(item, f"{path}[{index}]")
                return
            if not isinstance(value, str):
                return
            if EMAIL_RE.search(value):
                reasons.append(f"email address detected at {path}")
            for pattern in CREDENTIAL_PATTERNS:
                if pattern.search(value):
                    reasons.append(f"credential or secret pattern detected at {path}")
                    break
            for pattern in FILE_PATH_PATTERNS:
                if pattern.search(value):
                    reasons.append(f"local file path detected at {path}")
                    break
            for pattern in MAILBOX_MARKERS:
                if pattern.search(value):
                    reasons.append(f"mailbox access or message metadata detected at {path}")
                    break
            lowered = value.lower()
            for domain in self.owner_domains:
                if domain and domain in lowered:
                    reasons.append(f"owner domain detected at {path}")
                    break

        inspect(payload)
        return list(dict.fromkeys(reasons))

    def assert_payload(self, payload: dict[str, Any]) -> None:
        reasons = self.scan(payload)
        if reasons:
            raise PolicyViolation("Provider call blocked by pre-flight scan", reasons=reasons)

    def redact(self, payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        """Apply deterministic PII backstops after the hard-block scanner passes."""
        redacted = deepcopy(payload)
        applied: list[str] = []

        def visit(value: Any) -> Any:
            if isinstance(value, dict):
                return {key: visit(item) for key, item in value.items()}
            if isinstance(value, list):
                return [visit(item) for item in value]
            if isinstance(value, tuple):
                return [visit(item) for item in value]
            if not isinstance(value, str):
                return value
            result = value
            for name, pattern, replacement in PII_REDACTION_PATTERNS:
                result, count = pattern.subn(replacement, result)
                if count:
                    applied.extend([name] * count)
            return result

        redacted = visit(redacted)
        return redacted, list(dict.fromkeys(applied))

    def build_payload(self, task_type: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Construct from an allowlist. Never copy an internal object and strip it."""
        self.rule(task_type)
        if task_type == "public_general":
            context = []
            for item in list(fields.get("approved_context") or [])[-12:]:
                if not isinstance(item, dict):
                    continue
                role = str(item.get("role", ""))
                content = str(item.get("content", ""))
                if role in {"user", "assistant"} and content:
                    context.append({"role": role, "content": content[:12000]})
            return {
                "schema_version": 1,
                "task": str(fields.get("prompt", ""))[:30000],
                "approved_public_context": context,
            }
        if task_type == "outreach_draft":
            source = fields.get("public_profile") or {}
            if not isinstance(source, dict):
                source = {}
            profile = {
                key: source[key]
                for key in PUBLIC_PROFILE_FIELDS
                if key in source and source[key] not in (None, "", [], {})
            }
            return {
                "schema_version": 1,
                "task": "Write one personalised outbound message.",
                "public_profile": profile,
                "sender_positioning": str(fields.get("sender_positioning", ""))[:2000],
                "template_text": str(fields.get("template_text", ""))[:30000],
                "instructions": str(fields.get("instructions", ""))[:6000],
                "output_schema": {"subject": "string", "body": "string"},
            }
        if task_type == "template_rewrite":
            return {
                "schema_version": 1,
                "task": "Rewrite the template for a new human-reviewed A/B variant.",
                "template_text": str(fields.get("template_text", ""))[:30000],
                "performance": {
                    "sample_size": int(fields.get("sample_size") or 0),
                    "reply_rate_percent": float(fields.get("reply_rate") or 0),
                },
            }
        if task_type == "masked_parse_fallback":
            return {
                "schema_version": 1,
                "task": "Extract rows from masked input.",
                "masked_text": str(fields.get("masked_text", ""))[:30000],
                "expected_fields": [
                    str(item) for item in fields.get("expected_fields", [])
                ][:30],
            }
        if task_type == "health_check":
            return {"schema_version": 1, "task": "connection health check"}
        raise PolicyViolation("Task has no payload builder", reasons=[task_type])

    @staticmethod
    def serialise_for_provider(
        *, system_prompt: str, payload: dict[str, Any]
    ) -> tuple[str, str]:
        return system_prompt, json.dumps(payload, ensure_ascii=False)


class SandboxPolicy:
    """Build-time and BYO-tool guard. Network is denied unless explicitly designed."""

    def __init__(self, allowed_hosts: Iterable[str] = ()):
        self.allowed_hosts = {
            str(host).strip().lower() for host in allowed_hosts if str(host).strip()
        }

    def assert_host(self, host: str) -> None:
        value = host.strip().lower().split(":", 1)[0]
        if value not in self.allowed_hosts:
            raise PolicyViolation(
                "Sandbox egress blocked", reasons=[f"host={host or 'empty'}"]
            )

    @staticmethod
    def docker_command(
        *, image: str, command: Iterable[str], source_dir: str
    ) -> list[str]:
        if not re.fullmatch(r"[A-Za-z0-9./:_-]{1,300}", image):
            raise ValueError("Invalid sandbox image")
        return [
            "docker",
            "run",
            "--rm",
            "--pull=never",
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--user=65534:65534",
            "--pids-limit=128",
            "--memory=512m",
            "--cpus=1",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            "-v",
            f"{source_dir}:/workspace:ro",
            "-w",
            "/workspace",
            image,
            *[str(part) for part in command],
        ]
