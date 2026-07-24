export type Campaign = {
  id: string;
  name: string;
  status: "active" | "paused" | "archived";
  daily_send_limit: number;
  timezone: string;
  approval_mode: string;
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

export type SettingsStatus = {
  storage: string;
  database_path: string;
  api_token_enabled: boolean;
  gmail_configured: boolean;
  own_email: string;
  local_outbox: string;
  expert_sources: Record<string, number>;
  provider_profiles: number;
  off_ai?: Record<string, number>;
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
  credential_source: "encrypted_local" | "environment" | "none";
  data_policy: "minimal" | "standard" | "full";
  audit_payloads: boolean;
  fallback_strategy: "priority" | "round_robin" | "parallel";
  jurisdiction: string;
  retention_policy: "unknown" | "no_training_no_retention" | "no_training_limited_retention" | "may_train";
  trust_tier: "A" | "B" | "C" | "D";
  effective_trust_tier?: "A" | "B" | "C" | "D";
  host_origin: string;
  model_origin: string;
  model_origin_jurisdiction: string;
  model_origin_input_isolation_verified: boolean;
  terms_checked_at: string;
  rpm_limit: number;
  rpd_limit: number;
  context_window: number;
  input_cost_per_million: number;
  output_cost_per_million: number;
  daily_cost_cap: number;
  monthly_cost_cap: number;
  allowed_task_types: string[];
  fallback_profile_ids: string[];
  public_tasks_enabled: boolean;
  ai_eligible?: boolean;
  task_eligibility?: Record<string, boolean>;
  task_blockers?: Record<string, string[]>;
  usage?: {
    last_minute_requests: number;
    today: { requests: number; input_tokens: number; output_tokens: number; estimated_cost: number };
    month: { requests: number; input_tokens: number; output_tokens: number; estimated_cost: number };
  };
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

export type ProviderCall = {
  id: string;
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

export type AIProject = {
  id: string;
  name: string;
  description: string;
  instructions: string;
  archived: boolean;
  conversation_count: number;
  created_at: string;
  updated_at: string;
};

export type AIConversation = {
  id: string;
  project_id: string;
  project_name: string;
  title: string;
  selected_profile_id: string;
  task_type: "public_general";
  data_class: "public";
  pinned: boolean;
  archived: boolean;
  message_count: number;
  last_message: string;
  created_at: string;
  updated_at: string;
};

export type AIMessage = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  status: "sending" | "complete" | "blocked" | string;
  provider_profile_id: string;
  model: string;
  trust_tier: string;
  egress_call_id: string;
  egress_approved: boolean;
  retry_of_message_id: string;
  attachments: Array<Record<string, unknown>>;
  created_at: string;
  updated_at: string;
};

export type AIModel = ProviderProfile;

export type AIBootstrap = {
  projects: AIProject[];
  conversations: AIConversation[];
  conversation_total: number;
  models: AIModel[];
  stats: Record<string, number>;
  defaults: {
    public_positioning: string;
    task_type: "public_general";
    data_class: "public";
  };
  privacy: {
    models_pull_data: false;
    email_addresses_leave: false;
    mailbox_access: false;
    context_store_access: false;
  };
};

export type AIContextState = {
  id: string;
  scope_type: string;
  scope_id: string;
  current_task: string;
  rolling_summary: string;
  done: string[];
  pending: string[];
  entity_facts: Record<string, unknown>;
  decisions: Array<Record<string, unknown>>;
  constraints: Array<Record<string, unknown> | string>;
  updated_at: string;
};

export type AIEgressCall = {
  id: string;
  conversation_id: string;
  message_id: string;
  profile_id: string;
  provider_name: string;
  provider_type: string;
  model: string;
  trust_tier: string;
  jurisdiction: string;
  retention_policy: string;
  task_type: string;
  data_class: string;
  status: string;
  payload: Record<string, unknown>;
  response_text: string;
  blocked_reasons: string[];
  error: string;
  input_tokens: number;
  output_tokens: number;
  estimated_cost: number;
  duration_ms: number;
  created_at: string;
  completed_at: string;
};

export type AIIntake = {
  id: string;
  attachment_id: string;
  conversation_id: string;
  status: "inspecting" | "ready" | "needs_choice" | "failed" | "committed";
  detected_mode: "" | "generate" | "parse_send";
  selected_mode: "" | "generate" | "parse_send";
  ambiguous: boolean;
  mapping: Record<string, string>;
  public_preview: {
    columns?: string[];
    rows?: Array<Record<string, string>>;
    row_count?: number;
    errors?: Array<Record<string, unknown> | string>;
    warnings?: string[];
    commit_result?: Record<string, unknown>;
  };
  template_text: string;
  public_positioning: string;
  campaign_id: string;
  error: string;
  created_at: string;
  updated_at: string;
};

export type ConnectorsStatus = {
  gmail: {
    configured: boolean;
    connected: boolean;
    account: string;
    scopes: string[];
    token_location: string;
    ai_access: false;
    reply_sync_boundary: string;
  };
  ai_providers: AIModel[];
};

export type NotionStatus = {
  connected: boolean;
  workspace_name: string;
  contacts_database_id: string;
  sales_database_id: string;
};

export type NotionDatabase = {
  id: string;
  title: string;
};

export type NotionExportResult = {
  created: number;
  updated: number;
  failed: number;
  failures: Array<{ row: string; error: string }>;
  skipped_fields: string[];
};
