from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import parseaddr
from typing import Any, Mapping, Protocol

from ..models import IncomingMessage, SendResult, normalize_email

PERMISSION_MARKETING = "permission_marketing"
TARGETED_OUTREACH = "targeted_outreach"
TRANSACTIONAL = "transactional"
EMAIL_STREAMS = (PERMISSION_MARKETING, TARGETED_OUTREACH, TRANSACTIONAL)

MAIL_PROVIDERS = ("local", "gmail", "ses")
PERMISSION_STATUSES = ("unknown", "granted", "denied")
AUTH_STATUSES = ("pass", "fail", "unknown")

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)+$")


def unsubscribe_required(
    *, stream: str, provider_type: str, configured: bool
) -> bool:
    """Return the non-bypassable opt-out rule for a delivery lane."""
    if stream == TRANSACTIONAL:
        return False
    return configured or stream == PERMISSION_MARKETING or provider_type == "ses"


def valid_email(value: object, *, ascii_only: bool = False) -> bool:
    email = normalize_email(value)
    if not email or len(email) > 254 or parseaddr(email)[1] != email:
        return False
    if not _EMAIL_RE.fullmatch(email):
        return False
    if ascii_only:
        try:
            email.encode("ascii")
        except UnicodeEncodeError:
            return False
    return True


@dataclass(frozen=True, slots=True)
class PreflightIssue:
    code: str
    message: str
    field: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "field": self.field}


@dataclass(slots=True)
class PreflightReport:
    blockers: list[PreflightIssue] = field(default_factory=list)
    warnings: list[PreflightIssue] = field(default_factory=list)
    checks: dict[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return not self.blockers

    def block(self, code: str, message: str, field: str = "") -> None:
        if code not in {item.code for item in self.blockers}:
            self.blockers.append(PreflightIssue(code, message, field))

    def warn(self, code: str, message: str, field: str = "") -> None:
        if code not in {item.code for item in self.warnings}:
            self.warnings.append(PreflightIssue(code, message, field))

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "blockers": [item.to_dict() for item in self.blockers],
            "warnings": [item.to_dict() for item in self.warnings],
            "checks": self.checks,
        }


@dataclass(frozen=True, slots=True)
class PreparedEmail:
    to_email: str
    from_email: str
    from_name: str
    reply_to: str
    subject: str
    body: str
    headers: Mapping[str, str]
    tags: Mapping[str, str]


class RetryableDeliveryError(RuntimeError):
    def __init__(self, message: str, *, retry_after_seconds: int | None = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class PermanentDeliveryError(RuntimeError):
    pass


class AmbiguousDeliveryError(RuntimeError):
    """The provider may have accepted the message; automatic retry is unsafe."""


class DeliveryProvider(Protocol):
    provider_type: str

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
        from_email: str = "",
        from_name: str = "",
        reply_to: str = "",
        headers: Mapping[str, str] | None = None,
        tags: Mapping[str, str] | None = None,
    ) -> SendResult: ...

    def list_replies(self, *, since: datetime, own_email: str) -> list[IncomingMessage]: ...
