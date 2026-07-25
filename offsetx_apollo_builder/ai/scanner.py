"""Pre-flight scanner.

Runs on the constructed payload immediately before it leaves.  A hit **blocks
the call and raises**; it does not quietly redact.  That is deliberate: under
allowlist construction, forbidden content in a payload means the builder has a
bug, and silently cleaning it up would hide the bug forever (§5.5.3).

The scanner is a second line of defence.  Minimisation in
:mod:`offsetx_apollo_builder.ai.payload` is the primary control.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from .tiers import DataPolicy

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)

#: Credential shapes worth stopping on.  Deliberately broad — a false positive
#: costs one blocked call and an explanation; a false negative leaks a key.
_CREDENTIAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}")),
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{16,}")),
    ("google_key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}")),
    ("groq_key", re.compile(r"\bgsk_[A-Za-z0-9]{20,}")),
    ("nvidia_key", re.compile(r"\bnvapi-[A-Za-z0-9_-]{20,}")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}")),
    ("github_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}")),
    ("aws_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("bearer_header", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{20,}")),
    ("private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("connection_string", re.compile(r"\b(?:postgres|postgresql|mysql|mongodb(?:\+srv)?|redis)://\S+")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
)

#: Markers that mean the text came out of a mailbox rather than out of a
#: template.  Received mail must never reach a provider (§5.3).
_MAILBOX_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("message_id_header", re.compile(r"^\s*message-id\s*:", re.IGNORECASE | re.MULTILINE)),
    ("received_header", re.compile(r"^\s*received\s*:\s*from\b", re.IGNORECASE | re.MULTILINE)),
    ("return_path_header", re.compile(r"^\s*return-path\s*:", re.IGNORECASE | re.MULTILINE)),
    ("delivered_to_header", re.compile(r"^\s*delivered-to\s*:", re.IGNORECASE | re.MULTILINE)),
    ("mime_header", re.compile(r"^\s*content-transfer-encoding\s*:", re.IGNORECASE | re.MULTILINE)),
    ("dkim_header", re.compile(r"^\s*dkim-signature\s*:", re.IGNORECASE | re.MULTILINE)),
    ("forwarded_block", re.compile(r"-{2,}\s*forwarded message\s*-{2,}", re.IGNORECASE)),
    ("original_message_block", re.compile(r"-{2,}\s*original message\s*-{2,}", re.IGNORECASE)),
    ("quoted_reply", re.compile(r"^\s*on .{5,80}\bwrote:\s*$", re.IGNORECASE | re.MULTILINE)),
    ("gmail_thread_id", re.compile(r"\bthread-[af]:\d{10,}")),
)

#: Column and field names that only exist inside off_CRM.  Seeing one in an
#: outbound payload means an internal record was pasted in wholesale.
_INTERNAL_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "api_key",
        "api_key_env",
        "apollo_id",
        "campaign_contact_id",
        "credential_source",
        "deal_value",
        "gmail_token",
        "has_stored_secret",
        "identity_key",
        "internet_message_id",
        "provider_message_id",
        "refresh_token",
        "access_token",
        "commission",
        "net_revenue",
        "pipeline_stage",
        "lost_reason",
        "workspace_id",
        "own_email",
        "source_data",
    }
)

_ENV_VAR_RE = re.compile(r"\bOFFSETX_[A-Z0-9_]{3,}\b")
_FILE_PATH_RE = re.compile(r"(?:^|[\s\"'])(?:/(?:home|root|var|etc|Users)/[\w./-]{4,})")


@dataclass(slots=True)
class ScanFinding:
    """One reason the payload was refused."""

    kind: str
    detail: str
    location: str = ""
    sample: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "detail": self.detail,
            "location": self.location,
            "sample": self.sample,
        }


@dataclass(slots=True)
class ScanReport:
    findings: list[ScanFinding] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.findings

    def to_dict(self) -> dict[str, Any]:
        return {
            "clean": self.clean,
            "findings": [item.to_dict() for item in self.findings],
        }

    def summary(self) -> str:
        if self.clean:
            return "No forbidden content found."
        kinds = sorted({item.kind for item in self.findings})
        return f"Blocked: {', '.join(kinds)}"


def _mask(value: str, keep: int = 4) -> str:
    """Show enough of a hit to identify it, never enough to reuse it."""
    text = str(value)
    if len(text) <= keep:
        return "*" * len(text)
    return text[:keep] + "…" + "*" * min(6, max(0, len(text) - keep))


def _walk(payload: Any, path: str = "$") -> Iterable[tuple[str, str, Any]]:
    """Yield ``(path, kind, value)`` for every key and leaf string in the tree."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            child = f"{path}.{key}"
            yield (child, "key", str(key))
            yield from _walk(value, child)
    elif isinstance(payload, (list, tuple)):
        for index, value in enumerate(payload):
            yield from _walk(value, f"{path}[{index}]")
    elif isinstance(payload, str):
        yield (path, "value", payload)
    elif payload is not None:
        yield (path, "value", str(payload))


def scan_payload(
    payload: dict[str, Any],
    *,
    policy: DataPolicy = DataPolicy.MINIMAL,
    owner_domains: Iterable[str] = (),
    owner_addresses: Iterable[str] = (),
    allow_addresses: bool = False,
) -> ScanReport:
    """Inspect a constructed payload for anything that must not leave.

    ``allow_addresses`` is set by the broker only when the resolved policy is
    ``full`` — the owner's explicit per-provider opt-in.  Everything else on the
    deny list stays blocked at every policy level, including ``full``:
    credentials, mailbox headers and internal identifiers are never legitimate
    outbound content.
    """
    report = ScanReport()
    domains = {str(item).strip().lower().lstrip("@") for item in owner_domains if str(item).strip()}
    addresses = {str(item).strip().lower() for item in owner_addresses if str(item).strip()}

    # Every pattern runs against raw string values, never against a JSON dump of
    # the payload. Serialising first escapes newlines, which silently disables
    # the ``^``-anchored mail-header patterns — the payload would look clean
    # precisely when it holds a pasted email.
    for location, node_kind, value in _walk(payload):
        text = str(value)

        # ── credentials — blocked at every policy level, no exceptions ──────
        for kind, pattern in _CREDENTIAL_PATTERNS:
            match = pattern.search(text)
            if match:
                report.findings.append(
                    ScanFinding(
                        kind="credential",
                        detail=(
                            f"A value shaped like a {kind.replace('_', ' ')} is in the "
                            "payload. Credentials never leave off_CRM."
                        ),
                        location=location,
                        sample=_mask(match.group(0)),
                    )
                )

        # ── mailbox markers — blocked at every policy level ─────────────────
        for kind, pattern in _MAILBOX_PATTERNS:
            match = pattern.search(text)
            if match:
                report.findings.append(
                    ScanFinding(
                        kind="mailbox_content",
                        detail=(
                            f"The payload contains {kind.replace('_', ' ')}, which means "
                            "mail content reached it. Received mail never goes to a provider."
                        ),
                        location=location,
                        sample=_mask(match.group(0).strip(), keep=20),
                    )
                )

        env_match = _ENV_VAR_RE.search(text)
        if env_match:
            report.findings.append(
                ScanFinding(
                    kind="environment_variable",
                    detail="An off_CRM environment variable name is in the payload.",
                    location=location,
                    sample=_mask(env_match.group(0), keep=12),
                )
            )

        path_match = _FILE_PATH_RE.search(text)
        if path_match:
            report.findings.append(
                ScanFinding(
                    kind="file_path",
                    detail="A local filesystem path is in the payload.",
                    location=location,
                    sample=_mask(path_match.group(0).strip(), keep=12),
                )
            )

        if node_kind == "key":
            if text.lower() in _INTERNAL_FIELD_NAMES:
                report.findings.append(
                    ScanFinding(
                        kind="internal_field",
                        detail=(
                            f"Field {text!r} is internal to off_CRM. Its presence means an "
                            "internal record was copied in rather than a payload built."
                        ),
                        location=location,
                    )
                )
            continue

        if not allow_addresses:
            found = _EMAIL_RE.search(text)
            if found:
                report.findings.append(
                    ScanFinding(
                        kind="email_address",
                        detail=(
                            "An email address is in the payload. Addresses are replaced by "
                            f"<{'RECIPIENT_1'}> and re-attached locally after generation."
                        ),
                        location=location,
                        sample=_mask(found.group(0), keep=3),
                    )
                )

        lowered = text.lower()
        for domain in domains:
            if domain and domain in lowered:
                report.findings.append(
                    ScanFinding(
                        kind="owner_domain",
                        detail=(
                            f"Your own domain {domain!r} is in the payload. A model does not "
                            "need it to write an email."
                        ),
                        location=location,
                    )
                )
        for address in addresses:
            if address and address in lowered:
                report.findings.append(
                    ScanFinding(
                        kind="owner_address",
                        detail="Your own email address is in the payload.",
                        location=location,
                        sample=_mask(address, keep=3),
                    )
                )

    # De-duplicate: one finding per (kind, location) keeps the alert readable
    # when the same address appears in several fields.
    seen: set[tuple[str, str]] = set()
    unique: list[ScanFinding] = []
    for finding in report.findings:
        key = (finding.kind, finding.location)
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    report.findings = unique
    return report
