"""What the agent may do, where, and how fast.

`discovery.py` has always refused LinkedIn, Instagram, Facebook, TikTok and X.
That refusal was right, and it is about **anonymous headless scraping** — going
at somebody's site with no session, at machine speed, taking data that was never
offered to you.

Driving your own logged-in browser is a different act. You opening LinkedIn and
reading a profile you can already see is not scraping; it is you, using a
computer. An agent doing it in your session, on your machine, at your pace, is
that act automated.

**So this is a separate policy, not a hole in the old one.** The headless
engines keep their block list. This file governs the browser agent, and it draws
the line somewhere else — at *volume and autonomy* rather than at *domain*.

Since `S-03.02.05`, account-platform domain rules are declared in the same
registry row as sign-in signals and budgets. Host-only safety rules such as
Gmail remain explicit here because they are not account-platform declarations.

---

**Three things every domain gets a decision about.**

*May the agent go here at all?* Almost always yes. The internet is for reading.

*How fast?* A per-host floor between actions. On a site being driven through
your own session this is set to human pace, not machine pace, because the thing
that gets an account restricted is rhythm — thirty profile views a minute is not
something a person does, and no amount of good intent makes it look like one.

*May it run here unattended?* This is the one that matters. A routine firing at
3am against LinkedIn is the thing that breaches their terms, loses the account,
and — where the people are in the EU or UK — collects personal data with no
lawful basis and no notice to anyone. So session-gated social platforms are
**attended-only**: the agent may go there when you ask it to, in a run you can
watch. A schedule may not send it there.

---

**Sensitive actions get a countdown, not a dialog.** A confirm box trains people
to click through it; that is what confirm boxes are for. A visible five-second
delay with a cancel button does not, because there is nothing to click.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from .registry import load_platforms

#: Actions that change something outside the browser. Every one of these gets a
#: countdown before it fires, whatever site it is on.
SENSITIVE_ACTIONS = frozenset({"submit", "send", "delete", "purchase", "publish", "upload"})


@dataclass(frozen=True)
class DomainRule:
    """What the agent may do on one host."""

    #: Match on the registrable suffix, so `www.linkedin.com` and
    #: `uk.linkedin.com` are the same rule.
    suffix: str
    label: str
    #: Seconds between actions. The single most important number here.
    min_seconds_between_actions: float = 0.0
    #: Whether an unattended routine may drive this host.
    unattended: bool = True
    #: Actions refused outright on this host, whatever the mode.
    refuse: tuple[str, ...] = ()
    #: Actions that always get a countdown here, on top of SENSITIVE_ACTIONS.
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


def _platform_rules() -> tuple[DomainRule, ...]:
    rules: list[DomainRule] = []
    for platform in load_platforms().values():
        for declared in platform.domains:
            rules.append(DomainRule(
                suffix=declared.suffix,
                label=platform.label,
                min_seconds_between_actions=declared.min_seconds_between_actions,
                unattended=declared.unattended,
                refuse=declared.refuse,
                confirm=declared.confirm,
                note=declared.note or platform.note,
            ))
    return tuple(rules)


#: Rules that protect a host but do not describe a browser-account platform.
#: Gmail is an email transport surface, not a row in the social/platform sign-in
#: catalogue, so pretending it is one would require fake sign-in signals and a
#: fake account budget just to satisfy a schema.
EXTRA_RULES: tuple[DomainRule, ...] = (
    DomainRule(
        suffix="mail.google.com",
        label="Gmail",
        min_seconds_between_actions=1.5,
        unattended=False,
        confirm=("send", "delete", "submit"),
        note="Sending mail as you is the highest-consequence thing here.",
    ),
)

RULES: tuple[DomainRule, ...] = (*_platform_rules(), *EXTRA_RULES)

#: Hosts nothing may reach, ever. Not a policy choice — these resolve to the
#: machine off_CRM is running on, and a page that can be talked into fetching
#: one of them is the classic way an agent becomes a proxy into your network.
NEVER = (
    "localhost", "127.0.0.1", "0.0.0.0", "::1",
    "169.254.169.254",  # the cloud metadata endpoint, and the reason this list exists
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
    """The rule governing one URL. Matches on suffix, so subdomains inherit."""
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
    scheme = (urlsplit(text).scheme or "").lower()
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
