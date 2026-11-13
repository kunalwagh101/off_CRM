# Live end-to-end sweep — 2026-11-13

**What was tested:** `develop` at `2177e05`, run locally as a real server
(`offsetx-web`) on an empty data folder, driven over HTTP the way a customer
would, with a **real NVIDIA API key typed into the app** (the key was removed
from the server's environment on purpose, to prove the app-only key path).

**Verdict in one line:** the security walls and data safety are strong; the
AI layer was **dead on arrival for every NVIDIA user**, and cross-workspace CRM
isolation is still the #1 release blocker.

This is evidence of a local run. It is not a deployment, a merge to `main`, or
a release claim.

---

## 1. Numbers

| Layer | Result |
|---|---|
| Python unit/integration suite, before | 3,292 passed · 148 skipped · 0 failed (7 m 48 s) |
| Frontend (vitest) | 237 passed · build OK (one 653 kB chunk warning) |
| Lint (`ruff` fatal set) | clean |
| Route sweep: 245 paths × no-auth / empty / junk / binary bodies | **0** server errors · **0** auth bypasses · **0** non-JSON errors |
| Live feature checks (real server, real NVIDIA) | 234 PASS · 33 FAIL raw → **19 real defects** (below), 11 were the test script's own wrong inputs, 3 by design |
| Retest of every fixed defect on a fresh server | 10 / 10 PASS |
| New regression tests | 27 in `tests/test_e2e_findings_2026_11_13.py`, all written RED first |

The raw FAIL count overstates the problems. Where the script sent a wrong
field (`approval_mode: manual`, `q` instead of `query`, an unknown video edit),
the app answered with a precise sentence naming the fix. Those messages are a
strength and are counted as script mistakes, not defects.

---

## 2. What works (verified live)

**Security walls.** Every one of 245 routes refuses anonymous access. Bad,
empty, upper-cased, `Bearer`-prefixed and query-string tokens are all refused.
A foreign `Host` header gets 421 (DNS-rebinding guard). Login locks out after 5
tries (429). Session cookie is `HttpOnly`, `SameSite=strict`, and `Secure` off
loopback. CSP, `X-Frame-Options: DENY`, `nosniff`, `no-referrer`, `no-store` on
every page. `/api/docs` and `/api/openapi.json` need login. Path traversal in
static files and in media ids → 404. SQL-shaped search input → 422. 12 MB body
refused. No permissive CORS. Logout really kills the session. Disabled
workspace cannot log in. Weak workspace password refused. Non-owner cannot
create workspaces or export the install backup. The frontend has no
`dangerouslySetInnerHTML`, `innerHTML` or `eval`, so stored `<script>` names
render as text.

**Secrets.** The NVIDIA key never appears in any API response, the egress log,
the server log, the backup file, or anywhere on disk in plain text (byte search
of the whole data folder).

**AI privacy wall.** Email addresses in chats are swapped for `<RECIPIENT_1>`
before leaving. Mailbox data class refused. Above-ceiling "full data" needs a
written reason (400 without one). A pasted key inside an approved memory did
not reach NVIDIA in the observed call. Every outbound call is in the egress log
with its exact payload.

**AI features, once a live model is chosen.** Chat (with history), Run
(simple and verified), router plan, model discovery, balance check, companion
chat, template rewrite — all answered for real through NVIDIA.

**The outreach journey, end to end.** Campaign → contact with a sourced hook →
real NVIDIA draft (`mode: ai_personalized`) → quality audit → approve → send to
the local outbox exactly once → a second send sends nothing → the email file is
addressed to the real person with tokens re-attached. Gmail live send without
the typed confirmation is refused. Drafts without a verified hook are blocked
from approval (6 of 6 blocked correctly).

**Input validation.** Blank names, bad time zones, negative limits, invalid
emails, binary files posing as CSV, impossible dates, invalid months, stale
revisions (409, no lost update on the sales board) — all refused with readable
sentences. CSV export neutralises `=HYPERLINK(...)` formula injection.
Case-different duplicate emails return the existing membership.

**Data safety.** Encrypted backup (no plaintext emails, no key inside); wrong
passphrase and corrupt file refused with data untouched; good restore is a true
point-in-time rewind; the encrypted NVIDIA key still works after restore. Full
server restart: campaigns, AI audit log, sales leads and the encrypted key all
survive.

**SSRF guard.** Discovery refuses `127.0.0.1`, `169.254.169.254`, `[::1]`,
`localtest.me`, `file://` and `0x7f000001`. Agent routines refuse cloud-metadata
and `file://` targets. Uploads with wrong magic bytes (HTML as MP4) refused.

**Privacy (GDPR).** Subject-access export finds the person; deletion needs the
exact phrase `DELETE SUBJECT DATA`; after deletion the person is gone from
search.

---

## 3. Defects found

Fixed in this change (test-first, retested live where the provider allowed):

| ID | Sev | What was wrong | Fix |
|---|---|---|---|
| D-440 | critical | NVIDIA's default model was retired on 2026-08-26 (410 Gone). Every AI feature failed on a fresh NVIDIA connect. 10 of 11 listed chat models were dead. | New catalogue of models that answered today; default `nvidia/nemotron-3.5-lightning-30b-a3b` (1–2 s). |
| D-441 | high | A retired model was reported as "This is an off_CRM bug"; the user saw only "Check the settings". | 410 / end-of-life → `model_not_found`, advice says pick a current model in Connectors. |
| D-442 | medium | Phone numbers left for NVIDIA in clear text (seen: `+1 415 555 0199`). | Tokenised as `<PHONE>`; dates, money, years, versions and IPs untouched. |
| D-443 | medium | A draft could still contain `RECIPIENT_1` / `COMPANY_1` and be marked sendable. | Audit error "Privacy token left in the email". |
| D-444 | high | NVIDIA images went to an endpoint NVIDIA does not serve (404); an existing test asserted the wrong URL. SDXL gone. | NVIDIA genai adapter, same-domain key guard, content-filter refusal. **Not live-verified**: NVIDIA's FLUX service gave 500s and 300 s timeouts all day. |
| D-445 | low | CSV import kept a row with no email, silently. | Per-row warning. (The sender already skipped it.) |
| D-446 | medium | A pasted API key was saved as an approved memory. | Refused with a next step: keep keys in Connectors. |
| D-447 | low | Chinese labs z-ai, MiniMax, StepFun on NVIDIA fell to tier D instead of C. | Origin prefixes added. |
| D-448 | low | Companion refusal named an internal setting, no next step. | Plain sentence: choose Campaign data. |
| D-449 | low | Swagger's `/docs/oauth2-redirect` was public. | Disabled. |
| D-450 | high | Read timeouts were retried 3×, so a slow paid call could run and bill 3 times. | Never repeat a call that may have run; connection failures still retry. |
| D-458 | high (process) | The live AI path had never been run with a real key. | `scripts/live/check_provider_models.py`. |

Filed, not fixed (each has a backlog home):

| ID | Sev | What is wrong | How to fix | Where |
|---|---|---|---|---|
| D-451 | **critical** | A second workspace login reads **and changes** the first workspace's campaigns, contacts, drafts, CSV export, sales board, CRM search, and can trigger its send. | Activate the per-workspace CRM registry already built (DD-160) for the web app, CLI and workers; then rerun `d_sec.py`. Already the owner's decision (Q-27). | S-06.01.06 |
| D-452 | medium | Erasure deletes the person's unsubscribe too; the same email can be re-imported and emailed. | Keep a salted hash "do not contact" marker (owner decision). | S-06.02.04, Q-31 |
| D-453 | medium | Every default template says "I am building OffsetX in India"; positioning line never reaches the model; one global signature. | Neutral templates + per-workspace sender profile. | S-06.01.01, Q-32 |
| D-454 | medium | Connect accepts any text as a key and shows green. | Call the provider's free `/models` once on connect; mark "unverified" until it answers. | S-06.02.30 |
| D-457 | medium | No overall deadline across retries and fail-over (one image request held the browser 5+ minutes). | One deadline per request (e.g. 90 s) checked before each fail-over. | S-06.02.03 |
| D-455 | low | Image "generate" returns 200 when every model failed. | 502 with the failure list when nothing was stored. | S-06.02.56 |
| D-456 | low | No Origin check on cookie writes (SameSite=strict already blocks CSRF; tried form and text/plain: 422). | Reject a foreign `Origin` on unsafe methods. | S-06.02.23 |

By design, not defects: 1:1 Gmail/local outreach only *warns* without a public
unsubscribe URL (marketing and SES sends are blocked); sales accepts more
conversations than dials (inbound talks) and cash above deal value
(overpayment) — observations only.

---

## 4. Penetration and security summary

| Attack | Result |
|---|---|
| Anonymous access to any of 245 routes | blocked (0 leaks) |
| Token misuse (empty, case, Bearer, query string) | blocked |
| DNS rebinding (foreign Host) | blocked (421) |
| Brute-force login | locked after 5 (429) |
| CSRF from another site | not exploitable (SameSite=strict, JSON-only) |
| Clickjacking | blocked (frame deny, CSP) |
| Stored XSS via contact names | stored as text, React escapes; no raw-HTML sinks |
| CSV formula injection | neutralised on export |
| SQL injection in search | refused (422) |
| Path traversal (static, media ids, encoded) | 404 |
| SSRF via discovery / routines | blocked for loopback, metadata, IPv6, hex IP, file:// |
| Upload spoofing (wrong magic bytes) | refused |
| Secret leakage (logs, disk, backup, API) | none found |
| **Cross-workspace IDOR** | **FAILS — D-451, critical** |
| PII to AI provider | email protected; phone leaked → fixed (D-442) |

This is a targeted local penetration test, not a certified whole-application
assessment.

---

## 5. How to reproduce

`scripts/qa/live_e2e_sweep/README.md` (the exact harness used, now env-driven)
and `scripts/live/check_provider_models.py nvidia`.

## 6. Live NVIDIA model check on 2026-11-13

```
ok        1.7s  nvidia/nemotron-3.5-lightning-30b-a3b (default)
ok        1.0s  nvidia/nemotron-3-ultra-550b-a55b
ok       15.9s  meta/llama-3.2-90b-vision-instruct
ok       14.9s  mistralai/mistral-large-4-1t-a52b
SLOW     60.2s  deepseek-ai/deepseek-v4.1-flash   (answered in 215 s earlier; DD-165)
```

Retired or missing for a valid key: `meta/llama-3.1-70b-instruct`,
`meta/llama-3.3-70b-instruct` (410), `nvidia/llama-3.1-nemotron-70b-instruct`,
`microsoft/phi-3-medium-128k-instruct`, `google/gemma-2-27b-it`,
`ibm/granite-3.0-8b-instruct`, `mistralai/mistral-large-2-instruct`,
`deepseek-ai/deepseek-r1`, `qwen/qwen2.5-coder-32b-instruct` (410),
`qwen/qwen2.5-7b-instruct`, `stabilityai/stable-diffusion-xl` (404).
