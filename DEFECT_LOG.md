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
|---|---|---|---|---|---|
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
| D-47 | 2026-09-16 | security | medium | The frontend development dependency tree reports four audit findings, including a high-severity nanoid advisory; the production tree reports zero | open · `S-06.02.16` |
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
| D-80 | 2026-09-22 | process | high | In a shallow clone the verifier says every recorded commit is "not a commit in this repository at all", and CI checks out shallow — so once runners are available the ancestry rule turns every CI run red for a reason that has nothing to do with the board. Found when a cloud session started shallow and 32 DONE stories looked falsified; `git fetch --unshallow` made the board green | open · S-06.02.20 |
| D-81 | 2026-09-22 | security | medium | The video director puts the owner's typed house style in the system prompt, which the broker neither logs nor classifies — a `public` request can carry owner text to a tier C model and the egress log does not show it. Found while tracing where product details could safely travel; the GTM engine was designed around it rather than through it | open · S-12.01.03 |
| D-82 | 2026-09-22 | gap | high | A plan's posting channel had no path from the screens to a published post: nothing pairs its posting and picture campaigns in content automation, switches the automation on or approves a post, and Apply's next steps implied that connecting an account and resuming was enough. Found while writing the review's remedy for "nothing published" and looking for the screen it should open — there was none | open · `S-12.02.06` (next steps and the review now say it plainly) |
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
| D-97 | 2026-09-23 | gap | low | A plan's posts-a-day is read by nothing that posts — the rate is set on Posting — yet the rules revision "raised" it. The rules now name it as a Posting-screen action; the plan's number still shows as intent until posting runs from the plan. Found by the cold review | open · `S-12.02.06` |
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
| D-122 | 2026-09-23 | bug | medium | A valid 60-frame export of the default Colour clip is refused because it is smaller than the 4096-byte gate (audit A34; `MIN_BYTES = 4096` is unchanged) | open · `S-06.02.23` |
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
| D-137 | 2026-09-23 | bug | low | Opening a screen can scroll its own top out of view. Seen on Settings in real Chromium while checking `D-130`: the title sat half under the top bar, and the "Could not refresh campaigns" panel — the reason campaign work was blocked — was above the viewport. `focusMainContent()` focuses the main area without `preventScroll` under a 68px sticky top bar; whether every screen is affected is the first step of the work order | open · `S-06.02.25` |
| D-138 | 2026-09-23 | bug | medium | Two command-line defaults still ignore `OFFSETX_DATA_DIR`: `offsetx-outreach gmail-authorize` writes the Gmail token to `local_data/gmail_token.json` (the web app reads it from the data directory), and `offsetx-db` defaults to `local_data/ai_egress.db`. The same drift as `D-127`, in the paths it did not cover | fixed · `S-06.02.24` |
| D-139 | 2026-09-24 | gap | medium | `offsetx-artifacts` writes its XLSX, PPTX and PDF reports beside the trace, and the app records agent runs under the data directory, so rendering one wrote into the workspace without the lease. `S-06.02.24`'s work order listed it as not a workspace writer; the re-check the work order asked for found it | fixed · `S-06.02.24` |
| D-140 | 2026-09-24 | bug | medium | `.env.example` set `OFFSETX_OUTREACH_DB` and `OFFSETX_GMAIL_TOKEN` to paths under `local_data/`, so a `.env` copied from it kept both files behind when `OFFSETX_DATA_DIR` moved: a production start with that `.env` refused, and a local install's Gmail token fell outside the folder the backup covers. Both lines are now commented out, with the reason | fixed · `S-06.02.24` |
| D-141 | 2026-09-24 | bug | low | `offsetx-notebook` looked for the AI context beside the CRM database; the web app keeps it in the data directory. With the CRM database named elsewhere the two differ, and a notebook bundle silently lost its "what worked" section | fixed · `S-06.02.24` |
| D-142 | 2026-09-24 | bug | high | A tool run as root in the container before the app served a request left a root-owned 0600 lock file; the app's own user could not open it, and every API request answered 500 while health stayed green. The email worker could already do it; `S-06.02.24` added six tools that could. Lock files are now made 0644 (a 0600 one the app owns is widened) and opened read-only when they cannot be written; the first fix, read-only alone, could not open a 0600 file at all — a second fresh-context review caught it, and a check with two real users proves the second | fixed · `S-06.02.24` |
| D-143 | 2026-09-24 | bug | low | `offsetx-evals` and `offsetx-tools` worked out the data directory through the web app's settings, which write an API token into it — before the lease was taken, so a refused run still wrote, and could recreate a folder a restore had just moved | fixed · `S-06.02.24` |
| D-144 | 2026-09-24 | bug | low | The tools' second refusal said a restore was interrupted and that starting the web app rolls it back; a committed journal left by a cleanup failure is kept, not rolled back, in an app already running. It now says to restart the app, which completes it | fixed · `S-06.02.24` |
| D-145 | 2026-09-24 | gap | low | `offsetx-db` looked only at `copy-log --from` and at the data directory: a mistyped `--to` path made a SQLite file in a workspace held by a restore, and a check of a CRM database outside the data directory — which a backup covers — took no lease | fixed · `S-06.02.24` |
| D-146 | 2026-09-24 | gap | medium | The tools lock the data directory worked out from the current folder, not the workspace whose files they open: an explicit `--db`, `--token` or absolute path to the web app's files from another folder, `OFFSETX_DATA_DIR` set only in `.env` (read by two of the six tools), or `offsetx-artifacts --run-dir .` from inside a run still write during a restore. Found by the fresh-context review | open · `S-06.02.28` |
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
| D-196 | 2026-09-28 | gap | low | A login created in workspace `local` — allowed by the id rules on an install with no demo login — acts as the install owner: it sees every profile and settles waiting ones. `DD-59` accepted this as a cost; nothing warns the person creating it. Older than this work; found by the sixth check. Whether a second owner login should need an explicit choice is the owner's call | open · `S-06.02.36` |
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
| D-217 | 2026-10-03 | bug | medium | The CRM store given a PostgreSQL URL does not refuse it: it hands the URL to `sqlite3.connect`, which makes a SQLite file named after the URL in the working folder — a password in the URL becomes part of a file name, and the CRM looks saved while it sits on the disk that is wiped. Reachable today by putting a URL in `OFFSETX_OUTREACH_DB`. Found when the first draft of the `S-06.03.03` tests passed "on PostgreSQL" against these files | open · `S-06.03.03` |
| D-218 | 2026-10-03 | process | low | A session was started on a branch cut from `main`, 444 commits behind `develop`, where `S-06.03.03` does not exist at all. Asked to pull it, the session would have reported a missing story. Found by searching every remote branch before answering; the branch was fast-forwarded to `develop` | open · `S-06.02.19` |


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
