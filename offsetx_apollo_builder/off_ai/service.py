from __future__ import annotations

import csv
import hashlib
import html
import json
import os
import re
import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterable

from ..dedupe import build_exclusion_set, discover_exclusion_files
from ..locked_categories import DEFAULT_CATEGORY, normalize_category
from ..outreach.email_expert import route_for_category
from ..outreach.engine import OutreachEngine
from ..outreach.models import (
    INITIAL,
    ContactInput,
    DraftAudit,
    DraftContent,
)
from ..outreach.provider_profiles import ProviderProfileStore
from .broker import BrokerResult, EgressBroker
from .parsers import CampaignIntakeParser, SUPPORTED_INTAKE_SUFFIXES
from .policy import EMAIL_RE, PolicyViolation
from .store import OffAIStore
from .tools import BringYourOwnToolRegistry


def _safe_title(prompt: str) -> str:
    words = re.findall(r"[\w'-]+", prompt, flags=re.UNICODE)[:8]
    title = " ".join(words).strip()
    return (title[:80] or "New chat").capitalize()


def _atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    os.replace(temporary, path)


class OutreachCRMAdapter:
    """The only OFF_AI dependency on the existing outreach CRM domain."""

    def __init__(
        self,
        *,
        engine: OutreachEngine,
        broker: EgressBroker,
        project_root: Path,
        data_dir: Path,
    ):
        self.engine = engine
        self.broker = broker
        self.project_root = project_root
        self.data_dir = data_dir

    def _exclusions(self):
        files = discover_exclusion_files(
            exclusion_dir=self.project_root / "old_pois",
            include_previous_outputs=True,
            project_root=self.project_root,
        )
        data_old = self.data_dir / "old_pois"
        if data_old.exists():
            files.extend(
                path
                for path in data_old.rglob("*")
                if path.is_file() and path not in files
            )
        exclusion = build_exclusion_set(files)
        current_rows = self.engine.store.connection.execute(
            """
            SELECT full_name AS name, email, company, title, linkedin_url
            FROM contacts
            """
        ).fetchall()
        for row in current_rows:
            exclusion.add_record(dict(row))
        return exclusion

    def _queue_missing_emails(
        self, *, job_id: str, rows: list[dict[str, str]]
    ) -> str:
        if not rows:
            return ""
        root = self.project_root / "poi_file_queue" / "inbox"
        if not root.parent.exists():
            root = self.data_dir / "poi_file_queue" / "inbox"
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"off_ai_missing_emails_{job_id[:8]}.csv"
        fields = [
            "Full Name",
            "Company",
            "Title",
            "LinkedIn URL",
            "Category",
            "Source",
        ]
        temporary = path.with_suffix(".csv.tmp")
        with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "Full Name": row.get("full_name", ""),
                        "Company": row.get("company", ""),
                        "Title": row.get("title", ""),
                        "LinkedIn URL": row.get("linkedin_url", ""),
                        "Category": row.get("category", ""),
                        "Source": f"OFF_AI intake {job_id}",
                    }
                )
        os.replace(temporary, path)
        return str(path)

    @staticmethod
    def _contact(row: dict[str, str], *, job_id: str) -> ContactInput:
        category = normalize_category(
            row.get("category", ""), default=DEFAULT_CATEGORY
        )
        return ContactInput(
            full_name=row.get("full_name", ""),
            first_name=row.get("first_name", ""),
            last_name=row.get("last_name", ""),
            email=row.get("email", ""),
            company=row.get("company", ""),
            title=row.get("title", ""),
            category=category,
            route=route_for_category(category),
            linkedin_url=row.get("linkedin_url", ""),
            public_hook=row.get("public_hook", ""),
            hook_source=row.get("hook_source", ""),
            source_ref=f"off_ai_import:{job_id}",
            source_data={
                key: value
                for key, value in row.items()
                if key not in {"subject", "body"}
            },
        )

    @staticmethod
    def _draft(
        *,
        row: dict[str, str],
        subject: str,
        body: str,
        variant_id: str,
        mode: str,
        egress_call_id: str = "",
        provider_profile_id: str = "",
    ) -> DraftContent:
        errors: list[str] = []
        warnings = ["Human approval is required before this imported draft can send."]
        if not row.get("email"):
            errors.append("Recipient email is missing; Apollo enrichment is required")
        if not subject.strip():
            errors.append("Subject is missing")
        if not body.strip():
            errors.append("Body is missing")
        score = 100 if not errors else 0
        return DraftContent(
            subject=subject.strip(),
            body=body.strip(),
            stage=INITIAL,
            variant_id=variant_id,
            template_id=f"off_ai_{mode}",
            audit=DraftAudit(
                score=score,
                errors=errors,
                warnings=warnings,
                checks={
                    "source": "off_ai_campaign_intake",
                    "mode": mode,
                    "email_reattached_locally": bool(row.get("email")),
                    "human_approval_required": True,
                },
            ),
            retrieval_refs=[],
            generation_meta={
                "mode": mode,
                "provider_profile_id": provider_profile_id,
                "provider_attempts": [],
                "egress_call_id": egress_call_id,
            },
        )

    def commit_intake(
        self,
        *,
        job: dict[str, Any],
        campaign_name: str,
        daily_send_limit: int,
        selected_mode: str,
        selected_profile_id: str,
    ) -> dict[str, Any]:
        mode = selected_mode or str(job.get("detected_mode") or "")
        if mode not in {"generate", "parse_send"}:
            raise ValueError("Choose Generate or Parse & send before creating the campaign")
        private = job.get("private_result") or {}
        rows = list(private.get("rows") or [])
        if not rows:
            raise ValueError("The intake contains no usable rows")
        if mode == "generate" and not str(job.get("template_text") or "").strip():
            raise ValueError("Generate mode requires a template")
        if mode == "generate" and not str(
            job.get("public_positioning") or ""
        ).strip():
            raise ValueError("Generate mode requires the approved public positioning line")
        if mode == "generate":
            models = self.broker.list_models()
            eligible = [
                model
                for model in models
                if bool(
                    (model.get("task_eligibility") or {}).get("outreach_draft")
                )
            ]
            if selected_profile_id:
                selected = next(
                    (
                        model
                        for model in models
                        if str(model.get("id") or "") == selected_profile_id
                    ),
                    None,
                )
                if not selected:
                    raise ValueError("The selected AI provider no longer exists")
                if selected not in eligible:
                    reasons = (selected.get("task_blockers") or {}).get(
                        "outreach_draft", []
                    )
                    raise PolicyViolation(
                        "The selected provider cannot receive person-level outreach data",
                        reasons=reasons,
                    )
            elif not eligible:
                raise ValueError(
                    "Generate mode needs an eligible Tier A provider. "
                    "Classify and enable one under Connectors, or use Parse & send."
                )

        campaign_id = self.engine.create_campaign(
            name=campaign_name.strip(),
            daily_send_limit=min(20, max(1, int(daily_send_limit))),
            approval_mode="each_message",
        )
        exclusions = self._exclusions()
        added = 0
        generated = 0
        blocked = 0
        excluded = 0
        failures: list[dict[str, Any]] = []
        missing_email_rows: list[dict[str, str]] = []

        for index, row in enumerate(rows, start=1):
            candidate = {
                "name": row.get("full_name", ""),
                "email": row.get("email", ""),
                "company": row.get("company", ""),
                "organization_name": row.get("company", ""),
                "title": row.get("title", ""),
                "linkedin_url": row.get("linkedin_url", ""),
            }
            duplicate, reason = exclusions.is_duplicate_candidate(candidate)
            if duplicate:
                excluded += 1
                failures.append(
                    {"row": index, "status": "excluded", "reason": reason}
                )
                continue
            contact = self._contact(row, job_id=str(job["id"]))
            if not contact.normalized().full_name:
                failures.append(
                    {"row": index, "status": "failed", "reason": "Name is required"}
                )
                continue
            try:
                contact_id = self.engine.store.upsert_contact(contact)
                campaign_contact_id, was_added = (
                    self.engine.store.add_contact_to_campaign(
                        campaign_id, contact_id
                    )
                )
                if was_added:
                    added += 1
                membership = self.engine.store.get_campaign_contact(
                    campaign_id, campaign_contact_id
                )
                variant_id = str(membership.get("variant_id") or "A")
                if not row.get("email"):
                    missing_email_rows.append(row)
                if mode == "parse_send":
                    subject = str(row.get("subject") or "")
                    body = str(row.get("body") or "")
                    result = None
                else:
                    result = self.broker.dispatch(
                        task_type="outreach_draft",
                        fields={
                            "public_profile": {
                                "name": row.get("full_name", ""),
                                "first_name": row.get("first_name", ""),
                                "role": row.get("title", ""),
                                "company": row.get("company", ""),
                                "category": membership.get("category", ""),
                                "route": membership.get("route", ""),
                                "public_hook": row.get("public_hook", ""),
                                "hook_source": row.get("hook_source", ""),
                            },
                            "template_text": str(job.get("template_text") or ""),
                            "sender_positioning": str(
                                job.get("public_positioning") or ""
                            ),
                            "instructions": (
                                "Keep the template mould. Personalise only with supplied "
                                "public facts. Return subject and body JSON."
                            ),
                        },
                        selected_profile_id=selected_profile_id,
                        allow_failover=True,
                        conversation_id=str(job.get("conversation_id") or ""),
                    )
                    parsed = json.loads(result.text)
                    subject = str(parsed.get("subject") or "")
                    body = str(parsed.get("body") or "")
                draft = self._draft(
                    row=row,
                    subject=subject,
                    body=body,
                    variant_id=variant_id,
                    mode=mode,
                    egress_call_id=result.call_id if result else "",
                    provider_profile_id=result.profile_id if result else "",
                )
                self.engine.store.save_draft(campaign_contact_id, draft)
                generated += 1
                blocked += int(not draft.audit.sendable)
                exclusions.add_record(candidate)
            except Exception as exc:
                failures.append(
                    {"row": index, "status": "failed", "reason": str(exc)[:1000]}
                )

        apollo_queue = self._queue_missing_emails(
            job_id=str(job["id"]), rows=missing_email_rows
        )
        outcome = {
            "campaign_id": campaign_id,
            "mode": mode,
            "rows": len(rows),
            "contacts_added": added,
            "drafts_created": generated,
            "drafts_blocked": blocked,
            "excluded": excluded,
            "missing_email_count": len(missing_email_rows),
            "apollo_queue_path": apollo_queue,
            "failures": failures,
            "daily_send_limit": min(20, max(1, int(daily_send_limit))),
            "approval_required": True,
        }
        self.engine.store.add_event(
            campaign_id, "off_ai_campaign_intake_committed", outcome
        )
        return outcome

    def owner_activity_record(self) -> dict[str, Any]:
        """Return an owner-only CRM activity export without message bodies.

        This method is intentionally a local adapter read. Its output is never
        available to provider payload builders or the egress broker.
        """
        connection = self.engine.store.connection
        campaigns = [
            dict(row)
            for row in connection.execute(
                """
                SELECT id, name, status, timezone, daily_send_limit,
                       approval_mode, created_at, updated_at
                FROM campaigns
                ORDER BY created_at, id
                """
            ).fetchall()
        ]
        contacts = [
            dict(row)
            for row in connection.execute(
                """
                SELECT
                    cc.id AS campaign_contact_id,
                    cc.campaign_id,
                    campaign.name AS campaign_name,
                    contact.id AS contact_id,
                    contact.full_name,
                    contact.email,
                    contact.company,
                    contact.title,
                    contact.linkedin_url,
                    cc.variant_id,
                    cc.status,
                    cc.current_stage,
                    cc.next_action_at,
                    cc.replied_at,
                    CASE
                        WHEN cc.replied_at IS NOT NULL OR EXISTS (
                            SELECT 1
                            FROM messages reply
                            WHERE reply.campaign_contact_id = cc.id
                              AND reply.direction = 'inbound'
                        )
                        THEN 1 ELSE 0
                    END AS reply_received,
                    cc.stopped_reason,
                    cc.created_at,
                    cc.updated_at,
                    (
                        SELECT COUNT(*)
                        FROM messages sent
                        WHERE sent.campaign_contact_id = cc.id
                          AND sent.direction = 'outbound'
                    ) AS outbound_count,
                    (
                        SELECT MIN(sent.sent_at)
                        FROM messages sent
                        WHERE sent.campaign_contact_id = cc.id
                          AND sent.direction = 'outbound'
                    ) AS first_sent_at,
                    (
                        SELECT MAX(sent.sent_at)
                        FROM messages sent
                        WHERE sent.campaign_contact_id = cc.id
                          AND sent.direction = 'outbound'
                    ) AS last_sent_at
                FROM campaign_contacts cc
                JOIN campaigns campaign ON campaign.id = cc.campaign_id
                JOIN contacts contact ON contact.id = cc.contact_id
                ORDER BY campaign.created_at, contact.full_name, contact.email
                """
            ).fetchall()
        ]
        messages = [
            dict(row)
            for row in connection.execute(
                """
                SELECT
                    message.id,
                    membership.campaign_id,
                    campaign.name AS campaign_name,
                    message.campaign_contact_id,
                    contact.id AS contact_id,
                    contact.full_name,
                    contact.email,
                    contact.company,
                    message.direction,
                    message.stage,
                    message.variant_id,
                    message.template_id,
                    message.subject,
                    message.sent_at,
                    message.received_at,
                    message.created_at,
                    CASE WHEN message.direction = 'inbound' THEN 1 ELSE 0 END
                        AS is_reply
                FROM messages message
                JOIN campaign_contacts membership
                  ON membership.id = message.campaign_contact_id
                JOIN campaigns campaign ON campaign.id = membership.campaign_id
                JOIN contacts contact ON contact.id = membership.contact_id
                ORDER BY message.created_at, message.id
                """
            ).fetchall()
        ]
        for contact in contacts:
            contact["reply_received"] = bool(contact["reply_received"])
            contact["outbound_count"] = int(contact["outbound_count"] or 0)
        for message in messages:
            message["is_reply"] = bool(message["is_reply"])
        return {
            "content_included": False,
            "content_note": (
                "Message bodies and raw provider payloads are intentionally omitted. "
                "The record contains owner-visible operational metadata only."
            ),
            "campaigns": campaigns,
            "contacts": contacts,
            "messages": messages,
        }


class OffAIService:
    """Application service for the embedded, extractable OFF_AI Studio."""

    def __init__(
        self,
        *,
        database_path: Path | str,
        data_dir: Path | str,
        export_dir: Path | str,
        project_root: Path | str,
        outreach_engine: OutreachEngine,
        provider_profiles: ProviderProfileStore,
        owner_domains: Iterable[str] = (),
        default_public_positioning: str = "",
    ):
        self.data_dir = Path(data_dir)
        self.export_dir = Path(export_dir)
        self.project_root = Path(project_root)
        self.attachment_dir = self.data_dir / "off_ai" / "attachments"
        owner_domains = tuple(owner_domains)
        self.store = OffAIStore(database_path)
        self.store.initialize()
        self.parser = CampaignIntakeParser()
        self.broker = EgressBroker(
            store=self.store,
            profiles=provider_profiles,
            owner_domains=owner_domains,
        )
        self.tools = BringYourOwnToolRegistry(
            self.data_dir / "off_ai" / "tools",
            owner_domains=owner_domains,
        )
        self.crm = OutreachCRMAdapter(
            engine=outreach_engine,
            broker=self.broker,
            project_root=self.project_root,
            data_dir=self.data_dir,
        )
        self.default_public_positioning = default_public_positioning.strip()

    def close(self) -> None:
        self.store.close()

    def bootstrap(self) -> dict[str, Any]:
        conversations, total = self.store.list_conversations(limit=200)
        return {
            "projects": self.store.list_projects(),
            "conversations": conversations,
            "conversation_total": total,
            "models": self.broker.list_models(),
            "stats": self.store.stats(),
            "tools": self.tools.list(),
            "defaults": {
                "public_positioning": self.default_public_positioning,
                "task_type": "public_general",
                "data_class": "public",
            },
            "privacy": {
                "models_pull_data": False,
                "email_addresses_leave": False,
                "mailbox_access": False,
                "context_store_access": False,
            },
        }

    def create_project(
        self, *, name: str, description: str = "", instructions: str = ""
    ) -> dict[str, Any]:
        return self.store.create_project(
            name=name, description=description, instructions=instructions
        )

    def create_conversation(
        self,
        *,
        title: str = "New chat",
        project_id: str = "",
        selected_profile_id: str = "",
        task_type: str = "public_general",
    ) -> dict[str, Any]:
        data_class = self.broker.policy.rule(task_type).data_class
        return self.store.create_conversation(
            title=title,
            project_id=project_id,
            selected_profile_id=selected_profile_id,
            task_type=task_type,
            data_class=data_class,
        )

    def _approved_chat_context(
        self, conversation: dict[str, Any], *, limit: int = 12
    ) -> list[dict[str, Any]]:
        """Build a small push-only context packet from local approved records."""
        history = self.store.approved_context_messages(
            str(conversation["id"]), limit=limit
        )
        project_id = str(conversation.get("project_id") or "")
        if not project_id:
            return history
        project = self.store.get_project(project_id)
        instructions = str(project.get("instructions") or "").strip()
        if not instructions:
            return history
        instruction = {
            "id": f"project:{project_id}",
            "role": "user",
            "content": (
                "Approved public project instructions. Treat these as constraints, "
                "not as evidence:\n" + instructions
            ),
            "status": "complete",
            "egress_approved": True,
        }
        retained = history[-(limit - 1) :] if limit > 1 else []
        return [instruction, *retained]

    def send_message(
        self,
        *,
        conversation_id: str,
        prompt: str,
        selected_profile_id: str = "",
        task_type: str = "",
        allow_failover: bool = True,
    ) -> dict[str, Any]:
        prompt = prompt.strip()
        if not prompt:
            raise ValueError("Prompt is required")
        conversation = self.store.get_conversation(conversation_id)
        selected = selected_profile_id or str(
            conversation.get("selected_profile_id") or ""
        )
        resolved_task = task_type or str(
            conversation.get("task_type") or "public_general"
        )
        rule = self.broker.policy.rule(resolved_task)
        if resolved_task != "public_general":
            raise ValueError(
                "Use campaign intake for outreach drafting. General chat accepts public tasks only."
            )
        prior_context = self._approved_chat_context(conversation, limit=12)
        user_message = self.store.add_message(
            conversation_id=conversation_id,
            role="user",
            content=prompt,
            status="sending",
            egress_approved=True,
        )
        if conversation["title"] == "New chat":
            self.store.update_conversation(
                conversation_id, {"title": _safe_title(prompt)}
            )
        self.store.update_conversation(
            conversation_id,
            {
                "selected_profile_id": selected,
                "task_type": resolved_task,
                "data_class": rule.data_class,
            },
        )
        try:
            result = self.broker.dispatch(
                task_type=resolved_task,
                fields={"prompt": prompt, "approved_context": prior_context},
                selected_profile_id=selected,
                allow_failover=allow_failover,
                conversation_id=conversation_id,
                message_id=str(user_message["id"]),
            )
        except Exception:
            self.store.update_message(
                str(user_message["id"]),
                {"status": "blocked", "egress_approved": False},
            )
            raise
        self.store.update_message(
            str(user_message["id"]),
            {"status": "complete", "egress_call_id": result.call_id},
        )
        assistant = self.store.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=result.text,
            status="complete",
            provider_profile_id=result.profile_id,
            model=result.model,
            trust_tier=result.trust_tier,
            egress_call_id=result.call_id,
            egress_approved=True,
        )
        self.store.append_context_event(
            conversation_id, role="user", content=prompt
        )
        self.store.append_context_event(
            conversation_id, role="assistant", content=result.text
        )
        self.store.add_activity(
            record_type="conversation",
            event_type="assistant_response_created",
            payload={
                "message_id": assistant["id"],
                "provider_profile_id": result.profile_id,
                "model": result.model,
                "trust_tier": result.trust_tier,
                "egress_call_id": result.call_id,
            },
            conversation_id=conversation_id,
            project_id=str(conversation.get("project_id") or ""),
        )
        return {
            "conversation": self.store.get_conversation(conversation_id),
            "user_message": self.store.get_message(str(user_message["id"])),
            "assistant_message": assistant,
            "attempts": result.attempts,
        }

    def retry_message(
        self,
        *,
        conversation_id: str,
        assistant_message_id: str,
        selected_profile_id: str = "",
    ) -> dict[str, Any]:
        messages = self.store.list_messages(conversation_id, limit=1000)
        target_index = next(
            (
                index
                for index, item in enumerate(messages)
                if item["id"] == assistant_message_id
                and item["role"] == "assistant"
            ),
            -1,
        )
        if target_index < 0:
            raise KeyError("Assistant message not found in this conversation")
        user = next(
            (
                item
                for item in reversed(messages[:target_index])
                if item["role"] == "user" and item["status"] == "complete"
            ),
            None,
        )
        if not user:
            raise ValueError("No user prompt is available to retry")
        conversation = self.store.get_conversation(conversation_id)
        selected = selected_profile_id or str(
            conversation.get("selected_profile_id") or ""
        )
        context = [
            item
            for item in self._approved_chat_context(conversation, limit=12)
            if item.get("id") not in {assistant_message_id, user["id"]}
        ]
        result = self.broker.dispatch(
            task_type="public_general",
            fields={"prompt": user["content"], "approved_context": context},
            selected_profile_id=selected,
            allow_failover=True,
            conversation_id=conversation_id,
            message_id=str(user["id"]),
        )
        assistant = self.store.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=result.text,
            provider_profile_id=result.profile_id,
            model=result.model,
            trust_tier=result.trust_tier,
            egress_call_id=result.call_id,
            egress_approved=True,
            retry_of_message_id=assistant_message_id,
        )
        self.store.append_context_event(
            conversation_id, role="assistant", content=result.text
        )
        return {
            "assistant_message": assistant,
            "attempts": result.attempts,
        }

    def inspect_intake(
        self,
        *,
        conversation_id: str,
        filename: str,
        media_type: str,
        content: bytes,
        template_text: str = "",
        public_positioning: str = "",
        selected_mode: str = "",
    ) -> dict[str, Any]:
        safe_name = Path(filename or "upload").name
        suffix = Path(safe_name).suffix.lower()
        if suffix not in SUPPORTED_INTAKE_SUFFIXES:
            raise ValueError(
                "Unsupported intake file. Use CSV, XLSX, XLS, PDF, TXT, or Markdown."
            )
        digest = hashlib.sha256(content).hexdigest()
        storage = self.attachment_dir / f"{digest}{suffix}"
        if not storage.exists():
            _atomic_bytes(storage, content)
        attachment = self.store.create_attachment(
            conversation_id=conversation_id,
            original_name=safe_name,
            media_type=media_type,
            size_bytes=len(content),
            sha256=digest,
            storage_path=str(storage),
        )
        job = self.store.create_import_job(
            attachment_id=str(attachment["id"]),
            conversation_id=conversation_id,
            template_text=template_text,
            public_positioning=(
                public_positioning.strip() or self.default_public_positioning
            ),
        )
        try:
            inspection = self.parser.inspect(
                storage,
                template_text=template_text,
                selected_mode=selected_mode,
            )
        except Exception as exc:
            return self.store.update_import_job(
                str(job["id"]),
                {"status": "failed", "error": str(exc)},
            )
        private = inspection["private_result"]
        job = self.store.update_import_job(
            str(job["id"]),
            {
                "detected_mode": inspection["detected_mode"],
                "selected_mode": selected_mode,
                "status": inspection["status"],
                "ambiguous": inspection["ambiguous"],
                "mapping": inspection["mapping"],
                "private_result": private,
                "public_preview": inspection["public_preview"],
            },
        )
        self.store.add_activity(
            record_type="campaign_intake",
            event_type="file_inspected",
            payload={
                "job_id": job["id"],
                "file_sha256": digest,
                "detected_mode": inspection["detected_mode"],
                "row_count": private["row_count"],
            },
            conversation_id=conversation_id,
        )
        return self.store.get_import_job(str(job["id"]))

    def choose_intake_mode(self, job_id: str, mode: str) -> dict[str, Any]:
        job = self.store.get_import_job(job_id, private=True)
        attachment = self.store.get_attachment(str(job["attachment_id"]))
        inspection = self.parser.inspect(
            Path(str(attachment["storage_path"])),
            template_text=str(job.get("template_text") or ""),
            selected_mode=mode,
        )
        self.store.update_import_job(
            job_id,
            {
                "selected_mode": mode,
                "detected_mode": mode,
                "status": inspection["status"],
                "ambiguous": False,
                "mapping": inspection["mapping"],
                "private_result": inspection["private_result"],
                "public_preview": inspection["public_preview"],
            },
        )
        return self.store.get_import_job(job_id)

    def commit_intake(
        self,
        *,
        job_id: str,
        campaign_name: str,
        daily_send_limit: int = 20,
        selected_mode: str = "",
        selected_profile_id: str = "",
    ) -> dict[str, Any]:
        job = self.store.get_import_job(job_id, private=True)
        if job["status"] not in {"ready", "needs_choice"}:
            raise ValueError(
                "Fix the file mapping or choose an intake mode before creating a campaign"
            )
        outcome = self.crm.commit_intake(
            job=job,
            campaign_name=campaign_name,
            daily_send_limit=daily_send_limit,
            selected_mode=selected_mode,
            selected_profile_id=selected_profile_id,
        )
        self.store.update_import_job(
            job_id,
            {
                "status": "committed",
                "selected_mode": selected_mode
                or str(job.get("detected_mode") or ""),
                "campaign_id": outcome["campaign_id"],
                "public_preview": {
                    **dict(job.get("public_preview") or {}),
                    "commit_result": outcome,
                },
            },
        )
        conversation_id = str(job.get("conversation_id") or "")
        if conversation_id:
            self.store.update_context(
                "conversation",
                conversation_id,
                {
                    "done": [
                        f"Created campaign {outcome['campaign_id']} from intake {job_id}"
                    ],
                    "pending": [
                        "Review every draft",
                        "Enrich missing emails through Apollo",
                        "Approve drafts before scheduling or sending",
                    ],
                    "entity_facts": {
                        "campaign_id": outcome["campaign_id"],
                        "intake_job_id": job_id,
                        "mode": outcome["mode"],
                    },
                },
            )
        self.store.add_activity(
            record_type="campaign",
            event_type="campaign_created_from_ai_intake",
            payload=outcome,
            conversation_id=conversation_id,
            campaign_id=outcome["campaign_id"],
        )
        return outcome

    def suggest_template_rewrite(
        self,
        *,
        template_id: str,
        variant_id: str,
        current_template: str,
        sample_size: int,
        reply_rate: float,
        selected_profile_id: str,
    ) -> dict[str, Any]:
        if sample_size < 20:
            raise ValueError("Wait for at least 20 sends before changing a template")
        result = self.broker.dispatch(
            task_type="template_rewrite",
            fields={
                "template_text": current_template,
                "sample_size": sample_size,
                "reply_rate": reply_rate,
            },
            selected_profile_id=selected_profile_id,
            allow_failover=True,
        )
        return self.store.create_template_recommendation(
            template_id=template_id,
            variant_id=variant_id,
            sample_size=sample_size,
            reply_rate=reply_rate,
            current_template=current_template,
            suggested_template=result.text,
            egress_call_id=result.call_id,
        )

    def review_template_recommendation(
        self, recommendation_id: str, *, approved: bool
    ) -> dict[str, Any]:
        result = self.store.review_template_recommendation(
            recommendation_id, approved=approved
        )
        self.store.add_activity(
            record_type="template_recommendation",
            event_type="template_recommendation_approved"
            if approved
            else "template_recommendation_rejected",
            payload={
                "recommendation_id": recommendation_id,
                "template_id": result["template_id"],
                "variant_id": result["variant_id"],
                "sample_size": result["sample_size"],
                "reply_rate": result["reply_rate"],
                "activated": False,
            },
            variant_id=str(result["variant_id"]),
        )
        return result

    def export_project(self, project_id: str, *, format: str = "md") -> Path:
        project = self.store.get_project(project_id)
        conversations, _ = self.store.list_conversations(
            project_id=project_id, include_archived=True, limit=10000
        )
        self.export_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", project["name"]).strip("-")
        safe_name = safe_name[:80] or "off-ai-project"
        if format == "md":
            path = self.export_dir / f"{safe_name}-{uuid.uuid4().hex[:8]}.md"
            parts = [
                f"# {project['name']}",
                "",
                str(project.get("description") or ""),
                "",
                "## Project instructions",
                "",
                str(project.get("instructions") or "No project instructions."),
            ]
            for conversation in reversed(conversations):
                parts.extend(["", f"## {conversation['title']}", ""])
                for message in self.store.list_messages(
                    str(conversation["id"]), limit=100000
                ):
                    parts.extend(
                        [
                            f"### {str(message['role']).title()}",
                            "",
                            str(message["content"]),
                            "",
                        ]
                    )
            path.write_text("\n".join(parts).strip() + "\n", encoding="utf-8")
        elif format == "html":
            path = self.export_dir / f"{safe_name}-{uuid.uuid4().hex[:8]}.html"
            sections = [
                "<!doctype html><html lang=\"en\"><meta charset=\"utf-8\">",
                f"<title>{html.escape(project['name'])}</title>",
                "<main>",
                f"<h1>{html.escape(project['name'])}</h1>",
                f"<p>{html.escape(str(project.get('description') or ''))}</p>",
            ]
            for conversation in reversed(conversations):
                sections.append(
                    f"<section><h2>{html.escape(conversation['title'])}</h2>"
                )
                for message in self.store.list_messages(
                    str(conversation["id"]), limit=100000
                ):
                    sections.append(
                        f"<article><h3>{html.escape(str(message['role']).title())}</h3>"
                        f"<pre>{html.escape(str(message['content']))}</pre></article>"
                    )
                sections.append("</section>")
            sections.append("</main></html>")
            path.write_text("\n".join(sections), encoding="utf-8")
        else:
            raise ValueError("Project export format must be md or html")
        return path

    def export_owner_record(self, *, format: str = "md") -> Path:
        """Portable one-way record for Notion or NotebookLM import."""
        self.export_dir.mkdir(parents=True, exist_ok=True)
        calls, _ = self.store.list_egress(limit=100000)
        crm_activity = self.crm.owner_activity_record()
        record = {
            "schema_version": 2,
            "export_direction": "one_way_owner_controlled",
            "stats": self.store.stats(),
            "crm_activity": crm_activity,
            "egress_calls": calls,
        }
        path = self.export_dir / f"off-ai-owner-record-{uuid.uuid4().hex[:8]}.{format}"
        if format == "json":
            path.write_text(
                json.dumps(record, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return path
        if format != "md":
            raise ValueError("Owner-record format must be md or json")
        lines = [
            "# OFF_AI owner record",
            "",
            "This is a one-way, owner-controlled export for Notion or NotebookLM.",
            "",
            (
                "Message bodies and raw provider payloads are intentionally omitted; "
                "this record contains operational metadata."
            ),
            "",
            "## Campaigns",
            "",
        ]
        for campaign in crm_activity["campaigns"]:
            lines.extend(
                [
                    f"### {campaign['name']}",
                    "",
                    f"- Campaign ID: `{campaign['id']}`",
                    f"- Status: {campaign['status']}",
                    f"- Daily send limit: {campaign['daily_send_limit']}",
                    f"- Timezone: {campaign['timezone']}",
                    f"- Created: {campaign['created_at']}",
                    f"- Updated: {campaign['updated_at']}",
                    "",
                ]
            )
        lines.extend(["## Campaign contacts", ""])
        for contact in crm_activity["contacts"]:
            lines.extend(
                [
                    (
                        f"### {contact['full_name']} · "
                        f"{contact['campaign_name']}"
                    ),
                    "",
                    f"- Email: {contact['email'] or '—'}",
                    f"- Company: {contact['company'] or '—'}",
                    f"- Role: {contact['title'] or '—'}",
                    f"- Variant: {contact['variant_id']}",
                    f"- Status / stage: {contact['status']} / {contact['current_stage'] or '—'}",
                    f"- Reply received: {'yes' if contact['reply_received'] else 'no'}",
                    f"- Replied at: {contact['replied_at'] or '—'}",
                    f"- Outbound messages: {contact['outbound_count']}",
                    f"- First sent: {contact['first_sent_at'] or '—'}",
                    f"- Last sent: {contact['last_sent_at'] or '—'}",
                    f"- Next action: {contact['next_action_at'] or '—'}",
                    "",
                ]
            )
        lines.extend(["## Message activity", ""])
        for message in crm_activity["messages"]:
            timestamp = (
                message["received_at"]
                or message["sent_at"]
                or message["created_at"]
            )
            lines.extend(
                [
                    f"### {timestamp} · {message['direction']}",
                    "",
                    f"- Campaign: {message['campaign_name']}",
                    f"- Contact: {message['full_name']} ({message['email'] or '—'})",
                    f"- Stage / variant: {message['stage']} / {message['variant_id'] or '—'}",
                    f"- Subject: {message['subject'] or '—'}",
                    f"- Reply: {'yes' if message['is_reply'] else 'no'}",
                    "",
                ]
            )
        lines.extend(
            [
            "## Egress calls",
            "",
            ]
        )
        for call in calls:
            lines.extend(
                [
                    f"### {call['created_at']} · {call['status']}",
                    "",
                    f"- Provider: {call['provider_profile_id']} ({call['trust_tier']})",
                    f"- Task: {call['task_type']}",
                    f"- Data class: {call['data_class']}",
                    f"- Payload hash: `{call['payload_sha256']}`",
                    "",
                ]
            )
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
