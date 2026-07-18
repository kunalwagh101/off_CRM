from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..outreach.models import MESSAGE_STAGES


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DemoLogin(StrictModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=500)


class CampaignCreate(StrictModel):
    name: str = Field(min_length=1, max_length=120)
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
    provider: ProviderSpec | None = None
    use_provider_fallback: bool = False
    provider_profile_ids: list[str] = Field(default_factory=list, max_length=20)
    provider_owner: str = Field(default="", max_length=100)
    fallback_strategy: Literal["priority", "round_robin", "parallel"] = "priority"

    @field_validator("stages")
    @classmethod
    def valid_stages(cls, stages: list[str]) -> list[str]:
        unknown = [stage for stage in stages if stage not in MESSAGE_STAGES]
        if unknown:
            raise ValueError("Unknown stages: " + ", ".join(unknown))
        return list(dict.fromkeys(stages))


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


class ReplySyncRequest(StrictModel):
    mode: Literal["local", "gmail"] = "local"


class ProviderProfileUpsert(StrictModel):
    id: str = Field(default="", max_length=80)
    owner: str = Field(default="default", min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=120)
    provider_type: Literal[
        "openai",
        "anthropic",
        "openai_compatible",
        "template_engine_http",
    ]
    model: str = Field(default="", max_length=200)
    api_key_env: str = Field(default="", pattern=r"^[A-Z][A-Z0-9_]*$|^$")
    api_key: str = Field(default="", max_length=10000)
    base_url: str = Field(default="", max_length=1000)
    timeout_seconds: int = Field(default=60, ge=5, le=300)
    priority: int = Field(default=100, ge=1, le=1000)
    enabled: bool = True
    data_policy: Literal["minimal", "standard", "full"] = "minimal"
    audit_payloads: bool = False
    fallback_strategy: Literal["priority", "round_robin", "parallel"] = "priority"
    extra: dict[str, Any] = Field(default_factory=dict)


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
