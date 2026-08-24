SCHEMA_VERSION = 9


#: Indexes over columns that arrived through a migration. They cannot live in
#: :data:`SCHEMA_SQL`, which runs before the migration: on an existing database
#: ``CREATE TABLE IF NOT EXISTS`` is a no-op, so an index over a brand-new column
#: would be asked for before ``ALTER TABLE`` had added it. Applied after the
#: migration instead, where it works for both fresh and upgraded databases.
POST_MIGRATION_SQL = """
CREATE INDEX IF NOT EXISTS idx_campaigns_kind ON campaigns(kind, status);
"""


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
    -- What sort of campaign this is. Every column below is email-shaped; other
    -- kinds leave them at their defaults, and the email runner refuses to touch
    -- a row whose kind is not its own. The registry of kinds, including which
    -- ones can actually run, lives in offsetx_apollo_builder/campaigns.py.
    kind TEXT NOT NULL DEFAULT 'email',
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

# Email delivery is deliberately its own schema boundary. Campaigns are shared
# by image, distribution and future runners; consent, DNS authentication and
# provider feedback only make sense for the email runner.
_EMAIL_DELIVERY_SCHEMA = """
CREATE TABLE IF NOT EXISTS email_sending_identities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    provider_type TEXT NOT NULL
        CHECK(provider_type IN ('local', 'gmail', 'ses')),
    stream TEXT NOT NULL
        CHECK(stream IN ('permission_marketing', 'targeted_outreach', 'transactional')),
    from_email TEXT NOT NULL,
    reply_to TEXT NOT NULL DEFAULT '',
    domain TEXT NOT NULL,
    ses_identity TEXT NOT NULL DEFAULT '',
    aws_region TEXT NOT NULL DEFAULT '',
    configuration_set TEXT NOT NULL DEFAULT '',
    dkim_selector TEXT NOT NULL DEFAULT '',
    mail_from_domain TEXT NOT NULL DEFAULT '',
    sns_topic_arn TEXT NOT NULL DEFAULT '',
    max_per_second REAL NOT NULL DEFAULT 1 CHECK(max_per_second > 0),
    max_batch_size INTEGER NOT NULL DEFAULT 25
        CHECK(max_batch_size > 0 AND max_batch_size <= 500),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK(status IN ('active', 'paused', 'archived')),
    provider_verified INTEGER NOT NULL DEFAULT 0 CHECK(provider_verified IN (0, 1)),
    spf_status TEXT NOT NULL DEFAULT 'unknown'
        CHECK(spf_status IN ('pass', 'fail', 'unknown')),
    dkim_status TEXT NOT NULL DEFAULT 'unknown'
        CHECK(dkim_status IN ('pass', 'fail', 'unknown')),
    dmarc_status TEXT NOT NULL DEFAULT 'unknown'
        CHECK(dmarc_status IN ('pass', 'fail', 'unknown')),
    alignment_status TEXT NOT NULL DEFAULT 'unknown'
        CHECK(alignment_status IN ('pass', 'fail', 'unknown')),
    dmarc_policy TEXT NOT NULL DEFAULT '',
    check_details_json TEXT NOT NULL DEFAULT '{}',
    last_checked_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_email_identities_from_stream
ON email_sending_identities(lower(from_email), stream)
WHERE status <> 'archived';

CREATE TABLE IF NOT EXISTS email_campaign_settings (
    campaign_id TEXT PRIMARY KEY REFERENCES campaigns(id) ON DELETE CASCADE,
    stream TEXT NOT NULL DEFAULT 'targeted_outreach'
        CHECK(stream IN ('permission_marketing', 'targeted_outreach', 'transactional')),
    provider_type TEXT NOT NULL DEFAULT 'local'
        CHECK(provider_type IN ('local', 'gmail', 'ses')),
    identity_id TEXT REFERENCES email_sending_identities(id) ON DELETE SET NULL,
    daily_limit INTEGER NOT NULL DEFAULT 500
        CHECK(daily_limit > 0 AND daily_limit <= 100000),
    frequency_cap_days INTEGER NOT NULL DEFAULT 7
        CHECK(frequency_cap_days > 0 AND frequency_cap_days <= 365),
    frequency_cap_max INTEGER NOT NULL DEFAULT 3
        CHECK(frequency_cap_max > 0 AND frequency_cap_max <= 100),
    require_unsubscribe INTEGER NOT NULL DEFAULT 1
        CHECK(require_unsubscribe IN (0, 1)),
    auto_pause_enabled INTEGER NOT NULL DEFAULT 1
        CHECK(auto_pause_enabled IN (0, 1)),
    health_sample_size INTEGER NOT NULL DEFAULT 100
        CHECK(health_sample_size > 0 AND health_sample_size <= 1000000),
    max_hard_bounce_rate REAL NOT NULL DEFAULT 0.05
        CHECK(max_hard_bounce_rate >= 0 AND max_hard_bounce_rate <= 1),
    max_complaint_rate REAL NOT NULL DEFAULT 0.001
        CHECK(max_complaint_rate >= 0 AND max_complaint_rate <= 1),
    paused_reason TEXT NOT NULL DEFAULT '',
    paused_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_email_campaign_identity
ON email_campaign_settings(identity_id, stream);

CREATE TABLE IF NOT EXISTS email_contact_permissions (
    email TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'unknown'
        CHECK(status IN ('unknown', 'granted', 'denied')),
    basis TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    evidence TEXT NOT NULL DEFAULT '',
    obtained_at TEXT,
    expires_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_suppressions (
    email TEXT PRIMARY KEY,
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1)),
    reason TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT '',
    provider_event_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_email_suppressions_active
ON email_suppressions(active, updated_at DESC);

CREATE TABLE IF NOT EXISTS email_unsubscribe_tokens (
    token_id TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    campaign_id TEXT REFERENCES campaigns(id) ON DELETE SET NULL,
    stream TEXT NOT NULL,
    used_at TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_email_unsubscribe_email
ON email_unsubscribe_tokens(email, created_at DESC);

CREATE TABLE IF NOT EXISTS email_send_jobs (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    campaign_contact_id TEXT NOT NULL REFERENCES campaign_contacts(id) ON DELETE CASCADE,
    draft_id TEXT NOT NULL REFERENCES drafts(id) ON DELETE CASCADE,
    draft_revision INTEGER NOT NULL,
    identity_id TEXT REFERENCES email_sending_identities(id) ON DELETE SET NULL,
    stream TEXT NOT NULL,
    provider_type TEXT NOT NULL,
    lane_key TEXT NOT NULL,
    to_email TEXT NOT NULL,
    from_email TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    headers_json TEXT NOT NULL DEFAULT '{}',
    idempotency_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK(status IN (
            'queued', 'sending', 'accepted', 'delivered', 'deferred',
            'retry_wait', 'blocked', 'failed', 'delivery_unknown', 'cancelled'
        )),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count >= 0),
    available_at TEXT NOT NULL,
    lease_expires_at TEXT,
    provider_message_id TEXT NOT NULL DEFAULT '',
    last_error TEXT NOT NULL DEFAULT '',
    accepted_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_email_jobs_claim
ON email_send_jobs(status, available_at, created_at);
CREATE INDEX IF NOT EXISTS idx_email_jobs_campaign
ON email_send_jobs(campaign_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_email_jobs_recipient
ON email_send_jobs(to_email, status, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_email_jobs_provider_message
ON email_send_jobs(provider_message_id) WHERE provider_message_id <> '';

CREATE TABLE IF NOT EXISTS email_rate_state (
    lane_key TEXT PRIMARY KEY,
    next_send_at TEXT,
    backoff_until TEXT,
    consecutive_failures INTEGER NOT NULL DEFAULT 0 CHECK(consecutive_failures >= 0),
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_delivery_events (
    id TEXT PRIMARY KEY,
    provider_type TEXT NOT NULL,
    provider_event_id TEXT NOT NULL UNIQUE,
    job_id TEXT REFERENCES email_send_jobs(id) ON DELETE SET NULL,
    campaign_id TEXT REFERENCES campaigns(id) ON DELETE SET NULL,
    identity_id TEXT REFERENCES email_sending_identities(id) ON DELETE SET NULL,
    provider_message_id TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL
        CHECK(event_type IN (
            'accepted', 'delivered', 'deferred', 'soft_bounce', 'hard_bounce',
            'complaint', 'rejected', 'rendering_failed', 'unsubscribe'
        )),
    recipient_email TEXT NOT NULL DEFAULT '',
    diagnostic TEXT NOT NULL DEFAULT '',
    raw_json TEXT NOT NULL DEFAULT '{}',
    occurred_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_email_events_health
ON email_delivery_events(campaign_id, identity_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_email_events_recipient
ON email_delivery_events(recipient_email, occurred_at DESC);
"""

SCHEMA_SQL = SCHEMA_SQL + _EMAIL_DELIVERY_SCHEMA
