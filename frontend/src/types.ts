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
};

export type Paginated<T> = {
  items: T[];
  total: number;
  limit?: number;
  offset?: number;
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
};
