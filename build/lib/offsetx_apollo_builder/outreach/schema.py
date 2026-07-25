SCHEMA_VERSION = 7


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS contacts (
    id TEXT PRIMARY KEY,
    identity_key TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    first_name TEXT NOT NULL DEFAULT '',
    last_name TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    company TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    route TEXT NOT NULL DEFAULT '',
    linkedin_url TEXT NOT NULL DEFAULT '',
    public_hook TEXT NOT NULL DEFAULT '',
    hook_source TEXT NOT NULL DEFAULT '',
    hook_date TEXT NOT NULL DEFAULT '',
    tension TEXT NOT NULL DEFAULT '',
    identity_line TEXT NOT NULL DEFAULT '',
    contribution TEXT NOT NULL DEFAULT '',
    questions_json TEXT NOT NULL DEFAULT '[]',
    notes TEXT NOT NULL DEFAULT '',
    source_ref TEXT NOT NULL DEFAULT '',
    source_json TEXT NOT NULL DEFAULT '{}',
    recipient_timezone TEXT NOT NULL DEFAULT '',
    outcome_label TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_email_ci
ON contacts(lower(email)) WHERE email <> '';
CREATE INDEX IF NOT EXISTS idx_contacts_company ON contacts(company);
CREATE INDEX IF NOT EXISTS idx_contacts_category ON contacts(category);

CREATE TABLE IF NOT EXISTS campaigns (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    daily_send_limit INTEGER NOT NULL CHECK(daily_send_limit > 0),
    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    followup1_working_days INTEGER NOT NULL DEFAULT 4,
    followup2_working_days INTEGER NOT NULL DEFAULT 6,
    approval_mode TEXT NOT NULL DEFAULT 'each_message',
    variants_json TEXT NOT NULL DEFAULT '["A", "B"]',
    status TEXT NOT NULL DEFAULT 'active',
    send_window_start TEXT NOT NULL DEFAULT '00:00',
    send_window_end TEXT NOT NULL DEFAULT '00:00',
    send_weekdays_json TEXT NOT NULL DEFAULT '[0, 1, 2, 3, 4, 5, 6]',
    experiment_hypothesis TEXT NOT NULL DEFAULT '',
    experiment_metric TEXT NOT NULL DEFAULT 'reply_rate',
    experiment_min_sample INTEGER NOT NULL DEFAULT 40,
    control_variant TEXT NOT NULL DEFAULT 'A',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(status, updated_at);

CREATE TABLE IF NOT EXISTS campaign_contacts (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    contact_id TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    variant_id TEXT NOT NULL DEFAULT 'A',
    status TEXT NOT NULL DEFAULT 'new',
    current_stage TEXT NOT NULL DEFAULT '',
    next_action_at TEXT,
    replied_at TEXT,
    stopped_reason TEXT NOT NULL DEFAULT '',
    poi_response TEXT NOT NULL DEFAULT '',
    meeting_transcript TEXT NOT NULL DEFAULT '',
    checkbox INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(campaign_id, contact_id)
);

CREATE INDEX IF NOT EXISTS idx_campaign_contacts_due
ON campaign_contacts(campaign_id, status, next_action_at);
CREATE INDEX IF NOT EXISTS idx_campaign_contacts_variant
ON campaign_contacts(campaign_id, variant_id);

CREATE TABLE IF NOT EXISTS drafts (
    id TEXT PRIMARY KEY,
    campaign_contact_id TEXT NOT NULL REFERENCES campaign_contacts(id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    variant_id TEXT NOT NULL,
    template_id TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    quality_score INTEGER NOT NULL DEFAULT 0,
    sendable INTEGER NOT NULL DEFAULT 0,
    audit_json TEXT NOT NULL DEFAULT '{}',
    retrieval_refs_json TEXT NOT NULL DEFAULT '[]',
    approval_status TEXT NOT NULL DEFAULT 'pending',
    approved_at TEXT,
    sent_at TEXT,
    sending_started_at TEXT,
    send_error TEXT NOT NULL DEFAULT '',
    revision INTEGER NOT NULL DEFAULT 1,
    scheduled_at TEXT,
    generation_meta_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(campaign_contact_id, stage)
);

CREATE INDEX IF NOT EXISTS idx_drafts_approval ON drafts(approval_status, stage);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    campaign_contact_id TEXT NOT NULL REFERENCES campaign_contacts(id) ON DELETE CASCADE,
    draft_id TEXT REFERENCES drafts(id) ON DELETE SET NULL,
    stage TEXT NOT NULL,
    direction TEXT NOT NULL,
    provider_message_id TEXT NOT NULL DEFAULT '',
    thread_id TEXT NOT NULL DEFAULT '',
    internet_message_id TEXT NOT NULL DEFAULT '',
    idempotency_key TEXT NOT NULL DEFAULT '',
    from_email TEXT NOT NULL DEFAULT '',
    to_email TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    sent_at TEXT,
    received_at TEXT,
    raw_json TEXT NOT NULL DEFAULT '{}',
    variant_id TEXT NOT NULL DEFAULT '',
    template_id TEXT NOT NULL DEFAULT '',
    draft_revision INTEGER NOT NULL DEFAULT 0,
    ai_provider_profile_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_provider_id
ON messages(provider_message_id) WHERE provider_message_id <> '';
CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_idempotency
ON messages(idempotency_key) WHERE idempotency_key <> '';
CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_messages_sent ON messages(sent_at);

CREATE TABLE IF NOT EXISTS campaign_events (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    campaign_contact_id TEXT REFERENCES campaign_contacts(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_campaign
ON campaign_events(campaign_id, created_at DESC);

CREATE TABLE IF NOT EXISTS email_templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '*',
    route TEXT NOT NULL DEFAULT '*',
    stage TEXT NOT NULL,
    variant_id TEXT NOT NULL DEFAULT 'A',
    subject_template TEXT NOT NULL,
    body_template TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    source_ref TEXT NOT NULL DEFAULT '',
    provenance_json TEXT NOT NULL DEFAULT '{}',
    version_no INTEGER NOT NULL DEFAULT 1,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_templates_match
ON email_templates(active, stage, variant_id, route, category);

CREATE TABLE IF NOT EXISTS expert_chunks (
    id TEXT PRIMARY KEY,
    document_name TEXT NOT NULL,
    expert_name TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '',
    source_ref TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    source_type TEXT NOT NULL DEFAULT 'notes',
    rights_basis TEXT NOT NULL DEFAULT 'user_provided',
    content_sha256 TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS idempotency_records (
    scope TEXT NOT NULL,
    request_key TEXT NOT NULL,
    response_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    PRIMARY KEY(scope, request_key)
);

CREATE TABLE IF NOT EXISTS memory_items (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    scope TEXT NOT NULL DEFAULT 'global',
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    confidence REAL NOT NULL DEFAULT 0.5,
    approved INTEGER NOT NULL DEFAULT 0,
    source_type TEXT NOT NULL DEFAULT 'observation',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(workspace_id, scope, kind, content_sha256)
);

CREATE INDEX IF NOT EXISTS idx_memory_lookup
ON memory_items(workspace_id, scope, kind, approved, updated_at DESC);

CREATE TABLE IF NOT EXISTS provider_calls (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    profile_id TEXT NOT NULL DEFAULT '',
    provider_type TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    data_policy TEXT NOT NULL DEFAULT 'minimal',
    status TEXT NOT NULL,
    request_json TEXT NOT NULL DEFAULT '{}',
    response_json TEXT NOT NULL DEFAULT '{}',
    error TEXT NOT NULL DEFAULT '',
    duration_ms INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_provider_calls_created
ON provider_calls(created_at DESC, profile_id);

CREATE TABLE IF NOT EXISTS discovery_runs (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'running',
    engine TEXT NOT NULL DEFAULT 'scrapling_public',
    objective_prompt TEXT NOT NULL DEFAULT '',
    plan_json TEXT NOT NULL DEFAULT '{}',
    target_count INTEGER NOT NULL DEFAULT 100,
    seed_urls_json TEXT NOT NULL DEFAULT '[]',
    allowed_domains_json TEXT NOT NULL DEFAULT '[]',
    category TEXT NOT NULL DEFAULT '',
    route TEXT NOT NULL DEFAULT '',
    max_pages INTEGER NOT NULL DEFAULT 20,
    max_depth INTEGER NOT NULL DEFAULT 1,
    obey_robots INTEGER NOT NULL DEFAULT 1,
    pages_crawled INTEGER NOT NULL DEFAULT 0,
    candidates_found INTEGER NOT NULL DEFAULT 0,
    fresh_count INTEGER NOT NULL DEFAULT 0,
    excluded_count INTEGER NOT NULL DEFAULT 0,
    errors_json TEXT NOT NULL DEFAULT '[]',
    started_at TEXT NOT NULL,
    finished_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_discovery_runs_campaign
ON discovery_runs(campaign_id, created_at DESC);

CREATE TABLE IF NOT EXISTS discovery_candidates (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES discovery_runs(id) ON DELETE CASCADE,
    identity_key TEXT NOT NULL,
    full_name TEXT NOT NULL,
    first_name TEXT NOT NULL DEFAULT '',
    last_name TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    company TEXT NOT NULL DEFAULT '',
    company_domain TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    route TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT '',
    linkedin_url TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL,
    public_hook TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'new',
    exclusion_reason TEXT NOT NULL DEFAULT '',
    evidence_json TEXT NOT NULL DEFAULT '{}',
    source_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(run_id, identity_key)
);

CREATE INDEX IF NOT EXISTS idx_discovery_candidates_run
ON discovery_candidates(run_id, status, confidence DESC);

CREATE TABLE IF NOT EXISTS research_entities (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    entity_type TEXT NOT NULL,
    canonical_key TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    properties_json TEXT NOT NULL DEFAULT '{}',
    confidence REAL NOT NULL DEFAULT 0,
    source_count INTEGER NOT NULL DEFAULT 1,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    UNIQUE(workspace_id, entity_type, canonical_key)
);

CREATE INDEX IF NOT EXISTS idx_research_entities_lookup
ON research_entities(workspace_id, entity_type, name);

CREATE TABLE IF NOT EXISTS research_edges (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    source_entity_id TEXT NOT NULL REFERENCES research_entities(id) ON DELETE CASCADE,
    target_entity_id TEXT NOT NULL REFERENCES research_entities(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL,
    properties_json TEXT NOT NULL DEFAULT '{}',
    confidence REAL NOT NULL DEFAULT 0,
    evidence_url TEXT NOT NULL DEFAULT '',
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    UNIQUE(workspace_id, source_entity_id, target_entity_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_research_edges_source
ON research_edges(workspace_id, source_entity_id, relation_type);
CREATE INDEX IF NOT EXISTS idx_research_edges_target
ON research_edges(workspace_id, target_entity_id, relation_type);

CREATE TABLE IF NOT EXISTS research_observations (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    run_id TEXT REFERENCES discovery_runs(id) ON DELETE SET NULL,
    candidate_id TEXT REFERENCES discovery_candidates(id) ON DELETE SET NULL,
    entity_id TEXT NOT NULL REFERENCES research_entities(id) ON DELETE CASCADE,
    source_url TEXT NOT NULL DEFAULT '',
    evidence_hash TEXT NOT NULL,
    evidence_json TEXT NOT NULL DEFAULT '{}',
    observed_at TEXT NOT NULL,
    UNIQUE(workspace_id, run_id, entity_id, evidence_hash)
);

CREATE INDEX IF NOT EXISTS idx_research_observations_run
ON research_observations(workspace_id, run_id, observed_at DESC);

CREATE TABLE IF NOT EXISTS sales_leads (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    lead_name TEXT NOT NULL,
    company TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    setter_name TEXT NOT NULL DEFAULT '',
    closer_name TEXT NOT NULL DEFAULT '',
    lead_status TEXT NOT NULL DEFAULT 'new'
        CHECK(lead_status IN (
            'new', 'proposal', 'deposit', 'follow_up_ongoing',
            'meeting_follow_up', 'won', 'lost'
        )),
    date_created TEXT NOT NULL,
    first_contact_at TEXT,
    date_meeting_booked TEXT,
    meeting_at TEXT,
    meeting_status TEXT NOT NULL DEFAULT ''
        CHECK(meeting_status IN (
            '', 'show', 'no_show', 'rescheduled_by_us',
            'rescheduled_by_them', 'cancel', 'dq'
        )),
    offer_made INTEGER NOT NULL DEFAULT 0 CHECK(offer_made IN (0, 1)),
    sale_type TEXT NOT NULL DEFAULT ''
        CHECK(sale_type IN ('', 'one_call', 'follow_up')),
    loss_reason TEXT NOT NULL DEFAULT ''
        CHECK(loss_reason IN (
            '', 'price', 'timing', 'partner_spouse', 'competitor',
            'ghosted', 'not_qualified'
        )),
    deposit_amount REAL NOT NULL DEFAULT 0 CHECK(deposit_amount >= 0),
    deposit_received_at TEXT,
    total_deal_value REAL NOT NULL DEFAULT 0 CHECK(total_deal_value >= 0),
    cash_collected REAL NOT NULL DEFAULT 0 CHECK(cash_collected >= 0),
    date_paid_in_full TEXT,
    refund_clawback_amount REAL NOT NULL DEFAULT 0 CHECK(refund_clawback_amount >= 0),
    commission_percent REAL NOT NULL DEFAULT 0
        CHECK(commission_percent >= 0 AND commission_percent <= 100),
    last_touch_at TEXT,
    notes TEXT NOT NULL DEFAULT '',
    position INTEGER NOT NULL DEFAULT 0,
    revision INTEGER NOT NULL DEFAULT 1,
    status_changed_at TEXT NOT NULL,
    won_at TEXT,
    lost_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sales_leads_board
ON sales_leads(workspace_id, lead_status, position, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_sales_leads_setter
ON sales_leads(workspace_id, setter_name, date_created DESC);
CREATE INDEX IF NOT EXISTS idx_sales_leads_closer
ON sales_leads(workspace_id, closer_name, date_created DESC);
CREATE INDEX IF NOT EXISTS idx_sales_leads_source
ON sales_leads(workspace_id, source, date_created DESC);
CREATE INDEX IF NOT EXISTS idx_sales_leads_meeting
ON sales_leads(workspace_id, meeting_at);

CREATE TABLE IF NOT EXISTS sales_setter_activity (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    activity_date TEXT NOT NULL,
    setter_name TEXT NOT NULL,
    dials_dms_sent INTEGER NOT NULL DEFAULT 0 CHECK(dials_dms_sent >= 0),
    conversations INTEGER NOT NULL DEFAULT 0 CHECK(conversations >= 0),
    declines INTEGER NOT NULL DEFAULT 0 CHECK(declines >= 0),
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(workspace_id, activity_date, setter_name)
);

CREATE INDEX IF NOT EXISTS idx_sales_activity_lookup
ON sales_setter_activity(workspace_id, activity_date DESC, setter_name);

CREATE TABLE IF NOT EXISTS sales_monthly_goals (
    workspace_id TEXT NOT NULL DEFAULT 'local',
    month TEXT NOT NULL,
    revenue_goal REAL NOT NULL DEFAULT 0 CHECK(revenue_goal >= 0),
    cash_goal REAL NOT NULL DEFAULT 0 CHECK(cash_goal >= 0),
    currency TEXT NOT NULL DEFAULT 'INR',
    updated_at TEXT NOT NULL,
    PRIMARY KEY(workspace_id, month)
);

CREATE TABLE IF NOT EXISTS sales_lead_events (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    lead_id TEXT NOT NULL REFERENCES sales_leads(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    previous_status TEXT NOT NULL DEFAULT '',
    current_status TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sales_lead_events
ON sales_lead_events(workspace_id, lead_id, created_at DESC);
"""

# AI chat tables are appended as IF NOT EXISTS so existing DBs migrate safely
_AI_CHAT_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_chat_projects (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_chats (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    title TEXT NOT NULL DEFAULT 'New chat',
    project_id TEXT REFERENCES ai_chat_projects(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ai_chats_workspace
ON ai_chats(workspace_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS ai_messages (
    id TEXT PRIMARY KEY,
    chat_id TEXT NOT NULL REFERENCES ai_chats(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
    content TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ai_messages_chat
ON ai_messages(chat_id, created_at ASC);
"""

SCHEMA_SQL = SCHEMA_SQL + _AI_CHAT_SCHEMA
