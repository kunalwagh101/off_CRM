"""What the browser agent may do, where, and how fast.

Connected-platform policy is declared in ``platforms.yaml``.  `S-03.02.05`
means adding a platform must not require another Python branch for identity,
budget or pacing. Generic browser safety remains code because a platform row
must never be able to weaken localhost, metadata, scheme or CRM boundaries.

Three decisions are enforced here: may the browser navigate there, how quickly
may it act, and may it run unattended. Sensitive actions still receive a
countdown rather than a prompt-time suggestion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from .platform_registry import platform_domains

#: Actions that change something outside the browser. Every one of these gets a
#: countdown before it fires, whatever site it is on.
SENSITIVE_ACTIONS = frozenset({"submit", "send", "delete", "purchase", "publish", "upload"})


@dataclass(frozen=True)
class DomainRule:
    """What the agent may do on one host."""

    #: Match on a hostname suffix, so ``www.linkedin.com`` and
    #: ``uk.linkedin.com`` are governed by the same declaration.
    suffix: str
    label: str
    min_seconds_between_actions: float = 0.0
    unattended: bool = True
    refuse: tuple[str, ...] = ()
    confirm: tuple[str, ...] = ()
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "suffix": self.suffix,
            "label": self.label,
            "min_seconds_between_actions": self.min_seconds_between_actions,
            "unattended": self.unattended,
            "refuse": list(self.refuse),
            "confirm": list(self.confirm),
            "note": self.note,
        }


#: The default: anywhere not named below.
OPEN_WEB = DomainRule(
    suffix="*",
    label="the open web",
    min_seconds_between_actions=0.4,
    unattended=True,
    note="Ordinary sites. Paced enough to be polite, not enough to be slow.",
)


def _declared_platform_rules() -> tuple[DomainRule, ...]:
    """Convert the validated registry into the policy objects Page already uses."""
    return tuple(
        DomainRule(
            suffix=domain.suffix,
            label=domain.label,
            min_seconds_between_actions=domain.min_seconds_between_actions,
            unattended=domain.unattended,
            refuse=domain.refuse,
            confirm=domain.confirm,
            note=domain.note,
        )
        for domain in platform_domains()
    )


#: Gmail is deliberately not a connected-platform declaration. off_CRM's CRM
#: boundary says the browser may not turn the user's mailbox into model input;
#: this host-specific action policy remains explicit and attended-only.
GMAIL = DomainRule(
    suffix="mail.google.com",
    label="Gmail",
    min_seconds_between_actions=1.5,
    unattended=False,
    confirm=("send", "delete", "submit"),
    note="Sending mail as you is the highest-consequence thing here.",
)


def _ordered_rules() -> tuple[DomainRule, ...]:
    """Most-specific hostname suffix wins, independent of declaration order.

    A broad row such as ``google.com`` must never shadow the explicit
    ``mail.google.com`` CRM boundary. The same rule makes nested platform
    domains deterministic rather than dependent on YAML ordering.
    """
    rules = (GMAIL,) + _declared_platform_rules()
    return tuple(sorted(rules, key=lambda rule: len(rule.suffix), reverse=True))


#: Platform-specific rows come from the single registry. Non-platform safety
#: exceptions remain code. A newly declared platform therefore appears here on
#: the next process start with no edit to this module.
RULES: tuple[DomainRule, ...] = _ordered_rules()

#: Hosts nothing may reach, ever. These resolve to the machine off_CRM is
#: running on; letting a page point the browser at them turns it into a proxy
#: into the host/network. Registry configuration cannot relax this list.
NEVER = (
    "localhost", "127.0.0.1", "0.0.0.0", "::1",
    "169.254.169.254",
    "metadata.google.internal",
)


class Refused(ValueError):
    """The policy said no. The message says why and what to do instead."""


def host_of(url: str) -> str:
    try:
        return (urlsplit(str(url)).hostname or "").lower()
    except ValueError:
        return ""


def rule_for(url: str) -> DomainRule:
    """The most-specific rule governing one URL; subdomains inherit."""
    host = host_of(url)
    if not host:
        return OPEN_WEB
    for rule in RULES:
        if host == rule.suffix or host.endswith("." + rule.suffix):
            return rule
    return OPEN_WEB


def check_navigation(url: str, *, unattended: bool = False) -> DomainRule:
    """May the agent go here, in this mode? Returns the rule, or refuses."""
    text = str(url or "").strip()
    try:
        scheme = (urlsplit(text).scheme or "").lower()
    except ValueError as exc:
        raise Refused(f"Refusing an invalid URL: {exc}") from exc
    if scheme in ("file", "chrome", "chrome-extension", "devtools", "view-source"):
        raise Refused(
            f"{scheme}: URLs are refused. The agent drives the web, and a page "
            "that can talk it into opening a local file can read the machine."
        )
    if scheme not in ("http", "https", "about", "data", ""):
        raise Refused(f"Refusing an unrecognised scheme: {scheme}:")

    host = host_of(text)
    if host in NEVER or host.endswith(".internal"):
        raise Refused(
            f"{host} is on the machine itself or inside its network. An agent "
            "that can be pointed there is a way into your network, so it cannot be."
        )

    rule = rule_for(text)
    if unattended and not rule.unattended:
        raise Refused(
            f"{rule.label} is attended-only. The agent will go there when you ask "
            "it to, in a run you can watch — but not on a schedule. Running "
            "unattended against it is what breaches their terms and loses the "
            "account, and it is a different act from you reading a page."
        )
    return rule


def check_action(action: str, url: str, *, unattended: bool = False) -> tuple[DomainRule, bool]:
    """May this action happen here? Returns ``(rule, needs_countdown)``."""
    rule = check_navigation(url, unattended=unattended)
    name = str(action or "").strip().lower()
    if name in rule.refuse:
        raise Refused(f"{name!r} is refused on {rule.label}.")
    needs_countdown = name in SENSITIVE_ACTIONS or name in rule.confirm
    return rule, needs_countdown


def catalogue() -> dict[str, Any]:
    """Every rule, for a settings screen that shows what the agent may do."""
    return {
        "default": OPEN_WEB.to_dict(),
        "rules": [rule.to_dict() for rule in RULES],
        "sensitive_actions": sorted(SENSITIVE_ACTIONS),
        "never": list(NEVER),
    }
