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

## 8. The browser box: what it mounts, and what it refuses

The container the browser runs in. Print the exact `docker run` off_CRM would
issue, and look for a path from your own machine in it:

```bash
python - <<'EOF'
from offsetx_apollo_builder.browser.box import BrowserBox
import os

command = BrowserBox(workspace_id="local").command()
print(" ".join(command))
print()
joined = " ".join(command)
mounts = [command[i + 1] for i, part in enumerate(command) if part == "-v"]
print("mounted       :", mounts)
print("your home dir :", "PRESENT — a bug" if os.path.expanduser("~") in joined else "absent")
print("the CRM store :", "PRESENT — a bug" if "store" in joined else "absent")
EOF
```

Expect one mount — `offcrm-browser-local:/profile`, a Docker volume rather than
a path on your disk — and both checks reading `absent`.

Now the allow-list, decided per request:

```bash
python - <<'EOF'
from offsetx_apollo_builder.browser.guard import RequestGuard

unattended = RequestGuard(allowed_hosts=frozenset({"example.com"}), unattended=True)
attended = RequestGuard(unattended=False)

for url in ("https://example.com/page", "https://www.example.com/page",
            "https://example.com.evil.test/steal", "https://anything.test/page",
            "https://www.linkedin.com/feed/", "http://169.254.169.254/",
            "data:image/png;base64,AAAA"):
    u = "allow " if unattended.verdict(url).allowed else "REFUSE"
    a = "allow " if attended.verdict(url).allowed else "REFUSE"
    print(f"{url[:38]:<40} unattended: {u}   attended: {a}")
EOF
```

Real output:

```
https://example.com/page                 unattended: allow    attended: allow
https://www.example.com/page             unattended: allow    attended: allow
https://example.com.evil.test/steal      unattended: REFUSE   attended: allow
https://anything.test/page               unattended: REFUSE   attended: allow
https://www.linkedin.com/feed/           unattended: REFUSE   attended: allow
http://169.254.169.254/                  unattended: REFUSE   attended: REFUSE
data:image/png;base64,AAAA               unattended: allow    attended: allow
```

Two rows are worth pausing on. `example.com.evil.test` is refused: it ends with
neither `example.com` nor `.example.com`, and a naive substring check would let
it straight through. And LinkedIn is refused when unattended **even though a
platform rule, not the list, is what refuses it** — the list can only narrow.

To watch a real browser refuse a real request:

```bash
python -m pytest tests/test_browser_box.py -q
```

Expect `30 passed`. Four of those launch Chromium, attach the guard, have a page
call `fetch()` at an undeclared domain, and assert the request was **paused and
refused** — not merely that it failed, which a request to a domain that does not
resolve would do anyway.

---

## 9. Sign in to a platform, and go looking for the password

The login belongs to the person, not to off_CRM. off_CRM opens the page, waits,
and reads back **whether it worked** — nothing else crosses.

The first half of that is a claim about signatures, and it is checked by reading
them rather than by trusting a review:

```bash
python - <<'EOF'
import inspect
from offsetx_apollo_builder.browser import identity, signin

for module in (identity, signin):
    for name, function in vars(module).items():
        if name.startswith("_") or not inspect.isfunction(function):
            continue
        if function.__module__ != module.__name__:
            continue  # imported, not declared here
        parameters = list(inspect.signature(function).parameters)
        print(f"{module.__name__.split('.')[-1]}.{name}({', '.join(parameters)})")
EOF
```

Real output:

```
identity.platform(platform_id)
identity.read_state(snapshot, target)
identity.catalogue(store, workspace_id)
signin.check(page, target)
signin.open_login(page, target)
signin.wait_for_sign_in(page, target, timeout, poll_seconds, on_poll)
signin.connect(page, target, store, workspace_id, timeout, on_poll)
signin.verify(page, target, store, workspace_id)
```

There is no `password`, no `username`, no `token`, no `secret` and no
`credential` in any of them, and `tests/test_browser_signin.py` fails the build
if one ever appears.

Where you stand on every platform, in one call:

```bash
python - <<'EOF'
from pathlib import Path
from offsetx_apollo_builder.browser.identity import ConnectionStore, catalogue

store = ConnectionStore(Path("/tmp/offcrm-demo-connections"))
answer = catalogue(store, "local")
print("stores_no_credentials:", answer["stores_no_credentials"])
for row in answer["platforms"]:
    print(f"{row['label']:<12} {row['state']:<14} {row['login_url']}")
EOF
```

Real output, on a machine that has signed into nothing yet:

```
stores_no_credentials: True
Facebook     unknown        https://www.facebook.com/login/
Instagram    unknown        https://www.instagram.com/accounts/login/
LinkedIn     unknown        https://www.linkedin.com/login
TikTok       unknown        https://www.tiktok.com/login
X            unknown        https://x.com/i/flow/login
YouTube      unknown        https://accounts.google.com/ServiceLogin?service=youtube
```

`unknown` is a real answer and not a default — off_CRM has not looked at a page,
so it does not claim to know. It never guesses `disconnected`.

Then the live proof, which needs Chromium:

```bash
python -m pytest tests/test_browser_signin.py -q
```

Expect `21 passed`. Two of them are the acceptance criteria themselves. One
drives a real browser to a login page served from the test file, types a
password into it with real key events, watches the page flip to signed-in — and
then reads **every byte off_CRM wrote** and fails if the password is in any of
them. The other plants a cookie with an expiry, kills the browser, starts
another one against the same profile, and asks for the cookie back.

---

## 10. The whole test suite

```bash
python -m pytest tests/ -q
cd frontend && npm ci && npm test && npm run build
```

Expect ~1,520 Python tests and 115 frontend tests. The exact current counts are
recorded in `BUILD_STATE.md`; the command's exit code is the authority.
