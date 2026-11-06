# Open questions

Ambiguities that could change the shape of a story. **No business rule has been
invented to fill any of these.** Each carries the options, a recommended
default, and what it costs if the default turns out to be wrong.

An item on the board may not enter `READY` while an **open** question is filed
against it. `scripts/verify_board.py` enforces that. A question marked
`**Status:** answered` no longer blocks — the decision is recorded below it, so
the reasoning survives even though the block is lifted.

---

### Q-01 — Where does the master key come from? *(blocks S-03.02.02)*

**Status:** answered · **Decision:** Option 3 — OS keychain, with a passphrase fallback where no keychain exists. · **Decided by:** Owner, 2026-08-25, taking the recommended default.

**Ambiguity.** The vault needs a key. Today `ai/workspace.py` keeps a Fernet key
in a file beside the data it protects, which is fine for API keys and not fine
for social sessions — anyone who can read the directory has both halves.

**Options.**
1. **OS keychain** (macOS Keychain / Windows DPAPI / libsecret). Nothing to
   remember; unlocked when the owner is logged in.
2. **Passphrase, entered once per session.** Strongest. Costs a prompt at every
   start, and an unattended routine cannot start after a reboot.
3. **Keychain, with a passphrase fallback** where no keychain exists.

**Recommended default: 3.** It matches how the product actually runs — a desktop
machine that someone is logged into — and degrades to something real on a
headless box.

**Blast radius if wrong.** Choosing 2 and discovering routines must survive a
reboot means either weakening the model or losing unattended operation. Choosing
1 on Linux means depending on a service that is often absent. Reversible, but it
touches every stored session.

---

### Q-02 — What is on the browser box's domain allow-list, and who edits it? *(blocks S-03.01.01)*

**Status:** answered · **Decision:** Option 3 — deny by default for unattended runs; allow-with-policy for attended ones. · **Decided by:** Owner, 2026-08-25, taking the recommended default.

**Ambiguity.** "Network, but restricted" needs a list. A list too tight makes the
agent useless on the open web; too loose and the box's network boundary means
nothing.

**Options.**
1. **Deny by default**, only declared domains reachable.
2. **Allow by default**, with a deny list for the machine's own network.
3. **Deny by default for unattended runs, allow-with-policy for attended ones.**

**Recommended default: 3.** The threat is an unattended agent following a link
somewhere unexpected. A person watching is a control in itself.

**Blast radius if wrong.** Option 1 breaks general research and would be
discovered as "the agent cannot open anything". Option 2 makes the box's network
rule decorative. Option 3's cost is two code paths.

---

### Q-03 — Which platform does the browser log into first? *(blocks S-03.02.01)*

**Status:** answered · **Decision:** LinkedIn first. It is the platform with no usable CRM API, so the browser is necessary there rather than merely convenient. · **Decided by:** Owner, 2026-08-25, taking the recommended default.

**Ambiguity.** Six platforms were named. Each has a different login shape (2FA,
passkeys, device checks) and building all six at once means finishing none.

**Options.** LinkedIn first (highest CRM value, hardest device checks); YouTube
first (an API already exists, so the browser is only for gaps); Instagram first
(highest content value, strictest automation stance).

**Recommended default: LinkedIn.** It is the one with no usable API for the CRM
job, so it is where the browser is not merely convenient but necessary.

**Blast radius if wrong.** Low. Session capture is the same mechanism per
platform; the order only changes which one is proven first.

---

### Q-04 — What is "the owner" when a team uses this? *(blocks S-06.01.02)*

**Ambiguity.** The permission model says the owner approves. With a team, is
approval per person, per workspace, or is there an admin who sets rules others
cannot loosen?

**Options.**
1. Every user is their own owner in their own workspace.
2. A workspace admin sets ceilings; members work under them.
3. Per-person, with an org policy that can only tighten.

**Recommended default: 1 for now, designed so 3 is additive.** There is no
evidence yet of how this team actually divides responsibility, and inventing a
hierarchy is exactly the kind of business rule this process forbids me to invent.

**Blast radius if wrong.** Moderate. If an admin ceiling is needed later, adding
it means a migration and a permission re-evaluation, not a redesign.

---

### Q-05 — Does a competitor analysis reproduce structure only, or media? *(formerly blocked S-05.01.03)*

**Status:** answered · **Decision:** structure only; no copied frames, audio, captions, transcripts or source media. · **Basis:** the existing S-05.01.03 backlog contract already says “recipe reference and parameters, never copied media”; refinement makes that existing rule machine-testable rather than inventing a new business rule.

**Ambiguity.** "Extract the post and recreate it" has two readings. Reproducing
*structure* — pacing, hook shape, look, length — is ordinary competitive
practice. Reproducing *media* is copyright infringement.

**Options.**
1. Structure only: a recipe id and parameters. No frames, no audio, no copy.
2. Structure plus a stored reference copy for side-by-side comparison.
3. Media reuse.

**Recommended default: 1.** Option 3 is not something I will build. Option 2 is
defensible but the stored copy is a liability with a retention policy attached,
and no one has asked for the comparison view.

**Blast radius if wrong.** If the owner wanted side-by-side review, that is
option 2 and it is additive.

---

### Q-06 — Which model provider is assumed present? *(affects S-02.02.01)*

**Status:** answered · **Decision:** Require a Tier A/B planning model and fail closed before the run starts if none is connected. No lower-trust planner is used as a fallback. · **Decided by:** Owner, 2026-09-05, proceeding with S-02.02.01 under the production-grade default and the documented recommended safe option.

**Ambiguity.** The agent loop needs a model. Today no provider is connected in
this workspace, and the tier rules mean a run's capability depends on which one is.

**Options.** Require a tier A/B provider for planning; allow any permitted
provider and degrade; refuse to start without one.

**Recommended default: refuse to start, naming what to connect.** The existing
`ai/modes.py` already requires tier A or B for orchestration, and planning a
browser run is a wider exposure than that.

**Blast radius if wrong.** Low, and it is the safe direction: the failure is a
clear message rather than a weak model driving a logged-in session.

---

### Q-07 — What happens to a trace after the run ends? *(affects S-02.01.05, S-06.02.04)*

**Scope note:** this remains unanswered for automatic retention. It does not block S-06.02.04's explicit subject-access/deletion operation: that story will delete data only after an explicit confirmed privacy request. No default retention duration is being invented.

**Ambiguity.** A trace holds screenshots of whatever the agent was looking at.
On a logged-in session that is mail, a CRM, possibly a customer's personal data.
Nobody has said how long it is kept.

**Options.** Keep forever; keep N days then delete; keep the text and drop the
screenshots after N days.

**Recommended default: keep text, drop screenshots after 30 days, all
configurable.** The screenshots are the sensitive half and the least useful
later; the text is what makes a run resumable and auditable.

**Blast radius if wrong.** If an audit needs a screenshot from month four, it is
gone. If retention is too long, a laptop holds months of screenshots of a CRM.

---

*(Q-20 to Q-24 were raised on 2026-09-22 while opening `E-12`. Questions about
a tunable number name the constant, not a story: the number can change without
the story's shape changing, so it must not hold the story out of `READY`.)*

### Q-20 — Where does a demo video live before there is money for storage? *(affects F-12.03)*

**Status:** answered · **Decision:** the owner's personal Google Drive, with the
file encrypted before upload; move to Azure or AWS once there is runway. ·
**Decided by:** Owner, 2026-09-22.

**What the decision means for the design, written down now so Phase 3 does not
rediscover it.**

1. **Drive stores the bytes; it cannot be the player.** Drive has no
   per-recipient links, no watch-time events and a download quota that throttles
   popular files ("download quota exceeded"). So the email links to a small page
   off_CRM serves, one per recipient, and that page fetches the file. The page is
   also where watch time is measured.
2. **Encrypted at rest means decrypted in the viewer's browser.** The page
   carries the key in the URL fragment (`#k=…`), which browsers never send to a
   server — so neither Drive nor off_CRM's logs ever hold key and file together.
3. **Moving to Azure or AWS later is a storage swap, not a redesign,** as long as
   the page and the key scheme stay the same. Build the storage behind one
   interface in Phase 3 so the swap is one class.

**Blast radius.** Drive's quotas are per file and change without notice; a
campaign that goes well is exactly the one that hits them. Watch the first real
send.

---

### Q-21 — Does off_CRM create social accounts itself? *(affects the out-of-scope table)*

**Status:** open.

**What the owner said (2026-09-22).** Build it, leave the choice to each user,
and build it last. Some organisations want many accounts for a short burst of
visibility; others hand over the real accounts they already own on Instagram,
LinkedIn, Reddit, TikTok, Facebook and YouTube.

**Why it is still open.** It contradicts a recorded decision.
`PRODUCT_BACKLOG.md` §4 lists *"Buying followers, engagement pods, sock
puppets"* as out of scope: *"Fraud against the platform and against the owner's
own metrics."* A recorded decision is reversed deliberately, by a new entry,
not by a sentence in a chat.

**The two halves are different things.**
- **Real accounts handed over** is already built: sign in once inside the box
  (`S-03.02.01`) and several accounts per platform, each with its own budget
  (`S-03.02.04`). Nothing more is needed for that half.
- **Accounts created in bulk for a burst of visibility** is what the
  out-of-scope row forbids.

**Facts the owner should decide with.** Every one of those platforms forbids
creating accounts by automation and treats coordinated fake accounts as
inauthentic behaviour; the usual outcome is a ban, and it tends to take
connected assets with it. In the US, the FTC's rule on reviews and
testimonials, in force since 21 October 2024, prohibits selling, distributing,
buying or procuring fake indicators of social media influence for a commercial
purpose — followers, views, likes and the like generated by bots or by accounts
not associated with a real person (16 CFR 465.8,
<https://www.ecfr.gov/current/title-16/chapter-I/subchapter-D/part-465/section-465.8>).

**Options.** 1. Keep it out of scope. 2. Reverse the row and plan it as the
final milestone.

**Recommended default: 1.** The legitimate half exists today.

**Blast radius if wrong.** Choosing 2 puts a feature in the product whose normal
use breaks the platforms' terms and, in the US, may be unlawful to sell. Choosing
1 costs the burst-visibility use case.

---

### Q-22 — How many cold emails may one mailbox send a day? *(affects `gtm/strategy.py` `COLD_EMAILS_PER_IDENTITY_PER_DAY`)*

**Status:** open.

**Ambiguity.** The strategy brain must not plan more email than the connected
mailboxes can send without damaging their reputation. Warm-up scheduling is not
built (`EMAIL_DELIVERY.md` §236) and the health threshold is per campaign rather
than per mailbox (§237), so the ceiling has to come from a number.

**Options.** 20 (a new domain); 30; 50 (a warmed mailbox, the top of the range
cold-email operators commonly quote).

**Recommended default: 30.** Lowering later loses nothing; a plan that pushes a
new domain at 50 on day one can burn it. The owner can override the number per
plan on the Strategy screen.

**Blast radius if wrong.** Too high: a new sending domain is throttled or
blocked. Too low: a plan under-uses capacity and its reply goal looks harder
than it is.

---

### Q-23 — What reply rate does a plan assume before anything is measured? *(affects `gtm/strategy.py` `ASSUMED_REPLY_RATE`)*

**Status:** open.

**Ambiguity.** A reply goal needs an assumed rate before the first send, or the
feasibility arithmetic has nothing to multiply.

**Options.** 1%, 3.4% (the published 2026 average for plain-text cold email),
5%.

**Recommended default: 3.4%, clearly labelled as an industry average.** It is
replaced by the measured rate as soon as 20 people have been contacted — that
replacement is what "the brain learns" means here — and the owner can override
it per plan.

**Blast radius if wrong.** A number that is too high makes a plan look feasible
when it is not, for the first review cycle only.

---

### Q-24 — Should cold outreach rotate across several secondary domains? *(affects E-07)*

**Status:** open.

**Ambiguity.** The owner asked on 2026-09-22 whether off_CRM already sends
thousands a day "like Mailchimp, by changing DNS addresses". It does not.
Campaigns are pinned to one sending identity; there is no rotation.

**Two facts that shape the answer.** Mailchimp does not avoid spam by rotating
domains: it is a permission platform, and its terms forbid sending to purchased,
rented or scraped lists — which is what an Apollo list is. Separately,
cold-email tools do spread volume over several secondary domains and mailboxes,
but that only works with warm-up and per-mailbox reputation tracking, and
mailbox providers now look for exactly that pattern.

**Options.** 1. No rotation until warm-up scheduling and identity-wide
reputation exist. 2. Rotation now.

**Recommended default: 1.** Rotation without warm-up and without a per-domain
view of reputation spreads the damage instead of avoiding it — and the
per-campaign health threshold (§237) cannot see a domain burning across
campaigns.

**Blast radius if wrong.** Rotating too early burns several domains instead of
one. Waiting caps daily volume at one identity's safe number for longer.

### Q-25 — May the strategy brain's own numbers reach a model? *(affects `ai/payload.py` shape abstraction)*

**Status:** open. Raised 2026-09-23 by the cold review of `E-12`.

**Ambiguity.** Below the `full` policy the payload builder widens business
numbers before anything leaves: "20 replies within 30 days" arrives as "some
engagement within 30 days", and "5 replies from 150 contacted is 3.3%" as "a
share". It is on by default and no screen turns it off. So the plan, review and
revise models never see the goal size, the capacity or the measured rate. A
forbidden claim with a number in it ("100% accuracy") also arrives widened,
though the code still removes it from anything a model writes.

**Why the brain still works.** All of its arithmetic — volumes, the Wilson
verdict, what is left of the goal — is code. A model only chooses among the
remedies each finding permits, and the finding codes and remedy names survive
the filter; `test_what_the_brain_needs_survives_the_shape_filter` holds that.
What the model loses is the *size* of the problem, which makes its sentences
vaguer, not its choices wrong.

**Options.** 1. Keep hiding the numbers (today). 2. Let code-written
`instructions` for `gtm_*` tasks through unwidened — they are the owner's own
totals, not a person's data. That is a change to `ai/payload.py`, which the GTM
work orders may not touch, so it needs your yes.

**Recommended default: 1** until a model's remedies are measured against the
rules' — then decide on evidence. Shape abstraction exists to keep the business
strategy from providers, and these numbers are exactly that strategy.

**Blast radius if wrong.** Keeping them hidden makes model-written reasons
vaguer. Letting them through tells every tier A and B provider your volumes and
reply rates.

---

### Q-26 — Should `main` on Render keep its data across restarts? *(affects `render.yaml`)*

**Status:** answered 2026-09-25 — a fourth option: stay on Render's free plan
and keep the data in a free hosted PostgreSQL. Design:
`docs/architecture/HOSTED_STORAGE.md`; feature `F-06.03`; decision `DD-66`.
`S-06.03.02` (keys, settings, logins) is DONE; with `S-06.03.03` the CRM
follows the same database (built 2026-10-03, in review). Asked 2026-10-03
whether to wait the design's week of phase-1 use before moving the CRM, the
owner said not to wait.
Added by the owner 2026-10-02: Render's PostgreSQL is an option as well as
Neon's, and the system must be able to move to a PostgreSQL on AWS or Azure
later (`DD-66` amended, `DD-70`). Render's free database is deleted after 30
days plus 14 days' grace, so it is a trial, not a home.
Raised 2026-09-23 at the branch consolidation (`S-06.02.19`).

**Ambiguity.** Both Render services — `off-crm-demo` on `main` and
`off-crm-develop` on `develop` — are on the free plan. On the free plan the
filesystem is wiped on every restart and every deploy, so anything typed into
either is gone the next time it restarts. Render attaches a persistent disk only
to a paid service. The code for a production-safe setup is ready
(`S-06.02.21`): with `OFFSETX_PRODUCTION=1` and a mounted disk it keeps
everything under one root, backs all of it up, and refuses to start on `/tmp`.

**Options.** 1. Keep both free: fine while only testing, and nothing real may
be kept in either. 2. Move `main` to a paid plan with a disk (the block is in
`docs/BRANCHING.md`, "Making main keep its data"); keep `develop` free.
3. Pay for both.

**Recommended default: 1 now, 2 before the first real customer record.**
Nothing was changed without your yes, because it costs money every month.
`develop` should stay free: it is where unfinished work lands.

**Blast radius if wrong.** Staying on 1 after real use starts loses every
contact and campaign at the next deploy — and every push to `main` is a deploy.
Choosing 2 early costs a monthly fee for a demo.

### Q-27 — Should campaigns, contacts and drafts belong to a workspace? *(affects every CRM table)*

**Status:** answered · **Decision:** owner chose Option 2 on 2026-11-06: workspace-owned CRM data, isolated customers. Existing-record ownership requires an explicit migration/assignment; do not guess or modify customer data automatically. Raised 2026-09-23 by the cold review of `develop` (`D-135`).

**Ambiguity.** Workspaces have their own logins, provider keys, browser
sessions, AI settings and products (`S-06.01.01`). The CRM itself does not:
every login sees and changes the same campaigns, contacts, drafts and
templates. That is fine if every login is one team working one book of
business. It is not, if a workspace is a different client: a draft written from
one workspace's private product can then be read from any other login, and a
workspace can link a campaign nobody has linked yet. The draft writer no longer
lets another workspace *create* such a draft (`D-125`); drafts already written
stay readable.

**Options.** 1. Keep one shared CRM, and say so in the product: workspaces
separate credentials, not customers. 2. Give every CRM row a workspace, so each
login sees only its own. 3. Keep one CRM, but make products install-wide too.

**Recommended default: 1 for now, 2 before a second, unrelated customer shares
an install.** Option 2 changes every CRM table and query, and existing rows
need an owner, so it is a data migration — the kind that is cheap before real
data and expensive after. Nothing was changed until you choose.

**Blast radius if wrong.** Staying on 1 with unrelated customers on one install
shows each one's contacts and product text to the other. Choosing 2 when
everyone is one team adds a workspace filter to every screen for nothing.

### Q-28 — Should drafts personalise through Connectors, or get their provider-profile screen back? *(affects Drafts and the second model path)*

**Status:** answered · **Decision:** owner chose Option 1 on 2026-11-06: Drafts use Connectors with existing trust tiers, scanner and egress log. Preserve/migrate legacy profiles explicitly; no silent credential conversion. Raised 2026-09-25 while fixing the second review's findings (`D-173`).

**Ambiguity.** The Drafts screen writes with a model only through *provider
profiles* — a second, older path to a model with its own keys, priorities and
data policies. No screen has added a profile since the AI providers moved to
Connectors (`5e03c6c`): Settings still holds the code to save, test and remove
one, but no form, and the Drafts screen tells you to use it. The keys you type
in Connectors, with their trust tiers, scanner and egress log, do not reach
Drafts at all.

**Options.** 1. Drafts write through Connectors, like the AI screen: one set of
keys, the trust tiers and the egress log apply, and profiles are retired once
their drafts are moved. 2. Bring the profile form back in Settings, so the two
paths stay separate. 3. Leave it; drafts stay template-only unless a profile is
added through the API.

**Recommended default: 1.** It is the path every other model call already
takes, and it is the one the trust work of 2026-09-25 protects. Option 2 keeps
two places to paste a key and two sets of rules for what leaves. Nothing was
changed until you choose; `S-06.02.35` is filed for either answer.

**Blast radius if wrong.** Choosing 1 means profile-only settings — round-robin
and parallel strategies — need a Connectors equivalent or are dropped. Choosing
2 keeps a second egress path that the tiers do not govern.

### Q-29 — Which owner-controlled destination and key policy protect hosted CRM backups? *(blocks S-06.03.04)*

**Status:** answered · **Decision:** owner approved Option 1 on 2026-11-05: independent private S3-compatible object storage with restricted backup credentials and a separately managed AES-256-GCM backup key. The physical bucket, credentials, retention policy, scheduler and restore proof are still unprovided release dependencies. Raised 2026-10-13. The choice in Q-20 to use encrypted Google Drive for demo *video* does not grant access or storage permission for CRM/customer database exports.

**Ambiguity.** A real nightly backup must survive deletion of the hosted database and Render's ephemeral filesystem. Neither the location, its credentials nor custody of the separate decryption key is authorised yet.

**Options.** 1. Owner-supplied private S3-compatible object bucket with a restricted write/read identity and explicit retention policy. 2. Owner-supplied private Google Drive folder through an approved OAuth integration, retaining separately managed encryption keys. 3. Another durable independent store with a tested uploader and restore. No destination means no claim of scheduled backups.

**Recommended default: 1**, once an appropriately secured bucket is available, because it supports atomic object upload, independent recovery, access controls and lifecycle rules without sending a live database into the app's temporary disk. The provider/cost is still an owner choice.

**Blast radius if wrong.** Choosing a source-adjacent or temporary destination creates a backup that disappears with the primary data. Choosing the wrong retention period can permanently lose restore points or retain sensitive customer data beyond agreement.

### Q-30 — Who chooses which companion procedure enters a run? *(blocks S-04.01.02)*

**Status:** answered · **Decision:** owner approved Option 1 on 2026-11-05: only explicit owner-authorised procedure IDs select bounded text for a run; no page or model auto-selection. Dependency S-04.01.01 and live end-to-end evidence remain open. Raised 2026-10-13.

**Ambiguity.** A procedure can be selected explicitly by an owner/workflow or inferred by a model from the goal/page. The distinction changes prompt content, permissions and prompt-injection exposure.

**Options.** 1. Only an explicit workspace-authorised selection on the companion's run request chooses bounded skills; no ambient page or model may activate more. 2. Auto-suggest by deterministic tags, but the owner must approve the actual set before the run. 3. Model-selected relevance, with a separate trusted authorisation step before any playbook text is added.

**Recommended default: 1.** It is deterministic, cheap in tokens, and cannot be tricked into loading extra instructions by untrusted page content.

**Blast radius if wrong.** Implicit selection can leak another workspace's procedures or raise prompt/token costs unexpectedly. Explicit selection requires more UI/workflow setup but has a testable security boundary.


### 2026-11-06 — S-06.03.07 install/database ownership decision

Owner selected one hosted database per application install. A second independent install must be refused rather than sharing migration choices or customer state. Persistent install identity and explicit recovery/move procedure are required; losing an ephemeral local directory must not silently create a different owner or transfer a claim. No customer database has been changed by recording this decision.
