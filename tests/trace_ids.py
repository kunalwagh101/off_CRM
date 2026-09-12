"""Referring to a trace step without counting them.  `S-06.02.14`

Five test files named `step-000002` and meant "the read action". Adding any
step earlier in a run shifts every id after it, so a story that has nothing to
do with provenance breaks the provenance tests. It happened twice: a `finding`
step in `S-11.01.03`, and an estimate in `S-06.01.03`.

Both times the fix was to bump a number, which buys one story of quiet.

---

**Why the obvious fix does not work.** A scripted decision is written *before*
the run exists, and a decision that cites its evidence has to name a step id.
There is nothing to look up yet.

**What a real model actually does** is cite the id the run just handed it. The
observation carries `step_id=step-000002` into the prompt, and the model repeats
it back. So a scripted answer says `{cite}` and the broker double fills it in
from the instructions it was just given — which is both immune to renumbering
and a closer imitation of the thing being stood in for.

    _done({"company": _finding("Acme Ltd", "Company: Acme Ltd", CITE)})

**What is deliberately left alone.** Tests *of* the numbering — that a trace
with no ids gets them assigned in order, that `step-000002` follows
`step-000001` — keep their literals. There the number is the subject rather
than a way of pointing at something.
"""

from __future__ import annotations

import re

#: Put this where a scripted answer would name a step id. The broker double
#: replaces it with the id the run put in front of the model on that call.
CITE = "{cite}"

#: `step_id=step-000002`, as `_observation` writes it into the prompt.
_OFFERED = re.compile(r"step_id=(step-\d+)")


def offered_step_id(instructions: str) -> str:
    """The evidence id the run most recently offered the model.

    The last one in the prompt, not the first: a run that has read twice has
    offered two, and the one being cited is the one just captured.
    """
    found = _OFFERED.findall(str(instructions or ""))
    return found[-1] if found else ""


def fill_citations(text: str, instructions: str) -> str:
    """Answer as a model would: cite the step the run just pointed at."""
    if CITE not in text:
        return text
    return text.replace(CITE, offered_step_id(instructions))


def step_id_of(trace, kind: str, *, occurrence: int = 0) -> str:
    """The id of the *n*th step of some kind, found rather than counted.

    For assertions after a run: `step_id_of(trace, "action")` is "the first
    action", whatever number it ended up with.
    """
    matching = [step for step in trace.read() if step.kind == kind]
    if occurrence >= len(matching):
        raise AssertionError(
            f"the run has {len(matching)} {kind!r} step(s); there is no "
            f"occurrence {occurrence}"
        )
    return matching[occurrence].step_id
