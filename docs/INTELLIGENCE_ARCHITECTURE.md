# OffsetX intelligence architecture (v0.8)

## Product boundary

OffsetX remains a local-first, single-user application. React talks to FastAPI, FastAPI owns the workflow, and SQLite is the local source of truth. AI providers and Gmail are direct external dependencies; OffsetX does not place a hidden application server between the user and those services.

The hosted Render configuration is a disposable demo, not a multi-tenant production deployment. It must use synthetic contacts and local outbox mode.

## Runtime flow

```text
React review and controls
          |
          v
FastAPI control plane
          |
          +--> Outreach engine --> SQLite CRM / audit / memory
          |
          +--> Provider policy --> normalized multi-provider router
                                     |--> OpenAI
                                     |--> Anthropic
                                     |--> NVIDIA/Kimi/compatible API
                                     `--> future template application
          |
          `--> Local outbox or explicitly-authorized Gmail
```

## Pre-send guarantees

1. Generation starts from a versioned template blueprint.
2. Only approved memory and rights-declared expert material enters generation context.
3. A provider profile applies its data policy before any network request.
4. Every provider response is normalized to the same subject/body JSON contract.
5. The email expert reruns hard evidence, signature, CTA and language checks.
6. The exact draft, context references and selected provider are visible in React.
7. Edits reset approval. Bulk replacement requires a preview and re-audits every changed draft.
8. Sending requires `sendable = true`, explicit approval, due time, campaign send window and remaining daily allowance.
9. Reply sync runs first and cancels every unsent follow-up after a matched reply.

## Provider portability and control

Provider-specific transport is isolated behind `AIProvider.generate(system_prompt, user_prompt)`. Profiles contain provider type, model, URL, priority and routing strategy. Credentials are either read from named environment variables or encrypted locally outside SQLite.

Routing strategies:

- `priority`: use the first healthy provider and fail over in order.
- `round_robin`: rotate the starting provider while retaining failover.
- `parallel`: request all healthy providers and use the first normalized success.

All strategies validate the same canonical response. A provider outage or malformed result does not change the CRM workflow.

Data policies:

- `minimal`: removes recipient identity and direct source data.
- `standard`: permits business context but strips direct contact data and URLs.
- `full`: sends the complete generation prompt selected by the operator.

Call metadata is always inspectable. Redacted request and response bodies are stored only when `audit_payloads` is enabled for that profile.

## Memory and RAG

`MemoryBackend` is the stable boundary. The current backend uses SQLite; a future hosted edition can implement the same interface using a tenant-isolated retrieval service without changing the email expert.

Memory types include:

- human corrections and bulk rules;
- manually approved playbook instructions;
- reply observations;
- human-labelled outcomes.

Human edits and explicit labels are approved inputs. Automatic reply observations are factual but remain unapproved, preventing the system from converting every reply into an instruction. Corrections are de-identified before storage. Generation retrieves approved global and campaign memory only.

Expert documents remain a separate provenance-aware knowledge collection. The memory layer is for product learning; the expert library is for rights-declared guidance. Both return references in the generation trace.

## Scheduling

Campaigns define timezone, local start/end, allowed weekdays and daily cap. Drafts can add a UTC `scheduled_at` not-before gate. The effective send time is the later of sequence due time and manual schedule. Equal start/end times mean a full-day window for backwards compatibility.

## Experiments

Contact assignment is deterministic. Each outbound message stores variant, template, revision and AI profile exposure. Reports use first-touch sends as denominator, one reply per contact as outcome, an explicit control variant, lift in percentage points and Wilson 95% intervals. Minimum sample is a collection guardrail, not a claim of statistical significance.

## Hosted scale path

For a multi-user edition, retain the API and service boundaries while replacing:

| Local component | Hosted replacement |
|---|---|
| SQLite | PostgreSQL with tenant row isolation |
| local encrypted files | managed tenant secret vault |
| in-process scheduler | durable queue and worker fleet |
| local `MemoryBackend` | centralized tenant-scoped retrieval service |
| signed demo session | full identity, organization and role model |
| local outbox | audited delivery service with per-tenant quotas |

Provider calls, memory items, messages and experiments already carry stable workspace-oriented boundaries, so this migration does not require coupling product logic to a specific AI vendor or vector database.

## API additions

- `GET /api/v1/provider-calls`
- `GET /api/v1/memory` and `GET /api/v1/memory/stats`
- `POST /api/v1/memory` and `PATCH /api/v1/memory/{id}`
- `POST /api/v1/campaigns/{id}/drafts/bulk-replace`
- `POST /api/v1/campaigns/{id}/drafts/schedule`

The OpenAPI document at `/api/docs` is the canonical field-level contract.
