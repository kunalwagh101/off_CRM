# Demo

**Commands you paste yourself and watch work.** Nothing here is a screenshot or
a description of something working — every block is runnable, and if one stops
working that is a defect rather than a stale document.

Setup, once:

```bash
git clone https://github.com/kunalwagh101/off_CRM.git && cd off_CRM
uv sync --locked --extra dev --extra email
```

---

## 1. Check that everything claimed as done actually is

The most important one. This re-runs every test behind every `DONE` item on the
board and refuses the claim if any of them fails.

```bash
python scripts/verify_board.py
```

Expect: a board summary, then `OK — the board matches the repository.`

Now break it on purpose and watch it catch you:

```bash
sed -i.bak 's|code: offsetx_apollo_builder/video/effects.py|code: offsetx_apollo_builder/video/imaginary.py|' BOARD.md
python scripts/verify_board.py ; echo "exit code: $?"
mv BOARD.md.bak BOARD.md
```

Expect: `x S-01.02.03 names code 'offsetx_apollo_builder/video/imaginary.py', which does not exist.` and `exit code: 1`.

---

## 2. A topic becomes a finished video

The line the whole editor exists for. No timeline is touched by a human.

```bash
python - <<'PY'
from offsetx_apollo_builder.video import assembly, recipes
from offsetx_apollo_builder.video.timeline import TICKS_PER_SECOND as S

brief = assembly.AssemblyBrief(
    name="Why nobody reads changelogs",
    recipe="hook_hold_payoff",
    visuals=[assembly.Visual(f"shot-{n}", "image") for n in range(4)],
    target_ticks=15 * S,
    lines=["Nobody reads changelogs.", "Here is why.", "Write the why, not the what."],
    music=assembly.Sound("bed", 60 * S),
)
report = assembly.assemble(brief)
project = report.project
print(f"cut        : {len(project.tracks[0].clips)} clips on the video track")
print(f"length     : {project.duration / S:.2f}s  (asked for 15.00s)")
print(f"beats      : {[b['name'] for b in report.beats]}")
print(f"notes      : {report.notes or 'none — it met the brief exactly'}")
PY
```

Expect the length to be **exactly** 15.00s. Every recipe at every length lands on
the tick, because the export gate compares the file against the project's own
duration.

---

## 3. The effects catalogue, and the promise it makes

```bash
python - <<'PY'
from offsetx_apollo_builder.video import effects as fx

print(f"{len(fx.PRIMITIVES)} pixel operations, {len(fx.EFFECTS)} named looks")
print()
for pack in ("film", "cine", "neon"):
    names = [e.label for e in fx.EFFECTS.values() if e.pack == pack][:5]
    print(f"  {pack:<8} {', '.join(names)} …")

print()
drift = 0
for effect_id in fx.EFFECTS:
    for step in fx.resolve(effect_id, amount=0.0):
        spec = fx.PRIMITIVES[step["primitive"]]
        for name, value in step["numbers"].items():
            neutral = spec.numbers[name][3]
            if neutral is not None:
                drift = max(drift, abs(value - neutral))
print(f"all {len(fx.EFFECTS)} looks at strength 0 — largest drift from doing nothing: {drift}")
PY
```

Expect `largest drift ... 0.0`. Strength zero is a guaranteed no-op across the
whole catalogue, which is what makes every look's slider trustworthy.

---

## 4. The posting cap refuses to be argued with

```bash
python - <<'PY'
from datetime import datetime, timedelta, timezone
from offsetx_apollo_builder.distribution import pacing

metrics = [{"post_id": f"p{i}", "views": 1_000} for i in range(20)]
deadline = (datetime.now(timezone.utc) + timedelta(days=100)).isoformat()

for cap in (0, 1):
    d = pacing.decide(goal_target=1_000_000, goal_deadline=deadline,
                      metrics=metrics, current_per_day=1.0, owner_cap=cap)
    label = "no cap" if cap == 0 else f"cap {cap}/day"
    print(f"{label:<10} goal needs {d.required_per_day:5.2f}/day  ->  suggests "
          f"{d.posts_per_day:.2f}/day   capped by: {d.capped_by or '-'}")
PY
```

Expect the goal to want ~9.8/day and the suggestion to be held at your cap, with
`capped by: your own cap`. The goal does not get a vote.

---

## 5. The browser agent, driving a real browser

Needs Chrome, Edge, Brave or Chromium installed. Skips cleanly if none is.

```bash
python -m pytest tests/test_browser_agent.py -q
```

Expect `32 passed`. Three of those launch a real browser, open a page, read it
by meaning, type with real key events, refuse an unconfirmed *Send*, then send,
and read back the page's own output.

To watch the perception layer itself:

```bash
python - <<'PY'
from offsetx_apollo_builder.browser import perceive

def node(i, role, name="", children=(), backend=1):
    return {"nodeId": str(i), "role": {"value": role}, "name": {"value": name},
            "childIds": [str(c) for c in children], "backendDOMNodeId": backend,
            "ignored": False, "properties": []}

page = perceive.build([
    node(1, "RootWebArea", "Acme", children=[2, 3, 6]),
    node(2, "heading", "Acme Ltd"),
    node(3, "form", "Contact", children=[4, 5]),
    node(4, "textbox", "Email"),
    node(5, "button", "Send message"),
    node(6, "link", "Pricing"),
], url="https://acme.test", title="Acme")

print(page.render())
print()
print("the agent may act on:", [f"[{n.handle}] {n.name}" for n in page.actions])
PY
```

Expect an indented outline in **document order** with numbered handles. The
agent says `click(4)` — it cannot write a selector and it cannot run code.

---

## 6. Safety: what the agent refuses

```bash
python - <<'PY'
from offsetx_apollo_builder.browser import policy

for url, unattended in (
    ("https://example.com/about",            False),
    ("https://www.linkedin.com/in/someone",  False),
    ("https://www.linkedin.com/in/someone",  True),
    ("file:///etc/passwd",                   False),
    ("http://169.254.169.254/latest/meta-data/", False),
):
    mode = "on a schedule" if unattended else "you watching"
    try:
        rule = policy.check_navigation(url, unattended=unattended)
        print(f"ALLOW   {url[:44]:<45} ({mode})  pace {rule.min_seconds_between_actions}s")
    except policy.Refused as exc:
        print(f"REFUSE  {url[:44]:<45} ({mode})  {str(exc)[:60]}…")
PY
```

Expect LinkedIn allowed when you are watching and refused on a schedule; the
local file and the cloud metadata address refused always.

---

## 7. Protected email refuses unsafe sends and survives worker failures

This is the complete deterministic delivery slice: permission, suppression,
durable claims, ambiguous-send quarantine, domain authentication, SES MIME,
signed feedback, health pause and exact live-send confirmation. It uses fakes;
it does not send a real email.

```bash
uv run pytest tests/test_email_delivery.py -q
```

Expect `16 passed`. The test derives its send-window time from the day it runs,
so it does not expire with the calendar.

---

## 8. The whole test suite

```bash
python -m pytest tests/ -q
cd frontend && npm ci && npm test && npm run build
```

Expect 1,400+ Python tests and 100+ frontend tests. The exact current counts are
recorded in `BUILD_STATE.md`; the command's exit code is the authority.
