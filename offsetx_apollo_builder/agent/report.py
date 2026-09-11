"""One page per run, showing every claim beside its evidence.  `S-11.04.01`

Provenance has been bound to every fact since `S-11.02.02` — url, timestamp,
trace step, screenshot, quote. All of it sits in a JSONL file and a directory of
PNGs, which is the right way to *store* an audit trail and a hopeless way to
*read* one. Trusting the output was still a decision made without looking.

The report is written into the run's own directory, so the screenshots it points
at are the files beside it and it opens offline with no server. It carries real
harvested values, which is the point of it, and it inherits the directory's
`0700` and its own `0600` accordingly.

---

**This file renders attacker-controlled text, and that is the thing to get right.**

Every quote in it came off a web page. Every element name came off a web page.
The injection excerpts came off a page that was *actively trying* to be
interpreted as instructions. Write any of that into HTML unescaped and the
report proving the agent was not fooled becomes stored XSS in the owner's
browser — opened from `file://`, which is a more forgiving origin than most.

So: everything user- or page-derived goes through `_text`, there is no template
interpolation that bypasses it, and a test feeds a run a page full of `<script>`
and asserts the tags come back inert. No CSS or JS is loaded from anywhere; the
style is inline and static.
"""

from __future__ import annotations

import html
import json
import os
from pathlib import Path
from typing import Any, Iterable

from ..browser.trace import Step, Trace

REPORT_FILENAME = "report.html"

#: Endings a run can have. Ordered worst-first so the summary line leads with
#: the thing the owner has to act on.
ENDINGS = (
    "stuck", "looping", "stalled", "budget_exhausted", "over_budget",
    "needs_human", "human_gate", "needs_confirmation", "incomplete", "completed",
)

#: Step kinds that are worth colouring, and what they mean to a reader.
TONE = {
    "injection_suspected": "attack",
    "duplicate_refused": "guard",
    "result_field_unsupported": "guard",
    "result_field_unsourced": "guard",
    "result_field_dropped": "guard",
    "retry": "warn",
    "stuck": "bad", "looping": "bad", "stalled": "bad",
    "budget_exhausted": "bad", "incomplete": "bad",
    # Not "bad": nothing broke. These are endings that are waiting on the owner,
    # which is a different thing to read at a glance.  `S-11.03.01`
    "needs_human": "warn", "human_gate": "warn", "needs_confirmation": "warn",
    "completed": "good", "finding": "good", "resumed": "note", "run_started": "note",
}

#: Tones whose ending has to say why at the top of the page. A run that stopped
#: is a run somebody has to act on, and making them scroll for the reason is how
#: a report goes unread.
MUST_EXPLAIN = ("bad", "warn")

STYLE = """
:root{color-scheme:light dark}
body{font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;
 margin:0;padding:28px;background:#f6f6f4;color:#191919}
@media(prefers-color-scheme:dark){body{background:#141414;color:#e8e8e6}}
main{max-width:960px;margin:0 auto}
h1{font-size:22px;margin:0 0 4px}
h2{font-size:15px;text-transform:uppercase;letter-spacing:.09em;margin:34px 0 10px;
 color:#6a6a68}
.goal{font-size:17px;margin:0 0 18px}
.facts{display:grid;gap:12px}
.card{background:#fff;border:1px solid #ddd;border-radius:5px;padding:14px 16px}
@media(prefers-color-scheme:dark){.card{background:#1e1e1e;border-color:#333}}
.k{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;color:#6a6a68}
.v{font-size:17px;font-weight:600;margin:2px 0 8px;overflow-wrap:anywhere}
.q{font-style:italic;border-left:3px solid #ccc;padding-left:10px;margin:8px 0;
 overflow-wrap:anywhere}
.meta{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;color:#6a6a68;
 overflow-wrap:anywhere}
.meta a{color:inherit}
img{max-width:220px;border:1px solid #ddd;border-radius:3px;margin-top:8px;display:block}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;font:11px ui-monospace,monospace;text-transform:uppercase;
 letter-spacing:.07em;color:#6a6a68;border-bottom:1px solid #999;padding:6px 8px}
td{padding:6px 8px;border-bottom:1px solid #e5e5e3;vertical-align:top;
 overflow-wrap:anywhere}
@media(prefers-color-scheme:dark){td{border-color:#2c2c2c}}
td.n{font:12px ui-monospace,monospace;white-space:nowrap;text-align:right}
.pill{display:inline-block;font:11px ui-monospace,monospace;padding:2px 7px;
 border-radius:3px;text-transform:uppercase;letter-spacing:.05em}
.good{background:#dcefe2;color:#1c5b38}.bad{background:#f6dcd6;color:#8a2c14}
.warn{background:#f6eed4;color:#6a5410}.attack{background:#f0d9f4;color:#5f1c6b}
.guard{background:#dde5f4;color:#1e3d70}.note{background:#e6e6e3;color:#4a4a48}
.empty{color:#6a6a68;font-style:italic}
footer{margin-top:36px;font:12px ui-monospace,monospace;color:#6a6a68}
"""


def _text(value: object) -> str:
    """The only way anything reaches the page. Escapes quotes as well as tags."""
    return html.escape(str(value if value is not None else ""), quote=True)


def _findings(trace: Trace) -> list[dict[str, Any]]:
    """Every accepted fact, read back out of its capture artefact."""
    found = []
    for step in trace.read():
        if step.kind != "finding":
            continue
        try:
            item = json.loads(trace.captured_text(step) or "{}")
        except ValueError:
            continue
        if isinstance(item, dict) and item.get("field"):
            found.append(item)
    return found


def _ending(steps: list[Step]) -> Step | None:
    for step in reversed(steps):
        if step.kind in ENDINGS:
            return step
    return None


def _goal(trace: Trace) -> str:
    for step in trace.read():
        if step.kind == "run_started":
            try:
                return str(json.loads(trace.captured_text(step) or "{}").get("goal") or "")
            except ValueError:
                return ""
    return ""


def _image(step: Step) -> str:
    """A screenshot, only when its filename is local to the run directory.

    The filename comes off the trace, and a trace is a file. A name that tried
    to walk out of the directory would turn this report into a way of reading
    the disk, so the same rule `Trace._artifact_path` applies is applied here.
    """
    name = str(step.screenshot or "")
    if not name or Path(name).name != name:
        return ""
    return f'<img src="{_text(name)}" alt="Screenshot of {_text(step.url)}">'


def render(trace: Trace) -> str:
    """The whole report as one self-contained page.

    A trace with nothing in it still produces a page that says so — "shows where
    and why, not a blank page" is an acceptance criterion, and an empty run is
    the easiest way to fail it.
    """
    steps = list(trace.read())
    summary = trace.summary()
    ending = _ending(steps)
    facts = _findings(trace)
    goal = _goal(trace)
    status = ending.kind if ending else ("unfinished" if steps else "empty")

    head = [
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">",
        f"<title>Run {_text(trace.run_id)}</title>",
        f"<style>{STYLE}</style></head><body><main>",
        f"<h1>Run {_text(trace.run_id)} "
        f'<span class="pill {TONE.get(status, "note")}">{_text(status)}</span></h1>',
        f'<p class="goal">{_text(goal) if goal else "<em>No goal recorded.</em>"}</p>',
    ]
    if ending and TONE.get(ending.kind) in MUST_EXPLAIN:
        head.append(f'<div class="card"><span class="k">Why it stopped</span>'
                    f'<div>{_text(ending.detail)}</div></div>')

    head.append(
        '<p class="meta">'
        + " · ".join(
            _text(item) for item in (
                f"{summary['steps']} steps",
                f"{summary['failed']} failed",
                f"${summary['estimated_cost_usd']:.4f} estimated",
                f"{summary['tokens_in']} in / {summary['tokens_out']} out",
                f"{summary['took_ms']} ms",
                ", ".join(summary["models"]) or "no model recorded",
                f"{summary['started_at']} → {summary['ended_at']}",
            )
        )
        + "</p>"
    )

    body = ["<h2>What it found</h2>"]
    if not facts:
        body.append('<p class="empty">No facts were returned by this run.</p>')
    else:
        body.append('<div class="facts">')
        for fact in facts:
            source = fact.get("source") or {}
            step = trace.resolve(str(source.get("step_id") or "")) if source else None
            body.append(
                '<div class="card">'
                f'<span class="k">{_text(fact.get("field"))} '
                f'<span class="pill note">{_text(fact.get("kind"))}</span></span>'
                f'<div class="v">{_text(fact.get("value"))}</div>'
                + (f'<div class="q">{_text(source.get("quote"))}</div>'
                   if source.get("quote") else "")
                + '<div class="meta">'
                + _text(source.get("url") or "no url")
                + " · " + _text(source.get("captured_at") or "no time")
                + " · step " + _text(source.get("step_id") or "none")
                + "</div>"
                + (_image(step) if step else "")
                + "</div>"
            )
        body.append("</div>")

    body.append("<h2>What happened</h2>")
    if not steps:
        body.append('<p class="empty">This trace has no steps.</p>')
    else:
        body.append("<table><thead><tr><th>#</th><th>Step</th><th>Detail</th>"
                    "<th>Where</th><th>Cost</th></tr></thead><tbody>")
        for index, step in enumerate(steps):
            tone = TONE.get(step.kind, "note" if step.ok else "warn")
            cost = f"${step.estimated_cost_usd:.4f}" if step.estimated_cost_usd else ""
            body.append(
                f"<tr><td class=\"n\">{index}</td>"
                f'<td><span class="pill {tone}">{_text(step.kind)}</span></td>'
                f"<td>{_text(step.detail)}</td>"
                f'<td class="meta">{_text(step.url)}</td>'
                f'<td class="n">{_text(cost)}</td></tr>'
            )
        body.append("</tbody></table>")

    body.append(
        '<footer>Written by off_CRM from this run\'s own trace. Every value here '
        "came off a web page and is shown escaped; nothing in this file is "
        "loaded from the network.</footer></main></body></html>"
    )
    return "".join(head + body)


def write(trace: Trace) -> Path:
    """Put the report beside the trace it describes, readable only by the owner."""
    path = Path(trace.directory) / REPORT_FILENAME
    path.write_text(render(trace), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path
