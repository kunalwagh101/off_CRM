param(
    [string]$RunId = "dry_latest_processed_$(Get-Date -Format yyyyMMdd_HHmmss)",
    [int]$CreditCap = 10,
    [int]$BatchSize = 5
)
$ErrorActionPreference = "Stop"
uv run python run_offsetx_apollo.py `
  --enrich-existing-pois `
  --reuse-latest-processed `
  --outdir output_existing_poi_enrichment `
  --run-id $RunId `
  --credit-cap $CreditCap `
  --batch-size $BatchSize `
  --dry-run
