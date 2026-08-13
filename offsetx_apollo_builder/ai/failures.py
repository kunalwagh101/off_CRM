"""What kind of failure this was, and what to do about it.

Before this module every provider failure was treated identically: record it,
move to the next candidate, and if the circuit breaker had seen two of them,
cool the model off for a minute. That is right for exactly one kind of failure —
a provider having a bad day — and wrong for most of the others.

The three ways it was wrong, in order of how much they cost:

**A broken API key looked like a busy provider.** A 401 failed over silently to
the next model, which worked, so nobody found out. The key stays broken, every
call quietly costs more and runs on a different model than the owner chose, and
the first sign of trouble is a bill or a tier surprise. A configuration failure
has to *stop and say so*.

**A payload we built wrong took out healthy providers.** A 400 is our bug, not
theirs, and another model will reject it identically. Failing over tries every
provider in the tier and opens the circuit breaker on each one, so one malformed
request could leave the workspace with no usable model for a minute.

**A rate limit fell through to another provider's quota.** A 429 usually means
*wait a moment*, often with the server telling you exactly how long. Spending
another provider's budget instead is the expensive answer to a free problem.

---

**Classification is only worth having if each class leads to a different
action**, so the actions came first and the classes exist to select between
them. There are four:

| Action | What the broker does |
|---|---|
| ``RETRY_SAME`` | Wait, then ask the same model again |
| ``FAILOVER`` | This model is unhealthy; try the next one in the same tier |
| ``STOP_REQUEST`` | The request itself is wrong; every model fails the same way |
| ``STOP_CONFIG`` | Something a human must fix; nothing works until they do |

Both ``STOP`` actions refuse to fail over. That is the point of them: failing
over is what hid the problem.

---

**On retries and time**, which is the question the owner actually asked.

``outreach/providers.py`` already retries three times inside the HTTP call for
connection errors, 429 and 5xx. So this module does **not** add a second retry
loop on top for those — nine attempts to one model is not resilience, it is a
stuck request. ``RETRY_SAME`` is reserved for the cases the transport layer does
not handle, and the broker holds a wall-clock deadline over the whole chain so a
slow failure cannot become an unbounded one.

**An unrecognised error does not retry.** Default-deny, applied to spending: an
error nobody has classified, retried three times, costs three times as much and
has no particular reason to succeed. It fails over once and is recorded under
``unknown`` so the gap shows up in the log rather than in a bill.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class FailureKind(str, Enum):
    """What went wrong. One member per distinguishable, actionable cause."""

    TIMEOUT = "timeout"
    CONNECTION = "connection"
    RATE_LIMITED = "rate_limited"
    SERVER_ERROR = "server_error"
    OVERLOADED = "overloaded"
    AUTH = "auth"
    PAYMENT = "payment"
    MODEL_NOT_FOUND = "model_not_found"
    BAD_REQUEST = "bad_request"
    CONTEXT_LENGTH = "context_length"
    TRUNCATED = "truncated"
    CONTENT_FILTER = "content_filter"
    EMPTY_RESPONSE = "empty_response"
    MALFORMED_RESPONSE = "malformed_response"
    UNKNOWN = "unknown"


class FailureAction(str, Enum):
    """What to do about it."""

    RETRY_SAME = "retry_same"
    FAILOVER = "failover"
    STOP_REQUEST = "stop_request"
    STOP_CONFIG = "stop_config"


#: Kinds that mean *this provider is unhealthy*, and only those, count towards
#: opening its circuit breaker. A 400 we caused says nothing about the provider,
#: and letting it trip the breaker means one malformed payload can take every
#: model in the tier out of service for a minute.
PROVIDER_HEALTH_KINDS: frozenset[FailureKind] = frozenset(
    {
        FailureKind.TIMEOUT,
        FailureKind.CONNECTION,
        FailureKind.SERVER_ERROR,
        FailureKind.OVERLOADED,
        FailureKind.EMPTY_RESPONSE,
        FailureKind.MALFORMED_RESPONSE,
    }
)


@dataclass(frozen=True)
class Failure:
    """One classified failure, and what it implies."""

    kind: FailureKind
    action: FailureAction
    detail: str = ""
    status_code: int | None = None
    #: Seconds the server asked us to wait, when it said so.
    retry_after: float | None = None
    #: What the owner has to do. Empty when there is nothing for them to do.
    owner_action: str = ""

    @property
    def counts_against_provider(self) -> bool:
        return self.kind in PROVIDER_HEALTH_KINDS

    @property
    def is_terminal(self) -> bool:
        return self.action in (FailureAction.STOP_REQUEST, FailureAction.STOP_CONFIG)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "action": self.action.value,
            "detail": self.detail,
            "status_code": self.status_code,
            "retry_after": self.retry_after,
            "owner_action": self.owner_action,
            "counts_against_provider": self.counts_against_provider,
        }


#: Providers do not agree on wording, so matching is on phrases rather than on
#: any one vendor's error schema. Order matters: the first match wins, and the
#: specific patterns are listed before the general ones.
_PHRASE_RULES: tuple[tuple[re.Pattern[str], FailureKind], ...] = (
    (re.compile(r"\bmax_tokens\b|ran out of room|finish_reason: ?length", re.I), FailureKind.TRUNCATED),
    (re.compile(r"context length|context_length|too many tokens|maximum context", re.I), FailureKind.CONTEXT_LENGTH),
    # `refus` alone matched "Connection refused" and filed a dead network as a
    # content filter. Patterns on an error path get exercised by text nobody
    # chose, so each alternative here has to be specific enough to be wrong
    # about only what it is for.
    (
        re.compile(
            r"content[ _-]?filter|safety (?:filter|system|policy|settings)"
            r"|blocked by (?:the )?(?:safety|content|moderation)"
            r"|refused to (?:answer|respond|generate|comply)",
            re.I,
        ),
        FailureKind.CONTENT_FILTER,
    ),
    (re.compile(r"did not contain (text|message) (output|content)|no message content|returned nothing", re.I), FailureKind.EMPTY_RESPONSE),
    (re.compile(r"non-JSON|invalid JSON|malformed JSON|must contain a JSON", re.I), FailureKind.MALFORMED_RESPONSE),
    (re.compile(r"insufficient|quota exceeded|billing|payment|credit", re.I), FailureKind.PAYMENT),
    (re.compile(r"\bapi[ _]?key\b|unauthor|forbidden|invalid.*token|authentication", re.I), FailureKind.AUTH),
    (re.compile(r"model.*(not found|does not exist|unknown)|unknown model", re.I), FailureKind.MODEL_NOT_FOUND),
    (re.compile(r"rate ?limit|too many requests", re.I), FailureKind.RATE_LIMITED),
    (re.compile(r"overloaded|capacity", re.I), FailureKind.OVERLOADED),
    (re.compile(r"timed? ?out|timeout", re.I), FailureKind.TIMEOUT),
    (re.compile(r"connection|network|dns|unreachable|refused|reset by peer", re.I), FailureKind.CONNECTION),
)

#: HTTP status → kind, for the statuses that mean one specific thing.
_STATUS_KINDS: dict[int, FailureKind] = {
    401: FailureKind.AUTH,
    403: FailureKind.AUTH,
    402: FailureKind.PAYMENT,
    404: FailureKind.MODEL_NOT_FOUND,
    408: FailureKind.TIMEOUT,
    413: FailureKind.CONTEXT_LENGTH,
    422: FailureKind.BAD_REQUEST,
    429: FailureKind.RATE_LIMITED,
    529: FailureKind.OVERLOADED,
}

_ACTIONS: dict[FailureKind, FailureAction] = {
    # Transport already retried these three times; a fourth on the same model is
    # not resilience, so move on.
    FailureKind.TIMEOUT: FailureAction.FAILOVER,
    FailureKind.CONNECTION: FailureAction.FAILOVER,
    FailureKind.SERVER_ERROR: FailureAction.FAILOVER,
    FailureKind.OVERLOADED: FailureAction.FAILOVER,
    # The server usually says how long. Waiting is cheaper than spending another
    # provider's budget, so this is the one kind worth asking again for.
    FailureKind.RATE_LIMITED: FailureAction.RETRY_SAME,
    # Another model will not fix a broken key, a missing card, or a model name
    # that does not exist. Failing over is what hides these.
    FailureKind.AUTH: FailureAction.STOP_CONFIG,
    FailureKind.PAYMENT: FailureAction.STOP_CONFIG,
    FailureKind.MODEL_NOT_FOUND: FailureAction.STOP_CONFIG,
    FailureKind.TRUNCATED: FailureAction.STOP_CONFIG,
    # Our payload, not their service. Every model rejects it identically.
    FailureKind.BAD_REQUEST: FailureAction.STOP_REQUEST,
    FailureKind.CONTEXT_LENGTH: FailureAction.STOP_REQUEST,
    # These are about this model specifically, so another one may well work.
    FailureKind.CONTENT_FILTER: FailureAction.FAILOVER,
    FailureKind.EMPTY_RESPONSE: FailureAction.FAILOVER,
    FailureKind.MALFORMED_RESPONSE: FailureAction.FAILOVER,
    # Default-deny on spending: try one alternative, do not retry blindly.
    FailureKind.UNKNOWN: FailureAction.FAILOVER,
}

_OWNER_ACTIONS: dict[FailureKind, str] = {
    FailureKind.AUTH: (
        "The provider rejected the API key. Reconnect it in Connectors, or set "
        "OFFSETX_AI_<PROVIDER>_KEY. Nothing was sent to another model, because "
        "failing over would have hidden this."
    ),
    FailureKind.PAYMENT: (
        "The provider refused the call for billing reasons — out of credit, or "
        "a plan that does not cover this model."
    ),
    FailureKind.MODEL_NOT_FOUND: (
        "The provider does not have the model named in config/providers.yaml. "
        "Run 'Find models' in Connectors to see what this key actually reaches."
    ),
    FailureKind.TRUNCATED: (
        "The model hit its output limit before finishing. Raise max_tokens for "
        "it in config/providers.yaml under request_options. Another model would "
        "hit the same ceiling."
    ),
    FailureKind.CONTEXT_LENGTH: (
        "The payload is longer than the model's context window. Shorten the "
        "input rather than switching model — this is about size, not vendor."
    ),
    FailureKind.BAD_REQUEST: (
        "The provider rejected the request as malformed. This is an off_CRM "
        "bug, not a provider problem; the egress log holds the exact payload."
    ),
}

_STATUS_RE = re.compile(r"\b(\d{3})\b")
_RETRY_AFTER_RE = re.compile(r"retry[- _]?after\D{0,10}(\d+(?:\.\d+)?)", re.I)


def _status_from(text: str) -> int | None:
    """Pull an HTTP status out of a provider message.

    ``ProviderError`` is a plain ``RuntimeError`` whose message reads
    ``"AI provider returned 429: ..."`` — the status is in the text and nowhere
    else, so it has to be read back out. Only the leading ``returned NNN`` form
    is trusted; a bare three-digit number elsewhere in a body is far more likely
    to be part of the provider's prose than its status.
    """
    match = re.search(r"returned\s+(\d{3})\b", text, re.I)
    if match:
        return int(match.group(1))
    return None


def classify(error: object, *, status_code: int | None = None) -> Failure:
    """Work out what a provider failure was, and what should happen next.

    Takes the exception or its message. Deliberately tolerant about its input:
    this runs on the error path, and a classifier that raises while classifying
    would replace a useful message with a useless one.
    """
    text = str(error or "").strip()
    code = status_code if status_code is not None else _status_from(text)

    kind: FailureKind | None = None
    if code is not None:
        kind = _STATUS_KINDS.get(code)
        if kind is None and 500 <= code <= 599:
            kind = FailureKind.SERVER_ERROR
        elif kind is None and 400 <= code <= 499:
            kind = FailureKind.BAD_REQUEST

    # Phrases refine a status rather than only filling in for a missing one: a
    # 400 that says "context length" is a different problem from a 400 that says
    # the JSON was wrong, and they need different answers.
    for pattern, phrase_kind in _PHRASE_RULES:
        if pattern.search(text):
            if kind in (None, FailureKind.BAD_REQUEST, FailureKind.SERVER_ERROR):
                kind = phrase_kind
            break

    if kind is None:
        kind = FailureKind.UNKNOWN

    retry_after: float | None = None
    found = _RETRY_AFTER_RE.search(text)
    if found:
        try:
            retry_after = min(300.0, max(0.0, float(found.group(1))))
        except ValueError:
            retry_after = None

    return Failure(
        kind=kind,
        action=_ACTIONS.get(kind, FailureAction.FAILOVER),
        detail=text[:500],
        status_code=code,
        retry_after=retry_after,
        owner_action=_OWNER_ACTIONS.get(kind, ""),
    )


def describe_kinds() -> list[dict[str, Any]]:
    """Every kind with its action and owner guidance, for the API and the docs."""
    return [
        {
            "kind": kind.value,
            "action": _ACTIONS.get(kind, FailureAction.FAILOVER).value,
            "counts_against_provider": kind in PROVIDER_HEALTH_KINDS,
            "owner_action": _OWNER_ACTIONS.get(kind, ""),
        }
        for kind in FailureKind
    ]
