from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

from .models import clean_text


class MemoryBackend(Protocol):
    """Replaceable boundary for local SQLite today and a tenant service later."""

    def add_memory_item(self, **values: Any) -> str: ...

    def search_memory_items(self, query: str = "", **filters: Any) -> tuple[list[dict[str, Any]], int]: ...

    def set_memory_approval(self, memory_id: str, approved: bool) -> dict[str, Any]: ...

    def memory_stats(self, *, workspace_id: str = "local") -> dict[str, Any]: ...


@dataclass(slots=True)
class MemoryService:
    backend: MemoryBackend
    workspace_id: str = "local"

    @staticmethod
    def _deidentify(text: str, contact: dict[str, Any]) -> str:
        result = str(text)
        replacements = {
            clean_text(contact.get("email")): "[recipient-email]",
            clean_text(contact.get("full_name")): "[recipient-name]",
            clean_text(contact.get("first_name")): "[first-name]",
            clean_text(contact.get("last_name")): "[last-name]",
            clean_text(contact.get("company")): "[company]",
            clean_text(contact.get("linkedin_url")): "[profile-url]",
        }
        for value, placeholder in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
            if value:
                result = re.sub(re.escape(value), placeholder, result, flags=re.IGNORECASE)
        result = re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[email]", result, flags=re.IGNORECASE)
        return result[:12000]

    def remember_edit(
        self,
        *,
        contact: dict[str, Any],
        stage: str,
        variant_id: str,
        before_subject: str,
        before_body: str,
        after_subject: str,
        after_body: str,
        campaign_id: str,
    ) -> str:
        content = self._deidentify(
            "\n".join(
                [
                    f"Human-approved correction for {stage}, variant {variant_id}.",
                    f"Before subject: {before_subject}",
                    f"After subject: {after_subject}",
                    f"Before body: {before_body}",
                    f"After body: {after_body}",
                ]
            ),
            contact,
        )
        return self.backend.add_memory_item(
            workspace_id=self.workspace_id,
            scope=f"campaign:{campaign_id}",
            kind="human_correction",
            content=content,
            tags=[stage, variant_id, clean_text(contact.get("category")), clean_text(contact.get("route"))],
            metadata={"stage": stage, "variant_id": variant_id, "campaign_id": campaign_id},
            confidence=0.95,
            approved=True,
            source_type="user_edit",
        )

    def remember_bulk_rule(
        self,
        *,
        campaign_id: str,
        find: str,
        replace: str,
        fields: list[str],
        changed: int,
    ) -> str:
        return self.backend.add_memory_item(
            workspace_id=self.workspace_id,
            scope=f"campaign:{campaign_id}",
            kind="bulk_correction",
            content=f"Replace {find!r} with {replace!r} in {', '.join(fields)}; applied to {changed} reviewed drafts.",
            tags=["bulk-edit", *fields],
            metadata={"find": find, "replace": replace, "fields": fields, "changed": changed},
            confidence=0.98,
            approved=True,
            source_type="user_edit",
        )

    def remember_reply(
        self,
        *,
        campaign_id: str,
        campaign_contact_id: str,
        stage: str,
        variant_id: str,
    ) -> str:
        return self.backend.add_memory_item(
            workspace_id=self.workspace_id,
            scope=f"campaign:{campaign_id}",
            kind="reply_observation",
            content=f"A recipient replied after stage {stage or 'unknown'} using variant {variant_id or 'unknown'}.",
            tags=[stage, variant_id, "reply"],
            metadata={"campaign_id": campaign_id, "campaign_contact_id": campaign_contact_id},
            confidence=0.8,
            approved=False,
            source_type="system_observation",
        )

    def remember_feedback(
        self,
        *,
        campaign_id: str,
        campaign_contact_id: str,
        outcome_label: str,
        notes: str,
        contact: dict[str, Any],
    ) -> str:
        content = self._deidentify(
            f"Human-labelled outreach outcome: {outcome_label}. Notes: {notes or 'none'}",
            contact,
        )
        return self.backend.add_memory_item(
            workspace_id=self.workspace_id,
            scope=f"campaign:{campaign_id}",
            kind="labelled_outcome",
            content=content,
            tags=[outcome_label, clean_text(contact.get("category")), clean_text(contact.get("route"))],
            metadata={"campaign_id": campaign_id, "campaign_contact_id": campaign_contact_id},
            confidence=1.0,
            approved=True,
            source_type="user_label",
        )

    def generation_context(self, *, query: str, campaign_id: str, limit: int = 5) -> list[dict[str, Any]]:
        campaign_scope = f"campaign:{campaign_id}" if campaign_id else ""
        items, _ = self.backend.search_memory_items(
            query,
            workspace_id=self.workspace_id,
            scope=campaign_scope,
            approved_only=True,
            limit=limit,
        )
        return items

    def add_manual(
        self,
        *,
        content: str,
        kind: str = "playbook",
        scope: str = "global",
        tags: list[str] | None = None,
    ) -> str:
        return self.backend.add_memory_item(
            workspace_id=self.workspace_id,
            scope=scope,
            kind=kind,
            content=content,
            tags=tags or [],
            confidence=1.0,
            approved=True,
            source_type="manual",
        )
