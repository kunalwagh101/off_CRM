# GTM engine — gap analysis

*How far off_CRM is from the autonomous go-to-market engineer described by the
owner on 2026-09-16, what is missing, and the order the missing pieces should be
built in.*

Read against commit `aa38057`. Codebase figures come from reading the repository,
not from re-reading `BUILD_STATE.md` claims. Market figures are cited inline.

Companion artifact (same content, readable layout):
<https://claude.ai/artifact/2YHVuLx2dvnMqgQfKXpSh6>

---

## The goal, as stated

One application that:

1. Designs a go-to-market strategy, including a sales strategy.
2. Uses the orchestration layer to pick and understand its own tools.
3. Writes the emails, using psychology and proven marketing patterns.
4. Produces a demo video of the platform that tells a sellable story.
5. Finds the people worth contacting (Apollo), stores them.
6. Sends the email with the demo video attached.
7. Measures the hit rate, learns, rewrites, sends again.
8. Builds social presence and posts daily to grow an audience.

---

## Verdict

**Roughly 40% of the way there**, and the remaining 60% is not spread evenly.

| Subsystem | State | Note |
|---|---|---|
| Strategy brain | **0%** | Nothing produces a GTM plan. `campaigns.py` is a registry of *kinds*, not a planner. |
| Content factory | **70%** | Email writer, video editor, assembler, director, image campaign. Nothing *records* a demo. |
| Delivery & distribution | **55%** | Email delivery core is serious and still beta. Social publishing reaches a local outbox only. |
| Targeting & data | **35%** | `apollo_client.py` calls two endpoints. No ICP compiler, no waterfall, no signals. |
| Learning loop | **40%** | Reply counting, Thompson bandit, evals, verify loop — all good, all email-only. |

Weighted strategy 25 / content 20 / delivery 20 / targeting 20 / learning 15 →
**38%**. The weighting is a judgement and is stated so it can be argued with.

**The one-line summary: the limbs are built, the brain is not.**

---

## What is genuinely strong

Worth recording before the gap list, because it decides the strategy.

- **The egress wall.** Payloads are *constructed* from an empty allowlist rather
  than filtered. The pre-flight scanner **blocks and raises** instead of
  redacting. `PersonPublic` carries no email field, so an address cannot travel
  the person path at all. Trust tiers run on two axes — jurisdiction *and*
  retention terms.

  Clay, 11x and Artisan all send prospect data to US model hosts. off_CRM
  structurally cannot. For an EU, healthcare, finance or regulated-buyer
  customer that is not a feature, it is the purchase decision. **Nobody in the
  AI SDR category has this.**

- **The video engine.** Hand-written WebM muxer, MP4/Matroska demuxers, 48 GPU
  effect primitives verified against real pixels, 124 looks, an auto-assembler
  and a director. Sendspark and Vidyard sell a fraction of this as a separate
  per-seat product.

- **The honesty machinery.** The eval harness refuses to let a model grade
  anything; the bandit reports posterior means instead of raw fractions; the
  egress log records a cache hit as `cache_exact`, not `succeeded`. These are
  the decisions that make later measurement trustworthy.

---

## The eight gaps

Ranked by how directly each blocks the stated sequence.

### 1. There is no strategy layer — 0 lines

Nothing in 243 Python files takes "here is my product" and returns a
go-to-market plan. Nothing decides ICP, channels, offer, sequence or budget.
`campaigns.py` declares three *kinds* (email, image, distribution) and refuses
to let a runner touch the wrong one. That is a type system, not a planner.

Step 1 of the stated goal maps to no code.

### 2. No single source of truth about the product — 0 lines

Nothing in the schema holds: what the product is, who it is for, the problem,
the proof, the offer, the forbidden claims. Every generator takes ad-hoc
strings — the email writer one, `video/director.py` a topic, the caption writer
an angle. Three channels, three slightly different stories.

This is an architecture gap and it must be closed **before** the strategy layer,
not after, because the planner has nothing to reason over without it.

### 3. An email cannot carry a video — 0 lines

Grepping `offsetx_apollo_builder/outreach/` and `api/email_delivery.py` for
`attachment`, `video_url` and `thumbnail` returns nothing. The centre of the
stated story has an empty implementation.

What it needs: video hosting, a per-recipient landing page, an animated
thumbnail with a play affordance, a tracking token, and a watch-time event
flowing back into the reply store as a second signal beside replies.

### 4. Nothing records a product demo

The editor cuts, grades, captions and scores footage. It cannot produce footage.
`campaigns.py` states it directly: *"no generator produces footage or audio
yet."* So "it will create a demo video of the platform" today means a human
records their screen, uploads it, and the director cuts it.

### 5. No agent run loop

S-02.02.01 through 04 are specified and unbuilt. Without them every step needs a
human button press. The orchestration that *does* exist routes one question to
one model; it does not chain a plan across steps.

### 6. Apollo is wired thin, and there are no buying signals

`apollo_client.py` is 79 lines: `people_search` and `bulk_people_enrich`. No
ICP-to-query compiler. No waterfall across providers. No job changes, funding,
hiring spikes, tech installs or website visitors — Apollo's own API exposes job
postings and visitor tracking and neither is called.

Credit arithmetic worth designing against: an email reveal costs 1 credit, a
phone 8, so full enrichment can reach 9 credits per record. Email credits are
capped at the lesser of spend ÷ $0.025 or 1M per account per year.

### 7. Learning is trapped inside email

The bandit allocates between email template variants. The distribution engine
counts views. Nothing joins them. There is no *message angle* object that email,
video and social all reference, so a hook that works on one channel cannot teach
another.

### 8. External unlocks have not been started

- Google Cloud project + YouTube Data API v3 — free, ~10 minutes, and the only
  reachable publishing adapter.
- Meta / TikTok / LinkedIn app reviews — weeks of calendar time, zero
  engineering.
- Live AWS, DNS and mailbox-cohort validation before the email beta label comes
  off.

---

## Four disagreements with the stated plan

### Fine-tuning on top marketers' videos is the wrong first move

**Copy is not the bottleneck.** Senders failing the 2026 bulk rules see 22–34%
of mail routed to spam; compliant senders average ~89% inbox placement. If a
third of the mail never arrives, better copy is being applied to the two-thirds
that did.

**Training on other people's videos is real legal exposure.** Reading them to
write an internal playbook is normal. Putting transcripts of copyrighted
material into weights is a different act with a different risk profile.

**The sequence is backwards.** The 2026 consensus is Prompt → RAG →
eval-driven selection → *then possibly* a LoRA adapter. Fine-tuning shapes form,
not facts, and needs several hundred examples in exact production format plus an
owner for the adapter for 12+ months with quarterly revalidation.

off_CRM already has the expensive half — the eval harness and the verify loop.
What it lacks is a scored corpus and a rubric. Build those. Then a fine-tune can
be *measured* to be worth it instead of assumed.

### "Guaranteed good hit rate" is not achievable

`ai/bandit.py` already wrote the arithmetic down. Separating 2% from 4% needs
~1,140 sends per variant; 2% from 3% needs ~3,800. Twenty sends with no replies
occurs 54% of the time at a true rate of 3%.

No model beats that. The promise that *is* keepable and also true: the system
finds the best variant faster than a human would, and says honestly when it does
not have enough data. The code already says "stop trying" when the answer is tens
of thousands of sends away. That honesty is a product feature.

### Do not auto-create social accounts

Automated account creation breaks every platform's terms. The accounts get
banned and the associated domain gets flagged — which then damages the email
deliverability the repo spent months protecting. The existing call (official
APIs only) is correct and should stand. A human creates each account once.

### Do not chase full autonomy

The review queue and the per-handle posting cap are the two best product
decisions in the repository. 11x and Artisan sell full autonomy; the 2026 read on
that category is that autonomous senders maximise volume while the augmentation
camp wins on quality. Keep the human gate when the strategy layer lands.

---

## Physics the strategy layer must respect

Every number here caps what a generated plan may propose. Build the planner
deliverability-aware or it will write plans that destroy the sending domain.

| Figure | Meaning |
|---|---|
| **0.30%** | Spam complaint ceiling at Google, Yahoo, Microsoft. Practical working limit nearer **0.10%**. |
| **2%** | Hard bounce ceiling. Above it: throttling, then rejection. |
| **5,000/day/domain** | Threshold triggering full bulk-sender rules. |
| **~89%** | Inbox placement for compliant senders, 2026. |
| **22–34%** | Share routed to spam for non-compliant senders. |
| **3.4%** | Average plain-text cold email reply rate. |
| **10–16%** | Reported reply rate for video-first outreach; top performers past 25%. |
| **1,140** | Sends per variant to separate 2% from 4%, from this repo's own bandit maths. |

Read the last two together: video outreach reportedly runs 3–5× plain text, and
a full video engine already exists in this repository, unused by the email path.
**Gap 3 is worth more than months of copy tuning.**

---

## Competitive position

| Dimension | Field | off_CRM | Verdict |
|---|---|---|---|
| Data privacy | Prospect data goes to US model hosts | Structurally cannot | **Win, decisively** |
| Video | Sold separately per seat | Full editor inside the CRM | **Win, unused** |
| Data coverage | Clay waterfalls 100+ providers | Apollo + a web crawler | **Lose badly** |
| Buying signals | Job changes, funding, hiring, visitors | None | **Lose** |
| Strategy generation | Nobody does it well; Clay needs a GTM engineer | Nothing yet, but the substrate is unique | **Open field** |
| Autonomy posture | 11x/Artisan maximise volume | Human gate, caps, honest statistics | **Right side** |

The moat is real. The data layer is what will cost deals.

---

## Build order

| # | Phase | Cost | Why here |
|---|---|---|---|
| 0 | Google Cloud project + start app reviews | 10 min, free | Only reachable adapter; reviews run on calendar time in parallel. |
| 1 | `ProductTruth` — one object every generator reads | ~1 week | The planner has nothing to reason over without it. |
| 2 | The strategy layer (`gtm/`) | ~2–3 weeks | The missing brain. |
| 3 | Video in the email | ~2 weeks | Highest ROI in the repository. |
| 4 | Agent run loop (S-02.02.01–04) | ~2–3 weeks | The plan needs legs. |
| 5 | ICP compiler, provider waterfall, signals | ~2 weeks | Closes the Clay gap. |
| 6 | Cross-channel learning (message-angle object) | ~1–2 weeks | Three tools become one engine. |
| 7 | Demo capture — browser agent drives the product, records it | research | Nobody else has both halves already built. |

Phases 1–6: roughly **10–13 weeks** at this repository's existing standard —
tests, docs, verified evidence, nothing claimed that a script cannot re-run.
Phase 7 is research and should not be scheduled.

### Design rule for Phase 2, stated up front

The strategy model **picks from declared options and writes short text**. It
never emits a plan structure. This is the same closed-vocabulary rule already
proven twice in this repository: `video/director.py` picks one of eight declared
recipes, and `ai/tools.py` lets a model name a registered tool but never
describe a new one. A model asked to emit a whole plan emits invalid ones, and
nobody can review four hundred lines of JSON before it becomes a campaign.

---

## Scraper stack decision

| Library | Role | Reason |
|---|---|---|
| **Scrapling** *(already a dependency)* | Default fetcher + parser | Selectors re-find an element after a site redesign. Ships StealthyFetcher on modified Firefox. |
| **Crawl4AI** *(already an extra)* | JS-heavy pages → Markdown | Already wired as `crawl4ai_public_js`. LLM-ready output, no boilerplate stripper needed. |
| **Trafilatura** — add | Article body extraction | Best-in-class main-content isolation; returns author/date/sitename free. Cuts token spend. |
| **selectolax** — add | Fast HTML parsing | lexbor-based, ~5–10× faster than BeautifulSoup. Parsing is the CPU bill at crawl scale. |
| **Camoufox** — add | The hard 5% | Patches fingerprint leaks inside the Firefox engine. ~99% against Cloudflare managed challenges. |
| **Patchright** — optional | Chromium-side stealth | Drop-in patched Playwright; least disruptive given the existing CDP client. |
| **Firecrawl** — paid fallback | Pages that beat everything | Buying the hard 2% beats a proxy fleet. US hosted → **Tier B, public data only** under this repo's own rules. |

**Rejected:** Scrapy (its spider architecture fights the existing `PageFetcher`
protocol), Selenium (slower and more detectable in 2026), BeautifulSoup
(outclassed on both speed and adaptivity), Botasaurus (overlaps Camoufox, heavy).

**Hard line: do not scrape LinkedIn.** `discovery.py` already blocks it for
headless engines and that call stands. People data comes from Apollo's API.
LinkedIn scraping risks a banned account, a lawsuit, and the privacy position
that is currently the strongest asset here.

---

## Sources for the market figures

- Bulk sender requirements 2026 — <https://redsift.com/guides/bulk-email-sender-requirements>, <https://powerdmarc.com/bulk-email-sender-requirements/>
- Cold email deliverability 2026 — <https://growthengineer.ai/blog/cold-email-deliverability-2026>
- Video outreach reply rates — <https://blog.sendspark.com/best-video-email-platforms-sales-teams>
- AI SDR field — <https://www.stackfyi.com/guides/best-ai-sdr-tools-clay-vs-apollo-vs-artisan-vs-11x-2026>, <https://www.refontelearning.com/blog/ai-sdr-tools-clay-11x-artisan-compared>
- Fine-tuning vs prompting 2026 — <https://aishwaryasrinivasan.substack.com/p/fine-tuning-vs-prompt-engineering>, <https://bigdataboutique.com/blog/fine-tuning-llms-when-rag-isnt-enough>
- Apollo API limits and credits — <https://docs.apollo.io/reference/rate-limits>, <https://galadon.com/apollo-io-api>
- Stealth browsers 2026 — <https://scrapfly.io/blog/posts/best-stealth-browsers>, <https://scrapewise.ai/blogs/playwright-stealth-2026>
- Scrapling — <https://scrapling.readthedocs.io/en/latest/index.html>
- Crawl4AI vs Firecrawl — <https://brightdata.com/blog/ai/crawl4ai-vs-firecrawl>
