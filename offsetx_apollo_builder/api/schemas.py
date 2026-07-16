from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..outreach.models import MESSAGE_STAGES


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CampaignCreate(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    daily_send_limit: int = Field(default=25, ge=1, le=500)
    timezone: str = Field(default="Asia/Kolkata", min_length=1, max_length=80)
    followup1_working_days: int = Field(default=4, ge=1, le=30)
    followup2_working_days: int = Field(default=6, ge=1, le=30)
    approval_mode: Literal["each_message", "whole_sequence"] = "each_message"
    variants: list[str] = Field(default_factory=lambda: ["A", "B"], min_length=1, max_length=8)


class CampaignUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    daily_send_limit: int | None = Field(default=None, ge=1, le=500)
    timezone: str | None = Field(default=None, min_length=1, max_length=80)
    followup1_working_days: int | None = Field(default=None, ge=1, le=30)
    followup2_working_days: int | None = Field(default=None, ge=1, le=30)
    approval_mode: Literal["each_message", "whole_sequence"] | None = None
    status: Literal["active", "paused", "archived"] | None = None


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


class SendRequest(StrictModel):
    mode: Literal["local", "gmail"] = "local"
    confirmation: str = ""
    sync_replies_first: bool = True
    max_messages: int | None = Field(default=None, ge=1, le=500)


class ReplySyncRequest(StrictModel):
    mode: Literal["local", "gmail"] = "local"


class TemplateImport(StrictModel):
    templates: list[dict[str, Any]] = Field(min_length=1, max_length=500)
