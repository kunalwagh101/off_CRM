# Defect log

**What this is.** Every bug, security hole and broken connection found in
off_CRM, written down in plain English, with the date it was found.

**Why it exists.** The reasons things broke were scattered across commit
messages, `RETRO.md` prose and `CHANGELOG.md`. That is fine for a person reading
one story and useless for the question that actually matters later: *has this
kind of thing happened before?* One table answers that.

**Who it is for.** The next session — human or otherwise. A tool that reads this
file should be able to tell, without opening the code, what class of mistake
this codebase keeps making.

**The rules.**

1. Every defect found gets a row, whether it was fixed or filed for later.
2. Plain English. "The lock file was counted, not read" — not "stale mutex
   semantics".
3. Say **how it was found**. That is the most useful column, because it says
   which kind of checking works.
4. A defect found and not fixed gets a backlog ID, or it is not recorded
   honestly.
5. Design decisions do **not** go here. They go in `DECISIONS.md`.

**Kinds.** `security` · `data-loss` · `bug` · `gap` (built but not connected to
anything) · `process` (the way we work went wrong, not the code).

---

## The table

| ID | Found | Kind | Severity | What went wrong, in one line | Status |
|---|---|---|---|---|
| D-355 | 2026-11-03 | bug | medium | A21 persists in current `imagery/gates.py`: PNG header/dimensions may be accepted without actual image decoding, while a six-byte `GIF89a` payload reaches `struct.unpack` with only four missing dimension bytes and throws `struct.error`, outside the `ImageDecodeError` handler. Found by comparing September's reproduction with `develop` source. No new runtime reproduction performed in this checkpoint. | OPEN; S-06.02.56; failing regression contract in its work order; no app fix claimed |
| D-354 | 2026-11-03 | bug | high | A18 persists in current `agent/verify.py`: `_span_pattern` treats punctuation as token boundaries, so value `42` in a cited quote can match `-42`, `42.7` or `42,000`. Found by tracing the real source-owned `verify_finding` path from September's numeric-claim reproduction. This is a source-based diagnosis, not a newly observed pytest failure. | OPEN; S-06.02.55; failing regression contract in its work order; no app fix claimed |
| D-353 | 2026-11-02 | test harness | low | New F-06.22 SQL plan regression assumed the first EXPLAIN result column was descriptive text. SQLite actually returns integer id/parent columns before detail; the new 5,004-record test gave a false failure despite six feature tests passing. Source d931ba8 / Render dep-dbk9mpff3r2c7394ert0 reproduced 1 fail / 6 pass. Now test reads text cells from SQLite and PostgreSQL plans. | corrected test harness; QA verified green on f6de8a1: 7 focused, 2892 SQLite, 2915 PostgreSQL PASS; full-history verifier still open |
| D-352 | 2026-11-02 | security/reliability | medium | The F-06.22 duplicate-review API accepted unbounded group offsets. Huge values could overflow database bindings or consume excessive database work. A test-first real API/service run on Render a1c68e1 failed as expected (2 fail / 4 pass). The service and FastAPI contract now reject offsets >1,000,000. | F-06.22 corrected in d931ba8; full isolated SQLite/PostgreSQL QA passed in Render dep-dbk9o0gn74is73brdodg on f6de8a1 (7 focused, 2892 SQLite, 2915 PostgreSQL); independent penetration remains open |
| D-351 | 2026-11-02 | data quality | medium | Duplicate review called SQL trim(email), which removes only outer regular spaces and missed legacy TAB/CR/LF-padded emails. Test-first real CRM regression on Render a1c68e1 failed as expected (2 fail / 4 pass). Shared normalization now drives filter, grouped count and identity preview. | F-06.22 corrected in d931ba8; full isolated SQLite/PostgreSQL QA passed in isolated Render dep-dbk9o0gn74is73brdodg on f6de8a1 (7 focused, 2892 SQLite, 2915 PostgreSQL) |
| D-350 | 2026-11-02 | data-loss | medium | First version of the AI-context import kept SQLite snapshot connections alive longer than needed and let corrupt legacy SQLite files raise a raw database exception rather than a safe migration error. Closed the handles explicitly, refused unsupported sources and added recovery/rollback tests. | S-06.03.06 partial repair at 1236104; Render dep-dbk8on7f3r2c7391pn50 LIVE with 12 focused import PASS, real PG import PASS, full SQLite 2885 PASS, full PostgreSQL 2908 PASS; independent production acceptance still open |
| D-349 | 2026-11-02 | bug | high | The AI context template counter UPSERT used `sends = sends + 1`, which SQLite accepts but PostgreSQL raises AmbiguousColumn for because source and excluded rows both supply the column. The only new PG-focused test failed in full PostgreSQL after 2,894 tests passed. Qualified the target table column and added the real PostgreSQL test as the first PG gate. | S-06.03.06 fix `1ff58da`; verified in later pinned Render dep-dbk8on7f3r2c7391pn50 with PostgreSQL full suite 2908 PASS |
| D-348 | 2026-11-02 | bug | high | When AI task context was moved into the hosted DB, the runtime readiness probe still checked the old ephemeral ai_context.db path. Healthy hosted SQLite installs returned HTTP 503 and blocked CRM readiness, despite stored context being available. The full SQLite regression caught three failures after targeted context tests passed. Updated readiness to probe the actual database_target and added a focused regression gate. | S-06.03.06 fix at 7fdc4f2; verified in later pinned Render dep-dbk8on7f3r2c7391pn50 with SQLite full suite 2885 PASS |
| D-347 | 2026-11-02 | security | high | The initial timer migration held only the shared workspace lease; a live request or timer writer could overlap its archive/database copy and leave a stale or torn cutover. Added an exclusive workspace lock and active-lock regression. | S-06.03.06 partial fix at fe93aad and 0232cf5; exclusive lock, CLI and retry regressions passed in Render dep-dbjri0utlv9c73e36570; independent production acceptance still open |
| D-346 | 2026-11-01 | deployment documentation | medium | Branch/deployment docs described the intended main/develop Blueprint as if it were the live inventory and said both auto-deployed. The actual original, visitor and review services track develop with auto-deploy off, allowing stale runtime commits to be mistaken for current develop. Added the observed inventory and explicit branch-versus-live-commit distinction. | S-06.02.54 docs corrected from Render connector evidence; infrastructure settings unchanged |
| D-345 | 2026-11-01 | test harness | medium | Visitor Chromium asserted a synchronous Connect-button count immediately after the heading rendered, before the asynchronous provider list arrived. The real HTTPS API and cloud browser showed the provider list correctly. Wait for the actual visible Connect button, keeping the acceptance requirement. | S-06.02.54; verified desktop/mobile Chromium PASS on 97e1e7b, dep-dbj8jdgu01pc73eomva0 |
| D-344 | 2026-11-01 | test harness | medium | Visitor Chromium selected the first repeated no-provider text, a mode-tab hint deliberately hidden on mobile. Desktop passed; mobile timed out and correctly failed Render review. Scope the assertion to the actual visible welcome warning without removing the setup-flow check. | S-06.02.54; verified desktop/mobile Chromium PASS on 97e1e7b, dep-dbj8jdgu01pc73eomva0 |
| D-341 | 2026-11-01 | product regression | high | Public demo implementation disabled all AI routes and hid AI/Connectors, removing the product's main orchestration capability without owner instruction. Restored the existing broker-backed Chat, Compare, Plan and Image plus provider setup, with session-isolated AI state. | S-06.02.54 IN_REVIEW; repair LIVE on 39084d3; 37 real HTTPS checks, live browser AI/setup and final Render SQLite/PostgreSQL/Chromium review passed; valid model key still needed |
| D-342 | 2026-11-01 | security | high | Authenticated AI egress detail route looked up only log ID, without checking workspace, exposing another workspace's payload if its ID was known. RED returned 200 for a foreign log. Added the workspace check and 404 regression before exposing the visitor audit screen. | S-06.02.54 IN_REVIEW; regression passed locally and within Render 2847 full SQLite tests; visitor repair LIVE on 39084d3 |
| D-343 | 2026-11-01 | deployment gap | high | Original off-crm.onrender.com remained on eb4c820 with auto-deploy off while develop advanced. Review service test results did not update that website or prove a working model there. Its free local data may be lost on redeploy. Backup login was declined; after the risk was explained, owner go-ahead authorised the demo upgrade with that temporary-data reset. | S-06.02.54: original LIVE on reviewed 97e1e7b via dep-dbj8r2tg1s2s73f2oghg; credential settings retained; valid provider key still needed for real model proof |
| D-340 | 2026-11-01 | deployment | medium | New visitor service built successfully but its quoted custom Docker command exited early with no web listener. Public-demo container startup now selects the guarded web entry point itself and generates a private signing secret without a shell command; private container commands remain unchanged. Local TDD RED 1 failed/3 passed, GREEN 4 passed; live redeploy pending. | S-06.02.53: standard-command replacement service LIVE on aaa0a59; login/read-only/logout/readiness verified; prior override service failed/inert |
| D-338 | 2026-11-01 | security/usability | high | The existing privately configured demo login is the install owner, and CRM campaign/contact rows are shared across logins. Publishing that password or adding a guest over the same installation could expose owner/QA data. Added separate sample-only public-demo installation with fail-closed storage guards and server read-only access. | S-06.02.53: isolated visitor service LIVE, real HTTP acceptance and Render desktop/mobile Chromium PASS; full production tenancy is still separate |
| D-339 | 2026-11-01 | process | medium | Baseline board verifier found S-06.01.02 in BACKLOG and IN_REVIEW. Removed obsolete BACKLOG copy and preserved full existing IN_REVIEW evidence. | fixed in S-06.02.53 documentation; structural verifier OK, 70 recorded commits on branch |
| D-01 | 2026-08-25 | bug | high | The CDP client froze forever when a listener replied to an event | fixed · `S-03.01.01` |
| D-02 | 2026-08-25 | security | high | A URL checker checked its own prefix, so its first rule never ran | fixed · `S-03.01.01` |
| D-03 | 2026-08-25 | process | medium | A test passed with the feature deleted | fixed · `S-03.01.01` |
| D-04 | 2026-08-27 | process | medium | A large shipped module had no story, feature or requirement ID | fixed · `d96ea9d` follow-up |
| D-05 | 2026-08-27 | bug | low | A test hard-coded a date and started failing when the calendar moved | fixed |
| D-06 | 2026-08-28 | bug | high | A browser profile became permanently unopenable after a crash | fixed · `S-03.02.01` |
| D-07 | 2026-08-28 | data-loss | high | Closing the browser killed it, so a just-completed login was lost | fixed · `S-03.02.01` |
| D-08 | 2026-09-04 | security | high | A platform was reported "connected" before the vault existed | fixed · `S-03.02.02` |
| D-09 | 2026-09-04 | security | high | The outgoing-data scanner did not recognise cookies, passwords or tokens | fixed · `S-03.02.02` |
| D-10 | 2026-09-04 | process | medium | The board verifier ran under a different Python than the tests | fixed · `S-06.02.08` |
| D-11 | 2026-09-04 | security | high | Deleting the vault file left a working cookie alive inside Chromium | fixed · `S-03.02.03` |
| D-12 | 2026-09-04 | bug | medium | `Storage.deleteCookies` does not exist at browser level | fixed · `S-03.02.03` |
| D-13 | 2026-09-05 | security | high | A signed-in page counted as public, so private text could reach a weaker model | fixed · `S-02.02.01` |
| D-14 | 2026-09-06 | security | high | `press` was never paced, so Enter could be sent at machine speed | fixed · `S-03.02.04` |
| D-15 | 2026-09-06 | bug | medium | A value check accepted `42` inside `420`, and `profitable` from `not profitable` | fixed · `S-11.02.03` |
| D-16 | 2026-09-08 | data-loss | critical | Two writes at once destroyed 40 of 80 rows and reported success | fixed · `S-06.02.09` |
| D-17 | 2026-09-08 | bug | high | The first fix for D-16 passed its own test while the bug was still there | fixed · `S-06.02.09` |
| D-18 | 2026-09-08 | security | high | The login rate limiter never freed keys — 50,000 retained, all expired | fixed · `S-06.02.09` |
| D-19 | 2026-09-08 | security | medium | Demo login answered faster for a wrong username than a wrong password | fixed · `S-06.02.09` |
| D-20 | 2026-09-09 | security | critical | Every `/api/` route returned 200 with no login on a default local install | fixed · `S-06.02.10` |
| D-21 | 2026-09-09 | security | high | Nothing checked the `Host` header, so a rebound name reached the API | fixed · `S-06.02.10` |
| D-22 | 2026-09-09 | bug | low | The server advertised one auth header name and read another | fixed · `S-06.02.10` |
| D-23 | 2026-09-09 | security | high | A stale element handle was silently re-resolved instead of refused | fixed · `S-03.02.01` |
| D-24 | 2026-09-09 | gap | medium | Action signatures were recorded on failed steps only, never successful ones | fixed · `S-11.05.02` |
| D-25 | 2026-09-10 | gap | medium | Enter is not gated the way the Send button beside it is | fixed · `S-11.03.03` |
| D-26 | 2026-09-10 | bug | high | The loop detector could never fire, because its idea of progress was wrong | fixed · `S-11.01.02` |
| D-27 | 2026-09-10 | data-loss | high | A resumed run would have silently lost the facts it exists to keep | fixed before shipping · `S-11.01.03` |
| D-28 | 2026-09-10 | security | high | An injection attack split across two lines escaped the detector entirely | fixed · `S-11.03.02` |
| D-29 | 2026-09-10 | process | high | An XSS test was passing against output that was never escaped | fixed · `S-11.04.01` |
| D-30 | 2026-09-10 | bug | medium | A board audit script read story IDs wrongly and gave the opposite answer | fixed · filed as `S-06.02.11` |
| D-31 | 2026-09-11 | bug | medium | A watcher read the verb out of English prose, so `click` never matched | fixed · `S-11.04.02` |
| D-32 | 2026-09-11 | gap | medium | A read served from memory recorded no signature at all | fixed · `S-11.04.02` |
| D-33 | 2026-09-11 | process | medium | Two board entries pointed at a commit that no longer existed | fixed · filed as `S-06.02.12` |
| D-34 | 2026-09-11 | bug | medium | A page *explaining* two-factor login would have paused every run | fixed before shipping · `S-11.03.01` |
| D-35 | 2026-09-11 | security | high | The daily spend cap can never be reached — every call is recorded as costing $0.00 | fixed · `S-06.01.03` |
| D-36 | 2026-09-11 | gap | high | Providers tell us exactly what each call used, and we throw it away and guess from character counts | fixed · `S-06.01.03` |
| D-37 | 2026-09-11 | process | medium | Five test files hardcode `step-000002`, so adding any step to a run breaks them | fixed · `S-06.02.14` |
| D-38 | 2026-09-11 | bug | medium | The same pricing arithmetic existed in three places, one of which returned zero | fixed · `S-06.01.03` |
| D-39 | 2026-09-11 | process | low | A story sat unfinished for 15 days because nobody re-checked whether its blocker still existed | fixed · `S-08.01.05` |
| D-40 | 2026-09-11 | bug | high | The agent's Enter key never did anything — the event was raised and no default action followed | fixed · `S-11.03.03` |
| D-41 | 2026-09-11 | bug | low | The first Enter gate would have interrupted ordinary typing in a textarea | fixed before shipping · `S-11.03.03` |
| D-42 | 2026-09-11 | security | high | Two runs on one host each kept their own pace clock, so N runs divided the floor by N | fixed · `S-11.05.01` |
| D-43 | 2026-09-11 | data-loss | high | The budget ledger lost two thirds of its writes under concurrency — the lock was per object, the file was shared | fixed · `S-11.05.01` |
| D-44 | 2026-09-12 | process | high | The rule that an open question blocks READY had never fired — the parser threw away the line the story is named on | fixed · `S-06.02.11` |
| D-45 | 2026-09-12 | process | medium | A `git reset --hard` used to tidy up a live check destroyed an hour of uncommitted work | fixed · `S-06.02.12` |
| D-46 | 2026-09-16 | process | high | CI gave the verifier shallow Git history and no frontend dependencies, so truthful DONE evidence looked broken | fixed · `S-06.02.15` |
| D-47 | 2026-09-16 | security | medium | Historical frontend development dependency audit found four advisories including nanoid; superseded by a later five-advisory lockfile audit (D-299). Both npm production and development audits subsequently reported zero vulnerabilities after the reviewed lockfile upgrade; refer to D-299 for the executed remediation evidence | fixed and retested · `S-06.02.16`, `D-299` |
| D-48 | 2026-09-16 | process | high | The verifier allows a DONE story to declare an upstream story that is not DONE | fixed · `S-06.02.17` |
| D-49 | 2026-09-16 | process | medium | A delivery Action tried to push a `.github/workflows/` change with a contents-only token and GitHub rejected the otherwise-tested commit | fixed during `S-06.02.08` — workflow-file writes stay outside Actions |
| D-50 | 2026-09-17 | process | low | The S-06.02.17 one-shot delivery helper contained an uncompiled nested string and failed before pulling the story | fixed during `S-06.02.17` — one-shot helpers are syntax-compiled before execution |
| D-51 | 2026-09-19 | bug | high | Separate crawler processes could claim different URLs on one host and bypass the shared crawl-delay clock | code fixed · `S-05.01.01`; executable evidence pending |
| D-52 | 2026-09-19 | process | medium | TRACEABILITY.md disagreed with BOARD.md about S-05.01.01 and S-08.01.05 state | fixed during `S-05.01.01` review |
| D-53 | 2026-09-20 | bug | medium | The first competitor-teardown API route escaped its path parameter incorrectly, so FastAPI would not bind campaign_id | fixed during `S-05.01.03` source review |
| D-54 | 2026-09-20 | bug | high | The first privacy token matcher declared a two-character SQL LIKE escape, which SQLite would reject at runtime | fixed during `S-06.02.04` portability review |
| D-55 | 2026-09-20 | gap | high | Restoring a backup replaces the CRM engine, but the new privacy service would still point at the old closed store | fixed during `S-06.02.04` lifecycle review |
| D-56 | 2026-09-20 | bug | medium | Competitor teardown used Python truthiness, so the string `"false"` counted as true and could select the wrong recipe | fixed during `S-05.01.03` input review |
| D-57 | 2026-09-20 | security | high | The first privacy API draft accepted a caller-supplied workspace id instead of binding deletion/access to the authenticated workspace | fixed during `S-06.02.04` authz review |
| D-58 | 2026-09-20 | gap | high | The first privacy inventory missed residual discovery/audit JSON and personal rows in application-owned CSV queues/exports | fixed during `S-06.02.04` store-coverage review |
| D-59 | 2026-09-20 | gap | medium | Reddit had a browser action budget but no identity or policy declaration, so one platform existed in one control and not the others | fixed · `S-03.02.05` single platform registry |
| D-60 | 2026-09-20 | data-loss | high | The first companion persistence draft used process-local locking over JSON, so two server processes could overwrite each other's profile updates | fixed before review · `S-04.01.01` moved profiles into transactional SQLite |
| D-61 | 2026-09-20 | bug | high | Backup-restore fallback could replace the CRM engine without rebinding companion memory, leaving companions pointed at a closed store | fixed during `S-04.01.01` lifecycle review |
| D-62 | 2026-09-20 | gap | high | Adding persisted companion instructions created a new personal-data store that was not initially registered in subject deletion | fixed before review · companion profiles added to privacy inventory |
| D-63 | 2026-09-20 | bug | medium | The backup-restore fallback rebuilt privacy without the configured export directory, so CSV export deletion coverage could silently shrink after a failed restore | fixed during second-batch lifecycle review |
| D-64 | 2026-09-20 | data-loss | high | Backup restore could replace `ai_tools.db` while ToolRegistry still held an open SQLite connection, leaving tools/companions attached to pre-restore state | fixed during `S-04.01.01` lifecycle review; registry is closed and reconstructed around restore |
| D-65 | 2026-09-22 | security | high | Meeting creation declared a transcription provider/model but chunk upload could supply a different pair, allowing later requests to redirect raw audio to another connected provider | fixed before S-07.01.03 review; meeting provider/model are immutable and mismatch is refused before broker I/O |
| D-66 | 2026-09-22 | privacy/recovery | high | The new meeting transcript database was initially outside subject-access/deletion and encrypted backup coverage | fixed before S-07.01.03 review; meeting transcripts are a registered privacy store and SQLite-safe backup member |
| D-67 | 2026-09-22 | privacy/reliability | high | Local screen sharing was not owned by cleanup until after meeting creation, so a denied microphone or failed API create could leave screen capture active; failed final chunks also had no recovery path | fixed before S-07.01.03 review; streams are owned immediately and unfinished chunks expose retry/discard |
| D-68 | 2026-09-22 | security | high | 54 JSON API handlers accepted raw dictionaries, so malformed or wrongly typed values could enter business logic before framework validation | fixed · S-06.02.02 strict request contracts plus registered-route validation audit |
| D-69 | 2026-09-22 | accessibility | medium | Hash navigation changed the visible screen without moving keyboard/screen-reader focus, and one hover-only tooltip was not exposed on keyboard focus | fixed · S-06.02.05 shared main-focus management and focus-within tooltip path |
| D-70 | 2026-09-22 | process | medium | S-06.02.02 appeared twice in BOARD.md IN_REVIEW after sequential state updates, making board counts untrustworthy | fixed during batch-4 close-out; duplicate removed before handoff |
| D-71 | 2026-09-23 | bug | high | A persisted crawler URL rejected by the current policy could consume the claim limit forever and starve valid due URLs behind it | code fixed · `S-05.01.01`; executable evidence pending |
| D-72 | 2026-09-23 | bug | high | Extraction-pack CSS selectors were length-checked but never syntax-checked, so malformed config could load and fail only when a page was parsed | code fixed · `S-05.01.02`; executable evidence pending |
| D-73 | 2026-09-23 | bug | high | Competitor numeric evidence accepted NaN/Infinity, allowing later timeline crashes or non-finite performance records | code fixed · `S-05.01.03`; executable evidence pending |
| D-74 | 2026-09-23 | bug | medium | A removed/renamed video recipe leaked UnknownRecipe out of competitor teardown, turning catalogue drift into an API 500 | code fixed · `S-05.01.03`; executable evidence pending |
| D-75 | 2026-09-23 | process | high | GitHub-hosted CI repeatedly creates the quality job but fails before runner allocation with zero steps/no logs, blocking every repository evidence gate | open · `S-06.02.18` |
| D-76 | 2026-09-23 | bug | high | A partial privacy-deletion retry trusted an old per-store success without checking whether matching personal data had been written again | code fixed · `S-06.02.04`; executable evidence pending |
| D-77 | 2026-09-23 | security | high | Companion runtime asked for its own memory scope, but the production CRM memory search silently merged global memory into that result | code fixed · `S-04.01.01`; executable evidence pending |
| D-78 | 2026-09-23 | data-loss | high | Resume could regenerate a deleted managed PLAN.md from the original goal, silently losing the owner's edited steering state | code fixed · `S-02.02.02`; executable evidence pending |
| D-79 | 2026-09-23 | security | high | Generic model-visible assignments/fields such as api_key or client_secret could bypass the credential scanner when the value had no vendor-specific token prefix | code fixed · `S-06.02.01`; executable evidence pending |
| D-80 | 2026-09-22 | process | high | In a shallow clone the verifier says every recorded commit is "not a commit in this repository at all", and CI checks out shallow — so once runners are available the ancestry rule turns every CI run red for a reason that has nothing to do with the board. Found when a cloud session started shallow and 32 DONE stories looked falsified; `git fetch --unshallow` made the board green | in review · S-06.02.20 (full run pending) |
| D-81 | 2026-09-22 | security | medium | The video director puts the owner's typed house style in the system prompt, which the broker neither logs nor classifies — a `public` request can carry owner text to a tier C model and the egress log does not show it. Found while tracing where product details could safely travel; the GTM engine was designed around it rather than through it | in review · S-12.01.03 |
| D-82 | 2026-09-22 | gap | high | A plan's posting channel had no path from the screens to a published post: nothing pairs its posting and picture campaigns in content automation, switches the automation on or approves a post, and Apply's next steps implied that connecting an account and resuming was enough. Found while writing the review's remedy for "nothing published" and looking for the screen it should open — there was none | fixed · `S-12.02.06` IN_REVIEW; real browser and drafting gates open |
| D-83 | 2026-09-22 | bug | medium | The plan's capacity counted a disabled social account, so a plan could be sized on posts that `publish_due` would skip. Found while counting accounts for the review | fixed · `S-12.02.03` |
| D-84 | 2026-09-22 | bug | medium | The pacer steered by a campaign's *first* views goal, but setting a goal adds a row — so a goal set later, by hand or by a plan revised after its window closed, was never the one it steered by. Found while checking that a revised plan's goal would reach the pacer | fixed · `S-12.02.03` |
| D-85 | 2026-09-23 | bug | medium | With no model, a revision of a plan whose mail was bouncing kept the same email volume: the rules only halved it when a *model* had chosen "send fewer", and the rules' own first remedy for bad delivery is the owner's — clean the list. The design doc said the rules halve it. Found re-reading a test whose name promised it while its body hand-built a review to make it pass | fixed · `S-12.02.04` |
| D-86 | 2026-09-23 | bug | low | After a plan was revised, the Strategy screen still showed the previous version's Apply next steps under the new draft, and labelled every revision note "what was corrected" when most were not corrections. Found by walking the screens in a real browser | fixed · `S-12.02.04` |
| D-87 | 2026-09-23 | security | high | Pausing a posting campaign did not stop posting: `publish_due` checked the account and never the campaign, and content automation planned and drafted for paused pairs. So a plan's Apply — which pauses every campaign it touches and says "nothing has sent" — could be followed by a scheduled post going out. Found by the cold review of `E-12` | fixed · `S-12.02.03` |
| D-88 | 2026-09-23 | process | medium | Every GTM egress test checked the request the brain built, never the payload a provider receives, so none could see that the shape filter hides the goal and the measured rates below `full`. Tests now build the real payload; whether those numbers should leave is `Q-25`. Found by the cold review | fixed · `S-12.02.03` |
| D-89 | 2026-09-23 | gap | high | A plan's angle — and a revision's new angle — reached no email and no post: drafts came from templates and product fields, posts from the one-liner. So "try a new angle" changed nothing that was sent. Posts now use the applied plan's angle, and templates can say `{product_angle}`. Found by the cold review | fixed · `S-12.02.04` |
| D-90 | 2026-09-23 | bug | high | A plan whose campaign was deleted from the CRM (a restored backup does this) could never be applied again — Apply updated a campaign that was not there, every time — and the Product screen could not drop the dead link, because Save resent it and was refused. Found by the cold review | fixed · `S-12.02.02` |
| D-91 | 2026-09-23 | bug | medium | The CRM creates campaigns active and Apply paused them only after linking, so a failed link left an active, unlinked campaign behind. Found by the cold review, which made the link fail once | fixed · `S-12.02.02` |
| D-92 | 2026-09-23 | bug | low | A model reply with `"daily_volume": 1e999` (valid JSON for infinity) raised OverflowError and gave the owner a 500 instead of a clamped plan. Found by the cold review | fixed · `S-12.02.01` |
| D-93 | 2026-09-23 | bug | medium | The payload keeps the first 4,000 characters of campaign notes, and "Never claim" and the owner's notes came last — a full product lost both. They now lead. Found by the cold review | fixed · `S-12.02.01` |
| D-94 | 2026-09-23 | bug | low | Below five measured posts, every pacer hold became "wait for data" — including a hold for a passed deadline or no goal at all. Found by the cold review | fixed · `S-12.02.03` |
| D-95 | 2026-09-23 | bug | medium | Replies arriving between a review and the next version's Apply were counted by neither version, and a resumed first Apply recorded a baseline that hid its own earlier sends. The baseline is now taken from the review the revision is written from. Found by the cold review | fixed · `S-12.02.04` |
| D-96 | 2026-09-23 | bug | medium | With two revisions drafted, applying the older after the newer superseded the newer; and Apply turned archived campaigns — including ones a revision had dropped — back into paused. Found by the cold review | fixed · `S-12.02.04` |
| D-97 | 2026-09-23 | gap | low | A plan's posts-a-day is read by nothing that posts — the rate is set on Posting — yet the rules revision "raised" it. The rules now name it as a Posting-screen action; the plan's number still shows as intent until posting runs from the plan. Found by the cold review | fixed · `S-12.02.06` IN_REVIEW |
| D-98 | 2026-09-23 | process | medium | Tests that passed without the feature: the no-model-imports walk forbade three `ai/` modules instead of the package, and two tests asserted only `issubclass`. The walk now forbids all of `ai/` and a clean interpreter checks what really loads. Found by the cold review | fixed · `S-12.01.01` |
| D-99 | 2026-09-23 | bug | medium | On the Product screen, "New product" did nothing once a product existed, boxes ticked and not saved followed the owner to the next product, and "Save to drop them" could not drop a deleted campaign. Found by the cold review; the fix was checked in a real browser | fixed · `S-12.01.02` |
| D-100 | 2026-09-23 | data-loss | high | Independent WorkspaceAISettingsStore processes used only per-instance thread locks, so concurrent read-modify-replace writes could erase another workspace's provider settings or encrypted keys | code fixed · `S-06.01.01`; executable evidence pending |
| D-101 | 2026-09-23 | bug | high | The workspace username regex double-escaped NUL/CR/LF, accidentally rejecting ordinary characters such as r, n, x and 0 instead of the intended control characters | code fixed · `S-06.01.01`; executable evidence pending |
| D-103 | 2026-09-23 | bug | high | Every privacy route (subject access, deletion preview, deletion) raised NameError: a module-level helper called `_workspace_id`, which exists only inside `create_app`. Found by the repository's own ruff gate at consolidation; `feature/next-three-batch-4` had never run it because CI could not start (D-75) | fixed · `S-06.02.19` |
| D-104 | 2026-09-23 | process | high | `tests/test_frontend_accessibility_contract.py` put a backslash inside an f-string expression — valid only on Python 3.12 — so on 3.10 and 3.11, which the project supports, the whole file failed to load and its twelve tests never ran | fixed · `S-06.02.19` |
| D-105 | 2026-09-23 | process | high | The keyboard/screen-reader contract tests checked nothing: two regexes were double-escaped and could match only their own twin test's source; `[^>]*` stopped at the `>` of `onClick={() =>`, hiding every attribute after it; the focus check read the first component rule instead of the global one; and the vitest twin lacked the hidden-backdrop exemption the Python contract grants. Each repaired check was proven by breaking the code on purpose | fixed · `S-06.02.19` |
| D-106 | 2026-09-23 | security | high | The GTM brain set the AI key resolver on the one shared broker before each call, so two workspaces planning at once could each run on the other's key. Found when the merged branch ran batch-4's test that forbids mutating the shared broker | fixed · `S-06.02.19` |
| D-107 | 2026-09-23 | bug | high | The strict request schemas from `S-06.02.02` decided what the older endpoints already decided with a sentence: 34 fields became required that the handlers default (a pipeline without an image campaign, a clip without a track), 8 enums answered 422 before the handler's readable 400, and a clamped cap became a refusal. Separately, every ValueError reason was replaced by one fixed sentence, hiding "Unknown campaign kind" and the rest. 29 finished-story tests failed | fixed · `S-06.02.19` |
| D-108 | 2026-09-23 | process | high | The route-authentication test imported a name removed a day after it was written, and on FastAPI 0.139 it could not see routes inside included routers at all — so the email-delivery and GTM routes, the public SNS callback among them, were never checked | fixed · `S-06.02.19` |
| D-109 | 2026-09-23 | bug | high | Timers have no request, and reading a login from one crashed: every timed run of the content engine raised AttributeError on `cookies`. The GTM product lookup for drafts asked with the install's workspace, so a product linked from a workspace login was invisible to its campaign's emails and their forbidden-claim check | fixed · `S-06.02.19` |
| D-110 | 2026-09-23 | security | high | The scanner let a bare `token=<value>` in prompt text reach an image or transcription provider, although a `token` field name was already refused. Hidden because the tests for it switched on no model, so the broker refused at planning and the scanner was never reached | fixed · `S-06.02.19` |
| D-111 | 2026-09-23 | bug | high | The config check treated a session secret without a demo username and password as half a demo login and refused to start, but the secret also signs workspace logins — so no workspace-login install could start | fixed · `S-06.02.19` |
| D-112 | 2026-09-23 | bug | low | Four platform, sign-in, revoke and vault test files could not load: the platform registry made `domains` required, and code-built platforms in finished stories' tests had none. A companion fixture used an image reference the sandbox refuses by design | fixed · `S-06.02.19` |
| D-113 | 2026-09-23 | gap | medium | A finished story's test pinned the pre-meeting Permissions-Policy header, and no test covered a hosted install, where the meeting feature's microphone grant must not apply | fixed · `S-06.02.19` |
| D-114 | 2026-09-23 | data-loss | high | Restoring a backup left the old database's WAL and SHM files beside the restored one, so changes made after the backup replayed over it — a companion deleted after the backup stayed deleted. The backup also named a fixed list of stores and so omitted `gtm.db`, images, video and posts | fixed · `S-06.02.21` |
| D-115 | 2026-09-23 | process | high | `feature/next-three-batch-4`, the newest line, had never run its own suite: 33 tests failed and 5 files could not load. CI could not start (D-75) and nothing else ran it, while its board called the work IN_REVIEW rather than broken | fixed · `S-06.02.19` |
| D-116 | 2026-09-23 | bug | high | The Docker image could not build — on `main` too, so Render could not deploy the branch it is pointed at. `tsc -b` type-checks the video tests, which import a fixture from `tests/`, and the image copied only `frontend/`. Found by building the real image; `integration/main-consolidation` had fixed it and never merged | fixed · `S-06.02.21` |
| D-117 | 2026-09-23 | bug | medium | A transaction opened inside another raised "cannot start a transaction within a transaction", though the lock's docstring said nesting was supported. Now a savepoint | fixed · `S-06.02.21` |
| D-118 | 2026-09-23 | bug | high | In the ported restore, `/health/ready` — Render's health check — was a 404 in the built image, because the recovery routes were added after the frontend's mount at `/`. No test saw it: tests run without a frontend build. Found by running the real container before committing | fixed · `S-06.02.21` |
| D-119 | 2026-09-23 | data-loss | medium | The AI cache and the sent-mail index close only the calling thread's connection, so a connection another thread opened stayed open on the file a restore moves aside | fixed · `S-06.02.21` |
| D-120 | 2026-09-23 | bug | medium | The Connectors screen asked for `/api/v1/status`, which never existed, so its Gmail panel showed an error (audit A35). A new test now reads every API path the screens call and checks the server has it | fixed · `S-06.02.21` |
| D-121 | 2026-09-23 | bug | high | The sandbox's advertised writable `/work` directory rejects writes from the container's user (audit A32, reproduced in real Docker on 2026-09-07; the code is unchanged since) | open · `S-06.02.23` |
| D-122 | 2026-09-23 | bug | medium | A 60-frame default Colour export was refused by the old 4096-byte size floor (audit A34). A WebM video-sample check and independently encoded regression fixture are now implemented; full tests/browser acceptance remain unrun | in review · `S-06.02.39` |
| D-123 | 2026-09-23 | bug | high | Creating a second campaign left the first one selected, so a contact import right after went into the wrong campaign (audit A33). The new campaign was selected, then the stale list — which did not contain it yet — made a rule snap the selection to its first entry. Reproduced in real Chromium on `feature/next-three-batch-4`: after creating "Second campaign" the header still said "First campaign", through Contacts and a reload | fixed · `S-06.02.22` |
| D-124 | 2026-09-23 | security | critical | Backup export and restore answered any login. The whole-workspace archive holds the install token, the key that signs every session, every login and the AI keys — so a workspace login could export it, read the install token out, and administer every workspace, or restore over all of them. Found by the cold review of `develop`. Now only the install owner may (the token, or the `local` workspace's own login, DD-59), checked before an upload is opened | fixed · `S-06.02.21` |
| D-125 | 2026-09-23 | security | high | Any login could draft a campaign another workspace had linked to its private product and read the product in the drafts — every field, by adding placeholders to the install-wide templates. The draft writer read the product through the link's workspace, which was the `D-109` fix. It now reads with the caller's workspace and refuses another's (DD-60, DD-61). Any login could also run the content timer now, or reconfigure it, and it runs as the install on the owner's keys; both are owner-only | fixed · `S-06.02.19` |
| D-126 | 2026-09-23 | data-loss | high | With the CRM database outside the data directory (a local install that sets `OFFSETX_OUTREACH_DB`), a restore and its rollback moved only the database file. Its WAL and shared-memory files stayed at the live path, and SQLite replayed one generation's writes over the other: the integrity check failed and 26 of 400 rows were left. Production was not exposed — it keeps the database inside the data directory. The sidecar files now move with the file, before it | fixed · `S-06.02.21` |
| D-127 | 2026-09-23 | data-loss | high | `docker-compose.yml` still mounted `./local_data` at `/app/local_data`, but the image keeps its data under `/var/lib/offcrm/local_data` since the WP1 port: a restarted stack opened an empty CRM and wrote into an unnamed volume that `down` then `up` does not reattach. The outreach and notebook CLIs likewise ignored `OFFSETX_DATA_DIR` and opened a second, empty CRM beside the real one | fixed · `S-06.02.21` |
| D-128 | 2026-09-23 | bug | medium | Every backup and restore answered 500 on Python 3.10, which the package declares it supports: the drain used `asyncio.timeout`, new in 3.11. The suite could not even load on 3.10 (`tomllib`). The whole suite has now run on a real 3.10 | fixed · `S-06.02.21` |
| D-129 | 2026-09-23 | bug | medium | The web app could not start while the email worker was mid-cycle: start-up took the recovery lock without waiting, even with nothing to recover. And the worker never checked for an unfinished restore, so after a failed rollback it worked over a half-restored workspace | fixed · `S-06.02.21` |
| D-130 | 2026-09-23 | bug | medium | If the campaign list failed to load, every screen disappeared — Settings, where restore lives, included — which is when recovery is needed. `docs/architecture/CAMPAIGN_SELECTION.md` said only campaign work waits; now that is what happens | fixed · `S-06.02.22` |
| D-131 | 2026-09-23 | data-loss | low | The AI tool registry closed only the calling thread's connection, so the companion routes and the readiness probe left theirs open on the old workspace after a restore. The `D-119` fix, its test and a docstring all claimed every store was covered | fixed · `S-06.02.21` |
| D-132 | 2026-09-23 | security | low | The scanner let `api_token=`, `id_token=` and `bot_token=` through in prompt text, although `id_token` is refused as a field name: it matched `token` after four fixed prefixes only, so the `D-110` fix was incomplete | fixed · `S-06.02.19` |
| D-133 | 2026-09-23 | bug | low | A backup or restore shut the app to requests first, then waited — with no limit — for the scheduled jobs: a routine waiting half an hour for a browser lease held every request at 503. And a timer started again while still finishing a run ended after it, silently (DD-62) | fixed · `S-06.02.21` |
| D-134 | 2026-09-23 | gap | medium | The outreach, notebook and eval command-line tools write into the workspace without the shared lease the email worker takes, so a write made during a restore lands in the generation being swapped out and is lost with it | fixed · `S-06.02.24` |
| D-135 | 2026-09-23 | security | medium | Campaigns, contacts, drafts and templates belong to no workspace. A draft written from one workspace's private product can be read by every login, and a workspace can link any campaign nobody has linked yet. Workspace isolation (`S-06.01.01`) covers keys, sessions, AI settings and products, not CRM rows. Whether it should is the owner's call (`Q-27`) | open · `S-06.01.06` |
| D-136 | 2026-09-23 | bug | low | When the campaign list failed, the top bar said "API access needed" and offered the token box whatever the cause — a 500 or an unreachable server included — pointing the owner at the wrong fix. Found in a real Chromium while checking `D-130`. Now only a 401 or 403 says so; anything else says "Backend error" | fixed · `S-06.02.22` |
| D-137 | 2026-09-23 | bug | low | Opening a screen can scroll its own top out of view. Seen on Settings in real Chromium while checking `D-130`: the title sat half under the top bar, and the "Could not refresh campaigns" panel — the reason campaign work was blocked — was above the viewport. `focusMainContent()` focuses the main area without `preventScroll` under a 68px sticky top bar; whether every screen is affected is the first step of the work order | fixed · `S-06.02.25` |
| D-138 | 2026-09-23 | bug | medium | Two command-line defaults still ignore `OFFSETX_DATA_DIR`: `offsetx-outreach gmail-authorize` writes the Gmail token to `local_data/gmail_token.json` (the web app reads it from the data directory), and `offsetx-db` defaults to `local_data/ai_egress.db`. The same drift as `D-127`, in the paths it did not cover | fixed · `S-06.02.24` |
| D-139 | 2026-09-24 | gap | medium | `offsetx-artifacts` writes its XLSX, PPTX and PDF reports beside the trace, and the app records agent runs under the data directory, so rendering one wrote into the workspace without the lease. `S-06.02.24`'s work order listed it as not a workspace writer; the re-check the work order asked for found it | fixed · `S-06.02.24` |
| D-140 | 2026-09-24 | bug | medium | `.env.example` set `OFFSETX_OUTREACH_DB` and `OFFSETX_GMAIL_TOKEN` to paths under `local_data/`, so a `.env` copied from it kept both files behind when `OFFSETX_DATA_DIR` moved: a production start with that `.env` refused, and a local install's Gmail token fell outside the folder the backup covers. Both lines are now commented out, with the reason | fixed · `S-06.02.24` |
| D-141 | 2026-09-24 | bug | low | `offsetx-notebook` looked for the AI context beside the CRM database; the web app keeps it in the data directory. With the CRM database named elsewhere the two differ, and a notebook bundle silently lost its "what worked" section | fixed · `S-06.02.24` |
| D-142 | 2026-09-24 | bug | high | A tool run as root in the container before the app served a request left a root-owned 0600 lock file; the app's own user could not open it, and every API request answered 500 while health stayed green. The email worker could already do it; `S-06.02.24` added six tools that could. Lock files are now made 0644 (a 0600 one the app owns is widened) and opened read-only when they cannot be written; the first fix, read-only alone, could not open a 0600 file at all — a second fresh-context review caught it, and a check with two real users proves the second | fixed · `S-06.02.24` |
| D-143 | 2026-09-24 | bug | low | `offsetx-evals` and `offsetx-tools` worked out the data directory through the web app's settings, which write an API token into it — before the lease was taken, so a refused run still wrote, and could recreate a folder a restore had just moved | fixed · `S-06.02.24` |
| D-144 | 2026-09-24 | bug | low | The tools' second refusal said a restore was interrupted and that starting the web app rolls it back; a committed journal left by a cleanup failure is kept, not rolled back, in an app already running. It now says to restart the app, which completes it | fixed · `S-06.02.24` |
| D-145 | 2026-09-24 | gap | low | `offsetx-db` looked only at `copy-log --from` and at the data directory: a mistyped `--to` path made a SQLite file in a workspace held by a restore, and a check of a CRM database outside the data directory — which a backup covers — took no lease | fixed · `S-06.02.24` |
| D-146 | 2026-09-24 | gap | medium | The tools lock the data directory worked out from the current folder, not the workspace whose files they open: an explicit `--db`, `--token` or absolute path to the web app's files from another folder, `OFFSETX_DATA_DIR` set only in `.env` (read by two of the six tools), or `offsetx-artifacts --run-dir .` from inside a run still write during a restore. Found by the fresh-context review | in review · `S-06.02.28` |
| D-147 | 2026-09-25 | bug | high | Every chat call to NVIDIA's `nemotron-3-ultra` failed with 400: `config/providers.yaml` sent `reasoning_budget`, which NVIDIA forwards as vLLM's `thinking_token_budget`, and its V2 model runner refuses it. The owner saw "Every permitted provider failed", then a cool-down. The option is removed; `max_tokens` still bounds the thinking. A test had asserted the option was sent | fixed · `S-06.02.29` |
| D-148 | 2026-09-25 | bug | high | Every Render deploy of `develop` timed out: the host guard (DNS-rebinding defence, `S-06.02.10`) answered 421 to Render's health checker, which sends an internal host, so `/health/ready` never passed. Health checks are now exempt — they say only ready or not — and Render's own `RENDER_EXTERNAL_HOSTNAME` is answered without configuration. The API stays behind the allowlist | fixed · `S-06.02.10` |
| D-149 | 2026-09-25 | bug | high | Connecting any AI provider from the Connectors screen with the form's defaults answered "Request validation failed": the form sends a daily call cap of 0 ("use the provider's own limit"), and the strict request contract added on 2026-09-22 (`a3208f9`) required at least 1. Found by the owner on the live app, after a redeploy had wiped the stored connection. The contract accepts 0 again, which the quota already reads as no cap of ours. No other form sends 0 to an at-least-1 field (checked) | fixed · `S-06.02.30` |
| D-150 | 2026-09-25 | bug | medium | A refused request showed only "Request validation failed": the server listed the field and the reason under `errors`, but every screen shows `detail` alone, so the owner had nothing to change. `detail` now names the first refused field and what was wrong; the body is still never echoed | fixed · `S-06.02.30` |
| D-151 | 2026-09-25 | security | high | A key set as `OFFSETX_AI_<PROVIDER>_KEY` on the server was handed to every workspace login, other clients' included: any of them could connect that provider with a blank key and spend the owner's key, their data leaving on the owner's account. Found while answering the owner's "keys belong in the app". The fallback is removed, and a connect with no key is refused with the next step | fixed · `S-06.02.31` |
| D-152 | 2026-09-25 | security | medium | The trust override route stored whatever `decided_by` the request sent, so any caller could put a colleague's name on a decision to raise trust. Found while building per-model trust. "Who decided" now comes from the signed-in login; the field is still accepted and ignored | fixed · `S-06.02.33` |
| D-153 | 2026-09-25 | bug | medium | Granting a provider full access rebuilt its override record from scratch, which would have wiped the owner's per-model trust settings; and a trust tier raised through that route needed no reason. Found while building per-model trust | fixed · `S-06.02.33` |
| D-154 | 2026-09-25 | security | critical | Any login could make the server read any of its environment variables and send the value to a URL of its choosing: a draft request could bring its own provider naming `api_key_env` and `base_url`, and a provider profile could name a variable too. `OFFSETX_SESSION_SECRET` among them would let the caller forge the owner's login. Older code the `S-06.02.31` fix missed; found by its fresh-context review. A request can no longer bring a provider, a profile cannot name a variable, and profiles never read the environment | fixed · `S-06.02.31` |
| D-155 | 2026-09-25 | security | critical | Provider profiles were install-wide with a caller-chosen owner: any login could list the owner's profiles, re-point one at its own server and run the live test to receive the owner's typed key, or draft with the owner's profiles by naming them. Profiles now belong to the caller's workspace; the install owner still manages all | fixed · `S-06.02.31` |
| D-156 | 2026-09-25 | security | high | Blocking a provider did not block a model with its own trust setting: the model's setting won in both directions, so the broker still routed person data to it. A model is now trusted as much as its provider or less (`DD-65`, amended) | fixed · `S-06.02.33` |
| D-157 | 2026-09-25 | bug | high | The Connectors card's reset link posted an empty override, which deleted the owner's trust blocks along with a full-access grant. It now withdraws only the grant | fixed · `S-06.02.33` |
| D-158 | 2026-09-25 | security | high | A provider-level full-access grant let owner-lowered and origin-capped models be sent full data: the tier was right, the data policy was not clamped to it. A grant now applies only to models at their provider's tier | fixed · `S-06.02.33` |
| D-159 | 2026-09-25 | bug | high | Saving the model list reset the connection's call and spend caps to none and its data policy to the default: the Models panel posts only the models, and Connect rebuilt the record. Caps and policy not sent now keep their saved values | fixed · `S-06.02.32` |
| D-160 | 2026-09-25 | security | medium | A raised model tier could stand with no recorded reason (raise the provider with one, set a model to match, clear the provider), and clearing a setting deleted its who and why. The model's baseline is now its origin cap, not the path taken, and every trust change is kept in a bounded history | fixed · `S-06.02.33` |
| D-161 | 2026-09-25 | bug | medium | A blank or unreadable custom cap was posted as `Number("")`, which is 0 — "no cap". The form now refuses it with a sentence and saves nothing | fixed · `S-06.02.32` |
| D-162 | 2026-09-25 | bug | low | Connect checked for a stored key outside its write lock and stored the key after it: a disconnect landing in between left a provider connected with no key. Both now happen under the lock | fixed · `S-06.02.33` |
| D-163 | 2026-09-25 | bug | low | Models switched on from the live catalogue could not have their trust set; "Find models" showed default tiers, not the owner's; a card the owner blocked read "Blocked by default" and lost its Disconnect button; two models named alike (`gpt-4o`) had the same accessible name | fixed · `S-06.02.33` |
| D-164 | 2026-09-25 | security | low | An unknown model could be lifted by its own trust setting if an origin rule it once matched was deleted; and DeepSeek, Moonshot, Zhipu and Qwen's own APIs listed their models with no origin cap, so one provider raise lifted them where NVIDIA's copies stayed capped. Unknown models stay blocked, and those six models carry the cap | fixed · `S-06.02.33` |
| D-165 | 2026-09-25 | security | high | The install owner's fallback drafts used every workspace's provider profiles, so a client could save one at priority 1 pointing at its own server and receive the owner's contacts — and write the owner's drafts. Found by the second fresh-context review of the `S-06.02.31` fixes. A draft now uses only the caller's own profiles, the owner's included, and a request can no longer name whose | fixed · `S-06.02.31` |
| D-166 | 2026-09-25 | security | medium | A profile's owner was a label the request supplied: the old Settings form always sent "default", so a workspace given the id `default` owned the owner's profiles, key included, and client profiles saved before `D-155` sat in the owner's draft chain spending the client's key. The server now records the owner from the login; a profile saved before that is in no chain until the install owner confirms it (`DD-68`) | fixed · `S-06.02.31` |
| D-167 | 2026-09-25 | security | medium | The full-data grant applied wherever a model's tier equalled its provider's, so lowering NVIDIA to Restricted handed the grant to the Chinese-built model already capped there, and to a model the owner had lowered: lowering trust raised what was sent. The grant is now judged against the provider's default tier (`DD-67`). Found by the second fresh-context review | fixed · `S-06.02.33` |
| D-168 | 2026-09-25 | security | medium | The provider call log (`/provider-calls`) was not scoped: any login read every workspace's calls, prompts included where payload logging was on, and the calls recorded no workspace. Calls now carry the caller's workspace; a client reads its own, the install owner every workspace's | fixed · `S-06.02.31` |
| D-169 | 2026-09-25 | bug | low | Disconnect removed the provider and its key in two lock windows; a Models-panel save landing between them re-created the connection with no key. Both now go in one window, the key first | fixed · `S-06.02.33` |
| D-170 | 2026-09-25 | bug | low | A withdraw or trust click that changed nothing still wrote a history entry, into a record with no `provider_id`; and reasons of 2,000 characters times 100 entries times every provider sat in a document read on every request. No-change clicks now record nothing, reasons are capped at 500 characters and the history at 20 entries | fixed · `S-06.02.33` |
| D-171 | 2026-09-25 | bug | medium | The owner's "full access" grant never sent more: Connect clamped what is sent to the tier's ceiling and ignored the grant, and the "Allow anyway…" button appeared only on blocked providers, which receive nothing at any level — while the card said "Full access granted by you". Found while fixing `D-167`; older than this session's work. The grant now really sends full data, is offered only where it can change something, and says when it is paused | fixed · `S-06.02.33` |
| D-172 | 2026-09-25 | bug | low | After the owner changed a provider's trust, its card still showed the config tier's ceiling and data classes ("Tier C allows up to Standard"), and "Sends" showed the stored choice where the ceiling cut it. Both now follow the owner's trust | fixed · `S-06.02.33` |
| D-173 | 2026-09-25 | gap | medium | Drafts personalise with a model only through provider profiles, and no screen has added one since the AI providers moved to Connectors (`5e03c6c`): Settings keeps the save, test and remove code but no form, and the Drafts screen points at it. A dead end; which path drafts should take is the owner's call (`Q-28`) | open · `S-06.02.35` |
| D-174 | 2026-09-26 | bug | low | The connect form's "How much to send" had no Pseudonymous option, though it is the level a Restricted provider starts on: its form showed Strict, and saving other settings lowered what the provider was sent without saying so. Found walking the card for `D-172`. Every level the server has is now offered, in order | fixed · `S-06.02.33` |
| D-175 | 2026-09-26 | bug | low | Every page load logged a console error: no icon file ships, so the browser asked for `/favicon.ico` and got a 404. Found by the browser walk of this round. The page now declares an empty icon | fixed · `S-06.02.33` |
| D-176 | 2026-09-26 | bug | medium | The full-data grant wrote "full" into the owner's own "How much to send" level, and Connect stored a level cut to a temporarily lowered ceiling. So after a save made while the grant was paused, resuming it sent Pseudonymous while the card said "granted"; and after a raise to Highest trust, withdrawing it kept sending full data, real addresses included. The grant now decides what its models are sent without touching the owner's level, and Connect keeps that level up to the provider's standing trust (`DD-67`, amended). Found by the third fresh-context review | fixed · `S-06.02.33` |
| D-177 | 2026-09-26 | security | medium | After the upgrade, the owner's old provider profiles stopped with nothing on screen saying why: Drafts read none and pointed at a form that does not exist, and the only explanation was a 503 its disabled option never sent. That 503 called every waiting profile "your provider profiles", by names clients chose, and confirming one saved for a client moved the client's key and address into the owner's draft chain — the `D-166` harm, by the app's own instruction. Confirming now gives a profile to the workspace its old label names, never the caller's by default; Settings lists waiting profiles with where each one sends; Drafts says how many wait (`DD-68`, amended) | fixed · `S-06.02.31` |
| D-178 | 2026-09-26 | bug | low | Disconnect answered 500 and left the provider connected when the stored keys could not be decrypted — a regression from `D-169`, which moved the key into the same step as the record — and the "cannot be decrypted" message gave no next step. Disconnect now always removes the connection, and the message says to restore the whole backup or remove the key file and paste the keys again | fixed · `S-06.02.33` |
| D-179 | 2026-09-26 | bug | low | "Sends", the grant offer and the grant line were worked out for the provider, not the models switched on: with only the Chinese-built model on, the grant was offered and accepted and the card read "Sends: Full access" while Pseudonymous was sent; with the only model lowered, it read Standard. They now come from the router's own answer per switched-on model, and a paused grant says why — the card had said "less than its default" of a provider blocked at its default | fixed · `S-06.02.33` |
| D-180 | 2026-09-26 | security | low | Connect took any number of model ids of any length, and per-model trust settings were never bounded, so one login could grow the settings document every request reads without end — though `D-170` said it was bounded. Now at most 50 models of 200 characters each, and 50 per-model trust settings per provider | fixed · `S-06.02.33` |
| D-181 | 2026-09-26 | security | low | The confirm route checked for the install token but recorded the caller's workspace, where a session cookie wins over the token: the token and a client's cookie together confirmed the owner's old profile, key included, into the client. Confirming now goes by the profile's own label | fixed · `S-06.02.31` |
| D-182 | 2026-09-26 | bug | low | The profile save route read whose a profile was in one lock window and wrote in another, so a profile the owner deleted in between came back when a client saved it. The store now checks ownership in the same write | fixed · `S-06.02.31` |
| D-183 | 2026-09-26 | process | low | The test for `D-169` patched a method the fixed code no longer called, so it passed without ever reaching the gap it was about. It now runs the Models-panel save right after disconnect's locked write returns, which fails for two lock windows whatever they call — run inside the `05e9738` tree it fails with the provider connected and keyless, and it passes now. Found by the third fresh-context review | fixed · `S-06.02.33` |
| D-184 | 2026-09-26 | bug | medium | The card and Connect judged the full-data grant for the whole provider while the router judged it per model: with the grant reaching no switched-on model, the form read "Tier B allows up to Full access", and choosing Full stored Standard and answered "connected" as if nothing was cut. A cut save now says so, the form offers only levels the provider's standing trust allows, and its hint says what each level means right now. Found by the fourth fresh-context review | fixed · `S-06.02.33` |
| D-185 | 2026-09-26 | security | medium | Until `05e9738`, any login that saved a profile through the API without naming an owner got the label "default" — so a client's profile read "Saved for: default", and confirming it sent the owner's drafts to the client's server on the client's key. The changelog's "a client's key cannot end up in your drafts" was false. Confirming now takes the API key the profile holds, which a planted profile's owner cannot give (`DD-68`, amended) | fixed · `S-06.02.31` |
| D-186 | 2026-09-26 | bug | low | A grant made through the API for less than full decided alone what its models were sent, so with the owner's own level higher, withdrawing the grant raised what was sent. A grant now only ever lifts. Found by the fourth review's extended random test | fixed · `S-06.02.33` |
| D-187 | 2026-09-26 | bug | low | The old-profile panel offered Confirm on rows the server always refused — a label naming no workspace — with a next step ("add it again") no screen offers; and a profile whose key came from a server variable was confirmed with "Drafts can use it now" though every draft through it failed. A label naming no workspace is now the owner's once the key proves it, and a profile with no key stored offers only Remove | fixed · `S-06.02.31` |
| D-188 | 2026-09-26 | bug | low | "Sends: Strict" for a provider whose every switched-on model the owner had blocked; the router sends such a model nothing. It now reads "Nothing" | fixed · `S-06.02.33` |
| D-189 | 2026-09-26 | bug | low | Of three ways the stored AI keys become unreadable, only one message gave a next step: a lost master key — a hidden file a plain copy skips — or a damaged one said only "missing" or "invalid". And the one next step, removing the keys file, was shown to client logins without saying the file holds every workspace's keys. All three now say what the install owner can do, and what removing the file costs | fixed · `S-06.02.33` |
| D-190 | 2026-09-26 | security | medium | A regression from the `D-187` fix: a waiting profile's label was matched against workspace ids before "default" was read as the owner's, so with a client workspace given the id "default", the owner confirming their own "default" profile — with their own key — handed it to that client, which could re-point it and receive the owner's key. And the panel never said where Confirm would put a profile. "default", "local" and an empty label are always the owner's now, and each Confirm button names where it puts the profile. Found by the fifth check, the fourth reviewer's look at its own findings' fixes | fixed · `S-06.02.31` |
| D-191 | 2026-09-26 | bug | low | The refusal for a waiting profile with no key said it "read one from a server variable" and "nothing can use it" — false for a template engine, which needs no key. Without a key nothing proves whose the profile is, and a template engine is sent the drafts too, so it still cannot be confirmed; the message and the panel now say that instead | fixed · `S-06.02.31` |
| D-192 | 2026-09-26 | bug | low | `D-189`'s advice for a damaged master key — remove the keys file — did not work: a damaged master key is replaced only when missing, so every save kept failing. The advice now names both files | fixed · `S-06.02.33` |
| D-193 | 2026-09-26 | bug | low | Saving the model list could cut a level set under a raise since withdrawn — the server reported it — while the panel said only "N models enabled". It now says the level was saved lower | fixed · `S-06.02.33` |
| D-194 | 2026-09-28 | security | medium | The list worked out where Confirm would put a waiting profile, and the click worked it out again: with a workspace created in between — say the owner's own old label "kunal" becoming a colleague's workspace — a profile shown as "Confirm as yours" went to that workspace, the owner's key with it. The pressed button now names its destination and only a destination the list offers is taken: the owner always (the key proves it) and the client workspace a label names. Found by the sixth check | fixed · `S-06.02.31` |
| D-195 | 2026-09-28 | bug | low | The Confirm button's accessible name stayed "Confirm <name>", replacing its visible text, so screen-reader and voice-control users never heard where the profile would go. Each button's name now says it | fixed · `S-06.02.31` |
| D-196 | 2026-09-28 | gap | low | A login created in workspace `local` — allowed by the id rules on an install with no demo login — acts as the install owner: it sees every profile and settles waiting ones. `DD-59` accepted this as a cost; nothing warns the person creating it. Older than this work; found by the sixth check. Whether a second owner login should need an explicit choice is the owner's call | in review · `S-06.02.36` |
| D-197 | 2026-09-28 | security | medium | The `D-194` fix read which Confirm button was pressed from the browser's report of it, and fell back to the first button when there was none: in a browser that does not report it (Safari before 15.4) and on Enter in the key box. The first button is the client workspace a label names, so "Confirm as yours" or a plain Enter sent the owner's profile and key to a colleague's workspace — shown in real Chromium. Each button now sends its own destination on its own click, and Enter confirms only a profile with one place to go; with two it says to press a button. Found by re-reading that fix before it was pushed | fixed · `S-06.02.31` |
| D-198 | 2026-10-02 | gap | high | On Render's free plan the spend and call counters behind each provider limit lived in the data folder, which the service loses at every deploy, restart and spin-down after 15 minutes idle — so "200 a day" or "$5 a day" started again from zero many times a day: a limit that was not one. Found by the store inventory (`S-06.03.01`). With `OFFSETX_DATABASE_URL` and `OFFSETX_SECRETS_KEY` set, the counters live in the hosted database (`DD-69`); without them a free-plan install still loses them, which `S-06.03.05` refuses in production | fixed · `S-06.03.02` |
| D-199 | 2026-10-02 | bug | high | A store on PostgreSQL held one connection for the life of the process and never reopened it. Once the server dropped it — Neon's compute sleeps after five minutes idle; AWS and Azure close idle connections — every query of the egress log, video and GTM stores failed until a restart. Shown on a real PostgreSQL 16: "terminating connection due to administrator command", then "the connection is closed" on every later query. A connection idle 30 seconds or more is now checked before use and reopened; a statement that failed is never sent again, and a connection is never swapped inside a transaction | fixed · `S-06.03.02` |
| D-200 | 2026-10-02 | gap | medium | The privacy service read workspace logins straight from the SQLite file in the data folder, so with logins in the hosted database a subject-access or deletion request would have found, and erased, nothing there. It now reads and deletes through the login store. Found while designing `S-06.03.02`, before the logins moved | fixed · `S-06.03.02` |
| D-201 | 2026-10-02 | bug | low | The eval tool logged its provider calls to a file in the data folder even when the app's egress log was on PostgreSQL, splitting the record of what left into two places, and it read keys only from the data folder. It now opens the same stores as the app | fixed · `S-06.03.02` |
| D-202 | 2026-10-02 | bug | low | Connectors told every user a key was "encrypted on this machine" and usage "counted on this machine". With a hosted database the server encrypts the key and keeps it in the database, and on Render "this machine" was never the user's own. The texts now say what is true either way. Found in the real-browser walk of `S-06.03.02` | fixed · `S-06.03.02` |
| D-203 | 2026-10-02 | gap | low | Render's services set no `OFFSETX_UNSUBSCRIBE_SECRET`, so the key that signs unsubscribe links was generated into the data folder and lost at every spin-down: a link in mail already sent stopped working after the next restart. Render now generates the setting once. Found by the inventory | fixed · `S-06.03.01` |
| D-204 | 2026-10-02 | bug | low | `.env.example` still listed `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` and `NVIDIA_API_KEY` as places to put provider keys. Nothing has read them since `DD-64`; the template told people to do something that does nothing and that the rules forbid. It now says keys are typed in Connectors | fixed · `S-06.03.02` |
| D-205 | 2026-10-02 | bug | medium | With the keys and settings in a hosted database, a database that stopped answering would have given every screen that reads them a bare "500 Internal Server Error". It now answers 503 with a sentence and the next step; what failed and where goes to the server's log, not to every login, and readiness names the store. Found re-reading `S-06.03.02` before it was committed. As first fixed this held only for the install token: signed-in browsers until `D-209` | fixed · `S-06.03.02` |
| D-206 | 2026-10-02 | security | medium | An `OFFSETX_DATABASE_URL` that was a real connection string but not a URL — the key/value form Azure's portal shows, or a URL pasted with its quotes — was taken as a file path: keys, settings, logins and counters went to a SQLite file in the working directory, on the disk a deploy wipes, named after the string with the password in it, and the app started. Anything but a PostgreSQL URL (or an absolute SQLite path, for a machine with its own disk) is now refused at start without repeating the value. Found by the fresh-context review of `646c593` | fixed · `S-06.03.02` |
| D-207 | 2026-10-02 | bug | medium | With hosted counters, a provider with no limits was never checked before a call, so the first read of the counters came after the provider answered; a database that went away during the call threw that billed answer away and told the user to try again, which billed again. The counters are now read before any call, and counting a call that was made never fails it: a count that cannot be read is kept and added at the next good read. Found by the review | fixed · `S-06.03.02` |
| D-208 | 2026-10-02 | bug | medium | The connection check before a statement had no time limit and held the store's lock, so a flow a load balancer forgot without a reset — Azure's default — left every request on that store waiting, the login check of every signed-in request among them. Measured: 26.7 s until the flow came back; on a dead flow, until TCP gives up. Connections now ask the network to notice a silent drop in about 15 seconds (keepalives, `tcp_user_timeout`) unless the URL sets its own; a dropped flow is then reopened and the request answered. Found by the review | fixed · `S-06.03.02` |
| D-209 | 2026-10-02 | bug | medium | During a database outage every request from a signed-in browser answered a bare 500 — even `/health/live` — because the session check runs in the middleware, which the 503 handler of `D-205` did not cover. The middleware now answers the same sentence, and only API requests look a session up at all. Found by the review | fixed · `S-06.03.02` |
| D-210 | 2026-10-02 | gap | medium | Switching the database on for an install with a real disk — Docker's `./local_data`, a server with its own volume — silently hid the logins, keys and trust history its data folder held: colleagues could not sign in and every decision vanished from the screens. The start is now refused, naming the files, until the owner runs `offsetx-db import-local --yes` (copies them in, keys re-encrypted under `OFFSETX_SECRETS_KEY`) or `--skip`; the files are never touched. Found by the review | fixed · `S-06.03.02` |
| D-211 | 2026-10-02 | bug | medium | A database error while the broker read a provider key was treated as the provider failing: the task failed over, a call nothing sent was counted against the provider's limit and circuit breaker, the database's address went into the egress log that logins can read, and a database password failure read as the provider rejecting its key. The broker now lets the database's error through untouched, and the classifier never calls it the provider's. Found by the review | fixed · `S-06.03.02` |
| D-212 | 2026-10-02 | bug | low | BEGIN and COMMIT on a connection the server had just dropped raised the driver's own error, which the screens showed as a bare 500 and `forget-provider-keys` as a traceback. They now raise the database's sentence; a failed COMMIT says whether it was saved is unknown, and nothing is re-sent. Found by the review | fixed · `S-06.03.02` |
| D-213 | 2026-10-02 | security | low | The database password reached messages in two ways: a password in the URL's query string (`?password=`) passed through `describe_target`, and a `psql://` URL, accepted as PostgreSQL but unreadable to the driver, made the connection error quote the whole URL. Descriptions drop the password wherever it is, connection errors are cleaned of it, and `psql://` is no longer accepted. Older than this work; the new messages made it reachable. Found by the review | fixed · `S-06.03.02` |
| D-214 | 2026-10-02 | bug | low | Two instances starting together on a fresh database with the demo login configured: both checked for the login, both tried to create it, and the second refused to start on the unique key (6 of 6 attempts). The second now finds the login made and starts. Found by the review | fixed · `S-06.03.02` |
| D-215 | 2026-10-02 | gap | low | The inventory missed files the code writes into the data folder: the Gmail sign-in token (saved again on every refresh), the eval tool's scoreboard, and the prospecting files — the ledger of who was already contacted or ruled out, rejected matches, the discovery input queue — while its test passed. A second test now reads the code for every name joined onto a data folder. Found by the review | fixed · `S-06.03.01` |
| D-216 | 2026-10-02 | bug | low | Two connections opening the same new SQLite file at once could fail one of them with "database is locked": switching a file to WAL needs it to itself, and SQLite refuses at once rather than waiting. Seen 9 times in 40 runs of the two-writers test under load. The switch is now retried briefly and skipped once the file is in WAL. Older than this work; found when a test of it failed under load | fixed · `S-06.03.02` |
| D-217 | 2026-10-03 | bug | medium | The CRM store given a PostgreSQL URL does not refuse it: it hands the URL to `sqlite3.connect`, which makes a SQLite file named after the URL in the working folder — a password in the URL becomes part of a file name, and the CRM looks saved while it sits on the disk that is wiped. Reachable today by putting a URL in `OFFSETX_OUTREACH_DB`. Found when the first draft of the `S-06.03.03` tests passed "on PostgreSQL" against these files. A PostgreSQL URL now opens PostgreSQL, and any other URL is refused without being repeated or creating anything — including one `Path` has folded to `postgresql:/`, which is how it arrives through `OFFSETX_OUTREACH_DB`. That route was missed by the first fix and found by re-reading the diff before it was committed | fixed · `S-06.03.03` |
| D-218 | 2026-10-03 | process | low | A session was started on a branch cut from `main`, 444 commits behind `develop`, where `S-06.03.03` does not exist at all. Asked to pull it, the session would have reported a missing story. Found by searching every remote branch before answering; the branch was fast-forwarded to `develop` | open · `S-06.02.19` |
| D-219 | 2026-10-03 | bug | low | The harness that runs the CRM suite on PostgreSQL (task a, `207399d`) had three faults of its own: it sent `mysql://` and every other URL to PostgreSQL too, so the store's refusal of them could not fail in that mode; it hid the store's `__init__` from the audit that reads it for autocommit; and the CRM tests expected SQLite for their "sqlite" case in a mode where every store is PostgreSQL. Found by grouping that mode's failures by message in task b | fixed · `S-06.03.03` |
| D-220 | 2026-10-03 | process | low | The `S-06.03.03` work order's list of modules that run SQL on the CRM's connection was built by searching for the text `store.connection`, and missed `outreach/deliverability/`, which copies the connection onto itself as `self.connection`. (`gtm/service.py`, first named here too, runs no CRM SQL: it failed only through the bulk-email health check.) The exact list, from a trace of every statement on a CRM database across the whole suite plus a code search for every way of reaching the connection: the store, `privacy.py`, `ai_chat.py`, `sales.py`, `deliverability/store.py`, `api/production_runtime.py` and `engine.py`. Nothing shipped on the strength of the list; found when the whole suite was run with the CRM on PostgreSQL | fixed · `S-06.03.03` |
| D-221 | 2026-10-03 | bug | medium | On PostgreSQL the email worker failed every time it put a job back outside its send window: `defer_without_attempt` used SQLite's two-argument `MAX(0, attempt_count - 1)`, which PostgreSQL does not have. Now a `CASE`, the same on both. No other two-argument `MAX` or `MIN`, nor any other SQLite-only function, is in the CRM's modules. Found by running the whole suite with the CRM on PostgreSQL | fixed · `S-06.03.03` |
| D-222 | 2026-10-03 | bug | medium | A PostgreSQL connection closed on purpose reopened itself at its next use: the reconnect meant for a connection the server dropped could not tell the two apart. A store kept past a restore's close went on reading and writing, and readiness said "ready" for a CRM the app had closed. A closed connection now refuses, with a sentence; every other hosted store already opens a fresh one after closing. Older than this work (`S-06.03.02`); found by the readiness test run with the CRM on PostgreSQL | fixed · `S-06.03.03` |
| D-223 | 2026-10-03 | bug | low | The first version of the check that stops a start while a local CRM file holds rows counted what every start writes — 8 built-in templates and 1 built-in expert note — as the owner's, so it would have refused every install that had ever started once. Those rows are now asked of the real seeding and not counted; a template or note the owner wrote still is. Never committed; found by phase 1's own import tests (`S-06.03.02`) | fixed · `S-06.03.03` |
| D-224 | 2026-10-03 | process | low | The `import-crm` tests ran the command from the repository folder, and it took its workspace lease there: a stray `.local_data.workspace.lock` appeared in the working tree. The tests now run in their own folder. Never committed; found by `git status` before the commit | fixed · `S-06.03.03` |
| D-225 | 2026-10-03 | security | low | `offsetx-db copy-log` ended by printing `OFFSETX_DATABASE_URL=` and the `--to` URL as typed, password included, into the terminal and any log that captured it — the URL form `D-213` had made sure is never shown. It now names the setting and the URL passed, without printing it; `docs/architecture/POSTGRES.md`'s example follows. Older than this work (`S-06.03.02` era); found while matching `copy-crm` to it | fixed · `S-06.03.03` |
| D-226 | 2026-10-03 | bug | medium | Every screen's sidebar said "Local workspace — SQLite on this device", hard-coded, and `/settings/status` said `local_sqlite` with the CRM file's path, whatever was true. On a hosted install that tells the owner their CRM is on the very disk a deploy wipes, when it is in PostgreSQL; Settings also said provider keys sit "outside the CRM database", false there. The status now reads the CRM it opened (`storage`, a new password-free `database`, and `database_path` only for a real file), and the sidebar and Settings say what it says, claiming nothing while it loads. Older than this work (wrong since `S-06.03.02`); found by the browser walk of `S-06.03.03` task h | fixed · `S-06.03.03` |
| D-227 | 2026-10-03 | data-loss | high | Once anything had started on the hosted database, the owner's local CRM could no longer be imported. `copy_crm` refused any destination holding a row, and every engine start writes 8 built-in templates and 1 built-in expert note; only the web app refused to start while a local CRM was left behind, so one cycle of `offsetx-email-worker`, `offsetx-outreach` or `offsetx-notebook` seeded the database and `import-crm --yes` was refused for good. The only way out offered was `--skip`, which hides the owner's CRM and its queued jobs. The copy now replaces the built-in rows (the owner's own still refuse), and every tool that opens the CRM without an explicit `--db`/`--database` refuses while a local file holds rows. The tests had built both sides with a bare `OutreachStore`, which seeds nothing; they now build them with the engine. Found by the fresh-context review of `S-06.03.03` (task i), reproduced with the real tools | fixed · `S-06.03.03` |
| D-228 | 2026-10-03 | data-loss | medium | The copy changed values without a word and still reported every table as matching: SQLite keeps a REAL in an INTEGER column, PostgreSQL's cast rounds it (87.5 became 88), and counts alone cannot see that. Before writing anything the copy now asks the source for every value whose kind its column's PostgreSQL type would change, and names the table, column and count. No app path was found that writes such a value. Found by the fresh-context review of `S-06.03.03` (task i), reproduced with injected values | fixed · `S-06.03.03` |
| D-229 | 2026-10-03 | bug | medium | On PostgreSQL a CRM write waited without limit for another writer, holding the store's lock while it waited, so a worker session hung mid-transaction froze every CRM request in the web app, reads included. SQLite gives up after 5 seconds. A write now waits at most 5 seconds (`lock_timeout`) and says "the CRM is busy … nothing was changed; try again". Found by the fresh-context review of `S-06.03.03` (task i), reproduced: 20 seconds and still waiting | fixed · `S-06.03.03` |
| D-230 | 2026-10-03 | bug | medium | `offsetx-email-worker --watch` ended on the first moment the database was away (a free-plan compute waking, a restart): only a busy workspace was caught. It now says why and tries again, waiting longer each time up to a minute; `--once` exits with that sentence instead of a stack trace. Its default 2-second poll runs about 11 statements a cycle, which keeps a free-plan compute awake; `HOSTED_STORAGE.md` now says to poll slowly on a hosted install. Found by the fresh-context review of `S-06.03.03` (task i), reproduced against an unreachable URL | fixed · `S-06.03.03` |
| D-231 | 2026-10-03 | gap | medium | CI ran no PostgreSQL test at all: it installed without `--extra postgres`, had no PostgreSQL service and never set the test URLs, so every PostgreSQL case skipped and a regression on that side would merge green. The session-start hook dropped the driver the same way. CI now has a `postgres` job that runs the storage tests and then the whole suite with every CRM on PostgreSQL; the hook installs the driver. The job itself has not run yet: CI runners are down (`S-06.02.18`). Found by the fresh-context review of `S-06.03.03` (task i), by reading the workflow | fixed · `S-06.03.03` (unexercised until `S-06.02.18`) |
| D-232 | 2026-10-03 | security | low | `/settings/status` showed the CRM's database URL to every signed-in user, and the redaction removed only a parameter named exactly `password`: `sslpassword=` came through in the clear, with the host, user and database name. Any parameter whose name holds "password" is now hidden, and only the install owner is told where the database is; everyone else is told only "PostgreSQL" or "SQLite file". Found by the fresh-context review of `S-06.03.03` (task i), reproduced with `describe_target` | fixed · `S-06.03.03` |
| D-233 | 2026-10-03 | bug | low | A NUL character in outside text (a reply's subject or body) was stored on SQLite and refused by PostgreSQL with an error reply sync did not catch, so that campaign's run failed on every pass while the message stayed in the sync window. It failed closed — nothing was sent. NUL is now dropped from outside text before it is stored, on both backends. Found by the fresh-context review of `S-06.03.03` (task i), reproduced with psycopg | fixed · `S-06.03.03` |
| D-234 | 2026-10-03 | bug | low | `import-crm` recorded "imported" without checking that the counts reconciled, and if recording failed after the copy, a second `import-crm --yes` said "copy into an empty database", sending the owner the wrong way. It now records nothing unless every table matches, and a refused second import says the first may already have happened and how to record it. Found by the fresh-context review of `S-06.03.03` (task i), by reading the code | fixed · `S-06.03.03` |
| D-235 | 2026-10-03 | data-loss | low | `offsetx-db copy-crm` wrote the whole CRM into any existing file named as `--to` — another store's database included — and reported success. The check that source and destination differ compared spellings, so `x/./crm.db` passed it and an old source was migrated before the refusal. A file destination must now be new, and the same file by any name is refused before anything is opened. Found by the fresh-context review of `S-06.03.03` (task i), reproduced | fixed · `S-06.03.03` |
| D-236 | 2026-10-03 | gap | low | Whether a local CRM file was imported or skipped is recorded once per database, as phase 1's keys and logins are (`D-210`). A second install with its own disk sharing that database is never asked about its own file, so its CRM is hidden without a word. Whether two installs may share one database at all is the owner's call. Found by the fresh-context review of `S-06.03.03` (task i), by reading the code | open · `S-06.03.07` |
| D-237 | 2026-10-03 | process | low | The work order said CRM search "ignores case on both" backends (`DD-73`). True for A–Z only: SQLite's `lower` folds ASCII alone, PostgreSQL's folds accented letters, so "évora" finds "Évora" on PostgreSQL only. The claim is corrected by `DD-75` and the difference written into `HOSTED_STORAGE.md`'s limits; making SQLite match would mean replacing its `lower`, which an index is built on. Found by the fresh-context review of `S-06.03.03` (task i), reproduced | fixed · `S-06.03.03` (claim corrected; behaviour documented) |
| D-238 | 2026-10-03 | bug | low | `offsetx-email-worker --database postgresql://…` ended in a traceback: the option was parsed as a path, which folds `postgresql://` to `postgresql:/`, and the CRM rightly refused it. Task `e` had written the help saying it overrides `OFFSETX_DATABASE_URL` without trying a URL there. It is now a string, a file path is still resolved, and a target that is wrong (not merely away) stops the worker with its sentence instead of a traceback. Found by task i's live walk of `D-227` with the real commands, after the review | fixed · `S-06.03.03` |
| D-239 | 2026-10-04 | bug | low | Activating Skip to main content on Settings changes the hash to `#main-content`, which the router treats as an unknown screen and maps to Dashboard. Predates S-06.02.25; found by independent review and reproduced with Enter in real Chromium: Settings became Command centre | in review · `S-06.02.37` |
| D-240 | 2026-10-04 | process | low | The new browser launcher cleared the hosted database URL but inherited its secrets key, so the app correctly refused to start on a hosted-configured machine. Found by independent review before push; launcher now clears hosted and Gmail settings and passes all 32 checks even with an inherited hosted key | fixed · `S-06.02.25` |
| D-241 | 2026-10-04 | process | medium | The ordinary quality CI job still installs without the PostgreSQL extra. At baseline fa62312, run 37166288794 failed three existing Python tests because psycopg was unavailable, while the separate postgres job passed. Quality stopped before frontend and board checks. Found while establishing S-06.02.25's baseline; frontend work does not repair this pipeline configuration. *(2026-10-04:)* the failing tests were two of `S-06.03.03`'s task i (`test_a_watching_worker_rides_out_a_database_that_is_away`, `test_a_worker_run_once_says_why_the_database_is_away`) and `D-213`'s `test_no_message_or_description_repeats_the_database_password`; reproduced locally with the driver hidden. They test the driver's behaviour, and the Docker image ships it, so the quality job, the session hook and `AGENTS.md`'s command now install `--extra postgres` too. `S-06.03.03` was marked DONE on local runs that all had the driver; nobody had seen CI run | fixed · `S-06.03.03` |
| D-242 | 2026-10-04 | gap | medium | The app sets up no logging at all. An unexpected error reaches the screen as a sentence with nothing to quote, and the only record is whatever uvicorn prints to standard output, with no id to match the two; the whole package has seven log calls: four about a restore, two about the AI usage counters, one about the database being away. On Render's free plan anything written to a file is wiped with `/tmp`. So an error seen yesterday cannot be traced today. Found on the owner's question of 2026-10-04, by searching the code for loggers, handlers and request ids | open · `S-06.02.38` |
| D-243 | 2026-10-09 | security | high | The first traceable-errors implementation forwarded Starlette lifespan.failed traceback text before safe wrapping, exposing raw startup/shutdown secrets and customer text. Reproduced by independent review and a real Starlette lifespan test; failed protocol messages now carry only the recorded reference | fixed · S-06.02.38 |
| D-244 | 2026-10-09 | bug | high | The command-wide de-duplication map was reused by every watch cycle, retaining exception graphs and suppressing repeat failure IDs. Independent review and 100-cycle reproduction; scopes now discard handled failures and transfer only escaping references | fixed · S-06.02.38 |
| D-245 | 2026-10-09 | gap | medium | Inner API job boundaries emitted before request route/workspace metadata was attached; restore rollback 422 responses and hidden-CRM SystemExit chains lost the reference or logged twice. Reproduced at actual API/CLI boundaries; request context and preserved causes now retain one reference | fixed · S-06.02.38 |
| D-246 | 2026-10-09 | security | high | CLI catches printed raw upstream exception messages beside safe JSON, potentially exposing provider response/customer text. Artifact reproduction observed RED; catches now print safe fixed advice and their reference | fixed · S-06.02.38 |
| D-247 | 2026-10-09 | gap | high | Email and content timers swallowed individual send/publish failures into counts, and screens displayed success without their references. Independent review traced producer, timer and Settings/Posting consumers. Safe per-item status and rendered failure summaries are wired and regression-tested; the send is not repeated | fixed · S-06.02.38 |
| D-248 | 2026-10-09 | bug | medium | Redacting a serialized JSON record with a one-character database password corrupted IDs and JSON delimiters. Independent review reproduced passwords E and URL-encoded quote; test-first correction now serializes only allowed metadata and keeps IDs intact | fixed · S-06.02.38 |
| D-249 | 2026-10-09 | process | low | The first session-lookup regression patched a nested function as a module symbol and failed at setup, not the intended outage. Corrected to patch WorkspaceAuthStore.verify; a later trend fixture also used a channel id interpreted as a handle, corrected to its actual @Depot handle; the actual pre-dispatch outage now passes. This result is not claimed as RED evidence | fixed · S-06.02.38 |
| D-250 | 2026-10-09 | gap | medium | The content sweep/pipeline and routine scheduler retain swallowed failures outside outer boundaries; some raw provider text reached skipped results and scheduler last_error was not exposed by any consumer. Found by independent review during the traceable-errors inventory; references now survive fallback, API status and shutdown propagation | fixed · S-06.02.38 |
| D-251 | 2026-10-09 | bug | medium | Content cycle status kept a previous reference after a later successful cycle. Independent review and test-first correction; clear the prior cycle before collecting current failures | fixed · S-06.02.38 |
| D-252 | 2026-10-09 | gap | medium | Routine begin_run failure escaped its scope and was recorded again by the scheduler; scheduler status also depended on its failing history store. Reproduced through real service/API paths; per-poll scope retains one workspace-aware ID and independent owner status remains readable | fixed · S-06.02.38 |
| D-253 | 2026-10-09 | bug | medium | Scanning all result strings for reference-shaped text let a customer campaign label turn a successful cycle into a reported failure. Reproduced before correction; summaries now inspect only designated failure fields | fixed · S-06.02.38 |
| D-254 | 2026-10-09 | bug | high | A timer could replace the proposal shown for plan A with plan B before Accept; a holding pair also erased another proposal. Independent reproduction; per-pair identities and locked stale-decision refusal now bind the action to what was shown | fixed · S-12.02.06 |
| D-255 | 2026-10-09 | bug | high | Start read exact-version links although revisions reuse a line's campaigns, causing a 409 dead end; revision Apply raced an old Start under different locks. Independent API reproduction; current-line validation and a shared root lock preserve revision history | fixed · S-12.02.06 |
| D-256 | 2026-10-09 | bug | medium | SQL text ordering of ISO timestamps with offsets allocated a slot before an already queued post. The same legacy ordering delayed or advanced due checks. Reproduced before fixes; comparisons use actual UTC instants and new schedules serialize UTC | fixed · S-12.02.06 |
| D-257 | 2026-10-09 | bug | medium | Posting treated every attachment as a kept picture, including supported video renders. Independent review; workspace-checked typed previews now show images/videos without a false approval claim | fixed · S-12.02.06 |
| D-258 | 2026-10-09 | bug | high | Starting one plan after an install-wide stop restarted other legacy pairs; publishing ignored the resulting per-pair stop. Config and real timer regressions reproduced it; other pairs remain disabled and scheduled rows wait for explicit resume | fixed · S-12.02.06 |
| D-259 | 2026-10-09 | security | high | Workspace callers could alter install pacing or another account's cap. API regression failed before correction; pacing decisions require the install owner and account mutations check ownership | fixed · S-12.02.06 |
| D-260 | 2026-10-09 | bug | medium | A selected pair's pacer counted unrelated accounts and their caps. Real API reproduction; account capacity is scoped to workspace, enablement and the pair's declared handles | fixed · S-12.02.06 |
| D-261 | 2026-10-09 | security | high | Missing or foreign attachments could be approved/scheduled and then copied from another workspace, or published as caption-only. Independent API reproduction; mutation and publishing revalidate owned available media, with durable safe failure references | fixed · S-12.02.06 |
| D-262 | 2026-10-09 | bug | medium | Eagerly loading a full draft queue could retain hundreds of 32 MiB blobs. Independent review; explicit previews permit only one active attachment and abort/revoke it on change | fixed · S-12.02.06 |
| D-263 | 2026-10-09 | security | medium | A pacing request returned another campaign/workspace's pending owner proposal. Real API regression failed before correction; pending proposals and plan-pair lookup now follow the selected campaign/workspace | fixed · S-12.02.06 |
| D-264 | 2026-10-09 | bug | medium | The local outbox could accept a caption-only publication when an attachment disappeared after engine validation. Direct adapter regression failed before correction; the adapter raises before writing a successful receipt | fixed · S-12.02.06 |
| D-265 | 2026-10-09 | bug | medium | Invalid pre-upgrade scheduling dates blocked every valid publication and next-slot allocation. Two reproduced RED tests; quarantine invalid scheduled rows with a safe reference, include failures in publish results, preserve published receipts and continue valid work | fixed · S-12.02.06 |
| D-266 | 2026-10-11 | security | high | The browser navigation guard does not reject all private and local IP destinations; current source still uses a limited hostname list. Confirmed by an isolated policy-condition check, not a full browser test | in review · `S-03.01.03` |
| D-267 | 2026-10-11 | security | high | The public-page fetcher checks DNS then makes a separate request without binding the connection to the validated destination; current source confirms the gap, live retest pending | in review · `S-05.01.04` |
| D-268 | 2026-10-13 | bug | medium | GTM reference A/B discarded non-reference campaign/product notes with expert references, making the two arms measure different product contexts. Confirmed by code inspection; regression committed but pending execution | in review · `S-12.02.05` |
| D-269 | 2026-10-13 | bug | medium | Thirty identically identified GTM eval cases labelled as real were accepted as enough evidence for model promotion. Source review and duplicate-case regression committed; live run pending | in review · `S-12.02.05` |
| D-270 | 2026-10-13 | gap | high | The deployed Render configuration starts only web services; no independently supervised durable email worker runs queued approved sends. Found by read-only comparison of render.yaml and the existing worker CLI against audit A25; hosting/worker choice remains open | open · `S-06.02.40` |
| D-271 | 2026-10-13 | gap | medium | Original Contacts UI cap hid rows beyond 500. Implemented paged UI and authenticated API; Render QA dep-db93t2mi0phs73c6msq0 imported 503 persisted contacts and verified 6 authenticated pages, unique IDs, totals, last-row search and HTTP 401 for missing auth; Chromium visual/keyboard and independent review still open | in review · `S-06.02.41`; evidence: `docs/evidence/2026-10-16-S-06.02.41-42-validation.md` |
| D-272 | 2026-10-13 | security | high | Apollo/externally supplied spreadsheet formula text previously could be interpreted as executable cells. Export escaping tests now inspect saved real CSV/XLSX accepted/rejected/raw/audit/metadata tabs, confirm text cell types and unchanged input; Render QA dep-db93t2mi0phs73c6msq0 passed. Offline Excel/LibreOffice and independent security review still open | in review · `S-06.02.42`; evidence: `docs/evidence/2026-10-16-S-06.02.41-42-validation.md` |
| D-273 | 2026-10-13 | security | high | Logout deleted the cookie but did not invalidate a copied signed session. Durable token-digest revocation and tests prepared, tests unrun | in review · `S-06.02.43` |
| D-274 | 2026-10-13 | gap | medium | Contacts could not download the full matching filtered list across pages. A bounded all-pages CSV endpoint and tests prepared, tests unrun | in review · `S-06.02.44` |
| D-275 | 2026-10-13 | gap | medium | Contacts could not filter its existing server-backed table by category or variant from the screens. Facet endpoint and UI tests prepared | in review · `S-06.02.45` |
| D-276 | 2026-10-13 | gap | medium | Stored checkbox selections could not be viewed across pagination. SQL-level marked-only view and tests prepared | in review · `S-06.02.46` |
| D-277 | 2026-10-13 | reliability | medium | Send Queue API returned the entire campaign's full recipient rows with no pagination. Bounded UI endpoint and tests prepared | in review · `S-06.02.47` |
| D-278 | 2026-10-13 | reporting | medium | Queue dashboard counts were computed from the list on screen instead of separately from full campaign state. Server-wide counters and tests prepared | in review · `S-06.02.48` |
| D-279 | 2026-10-13 | usability | medium | Queue offered no view isolating ready, needs approval or replied contacts. View filter and tests prepared | in review · `S-06.02.49` |
| D-280 | 2026-10-13 | gap | medium | Campaigns screen lacked editable campaign settings despite backend PATCH; invalid timezone could persist until send scheduling. Product editor and boundary validation prepared, tests not yet executed | in review · `F-06.04` |
| D-281 | 2026-10-13 | usability | medium | A configured campaign could not be reused without manually rebuilding; naive reuse risks copying recipients or briefly activating a sender. Paused configuration-only clone prepared, integration test unrun | in review · `F-06.05` |
| D-282 | 2026-10-13 | reporting | medium | Campaign cards lacked accountable per-campaign contacted and reply-rate measurements; manually replied unsent prospects could distort results. CRM-based measures and tests authored, not run | in review · `F-06.06` |
| D-283 | 2026-10-14 | gap | medium | Contacts screen had no manual single-contact entry or safe explicit bulk stop, forcing a file import or per-row edits. Code, UI and tests prepared; verification pending | in review · `F-06.07` |
| D-284 | 2026-10-14 | gap | medium | The CRM had no read-only campaign-level readiness explanation before sending, making approval/schedule/limit problems hard to see. Code and tests prepared; verification pending | in review · `F-06.08` |
| D-285 | 2026-10-14 | usability | medium | Existing campaign events were accessible through the API but not from a paginated, filtered audit timeline in the interface. Source and tests prepared; execution pending | in review · `F-06.09` |
| D-286 | 2026-10-14 | product gap | medium | Actual incoming replies had no campaign-level review inbox or per-campaign outcome, making received conversations hard to triage. Implemented in source with tests authored; not yet executed | in review · `F-06.10` |
| D-287 | 2026-10-14 | product gap | medium | A campaign contact had no in-product chronological message history; mail context was scattered. Bounded member-only history API and UI authored; verification pending | in review · `F-06.11` |
| D-288 | 2026-10-14 | reliability gap | medium | No persistent per-campaign human follow-up worklist with owner, due dates and conflict-safe completion. New schema/API/UI and tests authored; migration and restore execution pending | in review · `F-06.12` |
| D-289 | 2026-10-15 | product gap | medium | Positive replies remained disconnected from the commercial Sales Tracker pipeline and manually reentering contacts could create duplicate leads. Explicit deduplicated promotion/source link prepared; tests unrun | in review · F-06.13 |
| D-290 | 2026-10-15 | usability | medium | Contact identity, reply context, task status and sales progress were scattered across multiple screens. Campaign-scoped Contact 360 prepared; privacy and browser review pending | in review · F-06.14 |
| D-291 | 2026-10-15 | product gap | medium | Operators lacked one ranked source-backed view of overdue human tasks, incoming replies awaiting triage and sales follow-ups. Daily Action Center prepared; runtime and query plan tests pending | in review · F-06.15 |
| D-292 | 2026-10-15 | product gap | medium | Contacts could be searched only inside selected campaigns, while sales leads lived in another screen; cross-campaign identity discovery had no unified UI. Read-only CRM Search feature code and tests prepared; runtime gates open | in review · F-06.16 |
| D-293 | 2026-10-15 | product gap | medium | No company-centric relationship view joined existing global contacts, campaign touchpoints and Sales Tracker opportunities. Account intelligence code/tests authored; grouping identity and performance review open | in review · F-06.17 |
| D-294 | 2026-10-15 | reporting gap | medium | Multiple campaign links to the same won sales lead could overstate commercial attribution if aggregated naively. Deterministic first-link metric and tests prepared; causal/financial semantics and PostgreSQL verification open | in review · F-06.18 |
| D-295 | 2026-10-15 | product gap | medium | No consolidated non-destructive contact field-completeness and possible Sales Tracker email-overlap queue. Read-only CRM quality source/UI/test prepared; no actual runtime or tenancy verification yet | in review · F-06.19 |
| D-296 | 2026-10-15 | reporting gap | medium | Per-campaign signals were scattered and repeated messages could distort direct comparisons. Unique-member comparison source/UI/test prepared; query plan/real DB/Chrome gates open | in review · F-06.20 |
| D-297 | 2026-10-15 | operations gap | medium | Human follow-up tasks lacked a cross-campaign assignee-label workload and completion timeliness view. Saved-state reporting source/UI/test prepared; label identity and runtime review open | in review · F-06.21 |
| D-298 | 2026-10-15 | process | high | Render review image excludes CI workflow and Git metadata, so source-context verifier tests fail without testing actual board behaviour. Re-run in a real Git checkout / fixture-complete review environment | in review · `S-06.02.20`, `S-06.02.16` |
| D-299 | 2026-10-15 | security | high | npm dev audit reproduced 5 advisories (2 high, 3 moderate); npm-regenerated lockfile pins Vitest 4.1.11 and patched transitive dependencies, with committed npm ci, 212 Vitest tests, build and both npm audits reporting 0 findings in Render runner dep-db8akqs9v7es73877d9g | fixed and retested · `S-06.02.16`, `cb5e2da` |
| D-300 | 2026-10-15 | process | medium | Campaign settings test expected 400 though API intentionally maps validation ValueError to 422. Updated assertion keeps rejection and persistence checks; focused rerun 86 passed | fixed · `F-06.04`, `dbf6562` |
| D-301 | 2026-10-15 | process | medium | Account Intelligence SSR test supplied list-shaped resource for detail request; test crashed on nested contacts.total. Test double fixed; 212 frontend tests passed on retest | fixed · `F-06.17`, `6885444` |
| D-302 | 2026-10-15 | process | medium | Render review image omitted committed WebM fixture and two Vitest suites failed to load. Review Dockerfile fixed to include tests/fixtures; 212 frontend tests passed on retest | fixed · `S-06.02.39`, `423913c` |
| D-303 | 2026-10-15 | process | medium | Follow-up migration test asserted SQLite user_version 10 even though migrated schema now targets 11; corrected to SCHEMA_VERSION and focused rerun passed | fixed · `F-06.12`, `f71d204` |
| D-304 | 2026-10-15 | process | medium | Reply-to-sales API regression expected HTTP 400 for missing qualification, but intentional ValueError response is 422; regression now checks 422 and reason, focused rerun passed | fixed · `F-06.13`, `311f1ab` |
| D-305 | 2026-10-15 | process | medium | CRM quality test assumed first inserted campaign UUID always sorts first, causing nondeterministic failures when two memberships share created_at; checks stable valid membership pair instead, focused 86-case rerun passed | fixed · `F-06.19`, `e671607` |
| D-306 | 2026-10-15 | process | medium | Workspace isolation test expected HTTP 403 for an unauthenticated owner-creation request; global auth boundary correctly returned 401. Asserted 401 without weakening access control; security rerun pending | fixed after 352-case security/storage QA rerun · `S-06.02.36`, `8b24965` |
| D-307 | 2026-10-15 | process | medium | Hosted privacy test tried to create an install-owner login in local workspace without required explicit owner confirmation; security correctly refused. Fixture now provides explicit confirmation; rerun pending | fixed after 352-case security/storage QA rerun · `S-06.02.36`, `a91ce08` |
| D-308 | 2026-10-15 | process | medium | GTM video-direction tests created unsupported campaign kind 'video'; registry's 'image' campaign handles image/video work. Test setup now uses real registered kind; rerun pending | fixed after 352-case security/storage QA rerun · `S-12.01.02`, `286c4b2` |
| D-309 | 2026-10-15 | bug | high | Egress-log copy opened target Postgres before checking that source SQLite database existed; offline target hid actionable missing-source error. Added source preflight before any remote connection; rerun pending | fixed after 352-case security/storage QA rerun · `S-06.03.02`, `9ace6b0` |
| D-310 | 2026-10-15 | reliability | medium | EGRESS_COLUMNS order diverged from ai_egress_log schema after system_prompt addition; fixed explicit column tuple to match schema and protect cross-engine copy contract; rerun pending | fixed after 352-case security/storage QA rerun · `S-06.03.02`, `9ace6b0` |
| D-311 | 2026-10-15 | bug | low | Python parsed a JavaScript `/\\s+/` regex in browser Enter-safety script as an invalid Python string escape, causing startup/test SyntaxWarning. Script literal is now raw so JS bytes are preserved; wave-four rerun 187 passed and warning total fell 45 to 44 | fixed · `S-02.02.04`, `024ef206` |
| D-312 | 2026-10-15 | process | medium | Real PostgreSQL 17 full CRM regression returned 2 failures among 2771 passes because two SQLite PRAGMA user_version migration tests lacked crm_sqlite_only markers. Markers added with explicit SQLite-file rationale; the SQLite suite still runs both and PostgreSQL migration coverage is separate. PostgreSQL rerun passed 2772, 94 skipped after both PRAGMA tests remained SQLite-only (Render dep-db8b26e89jmc73cssm00) | fixed · `F-06.12`, `F-06.13`; `b10fa24` |
| D-313 | 2026-10-15 | security | high | Real cross-workspace product disclosure from absent ContextVar: old shared reader interpreted missing caller as install-owner timer; reproduced RED in Render dep-db8cjmajnfac73f52o2g. Fixed default-deny principal and explicit finally-reset timer scope across asyncio.to_thread (DD-121); 3 focused tests, 2754 SQLite-mode full tests and 2774 PostgreSQL-mode full tests passed in dep-db8cnnou01pc73fb3d8g; no security check was bypassed | fixed and QA-regression-tested · `S-06.02.21`, `S-06.01.01`; `b179cc2`, `2678c11` |
| D-314 | 2026-10-16 | reliability | high | Concurrent FastAPI campaign creation reproduced mismatched HTTP 201 responses and persisted IDs (initial run also produced one 404). Code inspection found CRM `_row`/`_rows` executed SQLite SELECT under GuardedConnection's statement lock but fetched materialised rows after the lock had been released; a peer thread could advance the shared connection between execute/fetch. Store now holds its RLock through execute+fetch+copy. The new deterministic `tests/test_crm_read_lock.py` checks another thread cannot steal the lock before fetch; 12x40 worker stress passed on a pre-deterministic test build `dep-db94853rjlhs73c7e8o0`, full-suite/Chromium/postgres and deterministic gate rerun pending. No claim of complete fix yet | in review · `S-06.02.21`, `S-06.02.09`; commits `3690e2e`, `e0df5bf`; trace `dep-db945sft5n8s73au7dpg`; 2026-10-19: deterministic lock gate PASS, 12/12 concurrency stress runs PASS, full SQLite/PG green (see QA ledger); independent release signoff pending |
| D-315 | 2026-10-16 | QA test harness | medium | New real Chromium Contacts acceptance reached desktop 503-contact import, six page transitions and final row, but browser script immediately checked the filtered toolbar count after clicking Search while the API request was still updating; it saw stale count and falsely failed. Updated script to wait for the displayed filtered count and verify page reset; new clean rerun pending | in review · `S-06.02.41`; Render dep-db941vm7bikc73dk5e5g; 2026-10-19: Chromium Contacts at 1280px and 390px PASS in QA deploy |
| D-316 | 2026-10-16 | QA test harness | medium | Real Chromium contact import acceptance intermittently failed before submit because get_by_role(button, name=Import contacts) matched both a background and upload-modal button; Playwright strict mode correctly refused the ambiguous selector. Corrected the QA script to select the submit button only within form:has(input[name=contacts-file]); no application code changed for this failure. Browser rerun pending | in review · `S-06.02.41`; Render dep-db94853rjlhs73c7e8o0; 2026-10-19: Chromium Contacts at 1280px and 390px PASS in QA deploy |
| D-317 | 2026-10-19 | bug | medium | Campaign Comparison called an inbound-before-outbound message a reply after outreach, inflating the displayed reply rate. Isolated sqlite3 SQL reproduction: old 1, chronological 0; corrected query and added full API-store regression (not yet run). | fix authored, full QA pending · `F-06.20`; 2026-10-19: chronology regression passed in 2760/2780 full test runs on source 54864b0 |
| D-318 | 2026-10-19 | process | low | Prior documentation commit inserted a literal escaped newline between D-317 and D-316, merging two Markdown table records; corrected row separator and stable numeric order during QA handoff. Found while parsing defect rows for evidence update | fixed in QA documentation follow-up |
| D-319 | 2026-10-30 | security | high | A15: video-media and render upload handlers call unbounded await file.read(), bypassing OFFSETX_MAX_UPLOAD_BYTES and risking memory exhaustion. Minimal FastAPI mechanism red reproduction accepted 4096 bytes with 201. Added bounded endpoint reads and authenticated oversized/empty/real-file regression; still needs pre-parser stream/disk and concurrent request quotas. | in review · S-06.02.50, audit A15 open; Render QA pending; 2026-10-30: 6 added upload API regressions included in passing 2766 SQLite / 2786 Postgres suites, deploy dep-dbhqd96i0phs73f1vfrg; stream parser and concurrency gaps remain open |
| D-320 | 2026-10-30 | security | high | Render QA build for A15 stopped in the frontend audit because pinned vite@8.1.4 has 3 current advisories (2 moderate, 1 high). Upgraded to patched vite@8.1.6 without forced major/minor migration; changed package and lock integrity from independently published registry-backed package-lock evidence. | remediation source authored · Render rerun pending, S-06.02.50/F-06.02; 2026-10-30: patched Vite 8.1.6 installed with npm ci and npm high-severity audit gate passed on dep-dbhqd96i0phs73f1vfrg; two unrelated moderate Vitest advisories tracked D-321 |
| D-321 | 2026-10-30 | security | medium | Current npm audit reports 2 moderate dev-dependency advisories in @vitest/mocker inherited from vitest@4.1.11: GHSA-qxg6-89mg-rqv8 (manual mock registration injection), GHSA-xp26-3454-mjgp (Windows backslash traversal). High-severity npm audit gate passed and production-only audit shows zero findings; full-tree audit remains nonzero. Upgrade to locked vitest@4.1.12 with source/integrity verification and rerun tests. | open · F-06.02, independent dependency patch required |
| D-322 | 2026-10-30 | security | high | A15 remaining gap: video uploads were parsed/spooled by Starlette before endpoint per-file size check, allowing oversized/streaming media bodies to consume unbounded temporary resources. Implemented bounded pre-parser ASGI spool, per-worker 2-upload concurrency limit, 30-second idle timeout, and cleanup on disconnect. Local FastAPI prototype 11/11 passed; real repository Render QA: 2777 SQLite + 2797 PostgreSQL passed on 71fb99c, 215 focused PostgreSQL passed, 12/12 concurrency repetitions passed. Global quotas and penetration/load test remain open. | in review · S-06.02.51 / F-06.02; cross-process global limits and independent load test open |
| D-323 | 2026-10-30 | usability/security | medium | Owner lacked an authenticated inventory-based report of hosted CRM durability versus local media, agent, outbox and privacy data. A hosted database alone can appear safe though the data folder may be lost. Added owner-only read-only report, test-first HTTP acceptance and a protection against treating the OS root mount as a customer persistent disk. | IN_REVIEW S-06.03.08/F-06.03; initial source fc0a4cf passed 2782 SQLite/2802 PG suites, but later 2 security regressions unexecuted; Q-29 backups/file placement and final QA open |
| D-324 | 2026-10-30 | security | high | The scheduled agent's first `page.goto(routine.target_url)` runs in RoutineAgentExecutor before AgentRun's tool/action dispatcher. A per-tool denial of goto could therefore be bypassed at routine start. Added pre-browser policy gate and two denial/ask regressions; no container or navigation starts if prohibited. | S-06.01.02 IN_REVIEW; authored at 27aad6e; final Render QA pending |
| D-325 | 2026-10-30 | security/contract | medium | New F-06.01 PUT agent-permissions endpoint used untyped dict[str, Any] body, violating the existing strict API contract enforced by tests/test_api_auth.py. Render full SQLite returned 1 FAILED, 2798 PASSED. Fixed using AgentPermissionUpdate(StrictModel) with bounded typed modes and early QA contract gate. | fixed in 851d6de; targeted typed-body regression and permission tests passed on Render dep-dbhrs0l9fdbs73af8e60, full QA pending |
| D-326 | 2026-10-30 | reliability/security | high | Existing web readiness probes required stores but did not show whether enabled email, content, or agent-routine schedulers were stopped. Implemented owner-only operational-health API with sanitized component codes and error references without tying optional automation to load-balancer readiness. External email-worker CLI heartbeat, queue-age measurement and actual alert delivery are still uninstrumented. | S-06.02.52 IN_REVIEW; TDD RED 7 / initial GREEN 7 on Render; final tested 3e5058c: 2806 SQLite/2826 PostgreSQL PASS and QA LIVE; independent worker monitoring/alerts pending |
| D-327 | 2026-10-31 | security | high | Scheduled browser agent used a permission snapshot: an owner changing a policy mid-run could leave later browser actions allowed. Damaged AI settings could also silently fall back to an empty/default-allow policy. Test-first Render reproduction showed 2 new failures (22 other tests passed); added per-action reload, strict security reads, fail-closed error references, and API corruption regressions. | corrected and automated QA verified on e820071, isolated Render dep-dbifv8942hec73f36l50 LIVE (26 permission tests, 2810 SQLite, 2830 PostgreSQL); S-06.01.02 remains IN_REVIEW; D-330, attended-chat approval, independent penetration and production acceptance still open |
| D-328 | 2026-10-31 | security | high | Owner permission PUT preflights strict settings, but then called lenient save in a separate step. If settings became corrupt between the two calls, the operation overwrote damaged data and could lose permission rules. The adversarial test injected corruption after preflight: Render RED 1 failed/25 passed at dep-dbifr0afngtc73dig9l0. Corrected save to re-read strictly under its existing exclusive write lock. | corrected and automated QA verified on e820071, isolated Render dep-dbifv8942hec73f36l50 LIVE (26 permission tests, 2810 SQLite, 2830 PostgreSQL); S-06.01.02 remains IN_REVIEW; D-330, attended-chat approval, independent penetration and production acceptance still open |
| D-329 | 2026-10-31 | bug/contract | medium | Adding a strict-read keyword accidentally changed every ordinary WorkspaceAISettingsStore write to invoke _document(strict=False). Existing concurrency harness monkeypatched the old no-keyword _document method; the full SQLite run correctly caught this with 1 FAILED / 2809 PASSED on source 09ded49 (Render dep-dbifrl2jnfac738ptqhg). Preserve old zero-argument call for ordinary writes and use strict=True only for permission writes. | corrected and automated QA verified on e820071, isolated Render dep-dbifv8942hec73f36l50 LIVE (26 permission tests, 2810 SQLite, 2830 PostgreSQL); S-06.01.02 remains IN_REVIEW; D-330, attended-chat approval, independent penetration and production acceptance still open |
| D-330 | 2026-10-31 | security/design gap | high | Static review: strict permission reads reject malformed/unreadable settings, but if the entire settings document is missing, the existing virgin-install fallback still returns an empty record, which defaults to global allow. A lost persisted deny file could therefore be mistaken for a new install. No destructive reproduction or fix was attempted. Choosing fail-closed missing-document handling requires a backward-compatibility/migration plan for historic default-allow installs. | open · S-06.01.02 / F-06.03 production storage readiness; owner/default policy decision and separate regression required before production signoff |
| D-331 | 2026-10-31 | security | high | All public AI chat/project endpoints were invoking AIChatService without workspace_id; signed-in users were implicitly routed to the local workspace. Messages could be queried without a workspace condition and send_message inserted before validating ownership, potentially exposing another workspace to provider egress. Fixed by passing authenticated workspace through every chat/project route and checking chat ownership before storing messages or invoking responder; owner-chat permission grants are workspace-scoped. | F-06.01 / S-06.01.02 IN_REVIEW; Render TDD RED 3 failed/26 passed on 43a5d14, candidate a4e0855 in isolated QA dep-dbiqmb142hec73b8c12g; full SQLite/Postgres and pen tests pending |
| D-332 | 2026-10-31 | gap | medium | Existing ChatPermissionGrants had no authenticated chat approval, status, or closure API, so its grant object could not be managed from a real owner session and could outlive chat deletion. Added typed owner grant and close APIs with bounded memory-only per-workspace registry, chat deletion close and restart expiry. No browser-agent run is exposed from the AI Copilot chat; therefore grants cannot yet authorize a customer-visible attended browser run. | F-06.01 / S-06.01.02 IN_REVIEW; targeted Render QA pending; real attended AgentRun connection and frontend owner control still open |
| D-333 | 2026-10-31 | bug/security | medium | The project-delete API reported success for a project belonging to another workspace because AIChatService.delete_project silently deleted zero rows. This was misleading and hid an authorization failure. Changed service to return a truthful bool and API to raise 404; added authenticated two-workspace regression. | F-06.01 / S-06.01.02 IN_REVIEW; fix authored d2d4788; isolated final Render QA dep-dbiqouvlk1mc73ffueb0 pending |
| D-334 | 2026-10-31 | process/security | high | The new ChatPermissionRegistry was added to app.state without the service inventory and runtime close-order contract. Full isolated Render SQLite correctly FAILED test_every_open_service_is_closed_for_a_restore and test_every_service_the_app_opens_is_classified (2 failed/2815 passed). Fixed by registering a no-arg close hook, using targeted revoke_chat for API, listing registry in RUNTIME_CLOSE_ORDER and classifying it as a non-durable service in db/inventory.py; added both regressions as early Docker review gates. | F-06.01/S-06.01.02 IN_REVIEW; corrected source 8a35417, isolated QA dep-dbiqtah42hec73b8v1sg in progress; no production rollout |
| D-335 | 2026-10-31 | security | high | A read-oriented HTTP chat run was initially marked attended although no live monitor/cancel UI existed, which bypassed the attended-only site policy. The new LinkedIn-host refusal case failed on source b6cc20e (Render dep-dbisj1ks728c7386u920: 1 failed/36 passed). Corrected both API and actual BrowserBox/Page mode to enforce unattended restrictions. | corrected and verified by 40 targeted agent/security tests, full SQLite 2824, full PostgreSQL 2844 and Chromium desktop/mobile on exact source 3150fbb; isolated Render dep-dbiskimc6qcc739ivrcg LIVE. S-06.01.02 remains IN_REVIEW because no real watched browser flow, DNS rebinding pen test, live provider session, D-330 or production approval |
| D-336 | 2026-10-31 | bug/security | medium | The new browser-run URL preflight used urlsplit without catching malformed bracketed IPv6 host syntax. A hostile input could raise ValueError and cause a 500 instead of the intended safe 400; no browser launch was needed. Added malformed URL regression and reject invalid parsed hostname/credentials before browser execution. | corrected and verified by 40 targeted agent/security tests, full SQLite 2824, full PostgreSQL 2844 and Chromium desktop/mobile on exact source 3150fbb; isolated Render dep-dbiskimc6qcc739ivrcg LIVE. S-06.01.02 remains IN_REVIEW because no real watched browser flow, DNS rebinding pen test, live provider session, D-330 or production approval |
| D-337 | 2026-10-31 | gap/security | high | Owner-initiated read-oriented HTTP browser jobs were synchronous, with no way to see or stop a currently running request. A slow or unexpected run could continue until the 115-second timeout even after the owner wanted it stopped. Added a non-durable workspace/chat-scoped task registry, GET active-run and owner-only DELETE cancellation, cancelled result after cleanup, and lease release; app shutdown/restore and chat deletion cancel tasks. Actual Render TDD RED cf31c14 / dep-dbiugrm7bikc73dtnrr0: 3 failed, 40 passed; targeted GREEN 44 on fd8a73a / dep-dbiuigg473hc73ambq30. | F-06.01 / S-06.01.02 IN_REVIEW; fixed and verified on fd8a73a with 44 targeted, 2828 SQLite, 2848 PostgreSQL, 215 focused PG, Chromium desktop/mobile, verifier 67; isolated Render dep-dbiuigg473hc73ambq30 LIVE. No cross-process transport, real browser/provider test, UI watch/control or production security acceptance; see docs/evidence/2026-10-31-chat-browser-cancellation.md |



### D-71 — A stale forbidden frontier row could stop valid crawling · 2026-09-23

**What went wrong.** `claim_due()` selected rows with SQL `LIMIT` and only
then re-ran the current URL policy. If the first persisted row was now forbidden,
the validator rejected it but left it due and unleased. With `limit=1`, every
later claim selected the same forbidden row and returned no work even though a
valid due URL was waiting behind it.

**How it was found.** CHECK-mode cold review of S-05.01.01. An isolated RED
reproduction selected the forbidden row, returned zero claims, and showed the
valid row still due.

**The fix.** Policy-rejected persisted rows are deleted inside the same
`BEGIN IMMEDIATE` transaction and selection continues until the requested
number of valid claims is filled or no due work remains. No schema or public
interface changed.

**Evidence status.** The isolated corrected scheduling case now claims the valid
row and removes the forbidden one. The repository test
`test_claim_due_removes_a_persisted_url_rejected_by_current_policy` is committed,
but GitHub Actions still fails before workflow step 1, so S-05.01.01 remains
IN_REVIEW.


### D-72 — Malformed extraction selectors loaded as valid config · 2026-09-23

**What went wrong.** The extraction-pack registry bounded selector strings but
did not parse-check them. A malformed selector such as `div[` therefore passed
registry loading and failed later only when Scrapling parsed a matching page.
That violated S-05.01.02's fail-closed configuration criterion.

**How it was found.** CHECK-mode cold review compared the story acceptance
criteria with `ExtractionPack.from_data()`, `ExtractionRule.from_data()` and
the real `ScraplingPageParser` consumers.

**The fix.** Registry loading now validates selectors with Scrapling's own CSS
parser, the same parser used at runtime. Packs may select elements only; the
runtime continues to own text/attribute extraction. No second CSS grammar or
new dependency was added.

**Evidence status.** Regression tests for malformed record selectors, malformed
field selectors and pack-supplied pseudo-elements are committed. GitHub Actions
still fails before workflow step 1, so S-05.01.02 remains IN_REVIEW.


### D-73 — Competitor evidence accepted NaN and Infinity · 2026-09-23

**What went wrong.** `_non_negative_number()` converted values with `float()`
and checked only `number < 0`. IEEE NaN is not less than zero, so it passed.
Infinity passed too. A NaN duration could then crash timeline tick conversion;
non-finite performance metrics could survive into stored/API evidence.

**How it was found.** CHECK-mode cold review of S-05.01.03 followed every
accepted numeric fact through recipe selection, arithmetic and serialization.

**The fix.** The shared numeric validator now requires `math.isfinite()`
before the existing non-negative check. No recipe threshold or business rule
changed.

**Evidence status.** Regression cases for NaN duration and infinite views are
committed. GitHub Actions still fails before workflow step 1, so S-05.01.03
remains IN_REVIEW.


### D-74 — Missing teardown recipe leaked an internal exception · 2026-09-23

**What went wrong.** The deterministic analyser correctly called the canonical
recipe registry, but an `UnknownRecipe` from that registry was not translated
to the teardown domain error caught by the API. Catalogue drift could therefore
turn a controlled refusal into a 500.

**How it was found.** Final S-05.01.03 failure-path review compared the
architecture's explicit “recipe cannot be resolved” refusal with the actual
exception boundary.

**The fix.** Catch `recipes.UnknownRecipe` exactly and re-raise
`CompetitorTeardownError` with the original catalogue reason. Unrelated errors
still surface normally.

**Evidence status.** A monkeypatched catalogue-drift regression is committed.
Executable repository evidence remains unavailable because Actions fails before
workflow step 1.


### D-75 — GitHub-hosted CI never reaches step 1 · 2026-09-23

**What went wrong.** Push and pull-request runs create the `quality` job, but
GitHub completes it as failure before assigning a runner. The Jobs API returns
no workflow steps and no logs, so checkout, dependency installation, tests and
the verifier never execute.

**How it was found.** Repeated evidence attempts on the current branch,
including run 1205 / 35779093017. A manual re-run created job 106939339831 and
failed identically. The workflow itself still targets ordinary
`ubuntu-latest` and begins with `actions/checkout@v4`; there is no repository
step before the failure.

**Why it matters.** The repository Definition of Done requires real locked test
output from the current session. While runner allocation is unavailable, every
code-complete story must remain IN_REVIEW.

**Status.** Open under S-06.02.18. The remaining diagnosis is outside
application code: account Actions billing/budgets/payment state, repository
Actions policy, or GitHub-hosted runner provisioning/service state. Tests and
DONE rules will not be weakened to work around it.


### D-76 — Partial privacy retry could certify stale success · 2026-09-23

**What went wrong.** A store marked successful on the first deletion attempt was
skipped on every retry. If another store failed and matching personal data was
written again into the successful store before retry, the retry could clear the
failed store and report the whole request complete while the new row survived.

**How it was found.** CHECK-mode failure-path review of S-06.02.04 followed the
persisted receipt across two attempts instead of testing only an unchanged
fixture.

**The fix.** Historical success is reusable only after the same adapter's
read-only `find(subject)` inventory proves that store is still clean. If data
reappeared, deletion runs again. A failed re-inventory or missing adapter is a
failed store, never a cached success. CRM remains last.

**Evidence status.** The regression
`test_partial_retry_rechecks_previously_successful_stores_before_completion`
is committed. Executable repository evidence is still blocked by D-75, so the
story remains IN_REVIEW.


### D-77 — Global memory leaked into companion runtime context · 2026-09-23

**What went wrong.** `CompanionRegistry.start()` requested the companion's
exact scope, but the production `OutreachStore.search_memory_items()` defines a
scoped query as `global OR requested scope`. The companion unit fixture used
exact-scope semantics, so tests and production disagreed.

**How it was found.** CHECK-mode blast-radius review replaced the fake-memory
assumption with the actual memory store contract.

**The fix.** The shared search keeps its historic behaviour by default through
`include_global=True`. Companion runtime explicitly passes
`include_global=False`, so only approved items from the exact companion scope
are returned. Existing API memory searches keep their prior semantics.

**Evidence status.** A regression using the real `OutreachStore` is committed.
Executable evidence is blocked by D-75; S-04.01.01 remains IN_REVIEW.


### D-78 — Resume could recreate a lost owner-edited PLAN.md · 2026-09-23

**What went wrong.** `AgentRun.run()` calls `RunPlan.ensure()` on both start
and resume. If a managed run lost PLAN.md between processes, `ensure()` treated
it like a pre-feature legacy run and recreated the original boilerplate from the
owner goal. Any steering edits were silently lost.

**How it was found.** CHECK-mode restart-path review compared the documented
"missing PLAN refuses" contract with the actual resume call path.

**The fix.** Managed run directories carry an empty private
`.PLAN.managed` sentinel. It contains no instructions and is not a second
source of truth. Existing PLAN.md files without the marker are adopted
non-destructively for migration. A marker with a missing PLAN.md now fails
closed instead of regenerating content.

**Evidence status.** Regressions cover lost managed plans and adoption of an
existing legacy plan. Executable evidence remains blocked by D-75, so
S-02.02.02 stays IN_REVIEW.
| D-102 | 2026-09-18 | process | high | Artifact CLI registration wrote a literal `\\n` into `pyproject.toml`, which would make project metadata invalid | fixed before review · `S-07.01.04` — committed metadata is re-read after scripted edits |

---

## What these add up to

Read the `Found` column, not the `Fixed` one. Five patterns keep repeating, and
each one is a thing to check rather than a thing to feel bad about.

**1. The bug is usually in code that was already finished and passing.**
D-06, D-07, D-02, D-23 and D-24 were all in slices marked `DONE`. The new story
did not break them; it was the first thing that *looked*. When a story touches
old code, the old code is the suspect.

**2. A green test is not the same as a working feature — and a control that is
never exercised is not a control at all.**
D-03 passed with the feature deleted. D-17's test went green while the bug was
still there — the other thread survived because a five-second timeout released
the lock, not because anything was correct. D-29 checked for a string that
correctly escaped output legitimately contains. Ask of every test: *what would
make this pass if the feature were gone?* And if a test involves timing, look at
how long it took, not only whether it passed.

The sibling of this is worse, because nothing goes red at all. D-35, D-40 and
D-44 were each a control that existed, was configurable, was displayed on a
screen — and could never fire, because the one value feeding it was a hardcoded
zero, an absent field, or the wrong half of a parsed file. **For every control,
ask when it last actually refused something.** If the answer is "never", that is
the finding.

**3. Two lists that must match will drift apart, silently — and so does state
that must be shared.**
D-14: the verbs that act and the verbs that are paced were different lists, and
`press` fell in the gap. D-24: signatures were written on one code path and not
the other. D-32: the same again, on a shortcut path. D-38 is the same shape in
arithmetic rather than in a list — the price of a call was computed in three
separate places, and one of them returned zero, which is what `D-35` actually
was underneath. D-42 and D-43 are the same thing again in *state*: a pace clock
and a lock that had to be shared across runs, held per run. When a rule applies
to a set, test that the **set is complete**, not that the rule works; when a
calculation appears twice, one of the two is already wrong; and when something
must be shared, share it by construction rather than by asking every caller to
remember.

**4. A limit two files away will not be seen from the line that matters.**
D-27: a value may be 20,000 characters and the field holding it caps at 4,000,
so the JSON would have been cut in half and failed to parse on resume — losing
exactly what the feature exists to keep. Check the size limits of a store before
choosing what to put in it.

**5. For anything that detects, the false positives are the hard part.**
D-26 and D-34 were both definitions that sounded reasonable and were wrong.
Both were caught by a test about a case that must **not** match. Write those
tests first.

---

## Detail

### D-45 — Tidying up a live check destroyed the work it was checking · 2026-09-12

**What went wrong.** The live check for `S-06.02.12` needs a real orphaned
commit, so it made one in the working tree: commit, note the sha, `--amend`.
To undo that afterwards I ran `git reset --hard HEAD~1` — which also discarded
every *uncommitted* change in the tree, and that included the feature being
tested and its tests.

**How it was found.** The check stopped firing. I assumed the check was wrong
and went looking, which cost several minutes before `grep check_commits` came
back empty.

**Why it mattered.** Nothing was lost permanently — a scratch copy in `/tmp`
still had the source and the tests were rewritten — but it could easily have
been an hour, and the failure presented as a bug in the feature rather than as
missing code, which is the expensive kind of confusion.

**The fix, which is a habit rather than a line of code.** A live check that
needs to mutate git history does it in a throwaway clone:

    git clone -q . /tmp/gate2 && cd /tmp/gate2

The check is just as real there — the clone has the same history and the same
board — and nothing it does can reach the work in progress. Committing before
running a live check is the other half of it, and is now what happens.


### D-44 — A rule that had never fired once · 2026-09-12

**What went wrong.** The Definition of Ready says an item may not enter `READY`
while an open question is filed against it, and `scripts/verify_board.py`
enforces it — or appeared to. Every question in `OPEN_QUESTIONS.md` names the
story it blocks **in its heading**:

    ### Q-04 — What is "the owner" when a team uses this? *(blocks S-06.01.02)*

The parser split the file on those headings and handed the check only what came
*after* each one. So it searched every question's body for a story id, and no
body contains one. Three open questions were blocking nothing at all.

**How it was found.** Writing a test for a *different* rule — that a story with
an open question against it should not be reported as available to pull. The
test failed, I assumed my test was wrong, and checked. It was not.

**Why it mattered.** It is the third control this session that looked present and
was not, after `D-35` (a spend cap fed a hardcoded zero) and `D-40` (a key event
with no default action). The board was still honest, but by luck rather than by
the check: none of the three blocked stories happened to be sitting in `READY`.

**The fix.** Keep the heading. One line, and the rule immediately caught
`S-06.01.02` against `Q-04` when that story was moved into `READY` on purpose.


### D-42 — N runs divided the pace floor by N · 2026-09-11

**What went wrong.** `policy.py` sets a minimum gap between actions on a host,
and calls it the single most important number there: what gets an account
restricted is rhythm, not volume. The gap was kept in a dictionary on each tab.
Two tabs meant two clocks, so two runs on one host went twice as fast as the
floor allowed, and N runs went N times as fast.

**How it was found.** By measuring before building, rather than reading the
code and believing it. Two runs, a 1.0s floor, three actions each:

    elapsed        2.00s
    honest minimum 5.00s   (six actions on one host, one every second)

**Why it mattered.** The agent was not going faster because anyone asked it to.
It was going faster because nobody was counting the two runs together — and the
faster it goes, the more it looks like the thing the floor exists to stop it
looking like.

**The fix.** `browser/pace.py`. One `Pace` is shared by every tab in a browser
session, and it records a *deadline* per host rather than a last-seen time — so
a run claims its slot before sleeping. Two runs arriving together are spaced,
rather than both reading "the last action was ages ago" and both going.

### D-43 — The budget ledger lost two thirds of its writes · 2026-09-11

**What went wrong.** `BudgetLedger` reads a JSON file, changes it and writes it
back, under a `threading.RLock`. The lock was created per instance. Concurrent
runs each build their own ledger over the same file, so the lock protected each
object from itself and nothing else, and the writes overwrote each other.

**How it was found.** Measured concurrently, which mattered: a sequential probe
of the same thing counted 12 of 12 and looked fine.

    4 concurrent runs, 25 actions each
    actions taken   100
    ledger counted   33     — 67% of the account's budget spent off the books

**Why it mattered.** The budget is the ceiling that stops an account being used
at a rate that gets it closed. Counting a third of the actions makes the real
ceiling three times whatever the owner set.

**The fix.** One lock per ledger *file*, keyed by resolved path and shared by
every instance over it. Keyed rather than handed in, because correctness that
depends on every caller remembering to share an object lapses the first time
somebody builds one locally — which is exactly how this happened.

**Known limit, measured and pinned:** the ceiling can still be overshot by one
action per concurrent run, because `S-03.02.04` deliberately checks before an
action and records after it so a failed action costs nothing. Measured at 1, 2,
3, 5 and 8 runs: the overshoot was N-1 every time, and a test holds it there.


### D-40 — The agent's Enter key never did anything · 2026-09-11

**What went wrong.** `press` dispatched `keyDown` and `keyUp` to the page with
no `text` field. Chrome raises the event — a listener sees it, `isTrusted` is
true — and then performs **no default action**. So Enter did not submit forms.
The agent had a verb in its ten that half-worked, and nobody had noticed because
nothing had ever checked what the *page* did afterwards, only what the call
returned.

**How it was found.** By the live check for `S-11.03.03` failing in a way that
made no sense: the gate refused Enter correctly, but when Enter was allowed
through, the form still did not submit. Measured key by key rather than guessed:

    key         today          with `text`
    Enter       does nothing   WORKS
    Tab         WORKS          WORKS
    Backspace   WORKS          WORKS

**Why it mattered.** Two ways. A broken verb in a closed ten-verb vocabulary is
a large fraction of what the agent can do. And it meant `D-25` — the gate that
stopped a click but not an Enter — was a hole nobody could fall through *yet*.
The day somebody fixed `press`, it would have opened silently.

**The fix.** Send the character the key produces: `\r` for Enter, `\t` for Tab.
Measured, not assumed — the keys that need it are the keys that type something.

### D-41 — The gate would have interrupted ordinary typing · 2026-09-11

**What went wrong.** The first version of the Enter gate asked "is the focused
element inside a form with a Send button?" A `<textarea>` inside a compose form
answers yes — so writing a message and pressing Enter for a new paragraph would
have stopped the run and asked the owner to confirm.

**How it was found.** The live check, on a page that had a textarea in it
because that is what a compose box looks like.

**Why it mattered.** Enter in a textarea makes a newline in every browser there
is. It cannot submit. So this was pure interruption — and the story's second
acceptance criterion exists precisely to prevent it: *a key that cannot submit
anything asks nothing new*. A gate that interrupts typing is one people switch
off.


### D-39 — A blocker nobody re-checked · 2026-09-11

**What went wrong.** `S-08.01.05` was stuck in `IN_REVIEW` from 27 August to 11
September. Its code was finished and its Python tests passed. The only thing
missing was a frontend test that could not run, because that day's environment
could not install an npm package.

Nothing was wrong with the story. What was wrong is that the reason it was stuck
was **environmental and temporary**, and nobody asked again for fifteen days.
The install takes under a minute and works.

**How it was found.** By asking "what is actually left?" rather than reading the
board's own answer. The board said `pending`, which is honest and is also the
kind of note that stops being read.

**Why it mattered.** Two weeks of a finished feature looking unfinished, and a
row on the board that everybody had learned to skip. A blocked item that nobody
re-tests is indistinguishable from a broken one.

**The fix.** `npm ci`, then the recorded command. 2 passed and 11 passed.


### D-35 — The daily spend cap can never be reached · 2026-09-11

**What went wrong.** The owner can set a daily spend limit per provider. The
check for it is real and works. But the line that records what a call cost
passes `spend_usd=0.0` — a hardcoded zero — so the running total never moves off
zero and the cap never fires.

**How it was found.** By running it instead of reading it. A cap of $1.00, then
5,000 calls recorded the way the code records them today:

    calls recorded   : 5000
    cap the owner set: $1.00
    spend counted    : $0.0000
    still allowed?   : True   (nothing refused it)

The same 5,000 calls priced at the number the run's own log already computes
come to $8.00, and the cap refuses immediately.

**Why it mattered.** This is the only thing standing between an agent left
running overnight and an unbounded bill. It is a control that exists, is
configurable, is displayed on the Connectors screen as a usage bar, and does
nothing.

### D-36 — The provider tells us what we spent and we throw it away · 2026-09-11

**What went wrong.** Every major provider returns a `usage` block with the exact
token counts for the call. The adapter receives the whole JSON response, pulls
the text out of it, and drops the rest. Cost is then guessed elsewhere by
dividing the number of characters by four.

**How it was found.** Looking for where a real number could come from, while
fixing D-35.

**Why it mattered.** Two separate problems. The guess is wrong — characters per
token varies by model and by language, and it does not count the tokens a
provider adds itself. And it makes "what did this run cost" unanswerable with
authority: the number in the log is off_CRM's opinion, not the provider's
receipt.


### D-79 — Generic secret assignments could bypass the prompt scanner · 2026-09-23

**What went wrong.** The model-input scanner knew vendor token prefixes and
token/password assignments, but not ordinary credential names such as
`api_key`, `api_secret`, `client_secret` or `secret_key`. An opaque
secret value with no vendor prefix could therefore enter a system prompt as an
assignment, or survive inside a FULL-policy mapping under one of those field
names, without being classified as a credential.

**How it was found.** CHECK-mode boundary review tested the scanner's promise
against generic credential shapes rather than only known providers.

**The fix.** One bounded case-insensitive assignment pattern was added to the
existing credential rule table and the generic names were added to the
structural secret-field deny-list. The broker still blocks before provider
instantiation; nothing is silently redacted and retried.

**Evidence status.** The parametrized system-prompt regression is committed.
Executable evidence remains blocked by D-75, so S-06.02.01 stays IN_REVIEW.


### D-100 — Concurrent workspace settings writes could erase another workspace · 2026-09-23

*(Recorded as D-80 on `feature/next-three-batch-4`. Renumbered when the branches
were consolidated into `develop`, because E-12 had already reserved D-80–D-99
and used D-80 for a different defect.)*

**What went wrong.** Atomic file replacement protected against torn JSON, but
each WorkspaceAISettingsStore had its own threading lock. Two server processes
could both read the old settings/key document and each replace it, with the last
writer silently dropping the other's workspace changes.

**How it was found.** CHECK-mode blast-radius review followed the read-modify-
replace lifecycle rather than treating atomic rename as concurrency control.

**The fix.** Workspace settings/key writes now serialize their complete
read-modify-replace windows through a small SQLite write lock, which is
cross-process and standard-library only. Existing atomic replace remains for
crash safety. Shared readers and public method signatures are unchanged.

**Evidence status.** A regression uses two independent store instances and a
forced overlapping pre-fix snapshot. Executable evidence is blocked by D-75;
S-06.01.01 remains IN_REVIEW.


### D-101 — Workspace usernames rejected ordinary characters · 2026-09-23

*(Recorded as D-81 on `feature/next-three-batch-4`. Renumbered when the branches
were consolidated into `develop`, because E-12 had already reserved D-80–D-99
and used D-81 for a different defect.)*

**What went wrong.** The raw regex used double-escaped control sequences inside
a negated character class. It therefore excluded literal characters such as
`r`, `n`, `x` and `0` instead of only NUL, carriage return and newline.

**How it was found.** CHECK-mode login-path review compared the actual compiled
pattern with the error message and tried ordinary names that the existing
`alice`/`bob` fixtures never exercised.

**The fix.** The regex now contains the intended control-character escapes.
Regression cases cover normal names containing the formerly banned characters
and embedded newline/NUL refusal.

**Evidence status.** Tests are committed; executable evidence is still blocked
by D-75, so S-06.01.01 remains IN_REVIEW.


Only where the one-line version is not enough.

### D-16 — Two writes at once destroyed half the rows · 2026-09-08

**What went wrong.** The outreach store shares one database connection across
threads, and the web server runs 193 of its 206 handlers in a thread pool — so
two requests really do arrive at the same moment. Python's SQLite driver
promises to serialise one *statement*. A transaction is several statements, and
it did nothing for that.

    thread A   BEGIN, INSERT 'holder', raise  ->  ROLLBACK
    thread B   INSERT 'bystander'             ->  reported success
    rows left: none

Thread B's write was undone by thread A's failure, and B was told it worked.

**How it was found.** Two threads writing forty rows each. Forty of the eighty
were gone.

**Why it mattered.** 64 call sites depended on this, including `claim_next` —
the thing that stops the email worker sending the same message twice.

**The fix.** The transaction holds a reentrant lock for its whole body. But see
D-17: that was not the whole story.

### D-17 — The fix passed its own test while the bug was still there · 2026-09-08

**What went wrong.** Wrapping the connection made the test green. The bug was
still there — the real cause was `isolation_level`, a default that makes Python
open a transaction nobody asked for and leave it open.

**How it was found.** By not stopping at a green test. The holder thread was
still raising "cannot start a transaction within a transaction", which did not
fit the explanation in my head.

**Why it mattered.** Shipping it would have put a lock around the symptom and
left the cause in place, and the next person would have had no reason to look.

### D-20 — Every API route was open on a local install · 2026-09-09

**What went wrong.** Login was enforced only when a token or a demo login
happened to be configured. A default local install had neither, so it served
every contact to anything that could reach the port.

**How it was found.** Calling every `/api/` route with no credentials. All 200.

**Why it mattered.** "It only listens on localhost" is not a boundary. Every
other process and user on the machine can reach it, so can a browser extension,
and so can any web page that points a hostname it controls at 127.0.0.1.

**The fix.** Auth required on every host, loopback included. A local install
provisions its own token instead of failing. See also D-21.

### D-27 — A resumed run would have lost its facts, silently · 2026-09-10

**What went wrong.** The plan was to store each gathered fact inside its log
line. A fact's value can be 20,000 characters and its supporting quote 4,000.
The log line caps at 4,000 characters total. The JSON would have been cut off
mid-string, and then failed to parse when the run resumed.

**How it was found.** Checking the caps before writing the code, for once. The
mechanism that solves it — a separate file beside the log, for page text — had
existed the whole time.

**Why it mattered.** A run resumed after a crash would have come back having
lost exactly the facts it exists to collect, and nothing would have said so.

### D-29 — An XSS test that was testing nothing · 2026-09-10

**What went wrong.** The test planted a `<script>` tag in the page body. Page
bodies never reach the report — they live in a separate file — so the test was
checking that something absent stayed absent.

Rewriting it to plant the tag in text the model *quoted* then produced a second
wrong test: `assert "onerror=" not in page` **fails against correctly escaped
output**, because escaping turns `<` into `&lt;` and leaves the word `onerror`
sitting there harmlessly.

**How it was found.** By deleting the escaping and watching which tests noticed.
Three did, after the rewrite. None did, before.

**The fix.** Parse the tag names the browser would actually run and compare them
against the list the report is allowed to emit. Test the **property**, not the
shape of the output.

### D-34 — A help page about 2FA would have paused every run · 2026-09-11

**What went wrong.** Two rules in the new wall detector. One matched `/auth` as
a bare word, so `/help/two-factor-authentication` looked like a login URL. The
other counted "two-step verification language plus any text box" as a wall — and
a help article has a search box.

**How it was found.** By writing the *not-a-wall* tests before the wall tests: a
marketing homepage, a help article, a search results page.

**Why it mattered.** This detector is allowed to stop a run. A detector that
pauses on ordinary pages teaches the owner to ignore it, which is worse than not
having one.

### D-51 — Two crawler processes can outrun one host's crawl delay · 2026-09-19

**What went wrong.** The durable frontier leases URLs, not hosts. That correctly
prevents two workers from fetching the same URL, but two processes can still
claim two different due URLs on the same host at the same time. The existing
crawl-delay clock lives inside each fetcher process, so those two processes do
not share it.

**How it was found.** During the S-05.01.01 review, by tracing the full
frontier → claim → fetch path instead of treating the same-URL lease test as
proof of host-level politeness. `claim_due()` has no host pacing state, while
`SafePublicFetcher.last_request_at` is process-local.

**Why it matters.** S-05.01.01 explicitly promises that a host's robots.txt and
crawl delay are honoured. A multi-process deployment could satisfy the current
tests and still send requests closer together than the host asked for.

**Status.** Code fixed under S-05.01.01; executable evidence is still pending. The story remains IN_REVIEW. It must not move
to DONE until the host-level pace is durable/shared, has a concurrency test that
uses different URLs on the same host, and the repository evidence command runs.
