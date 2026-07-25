from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

INITIAL = "initial"
FOLLOWUP_1 = "followup1"
FOLLOWUP_2 = "followup2"
MESSAGE_STAGES = (INITIAL, FOLLOWUP_1, FOLLOWUP_2)

EXPERT_ROUTE = "expert_validation"
CLIENT_ROUTE = "future_client_discovery"
ROUTES = (EXPERT_ROUTE, CLIENT_ROUTE)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_utc_iso(value: datetime | None = None) -> str:
    value = value or utc_now()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def parse_datetime(value: str | datetime | None) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return re.sub(r"\s+", " ", text)


def normalize_email(value: object) -> str:
    return clean_text(value).lower()


def stable_identity_key(
    *,
    full_name: str,
    company: str,
    title: str = "",
    linkedin_url: str = "",
    email: str = "",
) -> str:
    normalized_email = normalize_email(email)
    if normalized_email:
        source = f"email|{normalized_email}"
    else:
        linkedin = clean_text(linkedin_url).lower().split("?", 1)[0].rstrip("/")
        if linkedin:
            source = f"linkedin|{linkedin}"
        else:
            parts = [
                clean_text(full_name).lower(),
                clean_text(company).lower(),
                clean_text(title).lower(),
            ]
            source = "person|" + "|".join(parts)
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class ContactInput:
    full_name: str
    email: str
    company: str = ""
    title: str = ""
    first_name: str = ""
    last_name: str = ""
    category: str = ""
    route: str = ""
    linkedin_url: str = ""
    public_hook: str = ""
    hook_source: str = ""
    hook_date: str = ""
    tension: str = ""
    identity_line: str = ""
    contribution: str = ""
    questions: list[str] = field(default_factory=list)
    notes: str = ""
    source_ref: str = ""
    source_data: dict[str, Any] = field(default_factory=dict)
    recipient_timezone: str = ""
    outcome_label: str = ""

    @property
    def identity_key(self) -> str:
        return stable_identity_key(
            full_name=self.full_name,
            company=self.company,
            title=self.title,
            linkedin_url=self.linkedin_url,
            email=self.email,
        )

    def normalized(self) -> "ContactInput":
        full_name = clean_text(self.full_name)
        first_name = clean_text(self.first_name)
        last_name = clean_text(self.last_name)
        if full_name and not first_name:
            parts = full_name.split()
            first_name = parts[0]
            last_name = last_name or " ".join(parts[1:])
        if not full_name:
            full_name = f"{first_name} {last_name}".strip()
        return ContactInput(
            full_name=full_name,
            email=normalize_email(self.email),
            company=clean_text(self.company),
            title=clean_text(self.title),
            first_name=first_name,
            last_name=last_name,
            category=clean_text(self.category),
            route=clean_text(self.route),
            linkedin_url=clean_text(self.linkedin_url),
            public_hook=clean_text(self.public_hook),
            hook_source=clean_text(self.hook_source),
            hook_date=clean_text(self.hook_date),
            tension=clean_text(self.tension),
            identity_line=clean_text(self.identity_line),
            contribution=clean_text(self.contribution),
            questions=[clean_text(item) for item in self.questions if clean_text(item)],
            notes=clean_text(self.notes),
            source_ref=clean_text(self.source_ref),
            source_data=dict(self.source_data),
            recipient_timezone=clean_text(self.recipient_timezone),
            outcome_label=clean_text(self.outcome_label),
        )


@dataclass(slots=True)
class DraftAudit:
    score: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: dict[str, Any] = field(default_factory=dict)

    @property
    def sendable(self) -> bool:
        return self.score >= 85 and not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "errors": self.errors,
            "warnings": self.warnings,
            "checks": self.checks,
            "sendable": self.sendable,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass(slots=True)
class DraftContent:
    subject: str
    body: str
    stage: str
    variant_id: str
    template_id: str
    audit: DraftAudit
    retrieval_refs: list[str] = field(default_factory=list)
    generation_meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SendResult:
    provider_message_id: str
    thread_id: str
    internet_message_id: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class IncomingMessage:
    provider_message_id: str
    thread_id: str
    from_email: str
    subject: str = ""
    body_preview: str = ""
    received_at: datetime = field(default_factory=utc_now)
    internet_message_id: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProviderConfig:
    provider_type: str
    model: str = ""
    api_key_env: str = ""
    base_url: str = ""
    timeout_seconds: int = 60
    extra: dict[str, Any] = field(default_factory=dict)


class AIProvider(Protocol):
    def generate(self, *, system_prompt: str, user_prompt: str) -> str: ...


class MailProvider(Protocol):
    def send_message(
        self,
        *,
        to_email: str,
        subject: str,
        body: str,
        thread_id: str = "",
        in_reply_to: str = "",
        references: str = "",
        idempotency_key: str = "",
    ) -> SendResult: ...

    def list_replies(self, *, since: datetime, own_email: str) -> list[IncomingMessage]: ...
