# Demo

**Commands you paste yourself and watch work.** Nothing here is a screenshot or
a description of something working — every block is runnable, and if one stops
working that is a defect rather than a stale document.

Setup, once:

```bash
git clone https://github.com/kunalwagh101/off_CRM.git && cd off_CRM
uv sync --locked --extra dev --extra email
npm ci --prefix frontend
```

---

## 1. Check that everything claimed as done actually is

The most important one. This re-runs every test behind every `DONE` item on the
board and refuses the claim if any of them fails. Run it inside the same locked
Python environment as the evidence commands it launches.

```bash
uv run python scripts/verify_board.py
```

Expect: a board summary, then `OK — the board matches the repository.`

Now break it on purpose and watch it catch you:

```bash
sed -i.bak 's|code: offsetx_apollo_builder/video/effects.py|code: offsetx_apollo_builder/video/imaginary.py|' BOARD.md
uv run python scripts/verify_board.py ; echo "exit code: $?"
mv BOARD.md.bak BOARD.md
```

Expect: `x S-01.02.03 names code 'offsetx_apollo_builder/video/imaginary.py', which does not exist.` and `exit code: 1`.

---

## 2. Prove the crawler remembers what is due

Run the focused acceptance slice:

```bash
uv run pytest tests/test_crawler_frontier.py -q
```

The seven cases prove: robots.txt + crawl-delay enforcement, month-stable pages
back off further than a page changed yesterday, crawl budget survives process
restart, a lease prevents two workers claiming one URL, a persisted URL that
the current policy now rejects cannot starve valid due work behind it, two
crawler processes cannot start different URLs on the same host inside one
crawl-delay window, and LinkedIn/Instagram cannot enter the frontier even if an
operator mistakenly allow-lists them.

The durable frontier is created on the first real discovery run at:

```text
<OFFSETX_DATA_DIR>/crawler_frontier.sqlite3
```

Inspect it with SQLite if you want the scheduler's reason for every URL:
`last_crawled_at`, `last_changed_at`, `next_due_at`, counters, last error
and lease expiry are stored as ordinary columns.

---

## 3. A topic becomes a finished video

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

## 4. The effects catalogue, and the promise it makes

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

## 5. The posting cap refuses to be argued with

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

## 6. The browser agent, driving a real browser

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

## 7. Safety: what the agent refuses

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

## 8. Protected email refuses unsafe sends and survives worker failures

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

## 9. The browser box: what it mounts, and what it refuses

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

## 10. Sign in to a platform, and go looking for the password

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

Current output includes:

```
identity.platform(platform_id)
identity.read_state(snapshot, target)
identity.catalogue(store, workspace_id)
signin.check(page, target)
signin.open_login(page, target)
signin.wait_for_sign_in(page, target, timeout, poll_seconds, on_poll)
signin.connect(page, target, store, workspace_id, vault, timeout, on_poll)
signin.verify(page, target, store, workspace_id)
```

There is no `password`, no `username`, no `token`, no `secret` and no
`credential` in any of them. `vault` is a required trusted storage object, not
credential material; the connection cannot be marked green without it.
`tests/test_browser_signin.py` and `tests/test_browser_vault_wiring.py` fail the
build if these boundaries regress.

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

## 11. The vault: one account key each, no secret in a model prompt

This is the acceptance proof for `S-03.02.02`. It does not contact a real
platform or AI provider. It proves the storage/key boundary, trusted CDP
capture/restore wiring, tamper refusal, and the shared AI scanner's refusal of
cookies, tokens and passwords even under `full` policy.

```bash
uv run pytest tests/test_browser_vault.py tests/test_browser_vault_wiring.py -q
```

Expect `15 passed`.

For the regression boundary around the two systems this slice touches:

```bash
uv run pytest tests/test_browser_vault.py tests/test_browser_vault_wiring.py tests/test_browser_signin.py tests/test_ai_egress_wall.py -q
```

Inspect the implementation contract itself in `docs/VAULT.md`. The important
shape is: Chrome session → trusted capture → per-account encryption → wrapped
account key → metadata-only result. Restore follows the reverse path straight
back into Chrome. Neither path is available to a model.

---

## 12. Revoke and forget: prove the session is really gone

This is the acceptance and live-browser proof for `S-03.02.03`.

```bash
uv run pytest tests/test_browser_revoke.py -q
```

The suite covers the success path, browser-deletion failure, cross-platform
material refusal, missing-vault refusal, and refusal to operate without an
attached page target. Its live test starts real Chromium, plants a persistent
session cookie, proves Chromium has it, disconnects the platform through the
attached page CDP session, and then asks Chromium whether the cookie survived.
It also proves the per-account vault can no longer decrypt and the append-only
trace contains the revocation but not the cookie value.

If the browser is not installed locally, the live test skips; CI is the recorded
Gate 2 environment for this increment and ran the live Chromium assertion.

---

## 13. The whole test suite

```bash
uv run pytest tests/ -q
cd frontend && npm ci && npm test && npm run build
```

The implementation release gate for `S-03.02.03` produced `1542 passed, 4 skipped`
for Python and `116 passed` for the frontend on 2026-09-04 UTC; the production
frontend build also passed. Exact counts continue to come from the command, not
from this prose; the command's exit code is the authority.

---

## 14. Production Run Loop: bounded decisions, broker-only AI, human gates

This is the deterministic production acceptance proof for `S-02.02.01`. It
uses controlled page and broker doubles so it can assert the security boundaries
without contacting a real provider or changing a real CRM account.

```bash
uv run pytest tests/test_agent_run.py -q
```

Expect `7 passed`. The suite proves the hard step budget, broker-only model
decisions, provider/model/cost trace records, Tier A/B planner floor, rejection
of invented actions and undeclared arguments, prompt-injection framing, and that
a consequential browser action stops for a human rather than self-confirming.

---

## S-06.02.03 — prove cost and latency ceilings stop new work

```bash
uv run pytest tests/test_agent_run_budgets.py tests/test_agent_money_ceiling.py -q
```

Expect: `33 passed`. The acceptance cases prove both sides of the boundary: a
model call can consume the remaining latency and prevent the next browser
action; a browser action can cross the ceiling and prevent the next model call;
resume keeps the original allowance; the existing money ceiling still stops
before a provider call.

Then run the independent delivery gate:

```bash
uv run python scripts/verify_board.py
```

Expect: exit code 0 and `OK — the board matches the repository.`

---

## S-06.02.08. Evidence uses one runner

```bash
uv run pytest tests/test_verify_board.py tests/test_ci_verifier_environment.py -q
uv run python scripts/verify_board.py --skip-tests
```

The first command proves the runner contract and clean-checkout setup. The
second checks the real board without replaying historical tests; every DONE
`command:` must begin with `uv run`, or the verifier refuses the board.

---

## DONE cannot depend on unfinished work

The verifier's delivery-history guard is tested against every non-DONE board
column, plus the valid all-DONE case:

```bash
uv run pytest tests/test_verify_board.py::test_done_with_any_unfinished_dependency_fails tests/test_verify_board.py::test_done_with_only_done_dependencies_passes -q
```

Expect `7 passed`. The failing fixtures deliberately put the upstream story in
BACKLOG, READY, IN_PROGRESS, IN_REVIEW, BLOCKED and DEFERRED; each must make the
verifier name both story IDs and refuse the DONE claim.



---

## S-05.01.02 — extraction packs are data

Run the focused contract:

```bash
uv run pytest tests/test_extraction_packs.py tests/test_discovery.py -q
```

Then inspect the production registry:

```bash
cat config/extraction_packs.json
```

A source is added by a JSON row containing domains, one record selector and
bounded text/attribute field selectors. Registry loading also parse-checks every
CSS selector with Scrapling itself; malformed selectors fail before a page is
processed. There is no Python/plugin/template/AI hook in the pack format. An
unmatched source still follows the existing JSON-LD parser.

## S-05.01.03 — competitor structure, not competitor content

```bash
uv run pytest tests/test_competitor_teardown.py tests/test_video_assembly.py tests/test_video_review.py -q
```

The focused cases prove that the same public facts map to the same existing
recipe, copied caption/transcript/audio/frame/media fields are rejected,
non-finite numeric evidence is refused, a missing declared recipe fails cleanly, session-gated sources are refused,
missing evidence is not guessed, and a derived project uses our campaign
material and enters the existing human review queue with origin
`competitor_teardown`.

## S-06.02.04 — subject access and deletion

```bash
uv run pytest tests/test_privacy.py tests/test_api_auth.py -q
```

The suite exercises cross-subject isolation, authenticated API access, exact
destructive confirmation, retry after one store fails, **revalidation of stores
that succeeded on an earlier partial attempt**, deletion of crawler and trace
copies, AI context/egress and redacted-mail recall, registered generated
artifacts, residual CRM metadata, and row-level cleanup of application-owned
CSV queues/exports.

The destructive confirmation is intentionally explicit:

```text
DELETE SUBJECT DATA
```

These three sections describe the commands to run during the dedicated
verification pass. No pass count is recorded here until those commands actually
execute.


---

## S-03.02.05 — one platform row drives three controls

```bash
uv run pytest tests/test_browser_platform_registry.py tests/test_browser_signin.py tests/test_browser_budget.py -q
```

Then inspect the packaged registry:

```bash
python - <<'PY'
from offsetx_apollo_builder.browser.platforms import default_registry
from offsetx_apollo_builder.browser.identity import platform
from offsetx_apollo_builder.browser.budget import Budget
from offsetx_apollo_builder.browser.policy import rule_for

p = platform("reddit")
print(p.to_dict())
print(Budget.for_platform("reddit").to_dict())
print(rule_for("https://www.reddit.com/r/python"))
print([x.id for x in default_registry().all()])
PY
```

The important property is not the output value; it is that Reddit has no
Reddit-specific branch in identity, budget or policy code.

## S-02.02.02 — edit PLAN.md and change the next decision

```bash
uv run pytest tests/test_agent_plan.py tests/test_agent_run.py tests/test_agent_resume.py -q
```

The focused cases edit the live run's PLAN.md after decision one and require
decision two to receive the edit. Deleting PLAN.md mid-run stops before another
model call, and deleting a **managed** PLAN.md before restart/resume refuses
instead of regenerating the original boilerplate. Existing legacy PLAN.md files
are adopted without overwriting owner text. Every decision also stores the exact
plan version it saw as its private trace capture.

## S-04.01.01 — persisted companions stay inside their grants

```bash
uv run pytest tests/test_agent_companions.py tests/test_privacy.py -q
```

The suite proves persistence, workspace isolation, unique memory scopes,
approved-memory-only recall, **exact-scope isolation against the real CRM memory
backend (global memory must not leak into a companion)**, immediate removal of
disabled tools, execution-time denial of an ungranted tool, authenticated
companion API behaviour, companion profile privacy deletion and backup/restore
reopening of the tool/companion DB.

No pass count is written here until the dedicated verification pass actually
executes these commands.


---

## S-06.02.01 — generic credentials never reach a model

```bash
uv run pytest tests/test_ai_prompt_secret_scan.py tests/test_ai_egress_wall.py -q
```

The focused regressions include opaque `api_key`, `api_secret`,
`client_secret` and `secret_key` assignments in model-visible system text,
plus the same names as FULL-policy unrestricted fields. The provider constructor
must not run.

## S-06.01.01 — workspace writes and logins stay isolated

```bash
uv run pytest tests/test_workspace_isolation.py tests/test_api_auth.py tests/test_ai_api.py tests/test_browser_vault.py -q
```

The suite now includes two independent workspace-settings store instances forced
through the old overlapping read/modify/write window. Both workspace provider
settings and both encrypted keys must survive. It also proves ordinary usernames
containing r/n/x/0 work while embedded newline/NUL are refused.

## S-06.01.04 — unattended routines only notify from verified findings

```bash
uv run pytest tests/test_agent_routines.py tests/test_agent_run.py tests/test_agent_provenance.py -q
```

The acceptance cases prove an attended-only target is refused at declaration,
event execution stays inside the authenticated workspace, duplicate event IDs do
not run twice, empty/model-prose-only outcomes do not notify, and only the
source-verified `notification` result becomes a persistent notification.

No pass count is recorded until these commands actually execute.

---

## S-06.02.02 — every private API route refuses unauthenticated access

```bash
uv run pytest tests/test_api_boundary_contract.py tests/test_api_auth.py -q
```

The contract enumerates FastAPI's registered routes. Private `/api/` methods
must return 401 without credentials. The only public exceptions are the closed
bootstrap/signed-callback list. Broken JSON and wrong body shapes must return
4xx without stack traces or echoing a planted secret.

## S-06.02.05 — keyboard and screen-reader contract

```bash
uv run pytest tests/test_frontend_accessibility_contract.py -q
npm test --prefix frontend
npm run build --prefix frontend
```

Owner pass to do later: start from the browser address bar, use only
Tab/Shift+Tab/Enter/Space/Escape through navigation, modals, AI drawer, Sales
moves and video controls; then repeat core screens with a screen reader. Focus
must remain visible and no required action may need a mouse.

## S-07.01.03 — local meeting capture with no bot

Engineering checks:

```bash
uv run pytest tests/test_meeting_transcription.py tests/test_privacy.py -q
npm test --prefix frontend
npm run build --prefix frontend
```

Owner/live check:

1. run off_CRM on localhost;
2. connect an allowed transcription provider;
3. open **Meetings** and choose the provider/model;
4. click **Start local capture**;
5. share a tab/screen **with audio** and permit the microphone;
6. play remote/system speech and speak locally;
7. stop the meeting and inspect the transcript;
8. confirm there is no stored raw recording file and the meeting record names
   the provider/model chosen before capture.

A hosted/non-loopback backend or non-loopback browser Origin must refuse capture.
A later chunk trying to change provider/model must also be refused before
provider I/O.

No pass count is recorded here until these commands actually execute.

---

## 15. The GTM brain: a goal becomes paused campaigns, a review, and the next version

No model and no keys needed: with nothing connected the brain uses its rules and
says so. Everything runs against a throwaway database.

```bash
uv run python - <<'PY'
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings

tmp = Path(tempfile.mkdtemp())
app = create_app(AppSettings(project_root=Path.cwd(), database_path=tmp / "crm.db",
                             data_dir=tmp / "data", export_dir=tmp / "exports",
                             frontend_dist=tmp / "none", allow_unauthenticated=True))
with TestClient(app) as http:
    api = "/api/v1/gtm"
    product = http.post(f"{api}/products", json={
        "name": "Ledgerline",
        "one_liner": "Reconciles freight invoices against delivery records overnight.",
        "audience": "Finance leads at logistics companies with 50 to 500 staff.",
        "problem": "Carriers overbill and nobody has time to check every invoice.",
        "offer": "a 15-minute walkthrough on your own invoices",
        "forbidden_claims": ["guaranteed"],
    }).json()
    plan = http.post(f"{api}/plans", json={"product_id": product["id"], "goal_kind": "replies",
                                           "goal_target": 20}).json()
    print("PLAN  ", plan["source"], "|", plan["notes"][0])
    print("       ", plan["feasibility"]["explanation"][:150], "...")

    applied = http.post(f"{api}/plans/{plan['id']}/apply").json()
    for item in applied["campaigns"]:
        status = app.state.engine.store.get_campaign(item["campaign_id"])["status"]
        print("APPLY ", item["kind"], item["action"], "->", status)

    review = http.post(f"{api}/plans/{plan['id']}/review", json={}).json()
    for finding in review["findings"]:
        print("REVIEW", finding["channel"], finding["code"], "|", finding["sentence"])
    print("DO    ", review["remedies"][0]["label"], "on", review["remedies"][0]["page"])

    nxt = http.post(f"{api}/plans/{plan['id']}/revise", json={}).json()
    print("REVISE version", nxt["version"], nxt["status"], "|", nxt["notes"][0])
PY
```

Expect, in this order:

- `PLAN rules | No model could write this plan: …` — nothing is connected, so the
  rules wrote it and the first note says why, instead of an error.
- `APPLY email created -> paused` — Apply never starts anything.
- `REVIEW email not_started | The email campaign is paused, so it is not sending.`
  — the review checks whether the pipe is running before it says a word about
  the copy.
- `DO Resume the campaign. on campaigns`
- `REVISE version 2 draft | Only 0 people were contacted …` — too little data, so
  the assumed rate carries forward and the note says so.

---

## 14. Turn one verified run into sendable artifacts

The focused contract:

```bash
uv run pytest tests/test_agent_artifacts.py -q
```

Expect the suite to prove all three format paths, exact trace-step provenance,
spreadsheet formula-injection protection, broken-provenance refusal, private
output permissions, the installed CLI path, and that the renderer has no AI
transport.

For an existing agent run:

```bash
uv run offsetx-artifacts --run-dir /path/to/run --format xlsx
uv run offsetx-artifacts --run-dir /path/to/run --format pptx
uv run offsetx-artifacts --run-dir /path/to/run --format pdf
```

The files appear beside that run's `trace.jsonl`. XLSX contains a Trace sheet
and every finding links to its exact step row. PPTX writes the step id on every
claim slide. PDF is the existing escaped offline provenance report printed by a
local Chromium-family browser.


## S-06.02.39 — Low-bitrate WebM validation (IN_REVIEW)

```bash
uv run pytest tests/test_video_gates.py tests/test_video_engine.py -q
uv run pytest -q
uv run python scripts/verify_board.py
```

`tests/fixtures/low_bitrate_valid.webm` is a real two-second, 60-frame VP9 file
(360x640, 2150 bytes) produced using ffmpeg. Before the change the 4096-byte
size floor rejected it. Check that the genuine video passes all gates, while the
existing fake/empty WebM and deliberately mismatched requirements fail.

A standalone EBML sample-scan reproduction passed 10 local test cases; these
were **not** the repository test suite. Manual acceptance still needs a real
browser export of a short Colour scene and playback verification. The GitHub
runner and full board tests remain unverified. See
`docs/evidence/S-06.02.39-validation.md`.

## A16 — Provider setup failures must not strand an email job

Runs actual `EmailDeliveryService.work_once` and the persistent CRM store with controlled provider factories. No email leaves the machine.

```bash
uv run pytest -q tests/test_email_delivery.py -k A16
uv run pytest -q tests/test_email_delivery.py::test_ambiguous_delivery_is_quarantined_and_never_retried
uv run pytest -q tests/test_email_delivery.py
```

Expected focused result on `144e1cb`: 5 A16 tests pass. Exercise SQLite and disposable PostgreSQL mode for the broad regression; run the full verifier before any DONE claim. See `docs/evidence/2026-11-04-a16-email-provider-setup.md`. Never use a live email recipient for this test.


## A11 — Atomic provider request and USD limits

No real provider calls. Runs simulated egress through the **real** broker with two independent worker processes and a disposable quota ledger:

```bash
uv run pytest -q tests/test_ai_quota_atomic.py
uv run pytest -q tests/test_ai_cost_ledger.py tests/test_ai_egress_wall.py tests/test_ai_failures.py
```

For PostgreSQL cross-worker contention use a disposable test database and set `OFF_CRM_TEST_POSTGRES_URL` as described in `tests/test_hosted_storage.py`; `tests/test_ai_quota_atomic.py::test_A11_postgres_two_processes_reserve_one_actual_provider_call` exercises two real independent Postgres clients. Never point this test at a customer database. The account ledger is authoritative, not a Python lock. See `docs/evidence/2026-11-04-a11-ai-quota-reservations.md` for actual isolated Render RED/GREEN evidence. No production claim from synthetic calls.

## A14 — Concurrent HTTP Idempotency-Key safety

The tests use disposable CRM databases, controlled API instances and fake transports, not customer campaigns or real sends.

```bash
uv run pytest -q tests/test_api_idempotency_a14.py
uv run pytest -q tests/test_outreach_api.py
```

Set `OFF_CRM_TEST_POSTGRES_URL` to a disposable PostgreSQL URL to run the A14 real-PostgreSQL concurrent-app test; it creates and drops a random temporary schema. A 409 on mismatched payload or principal is correct. A 409 after a crashed external provider call means **inspect that attempt**; do not retry automatically. Full verification evidence is in `docs/evidence/2026-11-04-a14-atomic-http-idempotency.md`.
