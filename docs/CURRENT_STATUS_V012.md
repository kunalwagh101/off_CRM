# OFF_CRM v0.12 status

Date: 2026-07-24

## Delivered

- Complete v0.11 discovery, outreach, Apollo, Gmail, sales, dashboard, and projection functionality retained.
- OFF_AI chat/projects workspace with the requested right-side history drawer.
- Independently closable left navigation and right history drawer.
- Connectors workspace for Gmail, providers, trust classification, quotas, egress audit, owner export, and GitHub tools.
- Deterministic campaign intake with Generate and Parse & send.
- Zero-access provider broker, trust tiers, quota/cost routing, same-tier failover, exact egress audit, and security tests.
- Deterministic internal continuation state.
- Reply-rate numeric feedback loop with human approval.
- Source-only Graphify build artifact and pinned rebuild script.

## Deliberate boundaries

- Local SQLite remains the v0.12 single-user database. PostgreSQL/JSONB is the production-team migration target.
- The model parse-fallback contract exists, but the UI currently stops for deterministic mapping instead of sending a masked file automatically.
- Public enrichment remains in the existing Lead Discovery/Apollo workflow; OFF_AI does not duplicate it.
- Graphiti remains parked until measured internal multi-hop relationship queries exceed the threshold.
- Notion/NotebookLM support is one-way Markdown/JSON export, not a connected read/write provider.
- Gmail reply bodies are not classified by AI.
- LinkedIn/Instagram authenticated scraping and protection bypasses are not implemented.
- Sandboxed GitHub tool execution requires local Docker.
- Render remains a disposable demo, not a production team deployment.

## Verification

The 2026-07-24 release pass completed:

- 94 backend tests passed;
- one Docker network-wall test skipped explicitly because Docker is unavailable in this build workspace;
- 9 frontend tests passed;
- the optimized frontend build passed;
- Python source and wheel builds passed;
- the live FastAPI readiness and metadata smoke test passed.

The authoritative verification ledger is in `BUILD_STATE.md`. Re-run with:

```powershell
uv run pytest -q
cd frontend
npm test
npm run build
```
