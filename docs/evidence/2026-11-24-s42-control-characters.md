# S-06.02.42 — D-518 illegal Excel control-character acceptance

**Status:** IN_REVIEW. **Source:** `develop`, 2026-11-24. This closes a specific export crash; it does not certify the whole A19 finding or the parent F-06.02.

## Reproduced failure

An isolated `openpyxl` workbook write using the current export-safe-cell algorithm was run with untrusted source strings:

- `Person\\x00Name` (NUL), embedded VT (`\\x0b`), FF (`\\x0c`) and US (`\\x1f`): **RED** with `IllegalCharacterError` on the first invalid cell, before XLSX can be saved.
- The patched algorithm converts only disallowed control bytes to *visible literal* `\\xNN` text in **human-readable exports only**. Identical isolated workbook write: **GREEN** (5 cells written/read, text type for formulas and integer type preserved); source input remains unchanged.
- This is an isolated regression reproduction, **not** proof that the complete repository tests have passed yet.

## Repository boundary changes

`offsetx_apollo_builder/io_utils.py::spreadsheet_safe_cell` makes only the human-facing frame values printable before the existing formula detection. Internal authoritative ledgers, saved CRM values and the raw `run_meta.json` remain unchanged. The new `tests/test_spreadsheet_exports.py` cases exercise actual `write_outputs`: accepted, rejected, raw, decision and metadata tabs; CSV and workbook cell types; unchanged caller inputs; numeric scores; raw JSON preservation. Previous SQL/CSV identity and deduplication paths are untouched.

## Outstanding acceptance

Run real GitHub Python3.10/11/12, PostgreSQL, frontend, Chromium, workbook round-trip and full-history board verifier. Then independent review and isolated actual Excel/LibreOffice open with external-link execution disabled. Do not mark S-06.02.42 DONE or customer release solely from synthetic workbook tests. New Render builds cannot be retried until the workspace build-minute problem is resolved.

Rollback: revert only this new human-report cell transformation and its tests; warn that previous reports containing OpenXML-forbidden inputs could fail to export. No data migration or customer credential changes.
