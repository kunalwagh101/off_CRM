"""Noticing a wall the agent must not climb.  `S-11.03.01`

A CAPTCHA, a sign-in form or a 2FA prompt is not a failure and not a puzzle.
It is the page saying *a person has to do this part*. Without this the agent
does the only thing left to it: burns its remaining budget clicking around a
page it can never get past, and reports `stuck` — which tells the owner that
something went wrong but not that **they** are the fix.

**Nothing here solves, evades or fingerprints around a challenge, and nothing
here ever will.** That was decided on 2026-09-06 and written up in `RETRO.md`:
enforcement on these platforms is account termination rather than a 429, so the
thing at risk is the asset the owner spent months building. This module's whole
job is to *recognise* a wall and get out of the way of the human.

---

**Why this one is allowed to stop a run, when `injection.py` is not.**

`injection.py` says at length that it must never be given the power to stop
anything without the trade being re-argued. So: re-argued here, and it comes out
differently, because the two detectors have opposite costs.

A wrong injection match costs one line in a trace — so those patterns are broad
enough to catch a rephrasing. A wrong match *here* pauses a run and asks the
owner to go and look. That is not free, so this reads structure rather than
prose and asks for corroboration before it speaks.

The asymmetry that makes it safe: pausing is **recoverable and cheap**. The
browser stays open on the page, no budget is spent (the pause happens before the
model is asked anything), and `S-11.01.03` resumes from the same step. A false
positive costs the owner a glance. A false *negative* costs a whole run's budget
spent against a locked door — so where the two errors are close, this leans
towards asking.

**Roles, not markup.** The accessibility tree has no "this is a password field"
flag — Chrome does not expose one, deliberately. So a password field is found by
its accessible name on an *editable* node, which is also what makes "Forgot
password?" (a link) and "Show password" (a button) not count.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..browser.perceive import Snapshot

#: Roles a person types into. A wall is a thing that wants input; a link or a
#: heading mentioning a password is a page *about* signing in, not a sign-in.
EDITABLE_ROLES = frozenset({"textbox", "searchbox", "combobox", "textarea"})

#: How much of the matched text is kept as evidence. It goes in the step's
#: capture artefact, never in `trace.jsonl` — the same rule the finding steps
#: and `injection.py` follow, and one several tests defend.
MAX_EVIDENCE_CHARS = 160


def _phrases(*expressions: str) -> "re.Pattern[str]":
    return re.compile("|".join(expressions), re.IGNORECASE)


#: A challenge widget announcing itself. These phrases do not turn up on a page
#: that is not one — which is what lets this fire on a single match.
CAPTCHA = _phrases(
    r"\bi'?m not a robot\b",
    r"\bi am not a robot\b",
    r"\bare you a robot\b",
    r"\brecaptcha\b",
    r"\bhcaptcha\b",
    r"\bverify (?:that )?you(?:'re| are) (?:a )?human\b",
    r"\bconfirm you(?:'re| are) (?:a )?human\b",
    r"\bchecking (?:if )?your browser\b",
    r"\bcomplete the (?:security )?challenge\b",
    r"\bunusual traffic from your computer\b",
)

#: A second factor being asked for. Needs a field to type it into as well — the
#: words alone appear in help pages and security-settings copy.
CODE_FIELD = _phrases(
    r"\b(?:verification|authentication|security|confirmation|login|access) code\b",
    r"\bone[- ]?time (?:code|password|passcode)\b",
    r"\b\d[- ]digit code\b",
    r"\bpasscode\b",
    r"\botp\b",
    # A field whose whole name is "code" is a code field. Matched only against
    # editable names, so a heading "Code of conduct" is not in scope here.
    r"^\s*(?:enter )?code\s*$",
)
TWO_FACTOR_LANGUAGE = _phrases(
    r"\btwo[- ]factor\b",
    r"\b2[- ]factor\b",
    r"\btwo[- ]step verification\b",
    r"\b2[- ]step verification\b",
    r"\bmulti[- ]factor\b",
    r"\benter the code we sent\b",
    r"\bcheck your (?:phone|authenticator)\b",
)

#: A sign-in form. The field is the signal; the button and the URL corroborate.
PASSWORD_FIELD = _phrases(r"\bpassword\b", r"\bpass ?phrase\b")
SIGN_IN_BUTTON = _phrases(
    r"^\s*(?:sign in|log in|login|signin)\b",
    r"\bcontinue with (?:google|apple|facebook|email|sso)\b",
    r"\bsign in to\b",
)
#: Anchored to whole path segments. An earlier version used `/auth\b`, which
#: matched `/help/two-factor-authentication` — a page *explaining* the wall,
#: which is the last page that should pause a run.
SIGN_IN_URL = _phrases(
    r"/(?:log[-_]?in|sign[-_]?in|signin|auth|authorize|oauth|sso|"
    r"sessions/new|accounts/login|checkpoint|challenge)(?:[/?#]|$)",
)


@dataclass(frozen=True, slots=True)
class Wall:
    """Something on the page only a person can get past."""

    #: What kind of wall, in the vocabulary the trace and the report speak.
    kind: str
    #: Which rule recognised it. This is what goes in the audit log, because it
    #: says what happened without putting page text in `trace.jsonl`.
    rule: str
    #: The text that matched, for the capture artefact beside the log.
    evidence: str
    url: str = ""

    #: Said to the owner. Names what was found and what only they can do about
    #: it — deliberately without quoting the page, so the same sentence is safe
    #: in the log, the report and a notification.
    def describe(self) -> str:
        what = {
            "captcha": "A CAPTCHA or bot check is in the way",
            "sign_in": "A sign-in form is in the way",
            "two_factor": "A two-factor prompt is in the way",
        }.get(self.kind, "Something only a person can pass is in the way")
        return (
            f"{what} ({self.rule}). off_CRM does not solve, evade or work around "
            "these. The browser is still open on that page: deal with it there "
            "and resume the run, which carries on from this step."
        )

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "rule": self.rule,
                "evidence": self.evidence, "url": self.url}


def look(snapshot: Snapshot) -> Wall | None:
    """The wall on this page, if there is one.

    Checked hardest-first: a 2FA page usually carries sign-in furniture too, and
    reporting it as a sign-in form would send the owner looking for the wrong
    thing.
    """
    names = snapshot.names
    editable = [
        node.name.strip().lower()
        for node in snapshot.nodes
        if node.role in EDITABLE_ROLES and not node.disabled and node.name.strip()
    ]
    url = str(snapshot.url or "")
    # The title is read alongside the names because a Cloudflare interstitial
    # is often a title and one line of text with no named nodes at all.
    surface = names + [str(snapshot.title or "").strip().lower()]

    hit = _first(CAPTCHA, surface)
    if hit:
        return Wall(kind="captcha", rule="challenge_widget", evidence=hit, url=url)

    hit = _first(CODE_FIELD, editable)
    if hit:
        return Wall(kind="two_factor", rule="code_field", evidence=hit, url=url)
    # Second-factor *language* is not enough on its own: a help article about
    # two-step verification says all of it, and a site search box would make it
    # a wall. It counts only where a sign-in actually happens.
    hit = _first(TWO_FACTOR_LANGUAGE, surface)
    if hit and editable and SIGN_IN_URL.search(url):
        return Wall(kind="two_factor", rule="second_factor_prompt", evidence=hit, url=url)

    hit = _first(PASSWORD_FIELD, editable)
    if hit:
        return Wall(kind="sign_in", rule="password_field", evidence=hit, url=url)
    # No password field, but a login URL with something to type and a button
    # that submits it. This is the passwordless and "enter your email first"
    # half of sign-in, which is most of them now.
    if SIGN_IN_URL.search(url) and editable and _first(SIGN_IN_BUTTON, names):
        return Wall(kind="sign_in", rule="sign_in_page",
                    evidence=_excerpt(url), url=url)
    return None


def _first(pattern: "re.Pattern[str]", texts: "list[str]") -> str:
    for text in texts:
        if text and pattern.search(text):
            return _excerpt(text)
    return ""


def _excerpt(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()[:MAX_EVIDENCE_CHARS]
