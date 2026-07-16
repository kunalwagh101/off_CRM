# Existing POI Enrichment Design

## Purpose

This pipeline enriches people already present in CSV, XLSX, or XLS files. It does not run Apollo People Search.

## Lifecycle

```text
inbox -> processing -> processed
                    -> failed
```

The file remains in `processing` until the complete run succeeds. A successful parse alone is not enough to mark a file processed.

## Credit protection order

For every input row, the pipeline checks:

1. duplicate inside the current input set
2. email already present
3. permanent Apollo attempt ledger
4. strong historical exclusion keys
5. competitor risk
6. minimum Apollo matching fields
7. credit cap
8. Apollo bulk enrichment

## Matching fields

A row is Apollo-matchable when it has one of:

- Apollo person ID
- LinkedIn profile URL
- first name + last name + company or domain
- full name + company or domain

## Attempt ledger identity keys

The ledger uses, in order:

- Apollo person ID
- LinkedIn URL
- email
- full name + company domain
- full name + company
- full name + company + title

## Empty inbox behaviour

Empty inbox is a valid no-work state. The CLI exits cleanly and uses zero credits.

Use `--reuse-latest-processed` when you intentionally want to run the latest archive again.

## Failure behaviour

If Apollo or output generation fails after a file is claimed:

- attempt history already completed is flushed
- the claimed file moves to `failed`
- `run_failed.json` is written
- the file is not shown as successfully processed
