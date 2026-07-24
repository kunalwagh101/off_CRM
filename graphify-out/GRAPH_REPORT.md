# Graph Report - .  (2026-07-24)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 1322 nodes · 3958 edges · 49 communities (46 shown, 3 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 256 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ec46d530`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- OutreachStore
- ProviderError
- create_app
- gmail.py
- app.py
- OffAIStore
- SalesTracker
- norm_text
- types.ts
- OffAIService
- run_existing_poi_enrichment
- runner.py
- existing_poi_enrichment.py
- email_expert.py
- OutreachEngine
- discovery.py
- test_discovery.py
- SalesTracker.tsx
- io_utils.py
- package.json
- validate_public_url
- service.py
- compilerOptions
- BringYourOwnToolRegistry
- Queue.tsx
- RunConfig
- cli.py
- ExclusionSet
- OutreachCRMAdapter
- App.tsx
- input_loader.py
- MemoryService
- test_off_ai.py
- compilerOptions
- useApp
- EgressBroker
- Settings.tsx
- Connections.tsx
- SandboxPolicy
- .__init__
- score_candidate
- tsconfig.json
- offsetx-apollo-builder

## God Nodes (most connected - your core abstractions)
1. `OutreachStore` - 105 edges
2. `to_utc_iso()` - 76 edges
3. `clean_text()` - 65 edges
4. `OffAIStore` - 62 edges
5. `create_app()` - 52 edges
6. `OffAIService` - 41 edges
7. `ProviderError` - 41 edges
8. `run_existing_poi_enrichment()` - 38 edges
9. `OutreachEngine` - 38 edges
10. `CampaignLocks` - 34 edges

## Surprising Connections (you probably didn't know these)
- `StaticFetcher` --uses--> `AppSettings`  [INFERRED]
  tests/test_discovery.py → offsetx_apollo_builder/api/config.py
- `_FixedProvider` --uses--> `AppSettings`  [INFERRED]
  tests/test_off_ai.py → offsetx_apollo_builder/api/config.py
- `_Provider` --uses--> `AppSettings`  [INFERRED]
  tests/test_outreach_intelligence.py → offsetx_apollo_builder/api/config.py
- `StaticFetcher` --uses--> `ParsedPage`  [INFERRED]
  tests/test_discovery.py → offsetx_apollo_builder/discovery.py
- `_FixedProvider` --uses--> `EgressBroker`  [INFERRED]
  tests/test_off_ai.py → offsetx_apollo_builder/off_ai/broker.py

## Import Cycles
- None detected.

## Communities (49 total, 3 thin omitted)

### Community 0 - "OutreachStore"
Cohesion: 0.06
Nodes (25): _canonical(), _header_score(), _lookup(), mask_identifiers_for_fallback(), _normalise_rows(), _pdf_or_text_rows(), _public_preview(), Any (+17 more)

### Community 1 - "ProviderError"
Cohesion: 0.06
Nodes (52): AIProvider, ProviderConfig, _atomic_json(), ProviderProfileStore, Any, Path, Return runtime material only to the single OFF_AI egress broker., Local provider profiles with API keys encrypted outside SQLite. (+44 more)

### Community 2 - "create_app"
Cohesion: 0.05
Nodes (61): deque, Fernet, create_app(), _decode(), DemoSessionAuth, _encode(), LoginAttemptLimiter, Small, stateless session layer for a single-user demo deployment. (+53 more)

### Community 3 - "gmail.py"
Cohesion: 0.08
Nodes (32): ArgumentParser, _mail_provider(), GmailConnectorManager, Any, Path, Request, Browser-safe Gmail OAuth coordinator. Tokens remain inside the mail module., _env() (+24 more)

### Community 4 - "app.py"
Cohesion: 0.09
Nodes (45): CampaignLocks, _discovery(), _engine(), Path, Request, _read_upload(), _sales(), _settings() (+37 more)

### Community 5 - "OffAIStore"
Cohesion: 0.11
Nodes (10): SQLite schema owned only by OFF_AI Studio., _json(), _loads(), OffAIStore, Any, Connection, date, datetime (+2 more)

### Community 6 - "SalesTracker"
Cohesion: 0.13
Nodes (17): parse_datetime(), _as_date(), _average(), _days_between(), _iso(), _minutes_between(), _month_bounds(), _option_items() (+9 more)

### Community 7 - "norm_text"
Cohesion: 0.12
Nodes (32): attempt_identity_keys(), AttemptLedger, _extract_matches(), _parse_keys(), _person_name(), _pick_historical_match(), Any, Path (+24 more)

### Community 8 - "types.ts"
Cohesion: 0.08
Nodes (35): AIStudio(), formatWhen(), modelLabel(), modelStatus(), SpeechRecognitionEventLike, SpeechRecognitionLike, storedValue(), trustTone() (+27 more)

### Community 9 - "OffAIService"
Cohesion: 0.12
Nodes (23): FastAPI, build_off_ai_router(), ConversationCreate, ConversationUpdate, IntakeCommit, IntakeMode, MessageCreate, MessageRetry (+15 more)

### Community 10 - "run_existing_poi_enrichment"
Cohesion: 0.17
Nodes (27): ExistingPoiEnrichmentConfig, make_existing_poi_run_id(), NoInputFilesError, RuntimeError, Raised when an enrichment run has no explicit or queued input file., Raised before queue claiming when a non-empty run directory already exists., Run the existing-POI enrichment pipeline with crash-safe queue handling.      Qu, run_existing_poi_enrichment() (+19 more)

### Community 11 - "runner.py"
Cohesion: 0.14
Nodes (31): build_existing_poi_final_row(), safe_get(), build_final_row(), _category_progress(), compact_candidate_row(), copy_latest_snapshot(), decision_audit_row(), enrichment_details() (+23 more)

### Community 12 - "existing_poi_enrichment.py"
Cohesion: 0.16
Nodes (28): Counter, _archive_all_failed(), _claim_files(), _decision_stage_counts(), ExistingPoiEnrichmentState, _prepare_run_output_dir(), Path, Existing POI file -> Apollo bulk enrichment pipeline.  This is intentionally sep (+20 more)

### Community 13 - "email_expert.py"
Cohesion: 0.12
Nodes (22): DraftAudit, audit_draft(), _body_word_count(), _chunk_text(), _extract_json_object(), import_expert_documents(), ImportResult, LocalEmailExpert (+14 more)

### Community 14 - "OutreachEngine"
Cohesion: 0.12
Nodes (18): _idempotent(), Any, add_working_days(), campaign_send_window(), _canonical(), _column_lookup(), local_day_bounds(), OutreachEngine (+10 more)

### Community 15 - "discovery.py"
Cohesion: 0.14
Nodes (24): _candidate_record(), _country_from(), CrawlResult, _first_url(), _iter_json_objects(), _person_from_jsonld(), PublicWebCrawler, Any (+16 more)

### Community 16 - "test_discovery.py"
Cohesion: 0.12
Nodes (18): Crawl4AIPageFetcher, CrawlPolicy, DiscoveredPerson, DiscoveryService, PageFetcher, Path, Protocol, RuntimeError (+10 more)

### Community 17 - "SalesTracker.tsx"
Cohesion: 0.10
Nodes (24): buildQuery(), CloserTable(), currentDate(), currentMonth(), formatSalesMoney(), LeadDraft, LeadEditor(), leadInitials() (+16 more)

### Community 18 - "io_utils.py"
Cohesion: 0.15
Nodes (26): _add_run_columns(), _apollo_rejection_identity(), _apollo_rejection_policy(), append_apollo_rejection_ledger(), _append_dedup_csv(), append_exclusion_ledger(), build_analytics_tables(), Any (+18 more)

### Community 19 - "package.json"
Cohesion: 0.07
Nodes (27): dependencies, react, react-dom, devDependencies, @types/react, @types/react-dom, typescript, vite (+19 more)

### Community 20 - "validate_public_url"
Cohesion: 0.17
Nodes (12): canonical_url(), DiscoveryFetchError, _host_matches(), normalize_domain(), ParsedPage, Validate syntax and domain policy without making a network request., Fetch public HTML with SSRF, robots, size, redirect and rate-limit guards., A page could not be fetched under the configured safety policy. (+4 more)

### Community 21 - "service.py"
Cohesion: 0.14
Nodes (12): BrokerResult, OFF_AI Studio, the extractable AI workspace embedded in OFF_CRM., EgressPolicy, PolicyViolation, Any, RuntimeError, Default-deny policy used before every provider call., Apply deterministic PII backstops after the hard-block scanner passes. (+4 more)

### Community 22 - "compilerOptions"
Cohesion: 0.08
Nodes (24): compilerOptions, allowJs, allowSyntheticDefaultImports, esModuleInterop, forceConsistentCasingInFileNames, isolatedModules, jsx, lib (+16 more)

### Community 23 - "BringYourOwnToolRegistry"
Cohesion: 0.21
Nodes (10): CompletedProcess, _atomic_json(), BringYourOwnToolRegistry, Any, Path, RuntimeError, Fetch one immutable public GitHub commit without credentials or submodules., Run a pinned checkout with no network, secrets, host writes, or CRM access. (+2 more)

### Community 24 - "Queue.tsx"
Cohesion: 0.30
Nodes (17): api, idempotencyKey(), Badge(), Button(), Field(), Modal(), PageHeader(), Panel() (+9 more)

### Community 25 - "RunConfig"
Cohesion: 0.15
Nodes (12): Any, OffsetX Apollo search plans mapped exactly to the nine locked CRM categories., SearchCategory, RunConfig, _empty_exclusion(), ManyPeopleApolloClient, Path, test_dry_run_honours_target_count_instead_of_selecting_every_search_result() (+4 more)

### Community 26 - "cli.py"
Cohesion: 0.17
Nodes (13): Namespace, ApolloApiError, ApolloClient, Any, RuntimeError, Thin Apollo API client with retries, fixed-window friendly throttling, and safe, main(), parse_args() (+5 more)

### Community 27 - "ExclusionSet"
Cohesion: 0.16
Nodes (18): build_exclusion_set(), discover_exclusion_files(), ExclusionSet, is_supported_exclusion_file(), norm_domain(), DataFrame, Path, Deduplication and exclusion logic for OffsetX Apollo POI building. (+10 more)

### Community 28 - "OutreachCRMAdapter"
Cohesion: 0.14
Nodes (9): CampaignIntakeParser, Deterministic-first CSV, workbook, PDF and text inspection., _atomic_bytes(), OutreachCRMAdapter, Path, Portable one-way record for Notion or NotebookLM import., Return an owner-only CRM activity export without message bodies.          This m, The only OFF_AI dependency on the existing outreach CRM domain. (+1 more)

### Community 29 - "App.tsx"
Cohesion: 0.16
Nodes (14): AuthenticatedApp(), currentPage(), EMPTY_AUTH, LoginScreen(), navigation, Page, pages, storedValue() (+6 more)

### Community 30 - "input_loader.py"
Cohesion: 0.22
Nodes (14): _alias_lookup(), _canonicalize_header(), _clean_cell(), load_existing_pois(), normalize_input_rows(), Any, DataFrame, Path (+6 more)

### Community 31 - "MemoryService"
Cohesion: 0.23
Nodes (5): MemoryBackend, MemoryService, Any, Protocol, Replaceable boundary for local SQLite today and a tenant service later.

### Community 32 - "test_off_ai.py"
Cohesion: 0.23
Nodes (14): _broker(), _FixedProvider, _profile(), Exception, Path, test_bring_your_own_tool_requires_pinned_github_commit_and_public_input(), test_declared_tier_a_is_downgraded_for_aggregator_or_china_host(), test_email_credentials_mailbox_and_context_requests_are_blocked_before_provider() (+6 more)

### Community 33 - "compilerOptions"
Cohesion: 0.12
Nodes (15): compilerOptions, allowImportingTsExtensions, lib, module, moduleDetection, moduleResolution, noEmit, skipLibCheck (+7 more)

### Community 34 - "useApp"
Cohesion: 0.32
Nodes (13): useApp(), formatDate(), Resource, stageLabel(), useResource(), Campaigns(), Contacts(), Dashboard() (+5 more)

### Community 35 - "EgressBroker"
Cohesion: 0.24
Nodes (6): BrokeredEmailProvider, EgressBroker, _estimate_tokens(), Any, The only runtime path from OFF_CRM to an AI provider., Compatibility adapter for the existing CRM draft engine.

### Community 36 - "Settings.tsx"
Cohesion: 0.21
Nodes (8): ApiError, getToken(), headers(), setToken(), Template, AutomationStatus, MemoryItem, SettingsStatus

### Community 37 - "Connections.tsx"
Cohesion: 0.27
Nodes (9): Connections(), healthTone(), PROVIDER_DEFAULTS, RegisteredTool, retentionLabel(), tierTone(), AIEgressCall, ConnectorsStatus (+1 more)

### Community 38 - "SandboxPolicy"
Cohesion: 0.22
Nodes (5): Build-time and BYO-tool guard. Network is denied unless explicitly designed., SandboxPolicy, Live wall test; enabled only when a pre-pulled Python image is supplied., test_networkless_container_cannot_reach_arbitrary_external_host(), test_sandbox_policy_denies_arbitrary_network_and_builds_networkless_container()

### Community 40 - "score_candidate"
Cohesion: 0.48
Nodes (5): competitor_risk(), Simple explainable scoring for OffsetX POIs., score_candidate(), test_competitor_hold(), test_trade_compliance_scores_high()

## Knowledge Gaps
- **78 isolated node(s):** `name`, `private`, `version`, `type`, `dev` (+73 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `create_app()` connect `create_app` to `test_off_ai.py`, `ProviderError`, `gmail.py`, `app.py`, `SalesTracker`, `OffAIService`, `OutreachEngine`, `test_discovery.py`, `io_utils.py`, `service.py`, `BringYourOwnToolRegistry`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Why does `OutreachStore` connect `OutreachStore` to `gmail.py`, `SalesTracker`, `.__init__`, `email_expert.py`, `OutreachEngine`, `discovery.py`, `test_discovery.py`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._
- **Why does `OffAIStore` connect `OffAIStore` to `test_off_ai.py`, `ProviderError`, `EgressBroker`, `gmail.py`, `OffAIService`, `service.py`, `OutreachCRMAdapter`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `OutreachStore` (e.g. with `ImportResult` and `LocalEmailExpert`) actually correct?**
  _`OutreachStore` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `OffAIStore` (e.g. with `BrokeredEmailProvider` and `BrokerResult`) actually correct?**
  _`OffAIStore` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `name`, `private`, `version` to the rest of the system?**
  _78 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `OutreachStore` be split into smaller, more focused modules?**
  _Cohesion score 0.05867082035306334 - nodes in this community are weakly interconnected._