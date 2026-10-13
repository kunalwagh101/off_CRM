export type ImageAsset = {
  id: string;
  brief_id: string;
  campaign_id: string;
  provider_id: string;
  model_id: string;
  width: number;
  height: number;
  bytes: number;
  media_type: string;
  status: "pending" | "approved" | "rejected" | "gate_failed";
};

export type ImageGeneratorStat = {
  provider_id: string;
  model_id: string;
  shown: number;
  approved: number;
  rejected: number;
  gate_failed: number;
  decided: number;
  approval_rate: number;
};

export type ImageSummary = {
  campaign_id: string;
  briefs: number;
  briefs_open: number;
  assets: { pending: number; approved: number; rejected: number; gate_failed: number };
  generators: ImageGeneratorStat[];
  min_decisions_to_judge: number;
};

export type CampaignKind = {
  id: string;
  label: string;
  unit: string;
  runner: string;
  implemented: boolean;
  summary: string;
  /** What is still missing. Only set when implemented is false. */
  missing: string;
  uses_email_columns: boolean;
};

export type Campaign = {
  id: string;
  name: string;
  kind: string;
  status: "active" | "paused" | "archived";
  daily_send_limit: number;
  timezone: string;
  approval_mode: string;
  followup1_working_days: number;
  followup2_working_days: number;
  variants: string[];
  contact_count?: number;
  replied_count?: number;
  sent_count?: number;
  updated_at: string;
  send_window_start: string;
  send_window_end: string;
  send_weekdays: number[];
  experiment_hypothesis: string;
  experiment_metric: "reply_rate";
  experiment_min_sample: number;
  control_variant: string;
};

export type AuthSession = {
  configured: boolean;
  authenticated: boolean;
  username: string;
  expires_at: number | null;
};

export type Contact = {
  id: string;
  campaign_id: string;
  full_name: string;
  email: string;
  company: string;
  title: string;
  category: string;
  route: string;
  status: string;
  variant_id: string;
  checkbox: boolean;
  public_hook: string;
  hook_source: string;
  next_action_at?: string;
  current_stage: string;
  sent_count: number;
  poi_response?: string;
  notes?: string;
  linkedin_url?: string;
  recipient_timezone?: string;
  outcome_label?: string;
};

export type DraftAudit = {
  score: number;
  errors: string[];
  warnings: string[];
  checks: Record<string, unknown>;
  sendable: boolean;
};

export type Draft = {
  id: string;
  campaign_contact_id: string;
  full_name: string;
  email: string;
  company: string;
  category: string;
  stage: "initial" | "followup1" | "followup2";
  variant_id: string;
  subject: string;
  body: string;
  quality_score: number;
  sendable: boolean;
  approval_status: string;
  audit: DraftAudit;
  retrieval_refs: string[];
  send_error?: string;
  scheduled_at?: string;
  generation_meta: {
    mode?: string;
    provider_profile_id?: string;
    provider_attempts?: Array<Record<string, unknown>>;
    memory_refs?: string[];
  };
};

export type QueueItem = {
  campaign_contact_id: string;
  full_name: string;
  email: string;
  company: string;
  status: string;
  current_stage: string;
  next_action_at?: string;
  draft_id?: string;
  draft_stage?: string;
  approval_status?: string;
  quality_score?: number;
  sendable: boolean;
  is_due: boolean;
  effective_due_at?: string;
  scheduled_at?: string;
  generation_meta?: Record<string, unknown>;
};

export type EmailIdentity = {
  id: string;
  name: string;
  provider_type: "local" | "gmail" | "ses";
  stream: "permission_marketing" | "targeted_outreach" | "transactional";
  from_email: string;
  reply_to: string;
  aws_region: string;
  configuration_set: string;
  status: "active" | "paused" | "archived";
  provider_verified: boolean;
  spf_status: "pass" | "fail" | "unknown";
  dkim_status: "pass" | "fail" | "unknown";
  dmarc_status: "pass" | "fail" | "unknown";
  alignment_status: "pass" | "fail" | "unknown";
  last_checked_at?: string;
};

export type EmailCampaignSettings = {
  campaign_id: string;
  stream: EmailIdentity["stream"];
  provider_type: EmailIdentity["provider_type"];
  identity_id: string | null;
  daily_limit: number;
  frequency_cap_days: number;
  frequency_cap_max: number;
  require_unsubscribe: boolean;
  auto_pause_enabled: boolean;
  health_sample_size: number;
  max_hard_bounce_rate: number;
  max_complaint_rate: number;
  paused_reason: string;
  updated_at?: string;
};

export type EmailPreflight = {
  campaign_id: string;
  allowed: number;
  blocked: number;
  evaluated: number;
  blocker_counts: Record<string, number>;
  items: Array<{
    campaign_contact_id: string;
    draft_id: string;
    email: string;
    allowed: boolean;
    blockers: Array<{ code: string; message: string; field: string }>;
    warnings: Array<{ code: string; message: string; field: string }>;
  }>;
};

export type EmailHealth = {
  campaign_id: string;
  accepted: number;
  delivered: number;
  hard_bounces: number;
  complaints: number;
  deferred: number;
  hard_bounce_rate: number;
  complaint_rate: number;
  sample_required: number;
  enough_data: boolean;
  breached: string[];
  status: "insufficient_data" | "healthy" | "review" | "paused";
  paused_reason: string;
};

export type EmailJob = {
  id: string;
  campaign_id: string;
  to_email: string;
  full_name: string;
  company: string;
  provider_type: string;
  stream: string;
  status: string;
  attempt_count: number;
  last_error: string;
  created_at: string;
};

export type EmailSuppression = {
  email: string;
  active: boolean;
  reason: string;
  source: string;
  updated_at: string;
};

export type Paginated<T> = {
  items: T[];
  total: number;
  limit?: number;
  offset?: number;
};

export type SalesLeadStatus =
  | "new"
  | "proposal"
  | "deposit"
  | "follow_up_ongoing"
  | "meeting_follow_up"
  | "won"
  | "lost";

export type SalesLead = {
  id: string;
  lead_name: string;
  company: string;
  email: string;
  phone: string;
  source: string;
  setter_name: string;
  closer_name: string;
  lead_status: SalesLeadStatus;
  lead_status_label: string;
  date_created: string;
  first_contact_at: string | null;
  date_meeting_booked: string | null;
  meeting_at: string | null;
  meeting_status: string;
  meeting_status_label: string;
  offer_made: boolean;
  sale_type: string;
  sale_type_label: string;
  loss_reason: string;
  loss_reason_label: string;
  deposit_amount: number;
  deposit_received_at: string | null;
  total_deal_value: number;
  cash_collected: number;
  date_paid_in_full: string | null;
  refund_clawback_amount: number;
  commission_percent: number;
  earnings: number;
  net_revenue: number;
  last_touch_at: string | null;
  notes: string;
  position: number;
  revision: number;
  follow_up_age_days: number;
  booking_lag_days: number | null;
  deposit_age_days: number;
  follow_up_aging: boolean;
  booking_lag_alert: boolean;
  deposit_unpaid_alert: boolean;
  leak_flags: Array<"booking_lag" | "follow_up_aging" | "deposit_unpaid">;
  created_at: string;
  updated_at: string;
};

export type SalesOption = { value: string; label: string };

export type SalesMeta = {
  statuses: SalesOption[];
  meeting_statuses: SalesOption[];
  sale_types: SalesOption[];
  loss_reasons: SalesOption[];
  setters: string[];
  closers: string[];
  reps: string[];
  sources: string[];
  currency_default: string;
};

export type SalesBoard = {
  columns: Array<{
    status: SalesLeadStatus;
    label: string;
    items: SalesLead[];
    count: number;
    pipeline_value: number;
  }>;
  total: number;
  leaks: SalesLeaks;
};

export type SalesLeaks = {
  follow_up_aging: number;
  booking_lag: number;
  deposit_unpaid: number;
  total: number;
};

export type SetterMetric = {
  rep_name: string;
  dials_dms_sent: number;
  conversations: number;
  conversations_to_booked_rate: number;
  speed_to_lead_minutes: number;
  booking_lag_days: number;
  calls_scheduled: number;
  calls_taken: number;
  declines: number;
  cancels: number;
  no_shows: number;
  rescheduled: number;
  show_up_rate: number;
  dq_rate: number;
  dq_count: number;
};

export type CloserMetric = {
  rep_name: string;
  calls_taken: number;
  offers_made: number;
  offer_rate: number;
  sales: number;
  close_rate: number;
  close_rate_on_offers: number;
  one_call_sales: number;
  follow_up_sales: number;
  average_deal_size: number;
  revenue_per_call: number;
  revenue_generated: number;
  follow_up_aging: number;
};

export type SalesMoney = {
  deposits: number;
  deposit_count: number;
  total_sales: number;
  revenue_generated: number;
  cash_collected: number;
  deposit_to_paid_in_full_rate: number;
  average_days_to_collect: number;
  refunds_clawbacks: number;
  net_revenue: number;
  revenue_goal: number;
  cash_goal: number;
  currency: string;
  goal_month: string;
  goal_completion_percent: number;
  cash_goal_completion_percent: number;
  commissions_total: number;
  commissions_by_rep: Array<{ rep_name: string; earnings: number }>;
};

export type SalesDashboard = {
  filters: { start_date: string; end_date: string; rep_name: string; source: string; search: string; date_basis: string };
  lead_count: number;
  setter_summary: SetterMetric;
  setter_metrics: SetterMetric[];
  closer_summary: CloserMetric;
  closer_metrics: CloserMetric[];
  money: SalesMoney;
  loss_reasons: Array<{ reason: string; label: string; count: number; percent: number }>;
  leaks: SalesLeaks;
};

export type SalesProjectionScenario = {
  name: "worst" | "expected" | "best";
  meetings: number;
  projected_shows: number;
  projected_offers: number;
  projected_sales: number;
  incremental_revenue: number;
  incremental_cash: number;
  end_of_month_revenue: number;
  end_of_month_cash: number;
};

export type SalesProjection = {
  forecast_month: string;
  history_start: string;
  history_end: string;
  rep_name: string;
  source: string;
  current_revenue: number;
  current_cash: number;
  currency: string;
  revenue_goal: number;
  assumptions: Record<string, number>;
  assumption_sources: Record<string, string>;
  samples: Record<string, number>;
  defaults_used: string[];
  scenarios: SalesProjectionScenario[];
};

export type DiscoveryRun = {
  id: string;
  campaign_id: string;
  status: "running" | "completed" | "partial" | "failed";
  engine: string;
  objective_prompt: string;
  target_count: number;
  plan: {
    objective?: string;
    role_groups?: string[];
    source_adapters?: string[];
    blocked_requirements?: string[];
    collect_social_handles?: boolean;
    collect_interactions?: boolean;
  };
  seed_urls: string[];
  allowed_domains: string[];
  category: string;
  max_pages: number;
  max_depth: number;
  obey_robots: boolean;
  pages_crawled: number;
  candidates_found: number;
  fresh_count: number;
  excluded_count: number;
  errors: Array<{ url?: string; error: string }>;
  created_at: string;
};

export type DiscoveryCandidate = {
  id: string;
  run_id: string;
  full_name: string;
  first_name: string;
  last_name: string;
  email: string;
  company: string;
  company_domain: string;
  title: string;
  category: string;
  country: string;
  linkedin_url: string;
  source_url: string;
  public_hook: string;
  confidence: number;
  status: "new" | "approved" | "rejected" | "excluded" | "apollo_queued" | "imported";
  exclusion_reason: string;
  evidence: Record<string, unknown>;
  source_data?: Record<string, unknown>;
};

export type ResearchEntity = {
  id: string;
  entity_type: string;
  name: string;
  properties: Record<string, unknown>;
  confidence: number;
  source_count: number;
};

export type ResearchEdge = {
  id: string;
  source_entity_id: string;
  target_entity_id: string;
  relation_type: string;
  properties: Record<string, unknown>;
  confidence: number;
  evidence_url: string;
};

export type ResearchGraph = {
  nodes: ResearchEntity[];
  edges: ResearchEdge[];
  stats: {
    nodes: number;
    edges: number;
    by_type: Record<string, number>;
    by_relation: Record<string, number>;
  };
};

export type ApolloRejection = {
  identity: string;
  run_id: string;
  decision: string;
  reason: string;
  outcome_class: string;
  retry_policy: string;
  blocks_automatic_retry: boolean;
  permanent_exclusion: boolean;
  apollo_person_id: string;
  email: string;
  full_name: string;
  company: string;
  title: string;
  linkedin_url: string;
  last_seen_at: string;
  occurrence_count: number;
};

export type ApolloExclusion = {
  apollo_person_id: string;
  email: string;
  full_name: string;
  company: string;
  title: string;
  linkedin_url: string;
  source: string;
};

export type DashboardStats = {
  active_campaigns: number;
  total_contacts: number;
  replies: number;
  sent: number;
  pending_review: number;
  due_now: number;
  reply_rate: number;
};

export type VideoSummary = {
  campaign_id: string;
  projects: number;
  total_duration_seconds: number;
  renders: number;
  renders_passed: number;
  renders_failed: number;
};

export type VideoProjectRow = {
  id: string;
  name: string;
  width: number;
  height: number;
  fps: string;
  duration_ticks: number;
  version: number;
  updated_at: string;
};

export type SettingsStatus = {
  storage: string;
  /** Where the CRM is, safe to show: never with a password. */
  database: string;
  /** The CRM's own file; empty when the CRM is in a hosted database. */
  database_path: string;
  api_token_enabled: boolean;
  gmail_configured: boolean;
  own_email: string;
  local_outbox: string;
  expert_sources: Record<string, number>;
  provider_profiles: number;
  automation: AutomationStatus;
  memory: MemoryStats;
};

export type ProviderProfile = {
  id: string;
  owner: string;
  name: string;
  provider_type: "openai" | "anthropic" | "openai_compatible" | "template_engine_http" | "local_command";
  model: string;
  api_key_env: string;
  base_url: string;
  timeout_seconds: number;
  priority: number;
  enabled: boolean;
  has_stored_secret: boolean;
  credential_source: "encrypted_local" | "none";
  /** Recorded by the server from the login that saved it; older profiles wait for the owner (D-166). */
  owner_confirmed: boolean;
  /** For a waiting profile: where Confirm suggests it goes — "local" is the owner (D-190). */
  confirm_to?: string;
  /** For a waiting profile: every place Confirm may put it, the suggestion first (D-194). */
  confirm_options?: string[];
  data_policy: "minimal" | "standard" | "full";
  audit_payloads: boolean;
  fallback_strategy: "priority" | "round_robin" | "parallel";
  last_health_status: string;
  last_checked_at: string;
  last_error: string;
};

export type AutomationStatus = {
  enabled: boolean;
  mode: "local" | "gmail";
  interval_seconds: number;
  max_messages_per_campaign: number;
  sync_replies_first: boolean;
  gmail_live_authorized: boolean;
  running: boolean;
  last_run_at: string;
  last_error: string;
  last_results: Array<Record<string, unknown>>;
};

export type MemoryStats = {
  backend: string;
  workspace_id: string;
  total: number;
  approved: number;
  by_kind: Record<string, number>;
};

export type MemoryItem = {
  id: string;
  scope: string;
  kind: string;
  content: string;
  tags: string[];
  metadata: Record<string, unknown>;
  confidence: number;
  approved: boolean;
  source_type: string;
  created_at: string;
};

/** The profile list, with how many old profiles wait for the install owner (D-177). */
export type ProviderProfileList = Paginated<ProviderProfile> & { waiting: number };

export type ProviderCall = {
  id: string;
  workspace_id: string;
  profile_id: string;
  provider_type: string;
  model: string;
  data_policy: string;
  status: string;
  request: Record<string, unknown>;
  response: Record<string, unknown>;
  error: string;
  duration_ms: number;
  created_at: string;
};

export type NotionStatus = {
  connected: boolean;
  workspace_name: string;
  contacts_database_id: string;
  sales_database_id: string;
};

export type NotionDatabase = { id: string; title: string };

export type NotionExportResult = {
  created: number;
  updated: number;
  failed: number;
  failures: Array<{ row: string; error: string }>;
  skipped_fields: string[];
};

// ── AI module ──────────────────────────────────────────────────────────────
// Shapes served by the config-driven provider registry. Nothing here is a
// hardcoded provider list: the backend reads config/providers.yaml, so adding a
// provider is a config edit and this file does not change.

export type AIModel = {
  id: string;
  context_window: number;
  cost_per_1m_input_usd: number;
  cost_per_1m_output_usd: number;
  good_at: string[];
  is_free: boolean;
  model_origin: string;
  model_origin_tier_cap: string;
  /** "chat" writes text, "image" draws pictures. Different endpoints. */
  kind: string;
  is_image: boolean;
};

export type ProviderBalance = {
  provider_id: string;
  supported: boolean;
  source?: "provider_reported";
  kind?: "account_balance" | "key_spend_limit";
  available?: boolean;
  remaining?: string | null;
  unit?: string;
  checked_at?: string;
  description?: string;
  reason?: string;
};

export type AIUsage = {
  provider_id: string;
  minute_used: number;
  minute_limit: number;
  day_used: number;
  day_limit: number;
  day_spend_usd: number;
  day_spend_cap_usd: number;
  source: string;
  exhausted: boolean;
};

export type AITrustDecision = { tier: string; reason: string; decided_by: string; decided_at: string };

export type AIOverride = {
  provider_id: string;
  trust_tier: string;
  data_policy: string;
  allow_above_ceiling: boolean;
  reason: string;
  decided_by: string;
  decided_at: string;
  // Trust set on the trust route (S-06.02.33), kept with its reason, who and when.
  trust_reason?: string;
  trust_decided_by?: string;
  trust_decided_at?: string;
  model_tiers?: Record<string, AITrustDecision>;
};

export type AIProviderRow = {
  id: string;
  name: string;
  flag: string;
  jurisdiction: string;
  adapter: string;
  base_url: string;
  default_model: string;
  models: AIModel[];
  retention: string;
  trains_on_input: boolean;
  is_aggregator: boolean;
  local_only: boolean;
  self_hostable: boolean;
  self_host_note: string;
  key_url: string;
  key_placeholder: string;
  how_to_get: string;
  verified_on: string;
  free_tier: { requests_per_minute: number; requests_per_day: number; notes: string } | null;
  trust_tier: string;
  trust_tier_source: string;
  policy_ceiling: string;
  default_policy: string;
  permitted_data_classes: string[];
  receives_nothing: boolean;
  connected: boolean;
  enabled: boolean;
  has_key: boolean;
  model_id: string;
  data_policy: string;
  effective_tier: string;
  override: AIOverride | null;
  requests_per_minute: number;
  requests_per_day: number;
  max_spend_usd_per_day: number;
  usage?: AIUsage | null;
  usage_report: "none" | "balance_endpoint" | "rate_limit_headers";
  /** One key reaches many models. These are the ones turned on. */
  model_ids: string[];
  supports_model_discovery: boolean;
  /** Every model in config for this provider, each with its own tier. */
  available_models: Array<AIModel & { tier: string; default_tier?: string }>;
  /** The provider's tier before any owner setting. */
  default_tier?: string;
  /** Every model trust can be set for: config's, plus any switched on from the live catalogue. */
  trust_models?: Array<{ id: string; tier: string; default_tier: string }>;
  /** What is sent now: the stored choice, cut to the ceiling the owner's trust sets. */
  sends?: string;
  /** Whether the owner's full-data grant decides what is sent now. */
  grant_active?: boolean;
  /** Why the grant is, or is not, in force: "", active, provider_lowered, provider_blocked, no_model. */
  grant_state?: string;
  /** Whether a grant now would change what is sent — the server's own refusal rule. */
  grant_offer?: boolean;
  /** True when the switched-on models are sent different levels; `sends` is the most. */
  sends_varies?: boolean;
  /** True when every switched-on model is blocked, so none is sent anything. */
  sends_nothing?: boolean;
  /** The most "How much to send" can be: the ceiling at the default or the owner's raise. */
  standing_ceiling?: string;
};

export type DiscoveredModel = {
  id: string;
  origin: string;
  tier: string;
  tier_cap: string;
  known: boolean;
  in_config: boolean;
  matched_prefix: string;
  usable: boolean;
  policy_ceiling: string;
};

export type DiscoveryResult = {
  provider_id: string;
  provider_name: string;
  models: DiscoveredModel[];
  source: string;
  note: string;
  error: string;
  total: number;
  usable: number;
  unknown: number;
};

export type AIProvidersPayload = {
  workspace_id: string;
  positioning_line: string;
  owner_domains: string[];
  owner_addresses: string[];
  mailbox_unlocked: boolean;
  mailbox_unlock_phrase_required: string;
  providers: AIProviderRow[];
  policy_levels: Array<{ value: string; label: string; description: string }>;
  tiers: Array<{ tier: string; label: string; policy_ceiling: string }>;
};

export type EgressLogRow = {
  id: string;
  created_at: string;
  provider_id: string;
  provider_name: string;
  model_id: string;
  jurisdiction: string;
  tier: string;
  policy: string;
  data_class: string;
  task_type: string;
  status: string;
  error: string;
  duration_ms: number;
  payload_summary: { fields?: string[]; recipient_fields?: string[]; character_count?: number };
};

export type EgressLogEntry = EgressLogRow & {
  payload: Record<string, unknown>;
  response_text: string;
  findings: Array<{ kind: string; detail: string; location?: string; sample?: string }>;
};

export type EgressStats = {
  calls: number;
  blocked: number;
  failed: number;
  by_tier: Array<{ tier: string; calls: number }>;
  by_provider: Array<{ provider_id: string; provider_name: string; jurisdiction: string; calls: number }>;
};

/** Alias so pages can read the /status shape under an AI-facing name. */
export type StatusPayload = SettingsStatus;

export type AIModeInfo = {
  value: "simple" | "compare" | "orchestrated";
  label: string;
  description: string;
  available: boolean;
  blocked_reason: string;
};

export type AIModesPayload = {
  modes: AIModeInfo[];
  connected_count: number;
  planner_provider_ids: string[];
  usage: AIUsage[];
};

export type AIBranch = {
  provider_id: string;
  provider_name: string;
  model_id: string;
  jurisdiction: string;
  tier: string;
  policy: string;
  flag: string;
  text: string;
  error: string;
  duration_ms: number;
  payload_fields: string[];
  log_id: string;
  estimated_cost_usd: number;
  ok: boolean;
};

export type AIPlanStep = {
  index: number;
  title: string;
  instructions: string;
  data_class: string;
  tags: string[];
  assigned_provider_id: string;
  assigned_provider_name: string;
  text: string;
  error: string;
  duration_ms: number;
  log_id: string;
  ok: boolean;
};

export type AIRunResult = {
  mode: string;
  data_class: string;
  branches: AIBranch[];
  steps: AIPlanStep[];
  planner_provider_id: string;
  planner_provider_name: string;
  planner_tier: string;
  excluded: Array<{ provider_id: string; reason: string; detail?: string }>;
  total_duration_ms: number;
  notes: string[];
  best_text: string;
};

/** The product, described once — `offsetx_apollo_builder/gtm/products.py`. */
export type GtmProduct = {
  id: string;
  workspace_id: string;
  name: string;
  one_liner: string;
  audience: string;
  problem: string;
  outcome: string;
  offer: string;
  proof: string[];
  differentiators: string[];
  forbidden_claims: string[];
  voice: string;
  website: string;
  version: number;
  created_at: string;
  updated_at: string;
};

/** One campaign a product speaks for. `exists` is false once it is deleted. */
export type GtmProductLink = {
  campaign_id: string;
  name: string;
  kind: string;
  exists: boolean;
};

/** Capacity a plan is fitted inside — `gtm/strategy.py` `Envelope`. */
export type GtmEnvelope = {
  email_identities: number;
  email_unverified: string[];
  email_daily_capacity: number;
  per_identity_daily_cap: number;
  platforms: string[];
  post_daily_capacity: number;
  apollo_ready: boolean;
  blockers: string[];
};

export type GtmDescribe = {
  envelope: GtmEnvelope;
  vocabulary: {
    kinds: string[];
    goal_kinds: string[];
    sources: string[];
    company_sizes: string[];
    platforms: string[];
    recipe_families: string[];
    roles: string[];
    weekdays: string[];
  };
  defaults: { assumed_reply_rate: number; per_identity_daily_cap: number; horizon_days: number };
};

export type GtmChannel = {
  kind: string;
  role: string;
  angle: string;
  hypothesis: string;
  daily_volume?: number;
  send_window?: string[];
  weekdays?: string;
  timezone?: string;
  stream?: string;
  platforms?: string[];
  recipe_family?: string;
};

export type GtmPlan = {
  id: string;
  product_id: string;
  root_id: string;
  parent_id: string;
  version: number;
  status: "draft" | "applied" | "superseded" | "discarded";
  source: "model" | "rules";
  provider_id: string;
  model_id: string;
  policy: string;
  created_at: string;
  applied_at: string | null;
  product_version: number;
  product_stale: boolean;
  product_deleted: boolean;
  request: {
    goal_kind: string;
    goal_target: number;
    horizon_days: number;
    contact_budget: number;
    channels: string[];
    assumed_reply_rate: number;
    per_identity_daily_cap: number;
  };
  product_snapshot: GtmProduct;
  envelope: GtmEnvelope;
  plan: {
    summary: string;
    audience: {
      description: string;
      source: string;
      titles: string[];
      industries: string[];
      company_sizes: string[];
      regions: string[];
    };
    channels: GtmChannel[];
  };
  feasibility: { kind: string; feasible: boolean | null; explanation: string };
  notes: string[];
  /** The latest review, or null before the first one. */
  review?: GtmReview | null;
  /** What the line's campaigns had already done when this version was applied. */
  baseline?: { email?: { campaign_id?: string; contacted: number; replied: number } };
};

export type GtmNextStep = { page: string; label: string; why: string };

export type GtmFinding = {
  channel: string;
  campaign_id: string;
  code: string;
  sentence: string;
  permitted: string[];
  numbers: Record<string, unknown>;
};

export type GtmRemedy = {
  channel: string;
  campaign_id: string;
  finding: string;
  action: string;
  why: string;
  proposal: string;
  /** The screen that does it, or "" when it belongs in the next version of the plan. */
  page: string;
  label: string;
};

export type GtmReview = {
  id: string;
  plan_id: string;
  summary: string;
  source: "model" | "rules";
  provider_id: string;
  model_id: string;
  policy: string;
  created_at: string;
  measurements: Array<Record<string, unknown> & { channel: string; campaign_id: string }>;
  findings: GtmFinding[];
  remedies: GtmRemedy[];
  notes: string[];
};

export type GtmApplyResult = {
  plan: GtmPlan;
  campaigns: Array<{ kind: string; campaign_id: string; action: "created" | "updated" | "left archived" }>;
  next_steps: GtmNextStep[];
  notes: string[];
};
