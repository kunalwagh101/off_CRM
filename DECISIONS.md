# Design decisions

**What this is.** Calls made while building, written down with what they cost.
Plain English.

**How this differs from the two files beside it.**

| File | Whose decision | Question it answers |
|---|---|---|
| `OPEN_QUESTIONS.md` | The **owner's** | "Which of these options do you want?" |
| `DECISIONS.md` | The **builder's** | "Why is it built this way and not the obvious way?" |
| `DEFECT_LOG.md` | Nobody's | "What broke, and how was it found?" |

**Why it exists.** These used to live in module docstrings and commit messages.
Docstrings are read by whoever opens that file; commit messages are read once.
Neither answers "have we already decided this?", which is the question that
wastes a session when nobody can answer it.

**The rules.**

1. Log a decision when the obvious thing was **not** done. Doing the obvious
   thing needs no entry.
2. Say what was given up. A decision with no cost was not a decision.
3. Say what would make it wrong. That is the trigger to revisit it.
4. Never delete an entry. If it is reversed, add a new one that says so.

---

| ID | Date | The call | Cost |
|---|---|---|
| DD-132 | 2026-11-01 | Restore the existing AI layer in the public demo and derive each visitor AI workspace from its verified signed session token; keep the real broker/trust boundary and delete only that session's keys on logout | A new login cannot recover its earlier session's AI chats or keys, and visitors must connect their own provider. Keys are encrypted on the demo server, not kept solely in the browser. Demo data remains disposable; arbitrary CRM/browser execution and original-site upgrade require separate existing permissions/data protection. |
| DD-131 | 2026-11-01 | Give public visitors a separate disposable sample-only installation, non-owner account, read allowlist and explicit visible credentials instead of a login over the private CRM | Adds a separate free Render service. Public visitors can browse sample CRM data but cannot mutate it, connect services or use AI. Sample data is recreated after disposable storage loss; this does not solve production tenancy or durability. |
| DD-130 | 2026-10-31 | Add an in-process owner-only active-run registry and cancellation request endpoint for bounded chat browser reads, using the existing asyncio task and workspace lease rather than starting a second scheduler or persisting live task IDs | This cancels only tasks running in the same web process; multi-instance cancellation, real browser test, disconnect behaviour, observable progress and true attended UI are still release gates. HTTP 202 means a cancel request, while the interrupted POST returns cancelled only after the runner finishes cleanup. |\n| DD-129 | 2026-10-31 | Add a bounded owner-initiated read-oriented HTTP browser run by reusing the existing RoutineAgentExecutor/AgentRun with chat grants, strict per-action permission refresh and workspace lease; deliberately enforce unattended domain limits and deny write-like browser verbs until a live watch/cancel session exists | A public GET may still cause site-side effects and browsing remains unavailable for attended-only sites. Response is synchronous with a 115-second limit and uses a process-local chat grant; it is not a full attended-agent experience. Nested Docker/browser smoke, real owner approval UI, multi-instance coordination, production egress firewall and durable trace storage still need separate acceptance. |\n| DD-128 | 2026-10-31 | Tie owner-approved attended browser grants to authenticated AI chat ownership and keep them process-local with a one-hour maximum lifetime and closure on chat deletion, rather than persist or broadcast approvals | An approval ends on restart and does not work across instances; users must explicitly re-approve. The AI Copilot is not a browser runner, so the future attended-agent entry point still needs to pass these grants to AgentRun and render a real approval control. Existing globally denied tools cannot be elevated. |
| DD-127 | 2026-10-31 | Keep the public WorkspaceAISettingsStore.save path but add strict mode only for owner browser-permission updates, checked inside the existing exclusive write lock, instead of trusting an API preflight read | Adds an extra strict locked document read for security-sensitive updates; a damaged settings file blocks permissions changes until repaired rather than letting the API overwrite it. Legacy unrelated settings writes continue with their lenient semantics. |
| DD-126 | 2026-10-31 | Reload scheduled-agent browser permissions before each action and refuse on unreadable/malformed stored policy instead of using a run-start snapshot | Adds a store read per action and pauses the run when policy storage fails. Other consumers keep their existing lenient settings reader; independent live revocation/penetration acceptance and attended-chat permission lifecycle are still needed. |
| DD-125 | 2026-10-30 | Keep load-balancer web readiness independent from enabled optional scheduler operations; expose a private, fail-closed operator signal instead | The owner must monitor this signal or connect an alert sink; it does not itself page anyone, and cannot certify health of a separately deployed email worker without persisted heartbeat proof. |
| DD-124 | 2026-10-30 | Store workspace browser-action policies in the existing hosted AI settings, rather than create a second SQLite policy database; default to allow for existing installs and treat global deny as a hard ceiling | Avoids a second lost-on-redeploy store and a migration; initial historical runs keep their previous behaviour until owner changes policy. A dedicated chat-grant API, audit approval identity and end-of-conversation event are still required before full S-06.01.02 signoff. |
| DD-123 | 2026-10-30 | Show owner-only inventory-derived data durability instead of treating a configured hosted database as proof of full production readiness | Does not migrate files, enable hosted production or certify backups; Q-29 external backup, S-06.03.06 remaining stores and a verified mount and restore remain release conditions. |
| DD-122 | 2026-10-30 | Pre-read video multipart request bodies into a size-limited temporary spool before Starlette's multipart parser rather than rely on endpoint UploadFile limits | Costs one extra disk write/read per accepted video, bounded by file budget plus 16 KiB; two concurrent streams per worker, not global across web replicas. Revisit when adding a streaming object-store media intake or a reverse proxy upload limit. |
| DD-01 | 2026-08-25 | No proxy inside the browser box | The allow-list lives in the browser, not at the socket |
| DD-02 | 2026-08-28 | off_CRM never handles a password | Sign-in cannot be automated at all |
| DD-03 | 2026-09-05 | A signed-in page counts as private by default | Planning fails closed without an approved high-trust model |
| DD-04 | 2026-09-06 | **No Cloudflare or anti-bot evasion. Ever.** | Pages that challenge a real browser stay unreachable |
| DD-05 | 2026-09-06 | Ten verbs, closed. No `evaluate`, no code | Some pages cannot be driven at all |
| DD-06 | 2026-09-10 | The trace *is* the progress — no checkpoint file | Resume costs a full replay of the log |
| DD-07 | 2026-09-10 | Page text never enters `trace.jsonl` | Every quote needs a second file beside the log |
| DD-08 | 2026-09-10 | Injection is recorded, never blocked | An attack is visible but not stopped |
| DD-09 | 2026-09-10 | `goto` is exempt from the duplicate-action guard | A URL whose GET has a side effect is not protected |
| DD-10 | 2026-09-11 | The step's signature is the record of what ran, not its English | Every writer of an action step must add the marker |
| DD-11 | 2026-09-11 | A wall **may** stop a run, though injection may not | A wrong match costs the owner a glance at a browser |
| DD-12 | 2026-09-11 | `needs_human` can be resumed; `human_gate` cannot | Two endings that look alike behave differently |
| DD-13 | 2026-09-11 | The provider's own token counts beat our character count | Two numbers to explain instead of one, so each call says which it is |
| DD-14 | 2026-09-11 | The run's estimate rides on `run_started`, not its own step | Less visible in the log than a step of its own would be |
| DD-15 | 2026-09-11 | The ceiling predicts from the worst decision so far, not the average | Runs stop a little earlier than they strictly need to |
| DD-16 | 2026-09-11 | A resumed run re-applies the ceiling it was started with | Raising it needs an explicit argument, which is easy to forget |
| DD-17 | 2026-09-11 | An unattended run may not use a countdown at all | The attended and unattended paths through the gate are different code |
| DD-18 | 2026-09-11 | Shared state is shared by construction, not by asking callers | A class-level registry keyed by file, which is global state by another name |
| DD-19 | 2026-09-11 | The pace floor records a deadline, not a last-seen time | A run reserves its slot before it knows whether it will use it |
| DD-20 | 2026-09-16 | A latency ceiling stops new work at operation boundaries; it does not kill an operation already in flight | The run can exceed the ceiling by the latency of one already-started operation; the overrun is measured and reported |
| DD-21 | 2026-09-18 | Keep crawl scheduling deterministic and local; do not add ML, Redis or a second crawler framework | SQLite is a single-host frontier today; a future multi-host crawler must move this boundary to shared storage |
| DD-22 | 2026-09-20 | Owner-authorized build-ahead may consume a code-complete upstream story in IN_REVIEW, but downstream work also stops at IN_REVIEW until the dependency chain is verified | More review debt can accumulate before the owner's dedicated verification pass |
| DD-23 | 2026-09-20 | Extraction packs are validated JSON data over the existing Scrapling parser; no parser plugins, templates, code or AI | DOM changes require pack maintenance and semantic extraction is intentionally absent |
| DD-24 | 2026-09-20 | Competitor teardown starts as deterministic structure mapping into the existing recipe/assembly/review path | It cannot infer subjective creative intent; adding AI later requires measured eval evidence |
| DD-25 | 2026-09-20 | Explicit privacy deletion removes a whole matching trace run and deletes CRM identity data last | A run containing mixed subjects can lose unrelated trace context, but append-only audit history is never silently rewritten |
| DD-26 | 2026-09-20 | Browser platform identity, pacing and default budgets come from one packaged validated registry | Changing a built-in platform declaration requires a code/config release rather than a runtime admin edit |
| DD-27 | 2026-09-20 | PLAN.md is mutable steering state, while every model decision captures the exact plan version it saw into the append-only trace | The same plan text exists once as current state and again as historical evidence |
| DD-28 | 2026-09-20 | Companions are rows in the existing tool-registry SQLite DB, with exact memory scopes and execution-time tool-grant checks | Companion persistence is coupled to the local tool-control database until the broader workspace storage story moves it |
| DD-35 | 2026-09-23 | A request schema bounds a body's shape — types, sizes, unknown fields — and leaves required-ness, allowed values and clamping to the older handlers that already refuse with a sentence | Those fields accept any string up to their size, and the handler, not the schema, is where to look for the rule |
| DD-36 | 2026-09-23 | A ValueError's reason goes back to the caller, bounded to 500 characters, unless the credential scanner flags it | A reason that quotes the caller's own input is echoed; only credential-shaped text is withheld |
| DD-37 | 2026-09-23 | The audit's live harness (`verification/`) and its two GitHub workflows stay on the archived branch; they were not ported | The Chrome, PostgreSQL and Docker acceptance run is not in `develop`; its WP1 container check was replayed by hand instead, and `S-06.02.23` owns bringing it back |
| DD-38 | 2026-09-23 | Both Render services stay on the free plan and neither claims production; they deploy on commit, not when checks pass | Anything typed into either is lost on restart until the owner pays for a disk (Q-26); a push deploys even if it would have failed CI |
| DD-39 | 2026-09-23 | A restore reopens services through the same function startup uses, not a list kept beside the restore code | `app.py` owns one more function; a store added to startup is reopened after a restore with no second list to forget |
| DD-40 | 2026-09-22 | The strategy brain picks channels, sources and shapes from declared lists; a model never writes a campaign structure | A strategy the vocabulary cannot express cannot be proposed until someone adds a registry row |
| DD-41 | 2026-09-22 | Product details travel only in classified request fields, never in a system prompt and never in `instructions` | At a `minimal` policy the model sees only the one-liner and the plan is thinner — the plan says so |
| DD-42 | 2026-09-22 | Apply creates campaigns paused, imports nobody and spends no Apollo credit | One more deliberate step per campaign before anything runs |
| DD-43 | 2026-09-22 | A plan's goal is replies or views only | An owner who thinks in meetings translates to replies until meetings link back to campaigns |
| DD-44 | 2026-09-22 | Plans send email only on the targeted-outreach stream | A genuine opt-in list cannot be planned for from this screen |
| DD-45 | 2026-09-22 | A review stops at the first thing wrong, in a fixed order, the pipe before the copy | A campaign with two problems shows them one review at a time |
| DD-46 | 2026-09-22 | Campaign-to-product links live in a table `gtm` owns, not a new column on `campaigns` | The campaigns screen cannot join to products in SQL; it has to ask `gtm` |
| DD-47 | 2026-09-22 | The review imports `pacing.decide()` but repeats `sales.py`'s ten-line Wilson interval, pinned equal by a drift test | Importing `outreach.sales` runs `outreach/__init__`, which pulls the whole engine and pandas into a pure module; the price is a copy a test must hold equal |
| DD-48 | 2026-09-22 | A forbidden claim in a model's plan removes that field; it does not refuse the whole plan | The owner can receive a plan with a named gap instead of no plan |
| DD-49 | 2026-09-22 | Apply is idempotent per channel and marks the plan applied only at the end, instead of one transaction | Campaigns and links live in two stores. A crash between creating a campaign and linking it leaves one unlinked campaign, and the per-plan lock holds only inside one process |
| DD-50 | 2026-09-22 | The review reads the pacer's `steering` flag, not only its action: "hold" means *not enough data* only below the pacer's own floor of measured posts, and a hold or a cut for any other reason (a deadline passed, the owner's cap) is `pacer_idle` with no remedy | Two more finding codes than the design table first had (`pacer_idle`, `window_ended`), and the review depends on a field of `PacingDecision` rather than one word. Wrong if the pacer's actions ever carry that meaning themselves |
| DD-51 | 2026-09-22 | A remedy with no screen says so — `set_up_posting` names the API — rather than linking to the nearest screen | The owner reads an API path in a product screen. Wrong once `S-12.02.06` gives posting a screen, which should replace the sentence |
| DD-52 | 2026-09-22 | When a model's review skips a channel whose finding permits something, that channel gets the rules' first remedy, with a note | A model cannot choose "say nothing" about a blocking finding. Wrong if owners start reading the filled-in remedies as the model's advice; the note is what prevents that |
| DD-53 | 2026-09-22 | A version's review counts only the sends since that version was applied, by subtracting a baseline Apply records, rather than the campaign's lifetime totals | A new version starts from zero data, so it waits for 20 fresh sends before its copy is judged even when the angle did not change. Wrong if revisions that keep the copy become common; then carry the data over for an unchanged angle |
| DD-54 | 2026-09-22 | A closed window — ended, under 7 days left, or the goal met — starts a new window at the first version's size, instead of refusing to revise | The owner does not choose the new window's size here; they draft a new plan for a different goal. For views the pacer counts views already earned toward the new goal, and the note says so. Wrong if owners want a new goal size per window, which needs the revise body to accept one |
| DD-55 | 2026-09-23 | A plan's angle reaches what is sent through the product link — posts use the applied version's angle, and templates may say `{product_angle}` — rather than by rewriting the owner's templates | An email changes only if its template uses `{product_angle}`; a template that does not keeps saying what it said. Wrong if owners expect every email to change with the plan; then the draft writer needs the angle as an input, not a placeholder |
| DD-56 | 2026-09-23 | *Revises DD-53's mechanism.* A version's baseline is taken from the review it was written from, not recorded when it is applied | Sends between the review and the Apply count toward the new version though the old angle made them. Chosen because the new version's goal is "what was left at the review" — counting from anywhere else loses replies or counts them twice (`D-95`) |
| DD-57 | 2026-09-23 | A paused posting campaign publishes nothing: its due posts are skipped and stay scheduled, and content automation makes nothing for a paused pair | Pausing now also holds posts the owner already approved, where before it held nothing. That is what pause means everywhere else in off_CRM, and a plan's "nothing has sent" depends on it (`D-87`) |
| DD-58 | 2026-09-23 | Apply never changes an archived campaign — not to pause a dropped channel, not to run a kept one — and says so | A revision whose channel's campaign is archived does not run that channel until the owner unarchives it. Wrong if owners archive to mean "pause"; then Apply should ask |
| DD-59 | 2026-09-23 | The install owner — who may back up, restore, or run and configure the install's timers — is whoever acts as the install's own workspace, `local`: the install token, the demo login, or a server run without auth. Not the token alone, as workspace administration requires | On Render the owner signs in with the demo login and has no token (none is made when a login is configured), and a backup is how that owner keeps data across a free-plan deploy. A workspace login created with the id `local` is the owner too |
| DD-60 | 2026-09-23 | The shared engine's product reader learns its caller from a per-request marker the security middleware sets, rather than every drafting call taking a workspace argument | The engine keeps its signature. An unsigned request carries "" and is refused. But a missing marker means "a timer" and reads through the link, so drafting moved onto a thread that does not copy the request's context — a bare `Thread`, `run_in_executor` — would read another workspace's product. None does today; `asyncio.to_thread` and FastAPI's threadpool copy it. The stronger design, a timer that marks itself and a missing marker that refuses, is the second review's to weigh |
| DD-61 | 2026-09-23 | Drafting a campaign linked to another workspace's product is refused with a sentence, not drafted without the product | That login cannot write drafts for that campaign at all. The alternative looked like success and skipped the product's forbidden-claim checks |
| DD-62 | 2026-09-23 | A backup or restore stops the scheduled jobs first, for at most 30 seconds, while requests still flow; one that will not stop refuses the operation and keeps running | A backup can be refused while a long job runs. The app is never held at 503 waiting for one |
| DD-63 | 2026-09-23 | Compose mounts the host's `./local_data` at the image's new data path, rather than moving to a named volume | Existing installs keep their data with no migration step; the folder is owned by the container's user (10001), as the old image's files already were |
| DD-64 | 2026-09-25 | Provider keys come only from the app: the `OFFSETX_AI_<PROVIDER>_KEY` fallback is removed, not limited to the owner | A headless install can no longer be keyed from its environment. One path for keys is the owner's rule, and the fallback served every workspace (`D-151`) |
| DD-65 | 2026-09-25 | *(Amended the same day after the fresh-context review.)* A model is trusted as much as its provider, or less — the lower of the provider's tier and the model's limit, where the limit is the model's own setting, else the cap from who built it. The provider sees every byte, so blocking it blocks every model on it. A model setting past its origin cap needs a typed reason; one above its provider is refused. A full-access grant never lifts a model held below its provider. Every change is kept in a bounded history | A model can never be trusted more than its host, even deliberately. The first version ("the model's own setting wins both ways") let a blocked provider keep routing to a model with its own setting (`D-156`) |
| DD-66 | 2026-09-25 | *(Amended 2026-10-02 at the owner's word: not only Neon — Render's PostgreSQL too, and build so the install can move to a PostgreSQL on AWS or Azure later.)* Durable data on the free plan goes to a hosted PostgreSQL — any PostgreSQL 13 or newer, the code naming no host; Neon free recommended to start, as Render's free database is deleted with its data after 30 days plus 14 days' grace — with the database address and one master key set once by the install owner; provider keys are still typed in the app | Weeks of work and a network dependency, instead of a monthly disk fee. Supabase was rejected: its free projects pause after a week idle |
| DD-67 | 2026-09-25 | *(Amended 2026-09-26 after the third and fourth fresh-context reviews.)* The owner's full-data grant (`BUILD_STATE.md` §5.1) reaches only a known model trusted at its provider's default tier or higher; lowering the provider pauses it, and returning to the default resumes it. While it stands it lifts what the models it covers are sent to its level — never lowers it. The owner's own "How much to send" level is kept underneath, unchanged; the form offers only levels up to the provider's standing trust (its default, or the owner's raise), and a save above that, from the API, is stored cut and reported as cut. A grant that can change nothing — on a blocked provider, a lowered one, tier A, or where no switched-on model is at the default — is refused, and the screen offers it by the same rule | The grant is not per model: a model held below its provider's default never gets it, even deliberately — raising that model's own trust to the default is the way. Lowering one provider can move its tasks to another, whose grant then decides what it receives (the broker's highest-tier-only rule). Full data above the standing trust is the grant's job, not the form's. Judging the grant against the provider's current tier let lowering raise what was sent (`D-167`); writing it into the owner's level lost that level (`D-176`); letting it decide alone let withdrawing raise what was sent (`D-186`) |
| DD-68 | 2026-09-25 | *(Amended 2026-09-26 after the third and fourth fresh-context reviews.)* Whose a provider profile is, is recorded by the server from the login that saved it — the install owner's is `local` — never taken from the request, and checked in the same write that saves it. A draft uses only the caller's own profiles. A profile saved before this is in no draft chain until the install owner settles it in Settings, under "Provider profiles to confirm". Confirming takes the API key the profile holds: its label proves nothing, since before `05e9738` every login's saves could read "default". It goes where the pressed Confirm button says, and only somewhere the list offers: the owner always — the key proves it — and, first, the client workspace its label names, if one does. Each button sends its own destination, and Enter in the key box confirms only a profile with one place to go — it does not press the first button. "default", "local" and an empty label name the owner whatever a workspace is called. One with no key stored — a template engine needs none — cannot be confirmed, only removed; none is adopted automatically, and a waiting profile cannot be saved over | An owner who no longer has a profile's key, or whose profile needs none, must remove it and add it again, through the API until `S-06.02.35`. Proof by key is the only evidence off_CRM has: labels were typed by whoever saved them, and nothing recorded who that was (`D-165`, `D-166`, `D-177`, `D-185`, `D-190`, `D-191`, `D-194`). With two places to go, Enter only says to press a button: one more click, as the first button would have sent the owner's key to a client (`D-197`) |
| DD-69 | 2026-10-02 | The spend and call counters behind each provider limit move to the hosted database with the keys and settings (`S-06.03.02`), though the design's phase 1 did not list them | One more document in the database. A free Render service loses its disk at every spin-down after 15 minutes idle, so a daily limit counted on that disk starts again from zero many times a day — a limit that is not one (`D-198`) |
| DD-70 | 2026-10-02 | The hosted stores are written for any PostgreSQL host, not for one: the URL is passed through untouched, a dropped connection is reopened but a failed statement never re-sent, no server-side prepared statements, a schema version per store (`offcrm_schema`), and the master key for provider keys only ever in the environment | A round trip to check a connection idle 30 seconds or more, and statements planned each time. Bought: Neon's sleep, Render's internal URL, a pooled URL, and a later move to AWS or Azure all work with no code change, as the owner asked on 2026-10-02 |
| DD-71 | 2026-10-03 | The CRM schema says `BIGINT` and `DOUBLE PRECISION` where it said `INTEGER` and `REAL`, so one DDL serves both backends; nothing rewrites SQL types at run time (`S-06.03.03`) | A schema file that reads less like SQLite. SQLite gives the new names the same affinity and leaves existing files alone; PostgreSQL's `INTEGER` stops at about 2.1 billion and its `REAL` keeps about 7 digits, and a regex over DDL is the pattern-matching that corrupts quietly |
| DD-72 | 2026-10-03 | A CRM transaction asked for as `immediate` takes a PostgreSQL advisory lock first, so one writer at a time holds across processes there as `BEGIN IMMEDIATE` holds it on SQLite (`S-06.03.03`) | Those transactions wait on each other, as they already did on SQLite. Without it, the web app and the email worker could both claim the same delivery job under PostgreSQL's default isolation |
| DD-73 | 2026-10-03 | CRM search compares `lower(column)` with `lower(term)` on both backends rather than `ILIKE` on one (`S-06.03.03`) | No index helps a `%term%` search either way. One query for both, and PostgreSQL's `lower` also folds non-ASCII letters, which SQLite's `LIKE` never did |
| DD-74 | 2026-10-03 | A local CRM file stops a hosted start only for rows the owner put there: the built-in templates and expert notes every start writes are recognised by asking the real seeding (an engine over a scratch file), not by a list kept here (`S-06.03.03`) | 21 ms once per process, and only when the database is on and a CRM file exists. Bought: no second copy of the seed to drift, no refusal for an install that never held the owner's data, and a template or note the owner wrote still counts |
| DD-75 | 2026-10-03 | **Corrects `DD-73`.** Its "PostgreSQL's `lower` also folds non-ASCII letters" reads as a gain on both; it is a difference. Search ignores case for A–Z on both backends and for accented letters on PostgreSQL only ("évora" finds "Évora" there, not on SQLite). SQLite's `lower` is left as it is (`D-237`) | The two backends answer an accented search differently, written in `HOSTED_STORAGE.md`'s limits. Replacing SQLite's `lower` would make them agree, but the unique index `idx_contacts_email_ci` was built with the old one: a uniqueness check that disagrees with its own queries. Wrong if accented names turn out to be searched often on SQLite installs |
| DD-76 | 2026-10-03 | A CRM copy replaces the built-in templates and expert note already in the destination, rather than refusing a destination that holds any row (`S-06.03.03`, `D-227`) | A destination holding a row the owner wrote is still refused, and telling the two apart reuses `DD-74`'s scratch seeding. Refusing everything was simpler and made the import impossible once any tool had started on the database |
| DD-77 | 2026-10-03 | On PostgreSQL a CRM write waits at most 5 seconds for another writer (`SET LOCAL lock_timeout`), then refuses with "the CRM is busy", as SQLite's `busy_timeout` already did (`S-06.03.03`, `D-229`) | A write behind a slow one fails and must be tried again, where it would have gone through late. Bought: one stuck worker cannot freeze every request in the web app. Wrong if a legitimate write is found holding the lock for longer |
| DD-78 | 2026-10-03 | Only the install owner is told where the CRM's database is; a workspace user sees "PostgreSQL" or "SQLite file" (`S-06.03.03`, `D-232`) | A workspace user cannot tell which host or file their data is on. The host, user and database name help an attacker and nobody else in a workspace |
| DD-79 | 2026-10-04 | Screen navigation focuses main with `preventScroll` then explicitly resets the window to its top (`S-06.02.25`, `D-137`). Chromium showed delayed warnings remain visible without another error-triggered scroll | Switching screens gives up the prior scroll position. Revisit if navigation gains deliberate position restoration. An extra scroll on background errors could interrupt someone already reading, so it is omitted |
| DD-80 | 2026-10-09 | Failure traces contain exception types and frame locations, never messages, source lines or locals; serialized JSON is never password-redacted | Less diagnostic detail; static metadata must stay allow-listed and IDs must stay searchable |
| DD-81 | 2026-10-09 | Every job/watch cycle owns a fresh de-duplication scope, transferring only the reference of an escaping exception to its caller | A small context/propagation seam to preserve exception types without retaining every cycle in a long-lived command |
| DD-82 | 2026-10-09 | Unexpected failures become safe API errors and nonzero CLI outcomes; known operator advice is explicitly mapped to fixed sentences | Generic failures need operator lookup; tests that expected raw exceptions from public API/CLI boundaries change while internal exceptions remain typed |
| DD-83 | 2026-10-09 | Plans declare disabled posting pairs; Start enables one, proposal decisions bind to exact identities, and declared media is revalidated before publication | A pair needs explicit Start after a global stop; stale proposals require refresh; unavailable attachments fail instead of becoming text-only posts. Revisit for workspace timers or official social adapters |
| DD-84 | 2026-10-12 | For a WebM shorter than 4096 bytes, inspect declared video tracks and nonempty encoded sample blocks instead of globally lowering the byte floor (S-06.02.39/A34) | Adds a small EBML scan and cannot itself decode codecs. Independent ffprobe and a real browser export remain acceptance requirements; MP4 retains the original rule. Revisit if codecs or small-file formats expand |
| DD-85 | 2026-10-13 | New workspace login `local` is explicitly owner-confirmed at the install-token API boundary (S-06.02.36), while existing logins and bootstrap are unchanged | A caller that previously created another owner by picking `local` must add a true JSON boolean; direct bootstrap remains a trusted internal operation |
| DD-86 | 2026-10-13 | CLI restore leases discover actual workspace roots from sidecar lock/journal ancestors, instead of inferring the root from cwd only (S-06.02.28) | A copy of a workspace with neither a lock sidecar nor restore journal cannot be discovered from an arbitrary file path; real restart and concurrent restore tests remain the acceptance gate |
| DD-87 | 2026-10-13 | Provider balance checks allow only hardcoded, documented vendor endpoints and show local usage separately (S-06.02.34) | New vendor balance endpoints need deliberate engineering updates; provider rate-limit header capture and a live credential check remain unfinished rather than returning a guessed figure |
| DD-88 | 2026-10-13 | Video director user style and linked ProductTruth travel only in classified CAMPAIGN fields, with system instructions fixed and logged (S-12.01.03) | Providers with a policy too thin for campaign data now legitimately refuse a styled/product-directed request; older egress rows contain blank prompt history and cannot reconstruct earlier calls |
| DD-89 | 2026-10-13 | Frontend CI must fail on a real npm audit rather than declare fixed vulnerabilities by checking only pinned direct versions (S-06.02.16) | The build may be blocked until npm registry and runner access return; no lockfile upgrade can be certified without network-backed dependency installation |
| DD-90 | 2026-10-13 | GTM reference evals require 30 fully judged real cases, never synthetic starter counts; imported unscoped expert chunks are withheld from nonlocal workspace models (S-12.02.05) | A/B promotion stays unavailable until user sources real corpus/cases and expert storage gains tenant ownership; third-party materials stay in campaign-class notes instead of instructions |
| DD-91 | 2026-10-13 | Production BrowserBox refuses launch through unrestricted Docker bridge until destination-level network isolation is proven (S-03.01.03/A07) | Browsing through BrowserBox is unavailable in production pending an operator-controlled egress network; local development remains possible but must not be treated as safe from DNS rebinding. Revisit after real zero-private-connection Chrome/Docker tests |
| DD-92 | 2026-10-13 | Temporarily refuse the unsafe JS-rendered Crawl4AI fetch path instead of trusting preflight DNS + Playwright route checks (S-05.01.04/A08) | JavaScript-only discovery sites cannot be crawled until verified destination-IP enforcement exists; safe_http remains available. Revisit only with a live firewall/proxy and DNS-rebind regression |
| DD-93 | 2026-10-13 | Reuse the existing authenticated contact offset API for 100-row pagination instead of caching a 500-row client list (S-06.02.41/A23) | Adds page requests and a small UI state; changing filters resets the page. User acceptance still needs a real large campaign |
| DD-94 | 2026-10-13 | Escape spreadsheet formulas only in human-readable report copies, leaving CRM and internal credit/identity ledgers in their original representation (S-06.02.42/A19) | Exported dangerous strings gain a leading apostrophe; internal CSV ledgers should not be opened in Excel. Retaining state fidelity avoids breaking deduplication |
| DD-95 | 2026-10-13 | Revoke individual signed workspace browser sessions by storing SHA-256 digests with expiry in the same SQLite/PostgreSQL auth database (S-06.02.43/A06) | Every cookie verification needs a revocation lookup and a hosted schema step; rollback to older code requires rotating the session-signing secret to prevent revoked-cookie replay |
| DD-96 | 2026-10-13 | Give Contacts a filtered all-page CSV rather than changing its existing full-campaign report, with no durable intermediate file (S-06.02.44) | Export only named operational contact fields under a consistent CRM read transaction; cap at 50,000 with explicit refusal; preserve full-campaign report and its consumer contracts |
| DD-97 | 2026-10-13 | Discover category/A-B variant filter values from the chosen campaign instead of shipping hardcoded client constants (S-06.02.45) | Adds one read-only authenticated facet endpoint, avoiding stale choices or mixed campaigns |
| DD-98 | 2026-10-13 | The existing stored checkbox is a campaign membership selection; filter it at SQL level before pagination and mirror it in CSV output (S-06.02.46) | All matching marked records reachable, no implicit send or mass-mutation command |
| DD-99 | 2026-10-13 | The Send Queue UI uses a page-limited read from existing queue-control rows while its sender keeps the original all-contacts queue contract (S-06.02.47) | A metadata scan across all contacts is still required for accurate totals; recipient names and generation metadata travel only for the selected page. Live campaign-scale benchmark remains pending |
| DD-100 | 2026-10-13 | Queue counts use the sender's timezone-aware due calculation and clearly distinguish candidate readiness from final provider preflight (S-06.02.48) | Counts can differ from actual sends because quota, suppression, email validation and delivery windows are checked later; avoid claiming they are an exact send forecast |
| DD-101 | 2026-10-13 | Server-filter actionable queue cohorts before slicing the page, with no new approval/send mutation (S-06.02.49) | Adds a validated view query and UI switch, preserves the existing live-send confirmation |
| DD-102 | 2026-10-13 | Expose the existing protected campaign PATCH as a complete settings editor, validate IANA timezone at the backend and require typed confirmation to archive (F-06.04) | No new table; archived restoration always stops at paused. Non-email campaign type-specific settings remain outside email editor |
| DD-103 | 2026-10-13 | Clone only the campaign configuration into an immediately paused row using one DB transaction, not the campaign's contacts/outbox/credentials (F-06.05) | Safe reuse requires explicitly repopulating audience and enabling sends; nested transaction and idempotency replay add complexity but avoid accidental outbound effects |
| DD-104 | 2026-10-13 | Measure response rate over distinct outbound-contacted recipients, excluding unsent manual replied statuses (F-06.06) | This differs from imported-contact reply rate and excludes pure inbound prospects from numerator; metrics only describe CRM state and not provider delivery |
| DD-105 | 2026-10-14 | Build Audience Management on the existing global-contact identity and campaign membership model, linking duplicate emails without modifying shared profiles (F-06.07) | Manual entry requires an email; no implicit generated drafts or sends; cross-workspace tenant ownership remains a separately tracked open contract |
| DD-106 | 2026-10-14 | Batch audience actions require 1–100 explicit validated campaign IDs, an all-or-nothing transaction and a typed UI stop confirmation (F-06.07) | Stopping excludes future queued sends but cannot recall an in-flight external delivery; no mass resume was added |
| DD-107 | 2026-10-14 | Readiness is strictly a local read-only report from existing CRM state, not a live sending permission or provider-delivery assurance (F-06.08) | Readiness result is intentionally conservative in meaning; external preflight remains with the sender |
| DD-108 | 2026-10-14 | Add event type filtering and faceting without changing existing payload response schema; render only whitelisted metadata in the new activity UI (F-06.09) | Stable paging and a visible history are added, but legacy raw event payload retention is unchanged |
| DD-109 | 2026-10-14 | Review received replies per campaign membership instead of changing global contacts.outcome_label; triage never changes sender status or creates outbound messages (F-06.10) | Adds a separate triage table and requires hosted schema upgrade and user-facing data boundary review |
| DD-110 | 2026-10-14 | Display correspondence by verified campaign membership with bounded message-body previews and no raw provider metadata (F-06.11) | Controlled CRM PII view needs cross-workspace authorisation/retention acceptance; no extra provider traffic |
| DD-111 | 2026-10-14 | Add durable manual follow-up tasks with optimistic revision checks and explicit IANA/timezone-aware due time, without automatic contact or permission implication from owner labels (F-06.12) | Additive SQLite v10/Postgres upgrade; backup and restore are release gates; schema downgrade requires real restore |
| DD-112 | 2026-10-15 | Permit sales conversion only for reviewed Positive/Meeting inbound replies; reuse exact normalized-email Sales Tracker lead or fail closed on ambiguous duplicate; persist campaign membership link in the same write transaction (F-06.13) | Additive SQLite v11/Postgres step 3 and backup/restore gates; no automatic sends or existing-lead overwrites |
| DD-113 | 2026-10-15 | Contact 360 validates exact campaign membership and returns only explicit safe identity, reply/task and sales-link projections (F-06.14) | Deliberate user navigation to separate correspondence preview remains; Q-27 workspace authorisation still needs independent review |
| DD-114 | 2026-10-15 | Priorities are a read-only SQL-composed worklist of overdue tasks, unreviewed incoming replies and linked stale/untouched opportunities with stable filtering and counts (F-06.15) | No model scoring, background notifications or automated external actions; large-campaign SQL performance requires validation |
| DD-115 | 2026-10-15 | Unified CRM search indexes only purpose-allowed name/email/company across global contacts and workspace-filtered Sales Tracker leads; match query is escaped, bounded and paged (F-06.16) | Supports efficient person finding without expanding access to raw private messages or changing sender/identity tables; future tenant Q-27 remains a gate |
| DD-116 | 2026-10-15 | Company intelligence groups only case-insensitive, trimmed exact company names; keeps opportunity and contact aggregates separate (F-06.17) | No unverified entity merge, subsidiary matching, fuzzy dedupe or externally enriched firmographics; large-account query plan needs validation |
| DD-117 | 2026-10-15 | Attribute each linked Sales Tracker lead to the campaign holding its earliest recorded link, with deterministic tie and no duplicate monetary credit (F-06.18) | Association is not causal attribution, booked value differs from cash collected, no FX conversion; financially sensitive interpretation needs review |
| DD-118 | 2026-10-15 | Keep contact quality as allowlisted read-only issue categories, with scoped exact-email Sales Tracker overlap as a human review hint rather than an automatic merge (F-06.19) | Avoids destructive identity decisions and disclosure of notes, messages or provider data; workspace Q-27 still applies |
| DD-119 | 2026-10-15 | Compare campaigns using unique membership presence of recorded inbound/outbound, explicitly declared denominator and N/A for no outbound (F-06.20) | A descriptive comparison only; does not prove reply timing, statistically significant lift or causal attribution |
| DD-120 | 2026-10-15 | Group human follow-up performance by case/outer-whitespace-normalized free-text assigned_to, with saved due/completed timestamps and unassigned group (F-06.21) | No verified user identity, access policy, activity prediction, automation or new schema |
| DD-121 | 2026-10-15 | A missing request context cannot imply install-owner permission: default-deny the shared linked-product reader, and give only the authorised content scheduler an explicit, resettable owner scope (S-06.02.21 / D-313) | Requires timer-context injection through the async-to-thread hop; unsafely unscoped CLI/background draft calls now fail visibly rather than inherit install privileges. Revisit only with an explicit principal-bearing job context |
| DD-34 | 2026-09-18 | Report artifacts are deterministic renderers: no second model call; XLSX reuses openpyxl, PPTX uses the small OOXML subset directly, PDF prints the existing safe HTML through installed Chromium | PPTX is intentionally plain and PDF requires a Chromium-family browser; branded templates or server-only PDF would justify a document library later |

---

## Detail

### DD-04 — No Cloudflare or anti-bot evasion. Ever. · 2026-09-06

**The obvious thing.** The owner asked for the agent to understand Cloudflare
"and bypass it". Fingerprint spoofing, CAPTCHA solving, TLS forgery and
headless-detection evasion.

**What was done instead.** None of it, and none of it will be.

**Why.** Four reasons, and the first is the one that decides it.

1. **The penalty is losing the account, not being slowed down.** These platforms
   do not answer a suspected bot with a rate limit. They close the account. The
   thing being risked is the asset the owner spent months building.
2. **The race is permanently lost.** The other side has more people on it than
   this project will ever have, and they ship continuously.
3. **It destroys the only thing competitors cannot copy.** An auditable agent is
   the product. An agent that forges its way in cannot be audited by anyone.
4. **It moves the legal exposure onto the owner**, in a jurisdiction where that
   is not a theoretical cost.

**What was built instead, and why most of the want is already met.** A real
Chrome, with the owner's real profile and real operating-system input events, is
not challenged — because it is not a bot. `S-11.03.01` handles the rest: when a
challenge does appear, the run stops and asks the owner.

**What would make this wrong.** Nothing about the arms race. Only a change in
what the owner is willing to risk, and that is `OPEN_QUESTIONS.md`, not here.

### DD-06 — The trace is the progress · 2026-09-10

**The obvious thing.** Write a checkpoint file: where the run got to, what it
found, what it tried.

**What was done instead.** Nothing new. The run resumes by replaying its own
append-only log.

**Why.** A checkpoint is a second record of the same facts, and two records
disagree eventually — usually after a crash, which is the exact moment resume is
needed. The log is written before anything else happens and is already the thing
the audit depends on. A design note from August had already said this; two
thirds of the story was reading it rather than reinventing it.

**Cost.** Resuming reads the whole log. Runs are capped at 50 steps, so this is
not a real cost yet. It would become one if that cap moved a lot.

### DD-08 — Injection is recorded, never blocked · 2026-09-10

**The obvious thing.** Find an instruction hidden in a page and stop.

**What was done instead.** Write it down and carry on under the owner's goal.

**Why.** The agent is already contained by something stronger than a detector: a
model driving this browser can name one of ten verbs, cannot supply code, and
cannot reach the CRM. An instruction sitting on a page has nothing to reach for.
The fire door was built first; this is the smoke alarm. What was missing was not
containment — it was that an attack left **no mark at all**.

**Cost.** A real attack is visible and not stopped. Accepted, because the thing
it would be stopped from doing is already impossible.

**What would make this wrong.** The verb list growing something that can act
outside the page — a file write, a network call, a CRM update. Then this trade
has to be re-argued from scratch. See DD-11, where it was.

### DD-11 — A wall may stop a run, though injection may not · 2026-09-11

**The obvious thing.** Follow DD-08: detect, record, carry on.

**What was done instead.** The wall detector stops the run.

**Why the same project made the opposite call twice.** The costs are opposite. A
wrong injection match costs one line in a log, so those patterns can be broad
enough to catch a rephrasing. A wrong wall match costs the owner a glance at a
browser — so that detector reads structure rather than prose and wants
corroboration before it speaks.

What makes stopping safe is that it is **cheap and reversible**: the check runs
before the model is asked anything, so no budget is spent, and the run resumes
from the same step. Where the two errors are close it leans towards asking,
because a false negative costs a whole run spent against a locked door.

**Cost.** A settings page with a password field on it will pause a run.
Accepted; the owner resumes.

### DD-12 — `needs_human` resumes, `human_gate` does not · 2026-09-11

**The obvious thing.** Both are "the run stopped and a person is needed", so
treat them the same.

**What was done instead.** One resumes and one does not.

**Why.** They are opposite situations wearing the same coat.

- **A wall** — a person must act before the run *can* continue. Once they have
  signed in, the right thing is for the run to carry on from where it was.
- **A human gate** — the agent wants to do something consequential and a person
  must decide whether it happens *at all*. That is not a thing you resume into;
  it is a thing you approve or refuse.

**Cost.** Two endings that look alike behave differently, which is a thing
somebody will get wrong later. It is written at the line that decides it, in
`resume()`, and not only here.

### DD-13 — The provider's receipt beats our guess · 2026-09-11

**The obvious thing.** Keep estimating from character counts. It was already
written, it was close enough, and it needed no new code.

**What was done instead.** Read the `usage` block the provider already sends,
price that, and label every figure with where it came from — `provider` when it
is the receipt, `estimated` when it is not, `cache` when nothing was sent.

**Why.** The guess is wrong in a way that cannot be corrected: characters per
token varies by model and by language, and it cannot see the tokens a provider
adds itself. More importantly it made "what did this run cost" unanswerable with
authority — the number was off_CRM's opinion, and the owner is entitled to the
provider's.

**Cost.** Two numbers to explain instead of one, so every call now has to say
which kind it is. That is a real cost in the interface and it is the honest
version: reporting a guess without saying so is the cheaper option and the
worse one.

**What would make this wrong.** Nothing likely. If a provider reported usage
that disagreed with its own invoice, this would need a third source, which is
what the `usage_source` field leaves room for.

### DD-14 — The estimate rides on `run_started` · 2026-09-11

**The obvious thing.** Give the estimate its own step in the trace, the way
every other notable event gets one.

**What was done instead.** It goes in `run_started`'s own record, beside the
goal and the budget it was derived from.

**Why.** It is not an event that happened. It is a property of the run, computed
from the budget recorded in that same line — and splitting "what this run was
asked to do" from "what that should cost" across two adjacent steps makes each
of them half a record. A resumed run also reads it back for free.

**Cost.** It is less visible in a `grep` of the log than a `needs_human` or
`injection_suspected` line is. Mitigated by putting the sentence in
`run_started`'s detail as well as the JSON beside it.

**Honest note.** There was a second reason, and it is not a good one on its own:
a new step shifts every trace id after it, and five test files hardcode
`step-000002`. That fragility is `D-37` and is filed as `S-06.02.14`. It is
recorded here because a decision that happens to avoid a problem should say so,
rather than being remembered later as pure design.

### DD-15 — Predict from the worst, not the average · 2026-09-11

**The obvious thing.** Predict the next decision from the average of the ones
so far. It is the standard estimator and it is what everybody reaches for.

**What was done instead.** The most expensive decision the run has made.

**Why.** A ceiling is a promise, and the average lags a trend. A run whose pages
keep getting bigger — which is the normal shape of a search that is working —
would walk straight past the line while the average still said there was room.
The two errors are not symmetrical: stopping early costs the owner a run they
can restart with a higher ceiling, and going over costs them a limit they set
and did not get.

**Cost.** Runs stop a little earlier than they strictly need to, and one
unusually large page makes every subsequent check pessimistic for the rest of
the run.

**What would make this wrong.** If stopping early turned out to be expensive in
practice — a run that has to be restarted repeatedly — the answer is a smarter
predictor, not a more optimistic one.

### DD-16 — A resumed run keeps its ceiling · 2026-09-11

**The obvious thing.** `resume()` reconstructs the goal, the budget and the
schema from the trace. Let the caller pass a ceiling if they want one.

**What was done instead.** The ceiling is recorded on `run_started` and
re-applied automatically. Raising it takes an explicit
`resume(spend_ceiling_usd=…)`.

**Why.** The default would have been "no ceiling", and that turns the whole
feature into a speed bump: stop at the limit, resume, spend without bound. The
spend is read from the trace too, so a run killed and restarted ten times
counts one allowance rather than ten.

**Cost.** Raising a ceiling needs an argument somebody has to remember exists.
That is the right way round — forgetting it means the run stops, which is safe;
forgetting it the other way means the run spends, which is not.

### DD-17 — An unattended run may not use a countdown · 2026-09-11

**The obvious thing.** A countdown is a delay with a cancel. Let any caller
supply one; if nobody cancels, the action goes ahead.

**What was done instead.** `Page.click` refuses a countdown outright when the
page is in unattended mode, and sends the action back to the owner instead.

**Why.** A countdown with nobody watching is a sleep with extra steps — and
worse, it is the human gate deleted while still looking like it is there. Five
seconds pass, nobody cancels because nobody is there, and the agent has
effectively approved its own consequential action.
`docs/architecture/AUTONOMOUS_BROWSING.md` already said this in words —
*E-11 does not auto-confirm anything; autonomy is about the path, not about the
permission* — and a rule that lives only in a document is a rule somebody will
implement past.

**Cost.** The attended and unattended paths through the gate are now different
code, so there are two behaviours to keep in mind rather than one. That is the
right trade: the alternative is one behaviour that is wrong half the time.

**What would make this wrong.** Nothing about the mechanism. Only a decision
that unattended runs may act consequentially without a person, which is a much
bigger question than this and belongs in `OPEN_QUESTIONS.md`.

### DD-18 — Shared state is shared by construction · 2026-09-11

**The obvious thing.** `BudgetLedger` already takes a data directory. Tell
callers to build one and pass it around, the way they already pass the ledger
into each `Page`.

**What was done instead.** The lock is keyed by the resolved file path on the
class, so any number of `BudgetLedger` objects over one file share it
automatically.

**Why.** That instruction was already in the design and it was already being
ignored: concurrent runs each built their own ledger, the per-instance lock
protected nothing, and two thirds of the writes were lost (`D-43`). Correctness
that depends on every caller remembering a convention lapses the first time
somebody constructs one locally — and the failure is silent, which is the worst
combination.

**Cost.** A class-level registry is global state wearing a smaller hat. It never
shrinks, and two ledgers over paths that resolve the same are treated as one,
which is right here and would not be right everywhere.

**Why `Pace` is not keyed the same way.** Its natural boundary is a browser
session rather than a file — one browser is one set of logins acting as one
person — and there is no path to key on. So `BrowserSession` holds one and the
obvious construction picks it up. That is weaker than the ledger's guarantee,
and it is the reason `Page.pace`'s docstring says to pass `session.pace` rather
than mentioning it in passing.

### DD-19 — The floor records a deadline, not a last action · 2026-09-11

**The obvious thing.** Remember when each host was last acted on, and make a
caller wait until `floor` seconds after that. It is what the code did.

**What was done instead.** Remember when each host may *next* be acted on, and
have a caller claim that slot — moving the deadline forward — before it sleeps.

**Why.** The obvious version has a race that only appears with more than one
run, which is the entire point of this story. Two runs arrive together, both
read "the last action was ages ago", both conclude they need not wait, and both
act in the same millisecond. Claiming first means the second run is told to wait
by the first run's reservation rather than by its own observation.

**Cost.** A run reserves a slot before it knows whether it will use it, so an
action that raises after pacing leaves a gap nobody fills. The floor is a
minimum, so waiting slightly longer than necessary is the harmless direction.

### DD-20 — Latency stops at an operation boundary · 2026-09-16

**The obvious thing.** Wrap every provider or browser call in a wall-clock timeout
and cancel it at the exact millisecond ceiling.

**What was done instead.** Let an already-started operation finish, record its
measured latency, then refuse to start anything else once cumulative trace
latency reaches the ceiling.

**Why.** A cancelled browser operation may already have clicked, submitted or
changed remote state, and a cancelled provider request may still be billed. The
current interfaces have no transaction or cancellation acknowledgement that can
prove the side effect rolled back. Exact cancellation would make the number look
stronger while making execution less trustworthy.

**Cost.** The ceiling can be exceeded by one operation already in flight. That
overrun is explicit in the trace and `RunOutcome`, never hidden.

**What would make this wrong.** Every effectful provider/browser operation gaining
an idempotency or cancellation contract that proves whether the effect happened.


### DD-22 — Build ahead, never certify ahead · 2026-09-20

**The normal rule.** A story enters READY only after every dependency is DONE.

**The owner's explicit change.** The owner wants implementation to continue in
batches and will run a dedicated verification pass later. When an upstream
story is code-complete and only verification is deferred, an explicitly named
downstream story may therefore be built on top of it.

**Guardrail.** This changes implementation flow, not truth. The downstream
story may move only as far as IN_REVIEW. It cannot be DONE while any declared
dependency is unfinished. Automated/unit/static checks should still be run when
the available execution environment permits them; owner-side acceptance is not
invented.

**Cost.** Several stories can accumulate in review at once, so a defect in an
early slice can create rework in later slices.

**What would make this wrong.** If the upstream contract itself is still
ambiguous or changing, build-ahead stops. This exception is for deferred
verification, not unresolved design.


### DD-23 — Extraction configuration stays data · 2026-09-20

A new source declares domains, one record selector and bounded text/attribute
rules in JSON. The existing Scrapling parser executes those selectors after the
existing URL/robots/SSRF boundary. Python callbacks, templates, JavaScript,
remote packs and model extraction are refused.

**Cost:** a changed DOM can break a pack. **Revisit when:** stable public pages
cannot be represented with bounded selectors and measured semantic extraction
beats the deterministic baseline.

### DD-24 — Competitive analysis is structural and deterministic first · 2026-09-20

Normalized public facts map to an existing recipe and bounded shape parameters.
No competitor media, caption, transcript or audio crosses into a project. The
project then uses our own material and the existing human review queue.

**Cost:** it does not claim to know why a post worked. **Revisit when:** a fixed
evaluation set shows an AI structural classifier materially improves recipe
selection without leaking source content or bypassing review.

### DD-25 — Delete the matching trace run; do not edit history · 2026-09-20

Trace JSONL is append-only by design. A privacy deletion that rewrites selected
lines would turn that guarantee into a lie, so a run containing a verified
subject identifier is deleted as one filesystem unit, including screenshots and
captures. Auxiliary stores delete first; CRM identity rows delete last so a
failed auxiliary cleanup can be retried with the same join keys.

**Cost:** a mixed-subject run can lose unrelated trace context. **Revisit when:**
traces gain a cryptographically safe subject-partitioned storage format.


### DD-26 — One platform registry owns the moving pieces · 2026-09-20

Identity signals, domains/pacing and default account budgets used to be three
Python constants. Reddit was already present in the budget table and absent from
the other two, proving that drift was not theoretical. A packaged JSON registry
now owns all three and is validated all-or-nothing at load time.

**Cost:** editing built-in platform policy is a release, not an admin-panel
change. **Revisit when:** platform policy needs owner-specific runtime overrides;
those overrides should layer on top of this baseline rather than duplicate it.

### DD-27 — PLAN.md is mutable; the trace records what was seen · 2026-09-20

There is exactly one current PLAN.md in a run directory and the model reads it
fresh before every decision. The owner can edit it directly to steer the next
decision. The exact text seen by each decision is copied into that decision's
private trace capture, preserving auditability without turning the trace into a
second editable plan.

**Cost:** historical plan versions consume small extra run storage. **Revisit
when:** plans become large enough that content-addressed snapshots materially
reduce storage without making audit inspection harder.

### DD-28 — A companion narrows existing capabilities · 2026-09-20

A companion does not own a second model/tool/memory engine. It stores a name,
instructions, one exact memory scope and owner-granted tool IDs. Runtime starts
by intersecting those grants with tools that still exist and are enabled, and
tool execution checks the grant again.

Profiles live in the existing ToolRegistry SQLite database. This gives durable
transactions and multi-process writer safety without adding another storage
mechanism.

**Cost:** the companion table shares the tool-control DB. **Revisit when:** a
future workspace storage migration moves both tools and companions together.



### DD-35 — Schemas bound the shape; handlers keep the rules they explain · 2026-09-23

**The call.** `S-06.02.02` gave every raw body a strict schema. For the endpoints
that existed before it, the schema now checks only what a schema is good at —
the type, the size, no unknown fields — and the handler keeps deciding what is
required, which values are allowed and what is clamped.

**Why not the obvious thing.** Letting the schema decide everything is tidier,
and it is what the story did. But those handlers answer with a sentence the
owner can act on ("Choose one of: simple, verified…") and a code the screens
expect, while the schema answers 422 with a field path. 29 tests of finished
stories failed on it, and some requests the screens send — a clip placed
without a track — were refused outright (`D-107`).

**What it cost.** The rule for a field is in two places: its bound in
`schemas.py`, its meaning in the handler. New endpoints from `S-06.02.02`
onwards keep their full schema, because nothing older speaks for them.

### DD-36 — Return the reason, withhold only a credential · 2026-09-23

**The call.** The ValueError handler returns the exception's message, cut to
500 characters, unless the credential scanner flags it; then it returns the
fixed sentence.

**Why not the obvious thing.** Withholding every message is the safest reading
of "never echo request-body content", and it hid every reason the product gives
— "Unknown campaign kind", "Loss reason is required" — behind one sentence that
tells the owner nothing. What the criterion protects against is a secret coming
back; the scanner is the repository's one definition of a secret.

**What it cost.** A reason can quote the caller's own input back to the caller.


### DD-37 — The live audit harness stays archived · 2026-09-23

**The call.** `verification/` and the `live-verification` and
`wp1-verification` workflows from `integration/main-consolidation` are not in
`develop`. They are in the archive tag.

**Why not the obvious thing.** Porting everything is the obvious reading of
"leave nothing behind". But the harness was pinned to the audited commit, it
needs a non-root Chrome, a PostgreSQL service and Docker in CI, and the hosted
runners cannot start on this repository (`D-75`). A workflow that cannot run
would sit in `develop` looking like a gate. Its WP1 container test was replayed
by hand against the `develop` image, with the same steps.

**What it cost.** The other live checks — the 18 screens, login, the sandbox,
Enter, export decoding — do not run anywhere now. `S-06.02.23` brings them back
when there is somewhere to run them.

### DD-38 — Free and honest on Render until the owner pays · 2026-09-23

**The call.** `render.yaml` runs `off-crm-demo` from `main` and
`off-crm-develop` from `develop`, both free, both with data in `/tmp`, neither
with `OFFSETX_PRODUCTION`. Both deploy on every commit.

**Why not the obvious thing.** The durable-state work was built for a paid
plan with a disk, and its blueprint said so. Committing that would put a monthly
bill in the owner's Render account from a merge. `checksPass` is the safer
trigger, but with CI unable to start it means no deploy ever happens.

**What it cost.** Data on either service lasts until the next restart. The test
that guarded the blueprint now checks the rule that holds either way: a service
claims production only with a disk, and a service on `/tmp` never does.

### DD-39 — One function builds the services, for startup and for a restore · 2026-09-23

**The call.** `_open_runtime` in `app.py` is what startup runs, and what a
restore runs once the restored workspace is in place. The runtime module takes
it as an argument.

**Why not the obvious thing.** The original kept its own rebuild list in the
runtime module. This line has twelve more services than that branch had, and the
restore it replaced kept exactly such a list — which had already missed stores.

**What it cost.** The runtime module cannot rebuild anything by itself; tests
that fail the rebuild patch `_rebind_runtime`, which calls the function it was
given.

### DD-29 — API privacy is default-deny; bootstrap and signed callbacks are explicit exceptions · 2026-09-22

All `/api/` routes are private unless they are in the closed public path/prefix
allowlist. Login/session bootstrap, signed unsubscribe and signed SES/SNS
callbacks cannot require an existing CRM session by definition; they are the
explicit exceptions and their own authentication/signature rules still apply.

**Cost:** adding a genuinely public endpoint requires an explicit allowlist edit
and a boundary-test change. **Why:** the alternative is a route becoming public
because somebody forgot to add an auth decorator.

### DD-30 — Accessibility is enforced as a frontend invariant, not a page checklist · 2026-09-22

The shared shell owns skip navigation, visible focus, current-page state, live
feedback and modal focus management. A recursive repository test rejects
pointer-only generic click targets, positive tab order and fake role-buttons
without keyboard handlers across every TSX screen.

**Cost:** unusual custom controls need a real semantic/keyboard contract rather
than a quick div+click implementation. That is intentional.

### DD-31 — Meeting audio is transient and provider-bound · 2026-09-22

Meeting capture exists only on a loopback backend reached from a loopback browser
Origin. The browser locally mixes microphone plus shared system/tab audio and
holds chunks in memory until they are sent through the existing governed
transcription broker. Raw audio is never stored by off_CRM.

The transcription provider/model is frozen when the meeting record is created;
later chunks cannot redirect audio to a different provider. Only derived
transcript/timing/provenance metadata is persisted.

**Cost:** capture cannot run from the hosted CRM and a browser must support
system-audio sharing. Failed chunks must be retried while the capture page still
holds them in memory. **Revisit when:** a native desktop capture process can
provide the same or stronger local custody with an inspectable permission model.


### DD-32 — A managed PLAN may be missing only by failure · 2026-09-23

A legacy run with no PLAN.md may receive its first plan when it enters the
managed runtime. Once that happens, the directory carries an empty private
`.PLAN.managed` sentinel. The sentinel contains no instructions; PLAN.md
remains the only editable source of truth.

If the sentinel exists and PLAN.md does not, resume refuses. Reconstructing from
the original goal would be data loss because owner edits are intentionally not
derivable from the trace's current state.

**Cost:** one empty hidden file per managed run and a migration branch for old
run directories. **Revisit when:** run metadata gains a durable versioned
manifest that can carry the same managed-state fact without becoming another
editable plan.


### DD-33 — Serialize workspace file writes without migrating the store · 2026-09-23

S-06.01.01 keeps its existing JSON settings document and Fernet-encrypted key
document. Their complete read-modify-replace write windows are serialized across
processes by a tiny SQLite lock file using `BEGIN IMMEDIATE`; atomic replacement
still protects each target file from torn writes.

This is deliberately narrower than migrating workspace AI settings into a new
database during a CHECK repair. The data formats, API contracts, backup payloads
and readers remain unchanged.

**Cost:** one small lock database lives beside the workspace AI files, and write
availability now depends on obtaining that local SQLite lock. **Revisit when:**
workspace settings themselves move to the shared production database; at that
point the database transaction becomes the write lock and this sidecar can be
deleted while the application is stopped.

### DD-40 — Keep timer settings in hosted documents, refuse silent local loss · 2026-11-02

**The call.** Email and content scheduler settings use separate `timer.email`
and `timer.content` named documents through the existing `HostedStorage`
seam when a hosted database is configured. Local installs retain the original
JSON files. Writes run under the existing cross-process database transaction
lock. A hosted instance seeing an old timer JSON file refuses to start until
its owner explicitly preserves/migrates that file; a failed database write
never falls back to the temporary folder.

**Why not the obvious thing.** Copying whatever local file happened to be
present would take a race with a previous deployment; ignoring it could
silently erase active schedules or live-send consent. Inventing a second timer
settings table also duplicates locking and schema. Fail-closed migration is
safer for existing approved automation.

**What it costs.** An existing hosted installation that has a nonempty or
empty timer JSON file requires explicit operator resolution, and only new
hosted installs or migrated ones can use this storage without intervention.
The timer configuration can survive deployments, but a timer **runner** is
still not independently supervised and multiple app instances must not be
assumed safe to run the same job. This is not proof of external email sends,
restore or durable media/outbox files.

**Revisit when.** A verified, owner-approved timer import/skip tool and
multi-instance supervised scheduler exist. See S-06.03.06 and S-06.02.40.

### DD-41 — Manual archive-first timer import, no consent carryover · 2026-11-02

**The call.** An explicit `offsetx-db import-timers` CLI action uses the
existing hosted-document transaction to accept or skip old timer settings.
Its operator-supplied archive must sit outside the app data directory, use
private permissions, keep the original bytes, and be fully fsynced before
removing source names. An exclusive workspace lease prevents simultaneous
operations. Imports disable all automated email/content scheduling and Gmail
send consent until the owner reauthorises it; skip preserves hosted settings.
Conflicting hosted values cause a refusal, not a guess or overwrite.

**Why.** Auto-import at app startup would recreate live unattended actions
without checking consent, and just discarding local files would lose approved
schedules. A nonexclusive lease was rejected because two processes could
change settings between backup and database commit.

**Cost.** Install owners must stop web and worker processes, retain a durable
private archive and explicitly choose import/skip. There is no transparent
hands-free migration, and pending schedules do not resume on import.
A free Render filesystem is *not* a safe archive destination.

**Revisit.** When S-06.03.06 provides verified shared-config migrations for
all stores and S-06.02.40 delivers supervised, idempotent worker execution.

### DD-42 — Hosted AI context is explicit; old local context blocks cutover · 2026-11-02

**The call.** The context layer's target is injected explicitly by the FastAPI
application. Local standalone installs keep their existing SQLite tables;
hosted installs persist AI task progress and template counters in versioned
PostgreSQL tables. Never infer a target from a process environment in the
context class itself, because unit tests and local tools must not write to a
live owner database.

**Why not auto-copy.** Local AI context may include sensitive owner decisions,
client strategies and template copy. Automatically creating a new empty
hosted database would silently erase that history; automatically copying it
at app startup could mix installs and write data without consent. A detected
legacy local file fails startup until an explicit, reconciled operator migration
exists.

**Cost.** A previously local install cannot enable hosted mode when its old
context DB still exists. The owner must preserve the file and follow a
verified migration process when developed; this is a deliberate deployment
blocker, not hidden data loss. Other unhosted stores and external backup still
prevent full production readiness.

**Revisit.** When S-06.03.06's explicit AI context migration and isolated
PostgreSQL restore tests are accepted.

### DD-43 — Explicit AI context history cutover, never silent merge · 2026-11-02

**The call.** The install owner chooses `offsetx-db import-context --yes` or
`--skip` with a separate private, persistent archive location. The importer
uses SQLite's online backup API to include WAL data, checks both AI context
tables, and runs any destination writes as one database transaction. An
unrelated hosted context is never merged or overwritten. Identical rows may
be recognised on retry after an interrupted cleanup.

**Why not automatic conversion.** Task decisions and template performance
history can belong to different workspaces. Auto-import at startup could
combine independent installations without the owner's permission. Simply
deleting the source would silently lose customer strategy and decisions.

**Cost.** The owner must stop web/worker processes, supply truly durable
private backup storage, and approve import or skip. The importer deliberately
refuses unknown schemas and existing conflicting data rather than guessing.
This does not address other unhosted stores or replace independent backup and
restore proof.

**Revisit.** When all S-06.03.06 stores are in verified durable homes and the
per-install/shared-database decision in S-06.03.07 is agreed.


### DD-133 — Duplicate candidates are read-only and preview-limited · 2026-11-02

**The call.** The CRM duplicate-review endpoint groups existing nonempty emails with `lower(trim(email))` and returns only three allowlisted identities per group. It never auto-merges records or accepts any correction command; this uses the same protected CRM API boundary and data already stored. No new index/schema was installed until a query-plan and scale test proves one is needed.

**Why not automatic deduplication.** Shared addresses and legacy whitespace differences are not proof that two contacts represent the same person. Merging can destroy campaign history, permissions, evidence and audit trails. A broad raw-contact payload also exposes more information than a reviewer needs.

**Cost.** Operators have to use existing contact-edit tools, group preview can omit extra records, and `lower(trim(email))` grouping may need a dedicated expression index for very large imports. Performance and tenant isolation remain release gates.

**Revisit.** After Q-27 establishes CRM tenancy and a measured PostgreSQL query plan justifies new indexing or a carefully audited human-approved merge flow.


### DD-134 — Do not infer numeric evidence from punctuation boundaries · 2026-11-03

**The call.** For source-backed observed numbers, match the whole literal number with its sign, fraction, separator, currency prefix and attached percentage. A quote containing `-42`, `42.7`, `42,000`, `42%` or `$42` is not evidence for the bare `42`. Sentence-ending punctuation and commas followed by words remain valid separators. This uses the one existing source-verification gate, never a post-processing redactor.

**Why not a full locale/units parser.** A typed numeric value and unit schema is not yet available in `Finding`; guessing whether a comma is a thousands mark, or which unit was implied, can create false confidence. Lexical equality is conservative: a different human-written representation may be refused rather than silently converted. The agent must show unsupported or incomplete, never invent a conversion.

**Cost.** More legitimate claims may require the model to quote the exact source representation; spaced units like `42 kg` are not semantically validated without a declared typed field, and derived arithmetic remains labelled derived rather than verified as a calculation. A separate typed-quantity contract would be required for stronger numeric proof. The previous S-11.02.01–04 source provenance and nonnumeric matching remain unchanged.

**Revisit.** When typed locale, units, numeric tolerance and derived-calculation semantics are defined with their own adversarial tests and explicit owner approval.

**DD-134 follow-on:** Exact presentation matching includes normalising mathematical minus, Arabic decimal/grouping and percent symbols and refusing ambiguous three-digit groups split by Unicode spaces. This still does not parse arbitrary locale or infer units/calculations. These are safe representation checks, not a broad unit-conversion policy.
