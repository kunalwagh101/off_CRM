# Troubleshooting

## No files found

Check:

```powershell
uv run python run_offsetx_apollo.py --queue-status
```

Put a file in `poi_file_queue\inbox`, or use:

```powershell
--reuse-latest-processed
```

## Run ID already exists

Use a new `--run-id`. The app never overwrites a completed run folder.

## Company names appear blank

Supported headers include:

- Company Name
- Company
- Company / Organisation
- Company / Organization
- Organisation Name
- Organization Name
- Employer
- Firm
- Account Name

## Apollo credits were already spent

Check:

```text
old_pois\offsetx_apollo_enrichment_attempt_ledger.csv
```

Rows in this ledger are skipped before a later Apollo call unless `--no-skip-previously-attempted` is explicitly used.

## A run failed

Check:

```text
poi_file_queue\failed
output_existing_poi_enrichment\runs\<run_id>\run_failed.json
```
