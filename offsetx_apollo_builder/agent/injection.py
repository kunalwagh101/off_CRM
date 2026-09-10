"""Noticing when a page tries to give the agent orders.  `S-11.03.02`

**This changes the record, not the behaviour, and that is the design rather
than a shortcut.** Containment is already structural: a model driving this
browser can only name one of ten verbs, cannot supply code, and cannot reach the
CRM — `payload.py` builds every outbound request from an allowlist starting
empty. An instruction sitting on a page has nothing to reach for. What was
missing is that an attack left *no mark at all*: the run carried on correctly and
nobody ever learned that somebody had tried.

So this is a smoke alarm, not a fire door. The fire door was built first.

---

**Why false positives are cheap here, and why that shapes the patterns.**

Because nothing is blocked, a wrong match costs one line in a trace. That is a
different economy from the browser guard, where a wrong match costs a run. It
means the patterns can be broad enough to catch a rephrasing, and it means this
module must never be given the power to stop anything without that trade being
re-argued.

It also means the honest name for what this reports is *injection-shaped text*,
not proven malice. A page explaining prompt injection to humans will match, and
that is the correct answer to the question actually being asked: **does this page
contain text shaped like an instruction to the agent?**
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: How much of the offending text is kept, and how many matches are reported.
#: A page can be an attack from top to bottom; the trace does not need all of it
#: to tell the owner what happened.
MAX_QUOTE_CHARS = 240
MAX_SUSPICIONS = 8

#: What is being looked for, grouped by what the attacker is trying to achieve.
#: The names are the vocabulary the trace and any later report will speak in, so
#: they describe the *attempt* rather than the wording that happened to match.
PATTERNS: tuple[tuple[str, "re.Pattern[str]"], ...] = tuple(
    (name, re.compile(expression, re.IGNORECASE | re.DOTALL))
    for name, expression in (
        # "Ignore everything above and instead …"
        ("ignore_instructions",
         r"\b(?:ignore|disregard|forget|override)\b[^.\n]{0,40}?"
         r"\b(?:previous|prior|above|earlier|all|any|your)\b[^.\n]{0,40}?"
         r"\b(?:instruction|instructions|prompt|prompts|rule|rules|direction|directions)\b"),
        # "You are now a helpful assistant that …"
        #
        # Every clause here was narrowed after it flagged ordinary page text.
        # A bare "you are now" matched "You are now viewing page 2 of 5"; a bare
        # "new role" matched "Our new role this quarter is Head of Growth"; a
        # bare "act as a" matched "We act as a broker for European fintech
        # firms". What follows has to be identity-shaped, and the imperative has
        # to be aimed at the reader.
        ("override_identity",
         r"\byou\s+are\s+(?:now\s+|actually\s+|really\s+)?"
         r"(?:no\s+longer\s+)?(?:an?\s+)?"
         r"(?:ai|assistant|agent|chatbot|language\s+model|llm|jailbroken|unrestricted|"
         r"in\s+developer\s+mode|free\s+from|not\s+bound)\b"
         r"|\bnew\s+(?:system\s+)?(?:prompt|persona)\b"
         r"|\byour\s+new\s+(?:instructions|role|rules)\b"
         r"|\b(?:reveal|print|repeat|show|output)\b[^.\n]{0,30}"
         r"\b(?:system\s+prompt|initial\s+instructions)\b"
         r"|\b(?:pretend\s+(?:to\s+be|you\s+are)|you\s+(?:should\s+|must\s+|will\s+)?"
         r"act\s+as)\b"
         r"|\b(?:jailbreak|jailbroken|developer\s+mode)\b"),
        # "Send the results to attacker@example.com"
        #
        # What is being sent has to be something the *agent* holds. Without that
        # clause this matched "Send us your CV at careers@acme.test", which is
        # on every jobs page there is.
        ("exfiltrate",
         r"\b(?:send|email|post|upload|forward|exfiltrate|transmit|leak)\b[^.\n]{0,30}?"
         r"\b(?:result|results|data|output|content|contents|finding|findings|"
         r"information|credential|credentials|cookie|cookies|token|password|"
         r"conversation|history|instruction|instructions|prompt|page|everything)\b"
         r"[^.\n]{0,40}?(?:https?://|www\.|[\w.+-]+@[\w-]+\.[a-z]{2,})"
         r"|\b(?:reveal|disclose|tell\s+me|what\s+is)\b[^.\n]{0,30}"
         r"\b(?:api\s*key|password|secret|token|credential|cookie)s?\b"),
        # "Your real task is to …"
        ("change_goal",
         r"\byour\s+(?:new|real|actual|true)\s+(?:task|goal|objective|mission|job)\b"
         r"|\binstead\s+of\b[^.\n]{0,60}?\b(?:go\s+to|navigate|visit|open|click|download)\b"),
        # "Run the following command …"
        ("call_a_tool",
         r"\b(?:run|execute|eval|evaluate)\b[^.\n]{0,20}\b(?:the\s+)?"
         r"(?:following|this|these)\b[^.\n]{0,20}"
         r"\b(?:command|commands|code|script|snippet|javascript|python|shell)\b"),
        # Text aimed past the human at whatever is reading the page.
        ("addressed_to_the_model",
         r"\b(?:attention|note\s+to|message\s+for|important)\b[^.\n]{0,20}"
         r"\b(?:ai|assistant|agent|language\s+model|llm|chatbot|bot)\b"
         r"|\bas\s+an?\s+(?:ai|assistant|language\s+model)\b"),
    )
)


@dataclass(frozen=True, slots=True)
class Suspicion:
    """One stretch of text that reads like an instruction to the agent."""

    rule: str
    quote: str
    offset: int

    def to_dict(self) -> dict[str, object]:
        return {"rule": self.rule, "quote": self.quote, "offset": self.offset}


def scan(text: str) -> tuple[Suspicion, ...]:
    """Every distinct injection-shaped passage in one piece of page text.

    Overlapping matches from different rules are kept — an attack that both
    overrides the identity and names an exfiltration address is two facts about
    it, and reporting one would understate what was found. Repeats of the *same*
    rule at the *same* place are not, because a page repeating itself is one
    attempt seen twice.
    """
    raw = str(text or "")
    if not raw.strip():
        return ()
    # Whitespace is collapsed **before** matching, not after. The patterns use
    # `[^.\n]` to stay inside one sentence, which means a newline stops them —
    # so an attacker who wraps "ignore all previous instructions" across three
    # lines would otherwise walk straight past. Page text arrives full of line
    # breaks and indentation, so that is not a hypothetical layout.
    #
    # Found by a test asserting the quote was readable: it split the attack over
    # newlines the way a real page does, and nothing matched at all.
    body = re.sub(r"\s+", " ", raw)

    found: list[Suspicion] = []
    seen: set[tuple[str, int]] = set()
    for name, pattern in PATTERNS:
        for match in pattern.finditer(body):
            key = (name, match.start())
            if key in seen:
                continue
            seen.add(key)
            found.append(
                Suspicion(
                    rule=name,
                    quote=_excerpt(body, match.start(), match.end()),
                    offset=match.start(),
                )
            )
            if len(found) >= MAX_SUSPICIONS:
                return tuple(sorted(found, key=lambda item: item.offset))
    return tuple(sorted(found, key=lambda item: item.offset))


def _excerpt(body: str, start: int, end: int) -> str:
    """The match with a little of what surrounds it, so it reads as a sentence.

    `body` is already whitespace-collapsed by `scan`, so offsets here refer to
    that normalised text — which is also what makes the quote readable rather
    than 90% blank space.
    """
    padding = max(0, (MAX_QUOTE_CHARS - (end - start)) // 2)
    window = body[max(0, start - padding): end + padding]
    return re.sub(r"\s+", " ", window).strip()[:MAX_QUOTE_CHARS]
