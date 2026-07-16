SCHEMA_VERSION = 2


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
"""
