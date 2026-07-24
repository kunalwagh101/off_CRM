"""SQLite schema owned only by OFF_AI Studio."""

OFF_AI_SCHEMA_VERSION = 1

OFF_AI_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS off_ai_projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    instructions TEXT NOT NULL DEFAULT '',
    archived INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_off_ai_projects_active
ON off_ai_projects(archived, updated_at DESC);

CREATE TABLE IF NOT EXISTS off_ai_conversations (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES off_ai_projects(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    selected_profile_id TEXT NOT NULL DEFAULT '',
    task_type TEXT NOT NULL DEFAULT 'public_general',
    data_class TEXT NOT NULL DEFAULT 'public',
    pinned INTEGER NOT NULL DEFAULT 0,
    archived INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_off_ai_conversations_recent
ON off_ai_conversations(archived, pinned DESC, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_off_ai_conversations_project
ON off_ai_conversations(project_id, archived, updated_at DESC);

CREATE TABLE IF NOT EXISTS off_ai_messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES off_ai_conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'complete',
    provider_profile_id TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    trust_tier TEXT NOT NULL DEFAULT '',
    egress_call_id TEXT NOT NULL DEFAULT '',
    egress_approved INTEGER NOT NULL DEFAULT 0,
    retry_of_message_id TEXT NOT NULL DEFAULT '',
    attachments_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_off_ai_messages_conversation
ON off_ai_messages(conversation_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_off_ai_messages_egress
ON off_ai_messages(egress_call_id);

CREATE TABLE IF NOT EXISTS off_ai_context_state (
    scope_type TEXT NOT NULL,
    scope_id TEXT NOT NULL,
    current_task TEXT NOT NULL DEFAULT '',
    plan_json TEXT NOT NULL DEFAULT '[]',
    done_json TEXT NOT NULL DEFAULT '[]',
    pending_json TEXT NOT NULL DEFAULT '[]',
    decisions_json TEXT NOT NULL DEFAULT '[]',
    working_drafts_json TEXT NOT NULL DEFAULT '[]',
    entity_facts_json TEXT NOT NULL DEFAULT '{}',
    rolling_summary TEXT NOT NULL DEFAULT '',
    revision INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(scope_type, scope_id)
);

CREATE TABLE IF NOT EXISTS off_ai_attachments (
    id TEXT PRIMARY KEY,
    conversation_id TEXT REFERENCES off_ai_conversations(id) ON DELETE CASCADE,
    message_id TEXT REFERENCES off_ai_messages(id) ON DELETE SET NULL,
    original_name TEXT NOT NULL,
    media_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    purpose TEXT NOT NULL DEFAULT 'campaign_intake',
    status TEXT NOT NULL DEFAULT 'stored',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_off_ai_attachments_conversation
ON off_ai_attachments(conversation_id, created_at DESC);

CREATE TABLE IF NOT EXISTS off_ai_import_jobs (
    id TEXT PRIMARY KEY,
    attachment_id TEXT NOT NULL REFERENCES off_ai_attachments(id) ON DELETE CASCADE,
    conversation_id TEXT REFERENCES off_ai_conversations(id) ON DELETE CASCADE,
    detected_mode TEXT NOT NULL DEFAULT '',
    selected_mode TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'inspecting',
    ambiguous INTEGER NOT NULL DEFAULT 0,
    template_text TEXT NOT NULL DEFAULT '',
    public_positioning TEXT NOT NULL DEFAULT '',
    mapping_json TEXT NOT NULL DEFAULT '{}',
    private_result_json TEXT NOT NULL DEFAULT '{}',
    public_preview_json TEXT NOT NULL DEFAULT '{}',
    campaign_id TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_off_ai_import_jobs_recent
ON off_ai_import_jobs(created_at DESC);

CREATE TABLE IF NOT EXISTS off_ai_egress_calls (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL DEFAULT '',
    message_id TEXT NOT NULL DEFAULT '',
    provider_profile_id TEXT NOT NULL DEFAULT '',
    provider_type TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    host_origin TEXT NOT NULL DEFAULT '',
    model_origin TEXT NOT NULL DEFAULT '',
    jurisdiction TEXT NOT NULL DEFAULT 'Unknown',
    retention_policy TEXT NOT NULL DEFAULT 'unknown',
    trust_tier TEXT NOT NULL DEFAULT 'D',
    task_type TEXT NOT NULL,
    data_class TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    payload_sha256 TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    blocked_reasons_json TEXT NOT NULL DEFAULT '[]',
    response_text TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    estimated_cost REAL NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_off_ai_egress_recent
ON off_ai_egress_calls(created_at DESC, provider_profile_id);
CREATE INDEX IF NOT EXISTS idx_off_ai_egress_status
ON off_ai_egress_calls(status, created_at DESC);

CREATE TABLE IF NOT EXISTS off_ai_provider_usage (
    profile_id TEXT NOT NULL,
    usage_date TEXT NOT NULL,
    requests INTEGER NOT NULL DEFAULT 0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    estimated_cost REAL NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(profile_id, usage_date)
);

CREATE TABLE IF NOT EXISTS off_ai_activity_records (
    id TEXT PRIMARY KEY,
    record_type TEXT NOT NULL,
    project_id TEXT NOT NULL DEFAULT '',
    conversation_id TEXT NOT NULL DEFAULT '',
    campaign_id TEXT NOT NULL DEFAULT '',
    contact_token TEXT NOT NULL DEFAULT '',
    variant_id TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_off_ai_activity_recent
ON off_ai_activity_records(created_at DESC, record_type);

CREATE TABLE IF NOT EXISTS off_ai_template_recommendations (
    id TEXT PRIMARY KEY,
    template_id TEXT NOT NULL,
    variant_id TEXT NOT NULL,
    sample_size INTEGER NOT NULL,
    reply_rate REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending_review',
    current_template TEXT NOT NULL,
    suggested_template TEXT NOT NULL,
    egress_call_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    reviewed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_off_ai_template_recommendations
ON off_ai_template_recommendations(status, created_at DESC);
"""
