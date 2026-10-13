from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from pydantic_core import PydanticCustomError

from ..outreach.models import MESSAGE_STAGES


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and key in self.model_fields_set

    def __getitem__(self, key: str) -> Any:
        if key not in type(self).model_fields:
            raise KeyError(key)
        return getattr(self, key)


class DemoLogin(StrictModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=500)



class WorkspaceCreate(StrictModel):
    username: str = Field(min_length=1, max_length=100)
    workspace_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    password: str = Field(min_length=12, max_length=500)
    confirm_install_owner: StrictBool = False


class WorkspaceUpdate(StrictModel):
    password: str | None = Field(default=None, min_length=12, max_length=500)
    enabled: bool | None = None



class AgentRoutineCreate(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    goal: str = Field(min_length=1, max_length=4000)
    target_url: str = Field(min_length=8, max_length=2000)
    trigger_type: Literal["interval", "event"]
    interval_seconds: int = Field(default=0, ge=0, le=30 * 24 * 60 * 60)
    event_name: str = Field(default="", max_length=100)
    step_budget: int = Field(default=10, ge=1, le=50)
    enabled: bool = True


class AgentRoutineUpdate(StrictModel):
    enabled: bool


class AgentRoutineEvent(StrictModel):
    event_id: str = Field(default="", max_length=200)
    payload: dict[str, Any] = Field(default_factory=dict)



class MeetingCreate(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    provider_id: str = Field(min_length=1, max_length=80)
    model_id: str = Field(min_length=1, max_length=240)
    language: str = Field(default="", max_length=32)


class CampaignCreate(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    # Free text rather than a Literal on purpose: the registry in
    # offsetx_apollo_builder/campaigns.py decides which kinds exist and which
    # can run, and a declared-but-unimplemented kind has to come back with the
    # sentence explaining what is missing. A Literal here would answer "not a
    # valid enumeration member" instead, which tells the caller nothing.
    kind: str = Field(default="email", min_length=1, max_length=40)
    daily_send_limit: int = Field(default=25, ge=1, le=500)
    timezone: str = Field(default="Asia/Kolkata", min_length=1, max_length=80)
    followup1_working_days: int = Field(default=4, ge=1, le=30)
    followup2_working_days: int = Field(default=6, ge=1, le=30)
    approval_mode: Literal["each_message", "whole_sequence"] = "each_message"
    variants: list[str] = Field(default_factory=lambda: ["A", "B"], min_length=1, max_length=8)
    send_window_start: str = Field(default="00:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    send_window_end: str = Field(default="00:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    send_weekdays: list[int] = Field(default_factory=lambda: list(range(7)), min_length=1, max_length=7)
    experiment_hypothesis: str = Field(default="", max_length=1000)
    experiment_metric: Literal["reply_rate"] = "reply_rate"
    experiment_min_sample: int = Field(default=40, ge=10, le=100000)
    control_variant: str = Field(default="A", min_length=1, max_length=40)


class CampaignClone(StrictModel):
    """Clone settings only. No recipient, draft, send or external credentials."""
    name: str = Field(min_length=1, max_length=120)



class CampaignUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    daily_send_limit: int | None = Field(default=None, ge=1, le=500)
    timezone: str | None = Field(default=None, min_length=1, max_length=80)
    followup1_working_days: int | None = Field(default=None, ge=1, le=30)
    followup2_working_days: int | None = Field(default=None, ge=1, le=30)
    approval_mode: Literal["each_message", "whole_sequence"] | None = None
    status: Literal["active", "paused", "archived"] | None = None
    send_window_start: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    send_window_end: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    send_weekdays: list[int] | None = Field(default=None, min_length=1, max_length=7)
    experiment_hypothesis: str | None = Field(default=None, max_length=1000)
    experiment_metric: Literal["reply_rate"] | None = None
    experiment_min_sample: int | None = Field(default=None, ge=10, le=100000)
    control_variant: str | None = Field(default=None, min_length=1, max_length=40)


class ContactUpdate(StrictModel):
    checkbox: bool | None = None
    full_name: str | None = Field(default=None, max_length=200)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=254)
    company: str | None = Field(default=None, max_length=200)
    title: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, max_length=120)
    route: str | None = Field(default=None, max_length=80)
    linkedin_url: str | None = Field(default=None, max_length=500)
    public_hook: str | None = Field(default=None, max_length=1000)
    hook_source: str | None = Field(default=None, max_length=1000)
    hook_date: str | None = Field(default=None, max_length=40)
    tension: str | None = Field(default=None, max_length=1000)
    identity_line: str | None = Field(default=None, max_length=1000)
    contribution: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=5000)
    poi_response: str | None = Field(default=None, max_length=10000)
    meeting_transcript: str | None = Field(default=None, max_length=100000)
    status: str | None = Field(default=None, max_length=40)
    recipient_timezone: str | None = Field(default=None, max_length=80)
    outcome_label: Literal["", "positive", "neutral", "negative", "meeting", "not_interested", "wrong_person"] | None = None


class ProviderSpec(StrictModel):
    provider_type: Literal[
        "openai", "anthropic", "openai_compatible", "template_engine_http"
    ]
    model: str = Field(default="", max_length=200)
    api_key_env: str = Field(default="", pattern=r"^[A-Z][A-Z0-9_]*$|^$")
    base_url: str = Field(default="", max_length=1000)
    timeout_seconds: int = Field(default=60, ge=5, le=300)
    extra: dict[str, Any] = Field(default_factory=dict)


class DraftGenerate(StrictModel):
    campaign_contact_ids: list[str] = Field(default_factory=list, max_length=5000)
    stages: list[str] = Field(default_factory=lambda: list(MESSAGE_STAGES), min_length=1)
    # A request can no longer bring its own provider: it named a server
    # environment variable and a URL to send it to (D-154). Accepted only as
    # null, so older clients that send `"provider": null` still work.
    provider: None = None
    use_provider_fallback: bool = False
    provider_profile_ids: list[str] = Field(default_factory=list, max_length=20)
    # Drafts use the profiles of the workspace signed in, the install owner's
    # included: naming another's put a client's planted profile in the
    # owner's chain (D-165). Empty passes, as older screens send "".
    provider_owner: str | None = Field(default=None, max_length=100)
    fallback_strategy: Literal["priority", "round_robin", "parallel"] = "priority"
    # A request-supplied provider still runs under a data policy. Defaulting to
    # "minimal" means an API caller cannot opt out of the guard by omission.
    data_policy: Literal["strict", "minimal", "standard", "full"] = "minimal"

    @field_validator("stages")
    @classmethod
    def valid_stages(cls, stages: list[str]) -> list[str]:
        unknown = [stage for stage in stages if stage not in MESSAGE_STAGES]
        if unknown:
            raise ValueError("Unknown stages: " + ", ".join(unknown))
        return list(dict.fromkeys(stages))

    @field_validator("provider_owner")
    @classmethod
    def own_profiles_only(cls, value: str | None) -> None:
        if value:
            raise PydanticCustomError(
                "own_profiles_only",
                "Drafts use the provider profiles of the workspace you are signed in to; leave this out",
            )
        # Nothing is kept: the route uses the caller's own workspace.


class DraftEdit(StrictModel):
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=30000)


class DraftApprove(StrictModel):
    draft_ids: list[str] = Field(default_factory=list, max_length=5000)
    stages: list[str] = Field(default_factory=list)


class DraftBulkReplace(StrictModel):
    find: str = Field(min_length=1, max_length=5000)
    replace: str = Field(default="", max_length=5000)
    draft_ids: list[str] = Field(default_factory=list, max_length=5000)
    stages: list[str] = Field(default_factory=list, max_length=3)
    fields: list[Literal["subject", "body"]] = Field(default_factory=lambda: ["subject", "body"], min_length=1)
    preview_only: bool = True


class DraftSchedule(StrictModel):
    draft_ids: list[str] = Field(min_length=1, max_length=5000)
    scheduled_at: datetime | None = None


class SendRequest(StrictModel):
    mode: Literal["local", "gmail"] = "local"
    confirmation: str = ""
    sync_replies_first: bool = True
    max_messages: int | None = Field(default=None, ge=1, le=500)


class EmailIdentityUpsert(StrictModel):
    id: str = Field(default="", max_length=80)
    name: str = Field(min_length=1, max_length=120)
    provider_type: Literal["local", "gmail", "ses"]
    stream: Literal["permission_marketing", "targeted_outreach", "transactional"]
    from_email: str = Field(min_length=3, max_length=254)
    reply_to: str = Field(default="", max_length=254)
    domain: str = Field(default="", max_length=253)
    ses_identity: str = Field(default="", max_length=254)
    aws_region: str = Field(default="", max_length=40)
    configuration_set: str = Field(default="", max_length=64)
    dkim_selector: str = Field(default="", max_length=63)
    mail_from_domain: str = Field(default="", max_length=253)
    sns_topic_arn: str = Field(default="", max_length=1000)
    max_per_second: float = Field(default=1, gt=0, le=1000)
    max_batch_size: int = Field(default=25, ge=1, le=500)
    status: Literal["active", "paused", "archived"] = "active"


class EmailCampaignSettingsUpdate(StrictModel):
    stream: Literal["permission_marketing", "targeted_outreach", "transactional"] | None = None
    provider_type: Literal["local", "gmail", "ses"] | None = None
    identity_id: str | None = Field(default=None, max_length=80)
    daily_limit: int | None = Field(default=None, ge=1, le=100000)
    frequency_cap_days: int | None = Field(default=None, ge=1, le=365)
    frequency_cap_max: int | None = Field(default=None, ge=1, le=100)
    require_unsubscribe: bool | None = None
    auto_pause_enabled: bool | None = None
    health_sample_size: int | None = Field(default=None, ge=1, le=1000000)
    max_hard_bounce_rate: float | None = Field(default=None, ge=0, le=1)
    max_complaint_rate: float | None = Field(default=None, ge=0, le=1)


class EmailPermissionUpdate(StrictModel):
    status: Literal["unknown", "granted", "denied"]
    basis: str = Field(default="", max_length=200)
    source: str = Field(default="", max_length=500)
    evidence: str = Field(default="", max_length=5000)
    obtained_at: datetime | None = None
    expires_at: datetime | None = None


class EmailSuppressionCreate(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    reason: str = Field(min_length=1, max_length=500)
    source: str = Field(default="operator", max_length=200)


class EmailEnqueueRequest(StrictModel):
    max_jobs: int = Field(default=5000, ge=1, le=10000)
    confirmation: str = Field(default="", max_length=100)


class EmailWorkerRequest(StrictModel):
    max_jobs: int = Field(default=25, ge=1, le=500)


class ReplySyncRequest(StrictModel):
    mode: Literal["local", "gmail"] = "local"


class ProviderProfileUpsert(StrictModel):
    id: str = Field(default="", max_length=80)
    # Whose a profile is, is the server's call (D-165, D-166). "default" is
    # what the old Settings form always sent, so it says nothing and passes.
    owner: str | None = Field(default=None, max_length=100)
    name: str = Field(min_length=1, max_length=120)
    provider_type: Literal[
        "openai",
        "anthropic",
        "openai_compatible",
        "template_engine_http",
    ]
    model: str = Field(default="", max_length=200)
    # Keys are typed in the app (DD-64); a profile naming a server variable
    # let any login send that variable anywhere (D-154). Only empty passes.
    api_key_env: str | None = Field(default=None, max_length=0)
    api_key: str = Field(default="", max_length=10000)
    base_url: str = Field(default="", max_length=1000)
    timeout_seconds: int = Field(default=60, ge=5, le=300)
    priority: int = Field(default=100, ge=1, le=1000)
    enabled: bool = True
    data_policy: Literal["minimal", "standard", "full"] = "minimal"
    audit_payloads: bool = False
    fallback_strategy: Literal["priority", "round_robin", "parallel"] = "priority"
    extra: dict[str, Any] = Field(default_factory=dict)

    @field_validator("owner")
    @classmethod
    def owner_set_by_server(cls, value: str | None) -> None:
        if value not in (None, "", "default"):
            raise PydanticCustomError(
                "owner_set_by_server",
                "The server records whose a profile is: the workspace you are signed in to. "
                "Leave owner out",
            )
        # Nothing is kept: the route records the caller's own workspace.


class ProviderProfileConfirm(StrictModel):
    # The key the profile holds: typing it proves the profile is the
    # confirmer's; its old label proves nothing (D-185).
    api_key: str = Field(default="", max_length=10000)
    # Where the list said Confirm would put it. Checked again as it is
    # written, so a stale page cannot send it anywhere else (D-194).
    confirm_to: str = Field(default="", max_length=64)


class ProviderHealthRequest(StrictModel):
    live_probe: bool = False


class AutomationUpdate(StrictModel):
    enabled: bool
    mode: Literal["local", "gmail"] = "local"
    interval_seconds: int = Field(default=300, ge=60, le=86400)
    max_messages_per_campaign: int = Field(default=25, ge=1, le=500)
    sync_replies_first: bool = True
    gmail_confirmation: str = Field(default="", max_length=100)


class BackupExport(StrictModel):
    passphrase: str = Field(min_length=12, max_length=500)


class TemplateImport(StrictModel):
    templates: list[dict[str, Any]] = Field(min_length=1, max_length=500)


class MemoryCreate(StrictModel):
    content: str = Field(min_length=1, max_length=30000)
    kind: str = Field(default="playbook", min_length=1, max_length=80)
    scope: str = Field(default="global", min_length=1, max_length=200)
    tags: list[str] = Field(default_factory=list, max_length=50)


class MemoryApproval(StrictModel):
    approved: bool


class DiscoveryRunCreate(StrictModel):
    seed_urls: list[str] = Field(min_length=1, max_length=20)
    allowed_domains: list[str] = Field(default_factory=list, max_length=20)
    objective_prompt: str = Field(
        default="Find relevant decision-makers from the supplied public pages.",
        min_length=10,
        max_length=5000,
    )
    engine: Literal["safe_http", "crawl4ai_public_js"] = "safe_http"
    target_count: int = Field(default=100, ge=1, le=1000)
    category: str = Field(default="Sustainability / ESG / Climate", max_length=120)
    max_pages: int = Field(default=20, ge=1, le=100)
    max_depth: int = Field(default=1, ge=0, le=3)
    obey_robots: Literal[True] = True
    request_delay_seconds: float = Field(default=0.75, ge=0.5, le=30)
    parallel_workers: int = Field(default=1, ge=1, le=4)

    @field_validator("seed_urls")
    @classmethod
    def unique_seed_urls(cls, values: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(item.strip() for item in values if item.strip()))
        if not cleaned:
            raise ValueError("At least one seed URL is required")
        return cleaned


class DiscoveryDecision(StrictModel):
    candidate_ids: list[str] = Field(min_length=1, max_length=5000)
    decision: Literal["approve", "reject"]


class DiscoverySelection(StrictModel):
    candidate_ids: list[str] = Field(min_length=1, max_length=5000)


class ResearchInteractionCreate(StrictModel):
    actor_name: str = Field(default="", max_length=300)
    actor_handle: str = Field(min_length=8, max_length=2000)
    target_name: str = Field(default="", max_length=300)
    target_handle: str = Field(min_length=8, max_length=2000)
    platform: str = Field(default="", max_length=50)
    interaction_type: Literal["like", "comment", "repost", "follow", "mention", "other"]
    source_url: str = Field(min_length=8, max_length=2000)
    observed_at: str = Field(default="", max_length=100)
    source_type: Literal["manual_import", "official_api"] = "manual_import"
    rights_basis: str = Field(default="public_evidence", min_length=3, max_length=200)
    evidence: dict[str, Any] = Field(default_factory=dict)


SalesLeadStatus = Literal[
    "new",
    "proposal",
    "deposit",
    "follow_up_ongoing",
    "meeting_follow_up",
    "won",
    "lost",
]
SalesMeetingStatus = Literal[
    "",
    "show",
    "no_show",
    "rescheduled_by_us",
    "rescheduled_by_them",
    "cancel",
    "dq",
]
SalesType = Literal["", "one_call", "follow_up"]
SalesLossReason = Literal[
    "",
    "price",
    "timing",
    "partner_spouse",
    "competitor",
    "ghosted",
    "not_qualified",
]


class SalesLeadCreate(StrictModel):
    lead_name: str = Field(min_length=1, max_length=200)
    company: str = Field(default="", max_length=200)
    email: str = Field(default="", max_length=254)
    phone: str = Field(default="", max_length=80)
    source: str = Field(default="", max_length=120)
    setter_name: str = Field(default="", max_length=160)
    closer_name: str = Field(default="", max_length=160)
    lead_status: SalesLeadStatus = "new"
    date_created: datetime | None = None
    first_contact_at: datetime | None = None
    date_meeting_booked: datetime | None = None
    meeting_at: datetime | None = None
    meeting_status: SalesMeetingStatus = ""
    offer_made: bool = False
    sale_type: SalesType = ""
    loss_reason: SalesLossReason = ""
    deposit_amount: float = Field(default=0, ge=0, le=1_000_000_000_000)
    deposit_received_at: datetime | None = None
    total_deal_value: float = Field(default=0, ge=0, le=1_000_000_000_000)
    cash_collected: float = Field(default=0, ge=0, le=1_000_000_000_000)
    date_paid_in_full: datetime | None = None
    refund_clawback_amount: float = Field(default=0, ge=0, le=1_000_000_000_000)
    commission_percent: float = Field(default=0, ge=0, le=100)
    last_touch_at: datetime | None = None
    notes: str = Field(default="", max_length=20000)


class SalesLeadUpdate(StrictModel):
    expected_revision: int | None = Field(default=None, ge=1)
    lead_name: str | None = Field(default=None, min_length=1, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=80)
    source: str | None = Field(default=None, max_length=120)
    setter_name: str | None = Field(default=None, max_length=160)
    closer_name: str | None = Field(default=None, max_length=160)
    lead_status: SalesLeadStatus | None = None
    date_created: datetime | None = None
    first_contact_at: datetime | None = None
    date_meeting_booked: datetime | None = None
    meeting_at: datetime | None = None
    meeting_status: SalesMeetingStatus | None = None
    offer_made: bool | None = None
    sale_type: SalesType | None = None
    loss_reason: SalesLossReason | None = None
    deposit_amount: float | None = Field(default=None, ge=0, le=1_000_000_000_000)
    deposit_received_at: datetime | None = None
    total_deal_value: float | None = Field(default=None, ge=0, le=1_000_000_000_000)
    cash_collected: float | None = Field(default=None, ge=0, le=1_000_000_000_000)
    date_paid_in_full: datetime | None = None
    refund_clawback_amount: float | None = Field(
        default=None, ge=0, le=1_000_000_000_000
    )
    commission_percent: float | None = Field(default=None, ge=0, le=100)
    last_touch_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=20000)


class SalesLeadMove(StrictModel):
    lead_status: SalesLeadStatus
    expected_revision: int | None = Field(default=None, ge=1)


class SetterActivityUpsert(StrictModel):
    activity_date: date
    setter_name: str = Field(min_length=1, max_length=160)
    dials_dms_sent: int = Field(default=0, ge=0, le=1_000_000)
    conversations: int = Field(default=0, ge=0, le=1_000_000)
    declines: int = Field(default=0, ge=0, le=1_000_000)
    notes: str = Field(default="", max_length=5000)


class SalesGoalUpdate(StrictModel):
    revenue_goal: float = Field(default=0, ge=0, le=1_000_000_000_000)
    cash_goal: float = Field(default=0, ge=0, le=1_000_000_000_000)
    currency: str = Field(default="INR", pattern=r"^[A-Za-z]{3}$")


class SalesProjectionRequest(StrictModel):
    forecast_month: str = Field(default="", pattern=r"^$|^\d{4}-(?:0[1-9]|1[0-2])$")
    history_start: date | None = None
    history_end: date | None = None
    rep_name: str = Field(default="", max_length=160)
    source: str = Field(default="", max_length=120)
    meetings_scheduled: int | None = Field(default=None, ge=0, le=1_000_000)
    show_up_rate: float | None = Field(default=None, ge=0, le=100)
    offer_rate: float | None = Field(default=None, ge=0, le=100)
    close_rate: float | None = Field(default=None, ge=0, le=100)
    average_deal_size: float | None = Field(
        default=None, ge=0, le=1_000_000_000_000
    )
    cash_collection_rate: float | None = Field(default=None, ge=0, le=100)


class NotionSettingsUpdate(StrictModel):
    token: str = Field(default="", max_length=300)
    workspace_name: str = Field(default="", max_length=120)
    contacts_database_id: str = Field(default="", max_length=80)
    sales_database_id: str = Field(default="", max_length=80)


class NotionExportRequest(StrictModel):
    scope: Literal["contacts", "sales"]
    campaign_id: str = Field(default="", max_length=64)
    limit: int = Field(default=500, ge=1, le=1000)


# ── S-06.02.02: strict contracts for formerly raw-dict API bodies ──────────

class CompanionCreateBody(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    instructions: str = Field(min_length=1, max_length=12000)
    granted_tool_ids: list[str] = Field(default_factory=list, max_length=100)
    memory_scope: str = Field(default="", max_length=160)

class CompanionUpdateBody(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    instructions: str | None = Field(default=None, min_length=1, max_length=12000)
    granted_tool_ids: list[str] | None = Field(default=None, max_length=100)
    memory_scope: str | None = Field(default=None, min_length=1, max_length=160)
    enabled: bool | None = Field(default=None, strict=True)

class CompanionContextBody(StrictModel):
    memory_limit: int = Field(default=8, ge=0, le=50, strict=True)
    memory_query: str = Field(default="", max_length=2000)

class CompanionMemoryBody(StrictModel):
    content: str = Field(min_length=1, max_length=30000)
    kind: str = Field(default="companion_fact", min_length=1, max_length=80)
    tags: list[str] = Field(default_factory=list, max_length=50)
    approved: bool = Field(default=False, strict=True)

class ContentAutomationPipelineBody(StrictModel):
    distribution_campaign_id: str = Field(min_length=1, max_length=80)
    image_campaign_id: str = Field(min_length=1, max_length=80)
    angle: str = Field(default="", max_length=500)
    account_ids: list[str] = Field(default_factory=list, max_length=100)
    posts_per_day: float | None = Field(default=None, ge=0, le=20, allow_inf_nan=False)
    plan_id: str | None = Field(default=None, max_length=80)
    enabled: bool | None = Field(default=None, strict=True)

class StartPostingBody(StrictModel):
    account_ids: list[str] = Field(min_length=1, max_length=100)

class ContentAutomationBody(StrictModel):
    enabled: bool | None = Field(default=None, strict=True)
    interval_seconds: int | None = Field(default=None, ge=300, le=86400, strict=True)
    per_channel: int | None = Field(default=None, ge=1, le=50, strict=True)
    posts_per_day: float | None = Field(default=None, ge=0, le=25)
    max_topics: int | None = Field(default=None, ge=1, le=10, strict=True)
    candidates: int | None = Field(default=None, ge=1, le=8, strict=True)
    auto_pace: bool | None = Field(default=None, strict=True)
    pace_mode: Literal["off", "suggest", "auto"] | None = None
    pending_pace: dict[str, Any] | None = None
    pipelines: list[ContentAutomationPipelineBody] | None = Field(default=None, max_length=100)
    sweep: bool | None = Field(default=None, strict=True)
    plan: bool | None = Field(default=None, strict=True)
    draft: bool | None = Field(default=None, strict=True)
    publish_due: bool | None = Field(default=None, strict=True)

class ImageBriefCreateBody(StrictModel):
    brief: str = Field(default="", max_length=12000)
    width: int = Field(default=0, ge=0, le=8192, strict=True)
    height: int = Field(default=0, ge=0, le=8192, strict=True)
    wanted: int = Field(default=1, ge=1, le=100, strict=True)

class ImageGenerateBody(StrictModel):
    count: int = Field(default=3, ge=1, le=100, strict=True)
    provider_id: str = Field(default="", max_length=80)

class VideoProjectCreateBody(StrictModel):
    name: str = Field(default="Untitled", max_length=200)
    preset: str = Field(default="vertical", max_length=80)
    fps: str = Field(default="30", max_length=20)
    width: int = Field(default=0, ge=0, le=16384, strict=True)
    height: int = Field(default=0, ge=0, le=16384, strict=True)

class VideoAssembleBody(StrictModel):
    recipe: str | None = Field(default=None, max_length=120)
    target_ticks: int = Field(default=0, ge=0, strict=True)
    name: str = Field(default="", max_length=200)
    lines: list[str] = Field(default_factory=list, max_length=500)
    asset_ids: list[str] | None = Field(default=None, max_length=1000)
    media_ids: list[str] | None = Field(default=None, max_length=1000)
    music_id: str = Field(default="", max_length=120)
    voice_id: str = Field(default="", max_length=120)
    preset: str = Field(default="vertical", max_length=80)
    fps: str = Field(default="30", max_length=20)
    seed: int = Field(default=0, strict=True)

class VideoDirectBody(StrictModel):
    topic: str | None = Field(default=None, max_length=12000)
    style: str = Field(default="", max_length=1000)
    target_ticks: int = Field(default=0, ge=0, strict=True)
    name: str = Field(default="", max_length=200)
    asset_ids: list[str] | None = Field(default=None, max_length=1000)
    media_ids: list[str] | None = Field(default=None, max_length=1000)
    music_id: str = Field(default="", max_length=120)
    voice_id: str = Field(default="", max_length=120)
    preset: str = Field(default="vertical", max_length=80)
    fps: str = Field(default="30", max_length=20)
    seed: int = Field(default=0, strict=True)

class CompetitorTeardownBody(StrictModel):
    facts: dict[str, Any]
    name: str = Field(default="", max_length=200)
    asset_ids: list[str] | None = Field(default=None, max_length=1000)
    media_ids: list[str] | None = Field(default=None, max_length=1000)
    music_id: str = Field(default="", max_length=120)
    voice_id: str = Field(default="", max_length=120)
    preset: str = Field(default="vertical", max_length=80)
    fps: str = Field(default="30", max_length=20)
    seed: int = Field(default=0, strict=True)

class VideoEditBody(StrictModel):
    operations: list[dict[str, Any]] | None = Field(default=None, max_length=500)
    op: str = Field(default="", max_length=80)
    operation: str = Field(default="", max_length=80)
    params: dict[str, Any] = Field(default_factory=dict)

class VideoPlaceAssetBody(StrictModel):
    asset_id: str | None = Field(default=None, max_length=120)
    track_id: str | None = Field(default=None, max_length=120)
    start: int = Field(default=-1, ge=-1, strict=True)
    duration: int | None = Field(default=None, gt=0, strict=True)

class VideoQueueBody(StrictModel):
    origin: str = Field(default="manual", max_length=80)

class VideoDecisionBody(StrictModel):
    decision: str = Field(default="", max_length=40)
    note: str = Field(default="", max_length=5000)

class VideoTranscribeBody(StrictModel):
    language: str = Field(default="", max_length=32)
    refresh: bool = Field(default=False, strict=True)

class VideoCaptionsBody(StrictModel):
    clip_id: str | None = Field(default=None, max_length=120)
    language: str = Field(default="", max_length=32)
    style: dict[str, Any] | None = None
    max_chars: int = Field(default=42, ge=1, le=500, strict=True)
    refresh: bool = Field(default=False, strict=True)

class PipelinePlanBody(StrictModel):
    angle: str = Field(default="", max_length=1000)
    image_campaign_id: str = Field(default="", max_length=80)
    window_hours: int = Field(default=72, ge=1, le=720, strict=True)
    min_channels: int = Field(default=3, ge=1, le=100, strict=True)
    max_topics: int = Field(default=3, ge=1, le=100, strict=True)
    candidates: int = Field(default=3, ge=1, le=100, strict=True)

class PipelineDraftBody(StrictModel):
    angle: str = Field(default="", max_length=1000)
    image_campaign_id: str = Field(default="", max_length=80)
    account_ids: list[str] = Field(default_factory=list, max_length=500)

class TrendWatchBody(StrictModel):
    handle: str = Field(default="", max_length=500)

class TrendSweepBody(StrictModel):
    per_channel: int = Field(default=10, ge=1, le=50, strict=True)
    limit: int = Field(default=0, ge=0, le=10000, strict=True)

class DistributionAccountCreateBody(StrictModel):
    platform: str = Field(default="", max_length=80)
    handle: str = Field(default="", max_length=500)
    label: str = Field(default="", max_length=200)
    daily_cap: int = Field(default=0, strict=True)

class DistributionAccountUpdateBody(StrictModel):
    daily_cap: int | None = Field(default=None, strict=True)
    label: str | None = Field(default=None, max_length=200)
    enabled: bool | None = Field(default=None, strict=True)

class PacingDecisionBody(StrictModel):
    campaign_id: str = Field(default="", max_length=80)
    suggestion_id: str = Field(default="", max_length=80)
    decision: str = Field(default="", max_length=40)

class DistributionGoalBody(StrictModel):
    metric: str = Field(default="views", max_length=80)
    target: int | None = Field(default=None, ge=0, strict=True)
    deadline: str = Field(default="", max_length=80)

class DistributionPostBody(StrictModel):
    account_id: str = Field(default="", max_length=120)
    caption: str = Field(default="", max_length=30000)
    asset_id: str = Field(default="", max_length=120)

class DistributionScheduleBody(StrictModel):
    at: str = Field(default="", max_length=80)

class DistributionMetricsBody(StrictModel):
    views: int = Field(default=0, ge=0, strict=True)
    likes: int = Field(default=0, ge=0, strict=True)
    comments: int = Field(default=0, ge=0, strict=True)
    shares: int = Field(default=0, ge=0, strict=True)
    source: str = Field(default="", max_length=500)

class AIProjectCreateBody(StrictModel):
    name: str = Field(default="", max_length=200)

class AIChatCreateBody(StrictModel):
    title: str = Field(default="New chat", max_length=500)
    project_id: str | None = Field(default=None, max_length=120)

class AIChatMoveBody(StrictModel):
    project_id: str | None = Field(default=None, max_length=120)

class AIChatRenameBody(StrictModel):
    title: str = Field(default="", max_length=500)

class AIChatMessageBody(StrictModel):
    data_class: str = Field(default="campaign", max_length=40)
    provider_id: str = Field(default="", max_length=80)
    model_id: str = Field(default="", max_length=240)
    content: str = Field(default="", max_length=50000)

class AIProviderConnectBody(StrictModel):
    api_key: str = Field(default="", max_length=10000)
    # Bounded because each model id — and any trust set for it — is kept in a
    # document read on every request; any length was stored (D-180).
    model_id: str = Field(default="", max_length=200)
    model_ids: list[Annotated[str, Field(max_length=200)]] = Field(default_factory=list, max_length=50)
    data_policy: str = Field(default="", max_length=40)
    enabled: bool = Field(default=True, strict=True)
    requests_per_minute: int | None = Field(default=None, ge=1, le=100000, strict=True)
    # 0 is the Connectors form's own default — "use the provider's own limit",
    # which the quota reads as no cap of ours. Refusing it meant no provider
    # could be connected from the screen (D-149).
    requests_per_day: int | None = Field(default=None, ge=0, le=10000000, strict=True)
    max_spend_usd_per_day: float | None = Field(default=None, ge=0)

class AIProviderOverrideBody(StrictModel):
    trust_tier: str = Field(default="", max_length=20)
    data_policy: str = Field(default="", max_length=40)
    allow_above_ceiling: bool = Field(default=False, strict=True)
    # A sentence. Each is kept in the trust history, which is read on every
    # request: 2,000 characters a reason made that megabytes (D-170).
    reason: str = Field(default="", max_length=500)
    decided_by: str = Field(default="", max_length=200)

class AIProviderTrustBody(StrictModel):
    # "" returns the provider, or the model, to its default (S-06.02.33).
    tier: str = Field(default="", max_length=2)
    model_id: str = Field(default="", max_length=200)
    reason: str = Field(default="", max_length=500)

class AIWorkspaceUpdateBody(StrictModel):
    positioning_line: str | None = Field(default=None, max_length=500)
    owner_domains: list[str] | None = Field(default=None, max_length=20)
    owner_addresses: list[str] | None = Field(default=None, max_length=20)

class AIMailboxUnlockBody(StrictModel):
    phrase: str = Field(default="", max_length=500)

class AIPlanBody(StrictModel):
    data_class: str = Field(default="person_public", max_length=40)
    task_type: str = Field(default="draft_email", max_length=120)
    task_tags: list[str] = Field(default_factory=list, max_length=20)

class AIRunBody(StrictModel):
    mode: str = Field(default="simple", max_length=40)
    data_class: str = Field(default="public", max_length=40)
    task_type: str = Field(default="ai_run", max_length=120)
    instructions: str = Field(default="", max_length=6000)
    template_text: str = Field(default="", max_length=12000)
    public_text: str = Field(default="", max_length=20000)
    task_tags: list[str] = Field(default_factory=list, max_length=4)
    system_prompt: str = Field(default="", max_length=12000)
    include_lower_tiers: bool = Field(default=True, strict=True)
    checks_suite: str = Field(default="", max_length=120)
    max_rounds: int = Field(default=3, ge=1, le=10, strict=True)
    provider_id: str = Field(default="", max_length=80)
    review: bool = Field(default=True, strict=True)
    planner_provider_id: str = Field(default="", max_length=80)
    model_id: str = Field(default="", max_length=240)

class AIImageBody(StrictModel):
    prompt: str = Field(default="", max_length=4000)
    data_class: str = Field(default="public", max_length=40)
    provider_id: str = Field(default="", max_length=80)

class AITemplateRegisterBody(StrictModel):
    template_id: str = Field(default="", max_length=120)
    variant_id: str = Field(default="", max_length=120)
    label: str = Field(default="", max_length=500)
    template_text: str = Field(default="", max_length=30000)
    parent_id: str = Field(default="", max_length=120)

class AITemplateRewriteBody(StrictModel):
    variant_id: str = Field(default="", max_length=120)
    use_winner: bool = Field(default=True, strict=True)

class AITemplateApproveBody(StrictModel):
    template_text: str = Field(default="", max_length=30000)
    variant_id: str = Field(default="b", max_length=120)
    label: str = Field(default="Rewritten", max_length=500)
    parent_variant_id: str = Field(default="", max_length=120)

class AITaskStartBody(StrictModel):
    kind: str = Field(default="campaign", max_length=80)
    title: str = Field(default="", max_length=1000)
    steps: list[str] = Field(default_factory=list, max_length=200)

class AITaskStepBody(StrictModel):
    step_index: int = Field(default=0, ge=0, strict=True)
    note: str = Field(default="", max_length=5000)
    status: str = Field(default="done", max_length=80)

class AITaskDecisionBody(StrictModel):
    decision: str = Field(default="", max_length=10000)

class AIRecallSearchBody(StrictModel):
    query: str = Field(default="", max_length=5000)
    limit: int = Field(default=5, ge=1, le=20, strict=True)
    replied_only: bool = Field(default=False, strict=True)

class AIRecallPreviewBody(StrictModel):
    query: str = Field(default="", max_length=5000)
    replied_only: bool = Field(default=False, strict=True)
    instructions: str = Field(default="", max_length=6000)
    data_policy: str = Field(default="standard", max_length=40)

class AIRecallForgetBody(StrictModel):
    campaign_contact_id: str = Field(default="", max_length=120)
    message_id: str = Field(default="", max_length=500)
    everything: bool = Field(default=False, strict=True)

class PrivacySubjectFields(StrictModel):
    emails: list[str] = Field(default_factory=list, max_length=100)
    urls: list[str] = Field(default_factory=list, max_length=100)
    contact_ids: list[str] = Field(default_factory=list, max_length=100)
    candidate_ids: list[str] = Field(default_factory=list, max_length=100)
    entity_ids: list[str] = Field(default_factory=list, max_length=100)
    sales_lead_ids: list[str] = Field(default_factory=list, max_length=100)
    workspace_id: str = Field(default="", max_length=120)

class PrivacySubjectBody(StrictModel):
    subject: PrivacySubjectFields

class PrivacyDeletionBody(PrivacySubjectBody):
    confirmation: str = Field(default="", max_length=200)


class ImageDecisionBody(StrictModel):
    decision: str = Field(default="", max_length=40)


class VideoPlaceMediaBody(StrictModel):
    media_id: str | None = Field(default=None, max_length=120)
    track_id: str | None = Field(default=None, max_length=120)
    start: int = Field(default=-1, ge=-1, strict=True)
    duration: int | None = Field(default=None, gt=0, strict=True)
