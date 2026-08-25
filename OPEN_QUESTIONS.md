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

### Q-05 — Does a competitor analysis reproduce structure only, or media? *(blocks S-05.01.03)*

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
