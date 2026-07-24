$ErrorActionPreference = "Stop"

# Code-only is mandatory: documents, PDFs, media, contacts, email and campaign
# data must never enter Graphify's semantic path.
$GraphifyVersion = "0.9.25"
$Graphify = @(
    "uvx",
    "--from",
    "graphifyy==$GraphifyVersion",
    "graphify"
)

& $Graphify extract . --code-only --no-cluster --max-workers 2 --force
& $Graphify cluster-only . --no-label --no-viz

Write-Host "Code graph ready: graphify-out/graph.json"
Write-Host 'Query it with: uvx --from graphifyy==0.9.25 graphify query "your question"'
