# Changelog

## Unreleased

- **A run now has a money ceiling, not only a step ceiling** (`S-11.01.04`).
  `run(..., spend_ceiling_usd=...)` stops the run with `status=over_budget`
  before the decision that would cross it. An agent left running overnight can
  no longer cost more than was agreed.
- **The check runs before the model is asked anything**, so the ceiling is never
  crossed rather than reported once it already has been. That also makes
  stopping free — which is what makes it safe to resume from. Whatever the run
  gathered before the limit is kept: a run that found three facts and stopped on
  the fourth has still found three facts.
- **The ceiling survives a resume.** It is recorded on `run_started` and
  re-applied by `resume()`, and the spend is read back off the trace — so a run
  killed and restarted ten times counts one allowance rather than ten. Without
  that the feature would be a speed bump: stop at the limit, resume, spend
  without bound. Raising it is `resume(spend_ceiling_usd=...)` and has to be
  done on purpose.
- **The next decision is predicted from the most expensive one so far, not the
  average.** A ceiling is a promise, and the average lags a trend — a run whose
  pages keep growing would walk past the line while the average still said there
  was room. Stopping early is recoverable; exceeding a limit the owner set is
  not.
- A projection that is already above the ceiling is said in `run_started`, not
  at the step it stops on. "This will not fit" is worth knowing before the first
  page loads.
- **Known limit, tested rather than discovered:** a model with no price list
  cannot have its first decision predicted, so that one goes through whatever
  the ceiling says; from the second on the run's own costs take over. Refusing
  every run on an unpriced model would make free and local models unusable, so
  the exposure is capped at one decision and a test keeps it there.

- **A run now says what it will cost before it starts, and what it did cost
  after** (`S-06.01.03`). The estimate goes into `run_started` beside the budget
  it was derived from, carries its own basis, and comes back on `RunOutcome`
  next to the actual — `estimate_error` is the difference, which is this
  story's own indicator.
- **Fixed: the daily spend cap could never be reached** (`D-35`). The owner can
  set a per-provider daily limit; the check for it is real, the usage bar
  displays it, and the line that recorded what a call cost passed a hardcoded
  `spend_usd=0.0`. Measured: a $1.00 cap, 5,000 calls, $0.0000 counted, nothing
  refused. Priced properly those same calls are $8.00 and the cap refuses at
  once. This was the only thing standing between an agent left running overnight
  and an unbounded bill.
- **Fixed: the provider tells us what each call used and we were discarding it**
  (`D-36`). Every major API returns a `usage` block; the adapter pulled the text
  out of the response and dropped the rest, and cost was then guessed by
  dividing characters by four. Captured now in `_post`, the one place every HTTP
  call passes through, so no adapter has to remember — and translated across the
  two naming conventions in use (`input_tokens`/`output_tokens` and
  `prompt_tokens`/`completion_tokens`).
- **Fixed: the price of a call was computed in three places** (`D-38`), one of
  which returned zero. `registry.price_tokens` is now the only implementation;
  `ModelEntry.price` is a convenience over it and `broker.measure` is the single
  funnel every caller uses. This is the defect log's pattern 3 — two things that
  must agree, drifting apart — in arithmetic rather than in a list.
- Every figure now says where it came from. `usage_source` is `provider` when it
  is the provider's own count, `estimated` when it was guessed, and `cache` when
  nothing was sent. "The bill was $2.40" and "we think the bill was $2.40" are
  different sentences, and the owner is entitled to know which one this is.
- A **failed** call is measured too. The provider bills for the tokens it read
  before giving up, and a ledger that counts only successes under-reports
  exactly when the owner most wants the number.
- The run report shows estimated-against-spent at the top, and the header figure
  is now labelled `spent` rather than `estimated` — they are two different
  numbers and must not share a word.

- **Added `DEFECT_LOG.md` and `DECISIONS.md`** (`S-06.02.13`), asked for by the
  owner. One table of every bug, security hole and broken connection found, in
  plain English, with the date it was found — and one of design calls where the
  obvious thing was *not* done, with what that cost. The reasons things broke
  were spread across commit messages, `RETRO.md` and `CHANGELOG.md`: fine for
  reading one story, useless for *has this happened before?*
- **Writing the 34 existing defects into one table made five patterns visible
  that no individual retro had shown.** The sharpest: the same defect has now
  been fixed three times under three names (`D-14`, `D-24`, `D-32`) — two lists
  that have to match each other drifting apart, silently. Also: the bug is
  usually in code that was already `DONE` and passing, and for anything that
  *detects* something, the false positives are where the real defects live.
- Both logs are enforced rather than encouraged. `scripts/verify_board.py` fails
  when a defect marked `open` names no backlog item that exists, when an id is
  used twice, when a row does not say what went wrong or when it was found, and
  when a decision names no cost. Nine tests, each proving its rule can go red —
  a checker that never fires is worse than none, because it launders a false
  claim into a green tick.
- `RETRO.md` keeps its job: three lines of process lesson per increment. It is
  not replaced, and the defect log is not a place for lessons.

- **A CAPTCHA, sign-in form or 2FA prompt now pauses the run and asks**
  (`S-11.03.01`). `agent/wall.py` reads the accessibility tree for something only
  a person can get past; the run ends `needs_human`, names what it found, and
  leaves the browser on that page. Before this, the agent did the only thing left
  to it — burned its budget clicking around a page it could never get past and
  reported `stuck`, which says something went wrong but not that *you* are the
  fix.
- **Nothing here solves, evades or fingerprints around a challenge, and nothing
  here will.** That was decided on 2026-09-06 and written up in `RETRO.md`:
  enforcement on these platforms is account termination rather than a 429, so
  the asset at risk is the one the owner spent months building. A test asserts
  the promise structurally — `wall.py` imports a snapshot and a regex engine and
  holds no browser, connection or network client, so there is nothing in it that
  could act even if a later edit wanted to.
- **The check runs before the model is asked anything**, so a locked door costs
  no decision and no budget: a paused run resumes with all of it. `needs_human`
  is deliberately absent from the set `resume()` treats as final — a run that
  stopped because a person has to do something is exactly the run that should
  carry on once they have. `human_gate` stays final, because there the question
  is whether a consequential action happens at all, which is not a thing you
  resume into.
- **This detector is allowed to stop a run, and `injection.py` is not.** The
  trade was re-argued rather than inherited. A wrong injection match costs one
  line in a trace; a wrong match here costs the owner a glance. So this one reads
  structure rather than prose — a password field is an *editable* node, which is
  what makes "Forgot password?" (a link) and "Show password" (a button) not
  count — and asks for corroboration before it speaks. Two rules were tightened
  after they fired on ordinary pages: `/auth\b` matched
  `/help/two-factor-authentication`, and second-factor language plus any text
  box made a help article about 2FA into a wall.
- `Snapshot.names` now carries the accessible names, so the two things that ask
  *what kind of page is this* — `identity.py` for signed-in state and
  `wall.py` for something in the way — read one definition instead of two.
- The run report explains itself at the top for any ending that is waiting on the
  owner, not only for ones that went wrong. `needs_confirmation` and `human_gate`
  had been stopping runs without saying why above the fold.

- **A run can now be watched while it happens** (`S-11.04.02`). `agent/watch.py`
  turns each recorded step into a `Progress` carrying the verb, the live page
  URL and the run's running cost, and `console()` prints one block per step and
  flushes it. `AgentRun.run(..., on_progress=...)` hangs the watcher on the
  trace for the duration of the run and takes it off again in a `finally`, so a
  watcher cannot outlive the run it was watching.
- The hook lives on `Trace`, not at each call site. The trace is already the one
  funnel every recorded event passes through, and there are forty of them — a
  watcher hung there cannot be forgotten when a forty-first is added. It fires
  *after* the disk write, so nothing reaches a watcher that a crash would then
  erase, and a watcher that throws is swallowed: somebody looking at a run must
  not be able to end it.
- `S-11.04.01` tells you what a run did once it is over. This is so a run heading
  for the wrong page at step 4 can be seen at step 4 rather than read about at
  step 40. It shows; it does not stop — interrupting is `S-02.02.03`, and was
  not smuggled in here.
- **The verb a watcher reports comes from the step's recorded signature, not
  from its prose.** A click records "clicked More", and `clicked` is not one of
  the ten verbs. `[signature=...]` was already written into every action step by
  `S-11.05.02` so a resumed run could tell what it had already done. The parser
  and the writer now live together in `browser/trace.py` as `signature_in` and
  `signature_mark`, beside the `Step` they describe, so the two cannot drift.
- **Fixed: a read answered from the run's memo recorded no signature.**
  `S-11.02.04` serves a second read of an already-read page without asking the
  page again, and that step was being written without the marker every other
  action step carries. It went unnoticed because nothing had needed the verb
  back until now; a watcher could not name the step, and a resumed run could not
  match it.

- **Every run now writes a report a person can read** (`S-11.04.01`).
  `agent/report.py` renders one self-contained HTML page into the run's own
  directory: each returned fact with its value, quote, source URL, timestamp,
  trace step and screenshot, then every step in order with its cost. Provenance
  has been bound to facts since `S-11.02.02`; it lived in a JSONL file and a
  directory of PNGs, which is the right way to store an audit trail and a
  hopeless way to read one.
- It is written from `_outcome`, the single funnel every ending passes through,
  so no exit quietly skips it — and a failure to render one is recorded rather
  than raised, because the outcome matters more than the page describing it.
- **The report renders attacker-controlled text, and that is what the tests are
  mostly about.** Every quote came off a web page; the injection excerpts came
  off a page actively trying to be interpreted as instructions. Everything
  page-derived is escaped, and the tests assert on the *tags a browser would
  parse* rather than on substrings — `"onerror=" not in page` is not a test,
  because escaped text legitimately contains those characters and is inert.
  Removing the escaping makes three tests fail.
- A screenshot filename that is not local to the run directory is dropped: the
  name comes off the trace, and a name walking out of the directory would turn
  the report into a way of reading the disk.
- Nothing is loaded from the network — no fonts, no scripts, no stylesheets — so
  it opens offline from `file://` and cannot phone anywhere. Mode `0600`, beside
  the evidence it describes.

- **A page that tries to give the agent orders is now reported** (`S-11.03.02`).
  `agent/injection.py` scans both what the model is shown — the page outline —
  and anything a `read` brings back, and writes an `injection_suspected` step
  naming which rules matched.
- **It changes the record, not the behaviour, and that is the design.**
  Containment is already structural: the model can only name one of ten verbs,
  cannot supply code, and cannot reach the CRM, so an instruction on a page has
  nothing to reach for. What was missing is that an attack left no mark at all —
  the run carried on correctly and nobody learned somebody had tried. A smoke
  alarm, not a fire door; the fire door was built first.
- The quote goes in the step's capture artefact, never in `detail`: page text
  does not belong in `trace.jsonl`.
- Every pattern was narrowed against real page text. A bare "you are now"
  flagged *"You are now viewing page 2 of 5"*; a bare "new role" flagged *"Our
  new role this quarter is Head of Growth"*; a bare "act as a" flagged *"We act
  as a broker for European fintech firms"*; and an unanchored send-to-address
  flagged *"Send us your CV at careers@acme.test"*. 12 attacks caught, 11 pieces
  of ordinary business text left alone.
- **Fixed an evasion before it shipped:** the patterns stay inside one sentence
  with `[^.\n]`, so a newline stopped them and an attack wrapped across three
  lines was missed entirely. Page text arrives full of line breaks, so that was
  not a hypothetical layout. Whitespace is now collapsed before matching.

- **A resumed run does not do again what it already did** (`S-11.05.02`). The
  pair to `S-11.01.03`: a resumed run re-decides from the **live page**, and the
  page does not remember that the message was already sent — the Send button is
  still sitting there looking unpressed. Nothing in the browser can say
  otherwise; only the trace can, so action steps now carry their signature and a
  resumed run reads them back.
- The guard covers `click` and `press`, the two verbs that can send without the
  URL changing, and **deliberately not `goto`** — navigating is how a resumed run
  gets back to where it was working, and blocking a repeat would make resuming
  useless. The cost is written down where the choice is made: a URL whose GET has
  a side effect is not protected here.
- It fires only across a resume point, never inside one continuous run, where
  the agent is entitled to click the same thing twice.
- Filed `S-11.03.03`: **`press` has no consequential-action gate.** Verified —
  `check_action` is called exactly once in `browser/page.py`, inside `click`, and
  `press` calls it zero times. Enter in a form is a submit, so the gate that
  stops the agent clicking Send does not stop it sending. Filed rather than fixed
  in flight because the fix belongs with the human-gate story.

- **A killed run resumes where it stopped** (`S-11.01.03`). Construct the agent
  with `Trace.open(root, run_id=...)` and call `resume()`: the goal, budget and
  schema come back off the trace, so the caller cannot get them wrong, and the
  facts already gathered come back with their provenance intact.
- **There is no checkpoint file.** The trace is append-only, written a step at a
  time with the handle opened per write, so a killed process leaves a complete
  record up to its last step — and `Trace.read` already said in its docstring
  that replaying it is what resuming is built on. A snapshot written every few
  steps has a failure mode this does not: the snapshot and the trace can
  disagree, and then the resumed run believes something that never happened.
- Accepted findings are now written to the trace as `kind="finding"` steps, with
  the finding as a **capture artefact rather than in `detail`** — a value may be
  20,000 characters and a quote 4,000 against a 4,000-character detail cap, so
  serialising into `detail` would have produced JSON that silently failed to
  parse on replay, losing the fact it was recording. The audit detail names the
  field and its size and never the value: harvested content stays out of the
  JSONL and lives only in the 0600 artefacts.
- A resumed run gets **the remaining budget, not a fresh one**, and comes back
  knowing what it already tried — so the recovery and progress detectors from
  `S-11.01.01` and `S-11.01.02` do not restart from nothing.
- Resuming a run that already ended is refused, and a fact whose artefact is
  missing is dropped rather than rebuilt without provenance.

- **A run that is busy and getting nowhere is stopped** (`S-11.01.02`).
  `S-11.01.01` catches the agent repeating one *failing* action; this catches the
  other shape, where every action succeeds and nothing is learned — bouncing
  between two pages, or clicking a working button forever. `looping` and
  `stalled` are separate statuses because they are separate problems, and both
  return the facts already gathered.
- One notion of progress serves both detectors: a step counts if it produced a
  **new fact**, reached a page the run has **not visited at all**, or performed
  an action it had **not performed before**.
- Two corrections that the story's own third criterion forced — *a false
  positive is worse than a wasted step*. **Unvisited, not merely different**:
  bouncing between two pages is a different URL every step, so "different from
  the last one" would have let the exact cycle through. And **the action
  clause**: filling in a form is a dozen successful steps on one page with no
  fact and no navigation, and stopping that would kill the runs that were
  working. Both are recorded in the backlog as clarifications.

- **A failed action is recovered from rather than repeated** (`S-11.01.01`).
  Before this a failure became an observation and the loop carried on, with
  nothing stopping the model choosing the same failing action until the budget
  ran out — and it does choose it again, because the refusal comes back as text,
  the next decision is made from the same page, and the same conclusion follows.
  The same verb with the same arguments is now spent after one failure, and the
  model is told so plainly.
- **Three failures in a row end the run as `stuck`.** A distinct status from
  `budget_exhausted` because the two ask different things of the owner: a run out
  of budget may just need a bigger one; a stuck run needs the goal or the page
  looked at. Facts already gathered are still returned.
- **A timeout is retried with backoff**, recorded in the trace as `kind="retry"`
  so a trace cannot be misread as the agent having tried three different things.
  `ActionRefused` is never retried: a stale handle or a refused domain is an
  *answer*, and asking again produces the same refusal having spent the wait.
- Scope corrected during the build: the story said "navigation timeout, 5xx".
  HTTP status is not observable through the ten verbs — a 500 still renders, so
  `goto` succeeds. Transient means timeout-shaped, and that is recorded in the
  backlog rather than left as a criterion the code silently does not meet.

- **A page is read once per run** (`S-11.02.04`), completing F-11.02. A run is
  capped at 50 steps, and a step spent re-reading a page the run already read is
  a step not spent finding anything — with the model paying for the same text
  twice on the way in. A repeated `read` is answered from the run's own memo and
  recorded in the trace as a reuse.
- Two URLs that differ only by **how somebody arrived** are one page: the
  fragment is dropped, the host lowercased, remaining parameters sorted, and the
  tracking parameters in `TRACKING_PARAMETERS` stripped. That list is
  deliberately short — `ref`, `id`, `page`, `q` and `source` are real parameters
  on real sites, and stripping them would merge pages that differ and then serve
  the wrong text. Under-deduplicating costs a page read; over-deduplicating
  returns a wrong answer, so the bias is one-directional on purpose.
- **Acting on a page forgets it.** A document can change while its URL does not
  — "load more", a filter, a tab — so `click`, `type`, `select`, `press`,
  `scroll` and `back` drop the memo for the page they acted on. `goto` does not
  need to: it changes the URL and lands on a different key.
- Only `read` is served from the memo. `goto` is never skipped, because the
  agent often needs to *be* on a page to act on it and silently not navigating
  would leave every following handle pointing at the wrong document.

- **Fixed a bare statement being rolled back with somebody else's failed
  request** (`S-06.02.09`). The lock added on 2026-09-08 made two transactions
  safe against each other but left this:

      thread A   BEGIN, INSERT 'holder', raise  -> ROLLBACK
      thread B   INSERT 'bystander'             -> reported success
      surviving rows: []

  B's write was destroyed by A's failure, and B was told it succeeded.
- **Root cause: the connection was not in autocommit.** Python's default
  `isolation_level` silently opens a transaction before any DML and leaves it
  open, so a bare INSERT was never bare — it began a transaction the next
  thread's `BEGIN` collided with, and whose fate a later `COMMIT` or `ROLLBACK`
  decided. `db/connection.py` has always opened `isolation_level=None` and
  documents that the stores were written against it; the Postgres backend has
  always behaved that way. SQLite was the odd one out, which made this a
  data-loss bug on one backend and not the other.
- Added `GuardedConnection`: the object all 155 call sites reach through now
  serialises every statement on the shared connection. Replacing the object
  rather than migrating the call sites is both the smaller change and the one
  with nowhere left to forget. What it does not cover is stated in its
  docstring — the lock is released before rows are fetched from a returned
  cursor, so a lazily-iterated `SELECT` can still span another transaction.
  That is a read seeing in-flight state, not a lost write.
- A test parses `outreach/` with `ast` and fails if any long-lived connection is
  assigned without the guard. `backup.py`'s short-lived, function-local
  connections are correctly excluded — the hazard is a connection stored on an
  object, because that is the one two threads reach at once.

- **BREAKING: off_CRM now requires authentication on every host, loopback
  included** (`S-06.02.10`). The middleware used to enforce login only when a
  token or demo login happened to be configured, so a default local install
  served every contact to anything that could reach the port — verified: every
  `/api/` route returned 200 unauthenticated. Loopback is not an exemption. An
  unauthenticated local API is readable by every other process and user on the
  machine, by a browser extension, and by any page that can rebind a hostname to
  127.0.0.1.
  - **This does not break a local install.** Starting through
    `run_offsetx_web.py` provisions a token at `<data_dir>/local_api_token` with
    mode `0600`, prints it once, and reuses it on every restart. Paste it into
    the web UI. An explicitly set `OFFSETX_LOCAL_API_TOKEN` or demo login is
    never overwritten.
  - Refusal happens at construction, so a misconfiguration is a startup error
    rather than a service quietly handing out data.
- **Added a `Host` allowlist** (`S-06.02.10`). DNS rebinding is what makes "it
  only listens on localhost" untrue: a page points a name it controls at
  127.0.0.1 and reaches the API with the browser's cooperation. CORS does not
  prevent the request — it only stops the attacker reading the reply — and a
  rebound name looks same-origin. Unknown hosts get 421, checked before the
  public-path exemption. Set `OFFSETX_ALLOWED_HOSTS` for a public deployment;
  loopback names work with no configuration.
- Fixed a CORS mismatch: `X-off-CRM-Token` was advertised while the server read
  `x-offsetx-token`, so a client that followed the advertisement was refused.
- Test fixtures that build an app now say `allow_unauthenticated=True`
  explicitly. A config that simply forgot a token used to be indistinguishable
  from one that meant it.

- **Fixed silent data loss under concurrent writes.** `OutreachStore` shares one
  `sqlite3` connection across threads (`check_same_thread=False`) and FastAPI
  runs 193 of its 206 handlers in a threadpool, so two requests genuinely arrive
  at once. `sqlite3.threadsafety` is 3, which serialises a single *statement*
  and does nothing for a transaction made of several. Reproduced with two
  threads writing forty rows each: one raised "cannot start a transaction within
  a transaction" and **forty of the eighty rows were gone**, because the second
  thread's commit and rollback acted on the first thread's open transaction.
  `transaction()` now holds a reentrant lock for its whole body, which is what
  `db/connection.py` has always done. 64 call sites depended on this, including
  `claim_next` — the email worker's exclusive claim.
- **Fixed unbounded memory growth in the login rate limiter.** Pruning emptied
  each client's deque and left the key behind, so the dict only ever grew.
  Measured at 50,000 retained keys with every window long expired; one IPv6 /64
  is a single residential allocation and 18 quintillion keys.
- **Fixed a username timing oracle in demo login.** `and` short-circuits, so a
  wrong username returned before the password was compared and the difference is
  measurable — which leaks which usernames are real and wastes the constant-time
  comparison underneath.
- Added `tests/test_security_audit.py`: 8 regressions covering all three.

- Specified **E-11 — the agent browses the open web alone and comes back with
  facts you can trust**: 6 features, 15 stories, R-76 to R-90.
  `docs/architecture/AUTONOMOUS_BROWSING.md` is the build manual and
  `docs/architecture/E11_HANDOFF_PROMPT.md` is the self-contained prompt for
  continuing it in a fresh session.
- The epic exists because `agent/run.py` returns `result: str`. A sentence
  cannot be validated, diffed, sourced field by field, or written to a CRM. The
  three stories that carry the epic replace it: a declared schema
  (`S-11.02.01`), provenance bound to every fact (`S-11.02.02`), and a claim the
  cited page does not support being dropped rather than returned
  (`S-11.02.03`).
- Delivered `S-11.02.01`, the structured-result spine for autonomous browsing.
  A run may now declare a closed list of required fields; off_CRM validates the
  model's `record` in deterministic code, drops and audits undeclared fields,
  reports `status=incomplete` with unfilled fields instead of guessing, and
  preserves the original free-text result when no schema is supplied. The
  acceptance suite includes a real-Chromium run that reads a local page through
  the production loop. Returned values are not copied into the decision trace
  before provenance exists; provenance remains `S-11.02.02` and claim
  verification remains `S-11.02.03`.
- Delivered `S-11.02.02`, binding every returned structured fact to evidence
  captured by off_CRM itself. Trace steps now have stable ids; read evidence is
  stored privately beside the append-only trace with a screenshot, and model
  output may name only a source step id plus its quote. URL, UTC capture time and
  screenshot filename are resolved from the host-owned trace rather than trusted
  from model text. An unresolvable source is refused, and facts saved on an
  earlier page survive later navigation through their immutable provenance. The
  public `record` remains a simple field-to-value mapping for CRM consumers;
  mechanical claim verification remains `S-11.02.03`.
- Delivered `S-11.02.03`, deterministic claim verification for source-bound
  browser findings. An observed value is returned only when its cited quote is
  present in off_CRM's host-owned capture and that quote itself supports the
  value after conservative Unicode, case and whitespace normalisation. Token
  boundaries and word order stay meaningful, so `42` does not match `420`, and
  immediate negation is not erased. Model confidence cannot override a failed
  check. Unsupported fields are dropped and traced; a missing span in a capture
  marked as cut is reported as inconclusive truncation rather than hallucination.
  Derived findings remain visibly `derived` and are accepted only when every
  declared input is already a verified observed finding; this story deliberately
  does not invent a universal arithmetic or summarisation language. The dedicated
  acceptance suite includes a real-Chromium page where a plausible confidence-1
  wrong number is refused.
- Added `PRODUCT_BACKLOG.md §3b`, superseding notes for shipped definitions.
  Shipped stories are **not** edited in place — an evidence block that describes
  something which never happened is worse than no record — so each amendment
  names the story that carries the new work instead.
- Added `S-06.02.08`: every evidence command should use one test runner. On
  2026-09-06 the board went red because some evidence used `uv run pytest`
  against an unsynced venv while the rest used `python -m pytest`, and it looked
  exactly like a code defect. A lie detector that cries wolf gets ignored.

- Added several accounts per platform, each with its own budget (`S-03.02.04`).
  An account is `linkedin:work`; the default account is named after the platform,
  so every connection record written before accounts existed keeps working with
  no migration step. `browser/budget.py` holds a per-account ceiling for the hour
  and the day, checked **before** the action and recorded after it, and the
  refusal says when the budget returns. The problem being solved is not rate
  limiting — a platform that decides you are a script closes the account rather
  than answering 429 — so the defaults sit below the observed thresholds and
  nothing raises them by itself.
- **Looking is free.** `read`, `screenshot` and `wait_for` cost no budget.
  Charging for observation pushes an agent towards acting without looking first,
  which is the behaviour that gets an account noticed.
- Fixed `press` skipping the pace gate entirely. It was the one interaction that
  never met the per-host floor, so Enter could be sent at machine speed on a host
  slowed everywhere else. Found while wiring budgets: the list of verbs that
  spend was not the list of verbs that were paced. `back` is now paced too.
- `signin.connect` and `signin.verify` take an `account` label, so a second
  account is reachable and not merely representable. No function in that path
  accepts a credential, and the test that reads every signature still holds.

- Added the bounded browser Run Loop (`S-02.02.01`). A run now accepts an owner goal plus a hard decision budget, repeatedly perceives the current page, sends each decision through the existing AI egress broker, validates the model response against the browser's fixed ten-verb action vocabulary, executes at most one browser action, and appends both decisions and actions to the existing audit trace. Logged-in page state defaults to `INTERNAL` data, planning requires a Tier A/B model and fails closed otherwise, page text is explicitly framed as untrusted data to resist prompt injection, and consequential actions stop at the existing human-confirmation boundary rather than self-approving. The trace records provider/model, token estimates and estimated model cost; exact provider-ledger reconciliation remains `S-06.01.03`.
- Added revoke-and-forget for browser platform sessions (`S-03.02.03`). Disconnect now validates that vaulted material belongs to the target platform, clears the platform's cookies and origin storage from Chromium, destroys the per-account vault envelope containing the wrapped account key, removes the public connection record, and appends the attempt/result to the existing append-only browser trace without logging any session value. Browser deletion failures fail safe: the encrypted vault and connection record are retained for retry rather than showing a false disconnected state. A real-Chromium acceptance test plants a persistent auth cookie and proves it is gone after revocation.
- Added the browser session vault (`S-03.02.02`). Successful platform logins are now captured into authenticated encrypted storage before the connection can be recorded as connected. Each workspace/platform account gets its own random data-encryption key; that key is wrapped by a master sourced from Windows DPAPI, macOS Keychain or Linux Secret Service, with an explicit scrypt passphrase fallback when an OS credential store is unavailable. The raw master key and passphrase are never stored beside vault data. Vault capture/restore returns metadata only and remains trusted host orchestration, not a browser-agent verb or model tool. The shared AI egress scanner now also refuses generic cookie/token/password fields and credential-shaped free text even under `full` provider policy. CI and the pre-push hook now run the board verifier inside the locked `uv` environment so its evidence subprocesses resolve the same tested Python environment.
- Added signing in to a platform inside the box (`S-03.02.01`).
  `browser/identity.py` declares the six platforms — LinkedIn, Instagram,
  Facebook, YouTube, X, TikTok — as the signals that mean signed-in and
  signed-out, and records per workspace which are connected. `browser/signin.py`
  opens the login page, waits, and reads back *whether it worked*. **No function
  in either module takes a password, a username or a token, and a test reads
  every public signature and fails the build if one ever does.** The person
  types their password into the browser; nothing about it crosses back.
- Refused a stale element handle instead of silently re-numbering against a
  newer page. `Page._resolve` used to re-capture when the cached snapshot had
  been dropped, so a handle taken *before* an action resolved against the tree
  *after* it — pointing at a different element rather than at nothing, and the
  action reported success. Found by typing into a password field: Chrome adds a
  "reveal password" control once one has content and every later handle shifts.
  `Page.snapshot()` no longer has a "use the cached one" flag, because that flag
  was the bug.
- Fixed `profile_is_locked` treating a leftover lock file as a running browser.
  A browser stopped by a signal leaves `SingletonLock` behind and nothing
  removes it, so a profile nobody held was refused for good — in the box, a
  login that persisted in the volume and became unreachable on the next restart.
  The lock records `hostname-pid` and is now interrogated: the pid on this host,
  the singleton socket when the hostname is a container id that no longer
  exists. `clear_stale_lock` removes a proven-dead lock before launch and
  touches nothing else.
- Made that stale-lock probe work on hardened hosts that deny AF_UNIX socket
  creation. A missing socket path is now proven stale without opening a socket;
  if the path exists but the host forbids the liveness probe, the profile stays
  locked rather than risking two browsers writing the same cookie database.
- `BrowserSession.close(quit_browser=True)` sends `Browser.close` before it
  signals. Chrome batches cookie-jar writes and flushes them on shutdown, so
  killing the browser could lose the login that had just been completed.

- Registered the shipped protected-email work under E-07 / F-08.01 with five
  vertical stories and R-61–R-71. Four core stories are DONE with rerunnable
  evidence; the operator dashboard remains IN_REVIEW until its frontend test is
  re-run in an environment with the locked npm dependencies.
- Fixed the deliverability send-window test so its queue time is derived from
  the run date instead of expiring after the hardcoded 2026-08-24 fixture.
- Added the browser box (`S-03.01.01`): `browser/box.py` composes the existing
  hardened `SandboxPolicy` with the network on and a Docker named volume for the
  browser profile, so no host path is mounted and the CRM databases and keys are
  absent from the container's filesystem entirely. The DevTools port is
  published to loopback only.
- Added `browser/guard.py`: the domain allow-list, enforced per request through
  the DevTools `Fetch` domain before Chrome dispatches anything. Deny-by-default
  when unattended, allow-with-policy when attended, and the list can only narrow
  — never widen past `browser/policy.py`. Attached automatically by
  `Page.start()`.
- `SandboxPolicy` gains a `network` field defaulting to `none`, and
  `validate_network` refuses anything but `none` and `bridge`. The workspace now
  supplies its own mounts, so two differently-shaped boxes share one flag list.
- Fixed a deadlock in the CDP client: event listeners were awaited by the read
  loop, so a listener that answered an event with a command waited on a reply
  only that loop could deliver. Listeners are scheduled now.
- Added `STATE_OF_THE_PRODUCT.md`, `DEMO.md`, `CONTINUE.md` and `RETRO.md`,
  completing the delivery-process artifact set. `DEMO.md` blocks are runnable
  and were each executed before being written down.
- Added F-01.05 (three stories, R-58 to R-60) for publishing to a real platform.
  The backlog had no story for the adapter that actually posts content, which is
  the reason the product exists — found on review and added under change control
  rather than silently.
- Added S-06.02.07: an answered question stops blocking READY, so recording a
  decision unblocks the board instead of deleting the question.

- Adopted an explicit delivery process: `PRODUCT_BACKLOG.md` (now 7 epics, 15
  features, 54 stories, 71 requirements with zero orphans), `BOARD.md` as the
  single source of truth with a WIP limit of 2, `OPEN_QUESTIONS.md`,
  `DEFINITION_OF_DONE.md` and `TRACEABILITY.md`.
- Added `scripts/verify_board.py` — a standard-library-only verifier that
  re-runs every DONE item's own evidence command, fails on orphan requirements,
  orphan stories, unresolvable evidence, WIP breaches, unescalated blocks and
  stubs inside a finished slice. Wired into CI and into a `pre-push` hook.
- Documented `docs/architecture/BROWSER_AGENT_BLUEPRINT.md`: how each Strawberry
  capability maps onto this codebase, and why a Chromium fork is replaced by CDP
  attach to the owner's own browser profile.

- Added an email deliverability subsystem with isolated traffic streams,
  permission evidence, global suppression, one-click unsubscribe, domain-auth
  checks, durable send jobs, rate/backoff state, an Amazon SES adapter, signed
  SNS feedback processing, seven-day authentication freshness, reply-aware job
  cancellation, health thresholds and automatic campaign pause.
- Added the Deliverability control-centre screen and the
  `offsetx-email-worker` production worker entry point.

- Rewrote the README around the complete local-first GTM workflow and labelled
  stable, beta, alpha and external-provider boundaries explicitly.
- Replaced real contact information in public sample and test data with
  synthetic records.
- Fixed the verified AI-run endpoint crash when `checks_suite` is supplied.
- Added a shared eval-suite path resolver and shipped the eval configuration in
  the Python package, guarded by source/package drift tests.
- Repaired the reproducible `uv --locked` installation and upgraded audited
  Python dependencies.
- Added critical Ruff checks and installed-CLI smoke tests to CI.
- Added Apache-2.0 and repository metadata to the Python package declaration.

## 0.12.0

- Added a self-contained AI module (`offsetx_apollo_builder/ai/`) with a single egress broker that every outbound provider call must pass through.
- Added a config-driven provider registry in `config/providers.yaml` covering 17 providers with jurisdiction, data-retention terms, rate limits, context window, cost and a verification date; adding a provider is now a config edit rather than a code change.
- Added four-level trust tiers derived from both jurisdiction and retention terms, with per-model provenance caps, default-deny for unlisted providers, and failover that never crosses a tier boundary.
- Added four data policies (strict, minimal, standard, full) with per-tier ceilings, and owner overrides that require a written reason and record who decided and when.
- Added allowlist payload construction that starts from an empty dict, replacing the previous strip-fields-from-an-object approach.
- Added a pre-flight scanner that blocks and raises on email addresses, owner domains, twelve credential shapes, mail headers, internal field names, environment variables and local paths.
- Added local quota accounting with per-minute, per-day and spend caps, and a usage display for providers with no usage endpoint.
- Added an egress log storing the exact payload of every call, with an inspector screen so the data guarantee can be verified rather than trusted.
- Added mailbox egress lockout for every provider by default, unlockable only with an exact typed phrase and still refused for restricted tiers.
- Added per-workspace AI settings and Fernet-encrypted per-workspace provider keys with an environment-variable fallback for server deployments.
- Fixed an AI chat path that sent raw conversation text to a provider with no data policy applied, contradicting the module's own docstring.
- Fixed a scanner defect where patterns ran against JSON-serialised text, silently disabling every line-anchored mail-header rule.
- Fixed two paths that reached an AI provider without the policy guard, in the drafts API and the outreach CLI; an AST test now fails the build if a third appears.
- Moved Gmail and AI providers out of Settings into a dedicated Connectors screen showing country, trust tier, retention terms and usage per provider.
- Removed the hardcoded TypeScript provider catalogue in favour of the backend registry.
- Added a model selector, task mode, Markdown/HTML export and optional dictation to the AI chat screen.
- Added three run modes the owner picks per task: one model, compare all models side by side, or let a trusted lead model plan the job into steps.
- Added a tier restriction on the planning role: only Highest and Default trust models may lead a plan, because deciding who does what means seeing the whole job. Restricted models can still be given steps.
- Added plan validation so a returned plan cannot widen its own reach beyond the data class the caller offered.
- Added a model strip showing every connected AI, its trust level and how close it is to its daily limit.
- Expanded release coverage to 158 Python tests and 6 frontend tests, including 30 security acceptance tests for the zero-access data architecture and 16 for the run modes.

## 0.11.0

- Added a complete sales-tracker CRM whose Kanban lead cards are the single source of truth for the lead log, metrics, commissions, leak alerts and forecast.
- Added seven drag-and-drop stages, mobile status controls, required Lost reasons, optimistic revision checks and an immutable lead event trail.
- Added setter activity, speed-to-lead, booking lag, schedule disposition, show-up and DQ visibility.
- Added closer offer and close rates, one-call/follow-up sales, average deal size, revenue per call and loss-reason reporting.
- Added deposit, cash, paid-in-full, refund/clawback, net revenue, goal and net commission calculations.
- Added red leak detection for booking lag over four days, untouched follow-ups at seven days and deposits unpaid at fourteen days.
- Added best, expected and worst end-of-month revenue/cash projections with historical, pipeline, manual and fallback assumption provenance.
- Added schema v6, dedicated sales APIs, responsive React views, audit tests and operating documentation.
- Expanded release coverage to 69 Python tests and 4 frontend tests.

## 0.10.0

- Added a guarded Crawl4AI 0.9.2 JavaScript-rendering adapter with fixed non-evasive settings, browser-route SSRF checks, robots.txt enforcement and no cookies, proxies, stealth or persistent profiles.
- Added a bounded prompt compiler for target counts, role focus, competitor expansion, social-handle collection and connector requirements.
- Added a persistent local research graph for people, companies, source pages, reference-only social profiles and approved/manual interaction evidence.
- Added an official-API/manual-import boundary for social interactions without exposing social OAuth sessions to AI providers.
- Added a visible Apollo rejection ledger with retry policy, automatic-repeat blocking and strict separation from the permanent accepted-contact exclusion ledger.
- Added CRM controls for crawler choice, research prompts, compiled plans, graph relationships and Apollo outcomes.
- Expanded release coverage to 63 Python tests and 3 frontend tests.

## 0.9.0

- Added guarded Scrapling parsing and public-web crawling with robots.txt, rate, redirect, size, content-type, domain allow-list and SSRF controls.
- Added persisted discovery runs and candidates with evidence, confidence, status and exclusion reasons.
- Added exclusion against `old_pois`, previous Apollo outputs and existing CRM contacts before review or enrichment.
- Added a React Lead Discovery screen with approval, rejection, Apollo queue and CRM-import controls.
- Added an explicit account boundary: no AI provider receives browser cookies or social-account credentials, and authenticated social scraping remains disabled.
- Expanded release coverage to 60 Python tests and 3 frontend tests.

## 0.8.0

- Added pre-send generation traces, exact bulk correction previews, re-audit, approval reset and per-draft not-before scheduling.
- Added campaign send windows, weekday controls, timezone enforcement and backwards-compatible all-day API defaults.
- Added provider data policies, optional redacted payload logging, persistent health state and priority, round-robin or parallel routing.
- Added a replaceable memory boundary with approved human corrections, de-identified outcome learning and local SQLite retrieval.
- Added provider-call observability and memory control APIs plus React control-centre surfaces.
- Added explicit experiment hypotheses, controls, minimum samples, Wilson intervals and lift reporting.
- Hardened Render writable storage and expanded release coverage to 56 Python tests and 3 frontend tests.

## 0.7.0

- Added a temporary single-user CRM login with signed HTTP-only sessions and login throttling.
- Added Render Blueprint configuration, automatic `PORT` handling, and a readiness health check.
- Added a dedicated responsive login screen and logout control.
- Documented disposable Render data and the hosted Gmail OAuth boundary.

## 0.6.0

- Added encrypted local AI provider profiles and secret storage.
- Added priority-ordered provider failover, response normalization and circuit breaking.
- Added reply-first campaign automation with daily caps and explicit Gmail activation.
- Added passphrase-encrypted local backup and verified restore.
- Added provider, automation and backup controls to the React Settings page.
- Expanded the release suite to 45 Python tests and 2 frontend tests.

## 0.5.0

- Added FastAPI local CRM API and React control centre.
- Added campaigns, contacts, drafts, queue, reply stop, exports and A/B reports.
- Added local SQLite schema, migrations, FTS expert library and event audit.
- Added strict OffsetX email expert and eight versioned A/B templates.
- Added OpenAI, Anthropic, compatible API and template-application adapters.
- Added Gmail OAuth and safe local outbox providers.
- Added daily limits, working-day scheduling, atomic send claims and idempotency.
- Added API token, upload, provider URL and spreadsheet export security controls.
- Preserved both Apollo search and existing-POI enrichment workflows.
- Expanded release suite to 38 Python tests and 2 frontend tests.