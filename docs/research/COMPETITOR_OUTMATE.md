# Competitive teardown — Outmate

**Status: point-in-time research, not a working record.** Written 2026-09-15.
Nothing here is maintained. Company facts decay fast; re-check before acting on
any number. `BOARD.md` is the truth about this repo, never this file.

Live page: <https://claude.ai/artifact/9JeRPPYEmAfk2Ace25ekE6>
Series: [`COMPETITORS_STRAWBERRY_CRUX.md`](COMPETITORS_STRAWBERRY_CRUX.md) ·
[`COPY_OR_REFUSE.md`](COPY_OR_REFUSE.md) · Floqer brief (artifact only).

---

## Method

31 pages of `outmate.ai` fetched 2026-09-15 with Scrapling's `Selector` over
`requests` — one request per second, `robots.txt` checked before each fetch,
boilerplate stripped by cross-page line frequency. The same pattern
`discovery.py` uses. The privacy policy was fetched separately. Infrastructure
was confirmed by DNS resolution of `api.outmate.ai`. 299,149 characters of page
text in total. No login, no paid data, nothing behind a wall.

---

## Verdict first

Outmate is a website-visitor-identification tool with a GTM automation layer on
top: identify anonymous B2B visitors, enrich them, score them against an ICP,
draft outbound that sends from the rep's real Gmail. Eight modules, four price
tiers, a free plan, nine competitor comparison pages.

**This is the closest competitor to off_CRM found so far, and the most
beatable.** Same buyer, same shape, same Apollo dependency, a team probably
smaller than you assume, and no funding anyone can find. Floqer was a larger
company in the category; Outmate is a company at roughly off_CRM's stage that
chose to ship instead of harden.

The counterweight is blunt: **they shipped.** Pricing page, free tier, working
pixel, signup. off_CRM has 1,520 passing tests and no buyer. In the market that
is not a close contest.

---

## What it is

| | |
|---|---|
| Modules | Website Identification, B2B Database, AI CRM, GTM Co-Pilot, Signals, Workflow Automation, Agents, Analytics |
| Named agents | 5 — of which **2 are live**, both manual-trigger |
| Competitor pages | 9 — RB2B (primary), Leadfeeder, Leadinfo, Warmly, Common Room, Factors, Happier Leads, Lead Forensics, Bullseye |
| Named humans | 0 |
| Terms effective | 2026-06-18 |
| Support page updated | 2026-07-28 |

### Pricing

| Plan | Price | Credits/mo | Seats | The tell |
|---|---|---|---|---|
| Free | $0 | 500 | 1 | Company-level ID only, 200 identifications, HubSpot read-only. A real free tier, not a trial. |
| Growth | $99 | 5,000 | 3 | Person-level ID unlocks here at 5 credits each. "Series A–B". |
| Scale | $149 | 15,000 | 8 | Where the actual product lives: workflow canvas, AI SDR Autopilot, Co-Pilot brief. "Series B–C". |
| Enterprise | from $299 | 50,000+ | unlimited | "99.9% SLA guarantee", "<1h support" — from a company with no named legal entity. |

$99 → $149 is a 50% price jump for 3× credits and the entire agentic product.
The ceiling before "talk to sales" is $149, which is low for a platform claiming
to replace five tools. Compare Floqer at $49–999 and Strawberry at $20–250.

---

## The architecture, reconstructed from their own privacy policy

Section 7 of the Outmate privacy policy is titled "Third-party enrichment
providers (subprocessors)". The law requires it. It is also, accidentally, a
complete bill of materials.

| Layer | What they use | What it means |
|---|---|---|
| Cloud | Microsoft Azure | `api.outmate.ai` → `outmate-api.greenbeach-….eastus.azurecontainerapps.io`. Azure Container Apps, East US, one region. **Confirmed by DNS**, not just the policy. |
| Database | Supabase | Managed Postgres. No self-hosted data layer. |
| Cache & queue | Upstash | Managed Redis. Azure + Supabase + Upstash is the modern small-team stack — fast to build, nothing operated in-house. |
| LLM | **OpenRouter → Anthropic Claude** | "Routed *exclusively* through OpenRouter." One router, one model family. |
| IP intelligence | ip-api, IPinfo, MaxMind GeoIP2 | Plus reverse DNS and ASN. The commodity way to do company-level visitor ID; licensable for a few hundred dollars a month. |
| Contact data | enrich.so, Explorium, ContactOut, **Apollo**, Hunter, BetterContact | Six providers in a waterfall. **The "300M+ contact database" is resold, not theirs.** Note Apollo — the same provider off_CRM uses. |
| Email verification | ZeroBounce | Named on the database page. |
| Web research | Serper, Tavily | Search APIs, not a crawler. Their "research" is Google results via a reseller. No browser, no crawl frontier. |
| Person-level identity | People Data Labs **or** LiveRamp | "Where expressly enabled." The legally spiciest component, and the only part that is genuinely hard to get. |
| Sending | User's own Gmail / Outlook via OAuth | Google API Limited Use compliance claimed. No sending infrastructure of their own, deliberately. |

**Eleven named third parties touch a visitor's personal data before an email is
written.** off_CRM's equivalent path has one gate — `ai/broker.py` — and writes
the exact payload to an egress log.

### The honest read on the stack

It is a *good* stack. Azure Container Apps + Supabase + Upstash + OpenRouter is
how you ship eight modules fast with one to three engineers. Nothing here is
incompetent; it is the correct set of choices for speed.

But the defensibility is not in the data and not in the infrastructure.
Everything they buy, anyone can buy. The moat is the workflow canvas and
whatever they learn from customers. At this stage that is thin.

---

## Nine places the site contradicts itself

Not hunted for. These fall out of reading 31 pages in one sitting, which no
prospect ever does and every diligence process does.

| The claim | Where it is contradicted |
|---|---|
| "Fully autonomous", "sends them on your behalf… fully autonomous", "autonomous GTM agents" | `/agents`: "**Nothing is sent on an agent's own authority.**" "Outbound-facing drafts wait for your review before anything sends." |
| **500M+** contact database (`/run-ai-powered-outbound`) | **300M+** on the nav, homepage, `/b2b-database` and `/outmate-vs-everyone` |
| "Five agents. Five jobs." (`/agents`) | "NO-CODE · **52 AI AGENTS**" (`/workflow-automation`) |
| **97%** visitor match accuracy (homepage) | Their own RB2B table: company identification rate **30–40%**, person "varies by source". And `/website-visitor-identification`: "**40–65%** match". |
| **4,000+** signals | Their own itemised library: 12 website + 45 competitor + 18 funding + 280+ hiring ≈ **355** |
| Reply classifier: **7 types** | Pricing table: "**6-intent** reply classifier", Enterprise only |
| Resolution **<2 seconds** | Also theirs: **118ms** average. A 17× spread on one metric. |
| +312% pipeline · 11.6× ROI · 97% accuracy | Footnote directly beneath: "**Illustrative figures, not a guarantee of results.**" Not customer outcomes. |
| "Integrations" in the global site footer | `/integrations` returns **404**. So does `/outmate-labs/workflows`, which search engines have indexed. |

### What this pattern means, and what it does not

It is **not** evidence of dishonesty. It is the signature of a very small team
shipping pages fast, where marketing copy on one page was written weeks apart
from a feature table on another and nobody owns consistency.

What it *is* evidence of: **no enterprise diligence has been run on them yet.**
The first serious procurement review finds all nine, and the 97%-versus-30–40%
gap is the kind that ends a deal.

---

## What is actually live

To their credit, the agents page carries the line *"Status reflects what's true
today, not a roadmap."* Then it lists the statuses.

| Agent | Status, their words | What it does |
|---|---|---|
| Competitive Battlecard | **Live**, manual trigger | Keeps an objection-handling doc current. The one agent allowed to write without review — because its output never leaves Outmate. |
| Buying Committee | **Live**, manual trigger | Infers economic buyer, champion, influencer, blocker at an account. |
| Deal Risk Coach | **Coming soon** | Scores a stalling deal, drafts a next action. "You review it and send." |
| Reply Intelligence | **Coming soon** | Classifies Gmail replies. Their own dashboard mock reads "CONNECTING GMAIL DATA SOURCE". |
| Product Signal (PLG) | **Not shipped** | "Gated behind legal and compliance sign-off before it goes live." |

Two of five agents are live and both need a human to press a button. Their RB2B
comparison marks their own AI email personalisation, multi-touch sequences and
A/B testing as *Beta*, and send-time optimisation as *Soon*.

The word doing the heaviest lifting on that website is "autonomous", and it is
the word least supported by the pages underneath it.

---

## Head to head with off_CRM

| Dimension | Outmate | off_CRM | Who wins |
|---|---|---|---|
| Visitor identification | Pixel, IP resolution, identity co-op, 30–65% match | **Nothing** | **Outmate, outright.** A real gap, and the cheapest one to close. |
| Contact data | Six providers, resold | Apollo + open web, hard credit cap | Outmate on breadth, off_CRM on cost control. Both rent the same kind of data. |
| LLM governance | "Routed exclusively through OpenRouter" to Claude | Trust tiers on jurisdiction *and* retention, allowlisted payload starting empty, one egress gate, exact payload logged | **off_CRM, not close.** |
| Sending | Rep's own Gmail via OAuth, no warmup domain | SPF/DKIM/DMARC preflight, SES lanes, durable jobs, signed unsubscribe, feedback auto-pause | Split — see below. |
| Workflow surface | No-code canvas, plain-English build | Run loop with budgets and a trace, no canvas | Outmate on usability, off_CRM on auditability. |
| Agent discipline | Draft, human reviews, audit trail, one job per agent | Bandit allocates inside owner-approved variants only | **Tie — and they arrived at your rule independently.** |
| Web research | Serper and Tavily search APIs | Scrapling + Crawl4AI, robots.txt, SSRF guards, plus a CDP browser agent | **off_CRM, clearly.** They buy search results; you drive a browser. |
| Content production | Email copy only | 13,000+ lines of video engine, imagery, captions, hand-written WebM muxer | off_CRM, and still unpriced. |
| Shipped and sellable | Free tier, pricing, pixel, signup, 9 comparison pages | 1,520 tests, no buyer | **Outmate, and this is the one that counts.** |

### The governance gap, stated precisely

Outmate's entire published LLM data-protection position is one sentence:
processing is *routed exclusively through OpenRouter, which in turn provides
access to Anthropic Claude models*.

OpenRouter is a router, not a model provider. A prospect's name, title,
employer, the pages they viewed and their inferred buying stage pass through an
additional US intermediary before reaching the model that writes about them.
Whether that is acceptable depends on OpenRouter's retention terms and the
customer's jurisdiction — and the customer cannot see either from Outmate's
documentation.

**This is the first time the egress wall has a concrete adversary.** Three briefs
said it had no buyer; that is still true. But "we can show you the exact payload
that left, and we chose the provider on jurisdiction and retention" is now a
sentence you can say beside a competitor who cannot say anything comparable.
That is not a market — it is a wedge into one deal type: an EU or India buyer
with a privacy function.

### The sending split

Outmate's "send from the rep's real Gmail, no warmup domain" is their sharpest
product idea and their largest unpriced risk. Sharp, because deliverability is
the real bottleneck in AI outbound and a real inbox with real history beats any
warmed pool. Risky, because pushing cold volume through a primary Google
Workspace mailbox is how a company loses its *actual* domain reputation, and
Google suspends accounts for bulk unsolicited sending. Their mitigation is human
approval per send, which limits volume, which limits risk, which also limits the
product.

off_CRM took the opposite road: separate lanes, authentication preflight,
feedback loops, automatic pause. Less immediately effective, far harder to blow
up. Neither is wrong; they are different bets on which failure you would rather
have.

---

## The trust gap, which is larger than the product gap

| Question a buyer asks | Outmate's answer |
|---|---|
| Who am I contracting with? | "Outmate.ai… operated by Outmate." No legal entity, no company number, no registered address anywhere on the site. |
| Under which law? | "These Terms are governed by the laws of **our jurisdiction of incorporation**" — never named. A contract that does not name its forum. |
| Where is my data processed? | Azure, East US (confirmed by DNS), with SCCs and the UK IDTA offered for transfers. EU visitor data leaves the EU. |
| What is collected about my visitors? | IP, user-agent, **device fingerprint**, approximate geolocation, dwell time, scroll depth, page sequence, inferred persona and buying stage. |
| On what legal basis? | Legitimate interests for "B2B relationship and sales-intelligence purposes", consent where required. The customer carries the consent obligation, and the Terms indemnify Outmate for the customer's failure to obtain it. |
| Who else sees it? | Eleven named subprocessors, plus identity-cooperative providers where enabled. |
| Who do I call? | `support@outmate.ai`. No phone, no address, one business day. |

**Fairness where it is due:** the privacy policy and DPA are genuinely well
drafted. They name subprocessors, cite GDPR, UK GDPR, CCPA/CPRA *and* the India
DPDP Act, describe encryption of identity data with deterministic hashes for
lookup and deletion, and honour CCPA opt-out. That is more care than most
seed-stage companies show, and more than most of their named competitors. Which
makes the missing entity and missing jurisdiction stranger, not less serious.
Someone competent wrote those documents.

**One unverified lead.** No team member is named anywhere on the site, and there
is no Crunchbase, G2, Product Hunt or funding coverage. The only human signal
found is a public LinkedIn post promoting "Outmate's signal-driven GTM system"
and "the 1-person GTM system" from an individual account. Who runs the company
is not asserted here. If a contact is wanted, that post is the thread to pull.

---

## Verdict

1. **This is the closest competitor, not Clay and not Strawberry.** Same buyer,
   same shape, same Apollo dependency, roughly the same stage. More useful and
   less comfortable than the earlier comparisons.
2. **Visitor identification is the one capability worth copying.** The module
   off_CRM completely lacks and the reason anyone signs up. The company-level
   version is commodity: a small pixel, ip-api or IPinfo, reverse DNS, ASN
   filtering to drop consumer ISPs and VPNs. Days, not months. Person-level is
   the hard, expensive, legally loaded part — do not touch it.
3. **Their agent philosophy is your agent philosophy.** "Reads your data.
   Reasons with guardrails. Hands you a draft." One job per agent, scoped
   inputs, logged reasoning, audit trail. Stop treating draft-then-approve as a
   constraint to apologise for; two competitors now sell it as the feature.
4. **The egress wall finally has something to be better than.** "Routed
   exclusively through OpenRouter" against tiered providers, an allowlisted
   payload and a logged egress. Still worth nothing to most buyers. Worth a lot
   to one specific kind.
5. **Nine contradictions are a competitive asset and a warning.** Against them,
   do not attack — ask the buyer to open two of their own pages. Then turn it
   around: off_CRM has the same disease in a different organ. `BUILD_STATE.md`
   disagreed with the code badly enough to put a wrong claim in a published
   brief. They ship faster than they document; this repo documents faster than
   it ships. One failure mode: nobody owns consistency.
6. **The uncomfortable one.** Outmate built eight modules, a pricing page, a
   free tier, a working pixel and nine comparison pages on rented
   infrastructure, almost certainly with fewer engineer-hours than off_CRM has
   spent on the video timeline alone. They bought everything buyable and built
   only the orchestration. off_CRM built the muxer by hand. Theirs is the
   correct strategy for getting a customer; this repo's is the correct strategy
   for building something that lasts. **Only one of those two has a deadline.**

---

## Confidence

**High** on everything quoted — it is published copy and their own legal
documents, and every contradiction cites both sources. **High** on the
subprocessor list and the Azure region: the first is a legal disclosure, the
second is a DNS record. **Medium** on interpretation of team size and stage,
inferred from stack choices, page inconsistencies and absence of coverage rather
than stated anywhere. **Unknown**: funding, headcount, revenue, customers, legal
entity, jurisdiction, and who runs it — none is public. The absence of a
Crunchbase, G2 or Product Hunt presence is only weak evidence; plenty of real
companies skip all three.

Everything critical above is drawn from documents Outmate published voluntarily,
several of which are more thorough than their competitors'. A company that
publishes a detailed subprocessor list is being more transparent than one that
does not, and it is slightly perverse that doing so is what made this teardown
possible.
