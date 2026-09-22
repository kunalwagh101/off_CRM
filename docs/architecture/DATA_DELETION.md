# S-06.02.04 — Data deletion and subject access

## Problem

Personal data is not stored in one table. It can exist in CRM/research rows,
discovery observations, crawler state, browser trace JSONL, screenshots,
captured page text and generated subject-specific artifacts.

A deletion function with a hard-coded list of tables will drift as the product
adds stores.

## Scope

This story implements **explicit subject access and confirmed deletion**.

Q-07 remains open for automatic retention duration. No 30-day/forever policy is
invented here. Automatic retention is separate from a person explicitly asking
for access or deletion.

## Architecture: one inventory, small adapters

Create a registry of personal-data stores. Each adapter exposes the same small
contract:

- identify itself and the record classes it owns;
- `find(subject)` for preview/export;
- `delete(subject)` for idempotent deletion;
- return counts/artifact classes, never unrelated subject content.

Use existing store transactions and standard filesystem operations. Do not build
a new persistence layer.

The implemented inventory has twelve named adapters:

1. redacted sent-mail recall;
2. AI task context;
3. exact AI egress audit records;
4. explicitly tagged generated subject artifacts;
5. application-owned CSV queues/exports;
6. persisted companion profile names/instructions;
7. durable agent routine definitions/results;
8. workspace login identities when the username is the verified subject;
9. derived meeting transcript/timing metadata (raw meeting audio is never stored);
10. crawler frontier/cache URLs where the subject itself is identifiable;
11. browser trace runs, including screenshots/captures when that run matches;
12. CRM/discovery/delivery/research/sales records, including residual discovery
    and audit JSON.

CRM identity rows are intentionally last. If an auxiliary cleanup fails, the
stable CRM join keys survive so the same deletion plan can be retried safely.

A new persistent personal-data store is not complete until it registers here.

## Subject identity

Deletion must use explicit normalized subject identifiers supplied by the
operator/request workflow, such as verified email plus known stable CRM entity
ids/URLs. Fuzzy name matching is not safe enough to delete data.

The preview step shows which store classes match before destructive execution.

## Execution semantics

Cross-database + filesystem deletion cannot be honestly called one ACID
transaction. The production contract is therefore:

1. build and persist a deletion plan from the inventory;
2. require explicit confirmation;
3. execute each adapter idempotently;
4. record per-store result;
5. return complete only if every required adapter succeeded;
6. on retry, re-inventory an adapter before reusing an earlier success; if
   matching data has reappeared, delete it again;
7. retry failed/incomplete adapters safely.

The deletion receipt contains store names, counts/classes, timestamps and
errors. It must not preserve the deleted personal data itself.

## Subject access

Access/export uses the same inventory, which prevents the export path and delete
path from disagreeing about where data lives.

Every adapter must isolate by verified strong identifiers and workspace. The
HTTP layer replaces any body-supplied workspace with the authenticated
workspace and rejects an explicit mismatch, so a caller cannot turn subject
access into a cross-workspace read.

A subject request must never return another subject's records.

## Safety tests

Required evidence:

- subject A export does not include subject B;
- confirmed deletion removes A from every registered fixture store;
- B remains unchanged;
- trace screenshots/captures are removed with their trace data;
- crawler subject URLs are removed without deleting unrelated frontier rows;
- one adapter failure returns incomplete and names that adapter;
- retry is idempotent and finishes the same plan;
- a store that succeeded earlier is re-inventoried, so newly reappeared subject
  data cannot hide behind a stale success receipt;
- receipt contains no deleted payload;
- registry coverage test fails when a known personal-data store is omitted;
- CSV queues/exports remove only matching rows and preserve unrelated rows;
- residual discovery/audit JSON no longer retains the strong subject token;
- a cross-workspace privacy request is refused;
- matching routine state is removed without touching unrelated routines;
- a matching workspace login identity is removed;
- matching meeting transcript metadata is removed without touching other meetings.

## Rollback

Deletion itself is intentionally irreversible. Safety comes from preview +
explicit confirmation + strict identity, not from pretending deleted personal
data can be restored.

Code rollback must remain possible because the registry/adapters are additive,
but it cannot resurrect data already deleted.

## Known limits

Cloud-provider deletion APIs that are not connected to off_CRM cannot be
claimed as completed. Their future adapters must report external completion
truthfully instead of marking local deletion as global deletion.
