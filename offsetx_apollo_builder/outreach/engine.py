from __future__ import annotations

import csv
import hashlib
import re
import threading
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd

from ..input_loader import read_input_table
from ..locked_categories import DEFAULT_CATEGORY, normalize_category
from .email_expert import LocalEmailExpert, import_expert_documents, route_for_category
from .models import (
    AIProvider,
    FOLLOWUP_1,
    FOLLOWUP_2,
    INITIAL,
    MESSAGE_STAGES,
    ContactInput,
    MailProvider,
    clean_text,
    utc_now,
)
from .store import OutreachStore


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEMPLATE_FILE = PROJECT_ROOT / "email_expert_library" / "default_templates.json"

CONTACT_ALIASES: dict[str, tuple[str, ...]] = {
    "full_name": ("full name", "name", "person name", "contact name", "poi name"),
    "first_name": ("first name", "firstname"),
    "last_name": ("last name", "lastname"),
    "email": ("email", "work email", "business email", "verified email"),
    "company": ("company", "company name", "organisation", "organization", "employer"),
    "title": ("title", "job title", "position", "designation", "role"),
    "category": ("category", "stakeholder category", "locked category"),
    "route": ("route", "recipient route"),
    "linkedin_url": ("linkedin", "linkedin url", "linkedin profile"),
    "public_hook": ("public hook", "verified public hook", "hook"),
    "hook_source": ("hook source", "source url", "public source"),
    "hook_date": ("hook date", "source date"),
    "tension": ("tension", "problem", "business tension"),
    "identity_line": ("identity line", "identity"),
    "contribution": ("contribution", "relevance"),
    "question_1": ("question 1", "prepared question 1"),
    "question_2": ("question 2", "prepared question 2"),
    "question_3": ("question 3", "prepared question 3"),
    "notes": ("notes", "note"),
    "recipient_timezone": ("recipient timezone", "contact timezone", "timezone"),
}


def _canonical(value: object) -> str:
    text = clean_text(value).lower().replace("&", "and")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def _column_lookup(columns: Iterable[object]) -> dict[str, str]:
    available = {_canonical(column): str(column) for column in columns}
    result: dict[str, str] = {}
    for field, aliases in CONTACT_ALIASES.items():
        for alias in aliases:
            if _canonical(alias) in available:
                result[field] = available[_canonical(alias)]
                break
    return result


def add_working_days(value: datetime, days: int, timezone_name: str) -> datetime:
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone: {timezone_name}") from exc
    local = value.astimezone(zone)
    remaining = days
    while remaining:
        local += timedelta(days=1)
        if local.weekday() < 5:
            remaining -= 1
    return local.astimezone(timezone.utc)


def local_day_bounds(value: datetime, timezone_name: str) -> tuple[datetime, datetime]:
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone: {timezone_name}") from exc
    local = value.astimezone(zone)
    start = datetime.combine(local.date(), time.min, tzinfo=zone)
    return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)


def campaign_send_window(campaign: dict[str, Any], value: datetime) -> dict[str, Any]:
    """Evaluate a campaign's local send window, including overnight windows."""
    try:
        zone = ZoneInfo(str(campaign["timezone"]))
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone: {campaign['timezone']}") from exc
    local = value.astimezone(zone)
    weekdays = {int(day) for day in campaign.get("send_weekdays", list(range(7)))}
    start = time.fromisoformat(str(campaign.get("send_window_start") or "00:00"))
    end = time.fromisoformat(str(campaign.get("send_window_end") or "00:00"))
    current = local.timetz().replace(tzinfo=None)
    within_time = True if start == end else (
        start <= current < end if start < end else current >= start or current < end
    )
    allowed = local.weekday() in weekdays and within_time
    return {
        "allowed": allowed,
        "local_time": local.replace(microsecond=0).isoformat(),
        "timezone": str(campaign["timezone"]),
        "start": start.strftime("%H:%M"),
        "end": end.strftime("%H:%M"),
        "weekdays": sorted(weekdays),
        "reason": "open" if allowed else "outside_campaign_send_window",
    }


class TemplateCounter(Protocol):
    """The two facts the context layer needs from the sending pipeline.

    Deliberately this narrow: outreach must not import the AI package, and a
    counter must not be able to ask for anything back.  ``ContextLayer`` satisfies
    this structurally, so wiring one in is an assignment in ``api/app.py``.

    Note the absence of any reply *content* parameter.  That a reply arrived is a
    fact worth counting; what it says is mailbox content and never leaves.
    """

    def record_send(
        self, *, workspace_id: str = ..., template_id: str, variant_id: str = ...
    ) -> None: ...

    def record_reply(
        self, *, workspace_id: str = ..., template_id: str, variant_id: str = ...
    ) -> None: ...


class OutreachEngine:
    """Application service for the local CRM, independent of UI and AI vendor."""

    def __init__(
        self,
        database_path: Path | str,
        *,
        template_file: Path | str | None = None,
        template_counter: TemplateCounter | None = None,
        workspace_id: str = "local",
    ):
        self.store = OutreachStore(database_path)
        self.store.initialize()
        self.email_expert = LocalEmailExpert(self.store)
        # Optional: counting reply rates is useful but never required to send.
        self.template_counter = template_counter
        self.workspace_id = workspace_id
        self._lock = threading.RLock()
        seed_path = Path(template_file) if template_file else DEFAULT_TEMPLATE_FILE
        if seed_path.exists():
            self.email_expert.seed_templates(seed_path)
        patterns = seed_path.parent / "transferable_patterns.md"
        if patterns.exists():
            import_expert_documents(
                self.store,
                [patterns],
                expert_name="off_CRM product team",
                tags="owned,transferable-patterns",
                source_type="owned_notes",
                rights_basis="owned",
            )

    def close(self) -> None:
        self.store.close()

    # ── reply-rate counting ────────────────────────────────────────────────
    #
    # Two facts, counted as they happen: this template went out, this template
    # earned a reply.  Nothing else is passed on — no recipient, no address, not
    # a word of the reply itself.  A counter is optional and a failure here must
    # never lose a send that already left, so both helpers swallow their errors.

    @staticmethod
    def _template_key(row: dict[str, Any]) -> tuple[str, str]:
        """Identify a template the way the drafts and messages tables do.

        ``template_id`` is the wording; ``variant_id`` is which arm of the A/B
        test it is.  Old rows predate ``template_id``, so fall back to the stage.
        """
        return (
            clean_text(row.get("template_id")) or clean_text(row.get("stage")),
            clean_text(row.get("variant_id")),
        )

    def _count_send(self, draft: dict[str, Any]) -> None:
        if self.template_counter is None:
            return
        template_id, variant_id = self._template_key(draft)
        if not template_id:
            return
        try:
            self.template_counter.record_send(
                workspace_id=self.workspace_id, template_id=template_id, variant_id=variant_id
            )
        except Exception:  # pragma: no cover - counting must never break sending
            pass

    def _count_reply(self, message: dict[str, Any]) -> None:
        if self.template_counter is None:
            return
        template_id, variant_id = self._template_key(message)
        if not template_id:
            return
        try:
            self.template_counter.record_reply(
                workspace_id=self.workspace_id, template_id=template_id, variant_id=variant_id
            )
        except Exception:  # pragma: no cover - counting must never break a sync
            pass

    def create_campaign(
        self,
        *,
        name: str,
        daily_send_limit: int = 25,
        timezone_name: str = "Asia/Kolkata",
        followup1_working_days: int = 4,
        followup2_working_days: int = 6,
        approval_mode: str = "each_message",
        variants: Iterable[str] = ("A", "B"),
        send_window_start: str = "00:00",
        send_window_end: str = "00:00",
        send_weekdays: Iterable[int] = (0, 1, 2, 3, 4, 5, 6),
        experiment_hypothesis: str = "",
        experiment_metric: str = "reply_rate",
        experiment_min_sample: int = 40,
        control_variant: str = "A",
    ) -> str:
        with self._lock:
            return self.store.create_campaign(
                name=name,
                daily_send_limit=daily_send_limit,
                timezone_name=timezone_name,
                followup1_working_days=followup1_working_days,
                followup2_working_days=followup2_working_days,
                approval_mode=approval_mode,
                variants=variants,
                send_window_start=send_window_start,
                send_window_end=send_window_end,
                send_weekdays=send_weekdays,
                experiment_hypothesis=experiment_hypothesis,
                experiment_metric=experiment_metric,
                experiment_min_sample=experiment_min_sample,
                control_variant=control_variant,
            )

    def import_contacts(
        self,
        campaign_id: str,
        path: Path | str,
        *,
        default_category: str = DEFAULT_CATEGORY,
    ) -> dict[str, Any]:
        path = Path(path)
        table = read_input_table(path)
        lookup = _column_lookup(table.columns)
        result: dict[str, Any] = {
            "rows": len(table.index),
            "added": 0,
            "updated_or_existing": 0,
            "skipped": 0,
            "errors": [],
        }

        def value(raw: dict[str, Any], field: str) -> str:
            column = lookup.get(field)
            return clean_text(raw.get(column, "")) if column else ""

        with self._lock:
            self.store.get_campaign(campaign_id)
            for number, raw in enumerate(table.to_dict(orient="records"), start=2):
                full_name = value(raw, "full_name")
                first_name = value(raw, "first_name")
                last_name = value(raw, "last_name")
                if not full_name:
                    full_name = f"{first_name} {last_name}".strip()
                if not full_name:
                    result["skipped"] += 1
                    result["errors"].append({"row": number, "error": "Name is required"})
                    continue
                category = normalize_category(value(raw, "category"), default=default_category)
                questions = [
                    value(raw, "question_1"),
                    value(raw, "question_2"),
                    value(raw, "question_3"),
                ]
                contact = ContactInput(
                    full_name=full_name,
                    first_name=first_name,
                    last_name=last_name,
                    email=value(raw, "email"),
                    company=value(raw, "company"),
                    title=value(raw, "title"),
                    category=category,
                    route=value(raw, "route") or route_for_category(category),
                    linkedin_url=value(raw, "linkedin_url"),
                    public_hook=value(raw, "public_hook"),
                    hook_source=value(raw, "hook_source"),
                    hook_date=value(raw, "hook_date"),
                    tension=value(raw, "tension"),
                    identity_line=value(raw, "identity_line"),
                    contribution=value(raw, "contribution"),
                    questions=[item for item in questions if item],
                    notes=value(raw, "notes"),
                    source_ref=f"{path.name}:row:{number}",
                    source_data={str(key): clean_text(item) for key, item in raw.items()},
                    recipient_timezone=value(raw, "recipient_timezone"),
                )
                try:
                    contact_id = self.store.upsert_contact(contact)
                    _, added = self.store.add_contact_to_campaign(campaign_id, contact_id)
                except (ValueError, KeyError) as exc:
                    result["skipped"] += 1
                    result["errors"].append({"row": number, "error": str(exc)})
                    continue
                if added:
                    result["added"] += 1
                else:
                    result["updated_or_existing"] += 1
            self.store.add_event(campaign_id, "contacts_imported", result)
        return result

    def generate_drafts(
        self,
        campaign_id: str,
        *,
        campaign_contact_ids: Iterable[str] = (),
        stages: Iterable[str] = MESSAGE_STAGES,
        provider: AIProvider | None = None,
    ) -> dict[str, Any]:
        requested_ids = set(campaign_contact_ids)
        requested_stages = list(dict.fromkeys(stages))
        unknown = [stage for stage in requested_stages if stage not in MESSAGE_STAGES]
        if unknown:
            raise ValueError("Unknown draft stages: " + ", ".join(unknown))
        generated = 0
        blocked = 0
        failures: list[dict[str, str]] = []
        with self._lock:
            contacts = self.store.campaign_contacts(campaign_id)
            contacts = [
                item
                for item in contacts
                if item.get("status") not in {"replied", "stopped", "completed"}
            ]
            if requested_ids:
                contacts = [item for item in contacts if item["id"] in requested_ids]
            for contact in contacts:
                original_subject = ""
                for stage in requested_stages:
                    try:
                        draft = self.email_expert.create_draft(
                            contact=contact,
                            stage=stage,
                            variant_id=str(contact["variant_id"]),
                            provider=provider,
                            original_subject=original_subject,
                            campaign_id=campaign_id,
                        )
                        self.store.save_draft(str(contact["id"]), draft)
                        generated += 1
                        if not draft.audit.sendable:
                            blocked += 1
                        if stage == INITIAL:
                            original_subject = draft.subject
                    except Exception as exc:
                        failures.append(
                            {
                                "campaign_contact_id": str(contact["id"]),
                                "stage": stage,
                                "error": str(exc),
                            }
                        )
            result = {"generated": generated, "blocked": blocked, "failures": failures}
            provider_audit = getattr(provider, "last_run", None)
            if provider_audit:
                result["provider_audit"] = provider_audit
            self.store.add_event(campaign_id, "drafts_generated", result)
            return result

    def edit_draft(
        self, campaign_id: str, draft_id: str, *, subject: str, body: str
    ) -> dict[str, Any]:
        with self._lock:
            current = self.store.get_draft_by_id(campaign_id, draft_id)
            contact = self.store.get_campaign_contact(
                campaign_id, str(current["campaign_contact_id"])
            )
            audited = self.email_expert.audit_edited_draft(
                contact=contact,
                stage=str(current["stage"]),
                variant_id=str(current["variant_id"]),
                template_id=str(current["template_id"]),
                subject=subject,
                body=body,
                retrieval_refs=current.get("retrieval_refs") or [],
                generation_meta=current.get("generation_meta") or {},
            )
            self.store.update_draft_content(draft_id, audited)
            self.email_expert.memory.remember_edit(
                contact=contact,
                stage=str(current["stage"]),
                variant_id=str(current["variant_id"]),
                before_subject=str(current["subject"]),
                before_body=str(current["body"]),
                after_subject=audited.subject,
                after_body=audited.body,
                campaign_id=campaign_id,
            )
            self.store.add_event(
                campaign_id,
                "draft_edited",
                {"draft_id": draft_id, "score": audited.audit.score},
                campaign_contact_id=str(current["campaign_contact_id"]),
            )
            return self.store.get_draft_by_id(campaign_id, draft_id)

    def bulk_replace_drafts(
        self,
        campaign_id: str,
        *,
        find: str,
        replace: str,
        draft_ids: Iterable[str] = (),
        stages: Iterable[str] = (),
        fields: Iterable[str] = ("subject", "body"),
        preview_only: bool = True,
    ) -> dict[str, Any]:
        if not find:
            raise ValueError("find text is required")
        selected_fields = list(dict.fromkeys(fields))
        if not selected_fields or any(field not in {"subject", "body"} for field in selected_fields):
            raise ValueError("fields must contain subject and/or body")
        selected_ids = set(draft_ids)
        selected_stages = set(stages)
        rows, _ = self.store.list_drafts(campaign_id, limit=100000)
        matches: list[dict[str, Any]] = []
        for row in rows:
            if selected_ids and row["id"] not in selected_ids:
                continue
            if selected_stages and row["stage"] not in selected_stages:
                continue
            if row.get("sent_at"):
                continue
            occurrences = sum(str(row[field]).count(find) for field in selected_fields)
            if occurrences:
                matches.append({"draft_id": row["id"], "occurrences": occurrences})
        if preview_only:
            return {
                "preview": True,
                "matched_drafts": len(matches),
                "occurrences": sum(item["occurrences"] for item in matches),
                "items": matches[:100],
            }
        changed = 0
        blocked = 0
        for match in matches:
            current = self.store.get_draft_by_id(campaign_id, str(match["draft_id"]))
            subject = str(current["subject"])
            body = str(current["body"])
            if "subject" in selected_fields:
                subject = subject.replace(find, replace)
            if "body" in selected_fields:
                body = body.replace(find, replace)
            updated = self.edit_draft(
                campaign_id,
                str(current["id"]),
                subject=subject,
                body=body,
            )
            changed += 1
            blocked += int(not updated["sendable"])
        if changed:
            self.email_expert.memory.remember_bulk_rule(
                campaign_id=campaign_id,
                find=find,
                replace=replace,
                fields=selected_fields,
                changed=changed,
            )
        result = {"preview": False, "changed": changed, "blocked": blocked}
        self.store.add_event(campaign_id, "drafts_bulk_corrected", result)
        return result

    def schedule_drafts(
        self,
        campaign_id: str,
        *,
        draft_ids: Iterable[str],
        scheduled_at: datetime | None,
    ) -> dict[str, int]:
        result = self.store.schedule_drafts(
            campaign_id, draft_ids=draft_ids, scheduled_at=scheduled_at
        )
        self.store.add_event(
            campaign_id,
            "drafts_scheduled",
            {**result, "scheduled_at": scheduled_at.isoformat() if scheduled_at else None},
        )
        return result

    def approve_drafts(
        self,
        campaign_id: str,
        *,
        draft_ids: Iterable[str] = (),
        stages: Iterable[str] = (),
    ) -> dict[str, int]:
        with self._lock:
            result = self.store.approve_drafts(
                campaign_id, draft_ids=draft_ids, stages=stages
            )
            self.store.add_event(campaign_id, "drafts_approved", result)
            return result

    def sync_replies(
        self,
        campaign_id: str,
        *,
        mail_provider: MailProvider,
        own_email: str,
        now: datetime | None = None,
    ) -> dict[str, int]:
        now = now or utc_now()
        with self._lock:
            earliest = self.store.earliest_outgoing_at(campaign_id)
            since = (earliest - timedelta(days=1)) if earliest else (now - timedelta(days=30))
            incoming = mail_provider.list_replies(since=since, own_email=own_email)
            matched = 0
            for message in incoming:
                updated = self.store.record_reply(campaign_id, message)
                matched += len(updated)
                for campaign_contact_id in updated:
                    contact = self.store.get_campaign_contact(campaign_id, campaign_contact_id)
                    self.email_expert.memory.remember_reply(
                        campaign_id=campaign_id,
                        campaign_contact_id=campaign_contact_id,
                        stage=str(contact.get("current_stage", "")),
                        variant_id=str(contact.get("variant_id", "")),
                    )
                    # Credit the template that was actually sent, not the contact's
                    # current stage — by now the contact has usually moved on.
                    self._count_reply(self.store.last_outgoing(campaign_contact_id) or {})
            result = {"scanned": len(incoming), "matched": matched}
            self.store.add_event(campaign_id, "replies_synced", result)
            return result

    def run_due(
        self,
        campaign_id: str,
        *,
        mail_provider: MailProvider,
        own_email: str,
        now: datetime | None = None,
        sync_replies_first: bool = True,
        max_messages: int | None = None,
    ) -> dict[str, Any]:
        now = now or utc_now()
        with self._lock:
            campaign = self.store.get_campaign(campaign_id)
            if campaign["status"] != "active":
                raise ValueError("Campaign must be active before sending")
            reply_result = {"scanned": 0, "matched": 0}
            if sync_replies_first:
                reply_result = self.sync_replies(
                    campaign_id,
                    mail_provider=mail_provider,
                    own_email=own_email,
                    now=now,
                )
            window = campaign_send_window(campaign, now)
            if not window["allowed"]:
                result = {
                    "sent": [],
                    "sent_count": 0,
                    "daily_limit": int(campaign["daily_send_limit"]),
                    "already_sent_today": 0,
                    "remaining_today": int(campaign["daily_send_limit"]),
                    "replies": reply_result,
                    "skipped": [{"reason": window["reason"]}],
                    "failed": [],
                    "send_window": window,
                }
                self.store.add_event(campaign_id, "send_run_deferred", result)
                return result
            self.store.recover_stale_sending(
                campaign_id, before=now - timedelta(minutes=15)
            )
            day_start, day_end = local_day_bounds(now, str(campaign["timezone"]))
            already_sent = self.store.sent_count_between(campaign_id, day_start, day_end)
            allowance = max(0, int(campaign["daily_send_limit"]) - already_sent)
            if max_messages is not None:
                allowance = min(allowance, max(0, max_messages))
            sent: list[dict[str, str]] = []
            skipped: list[dict[str, str]] = []
            failed: list[dict[str, str]] = []
            for queued in self.store.send_queue(campaign_id, now=now):
                if len(sent) >= allowance:
                    break
                if queued["status"] in {"replied", "stopped", "completed"}:
                    continue
                if not queued["is_due"]:
                    continue
                draft_id = clean_text(queued.get("draft_id"))
                if not draft_id:
                    skipped.append(
                        {"campaign_contact_id": str(queued["campaign_contact_id"]), "reason": "draft_missing"}
                    )
                    continue
                if queued.get("approval_status") != "approved" or not queued.get("sendable"):
                    skipped.append(
                        {"campaign_contact_id": str(queued["campaign_contact_id"]), "reason": "approval_required"}
                    )
                    continue
                email = clean_text(queued.get("email")).lower()
                if not email or "@" not in email:
                    skipped.append(
                        {"campaign_contact_id": str(queued["campaign_contact_id"]), "reason": "valid_email_required"}
                    )
                    continue
                draft = self.store.get_draft_by_id(campaign_id, draft_id)
                idempotency_key = hashlib.sha256(
                    f"{campaign_id}:{draft_id}:{draft['revision']}".encode("utf-8")
                ).hexdigest()
                if self.store.get_message_by_idempotency(idempotency_key):
                    skipped.append(
                        {"campaign_contact_id": str(queued["campaign_contact_id"]), "reason": "already_recorded"}
                    )
                    continue
                if not self.store.claim_draft_for_send(draft_id, now):
                    continue
                last = self.store.last_outgoing(str(queued["campaign_contact_id"])) or {}
                try:
                    provider_result = mail_provider.send_message(
                        to_email=email,
                        subject=str(draft["subject"]),
                        body=str(draft["body"]),
                        thread_id=clean_text(last.get("thread_id")),
                        in_reply_to=clean_text(last.get("internet_message_id")),
                        references=clean_text(last.get("internet_message_id")),
                        idempotency_key=idempotency_key,
                    )
                    stage = str(draft["stage"])
                    if stage == INITIAL:
                        next_action = add_working_days(
                            now, int(campaign["followup1_working_days"]), str(campaign["timezone"])
                        )
                        final_status = "waiting_followup"
                    elif stage == FOLLOWUP_1:
                        next_action = add_working_days(
                            now, int(campaign["followup2_working_days"]), str(campaign["timezone"])
                        )
                        final_status = "waiting_followup"
                    else:
                        next_action = None
                        final_status = "completed"
                    self.store.record_sent(
                        campaign_contact_id=str(queued["campaign_contact_id"]),
                        draft=draft,
                        result=provider_result,
                        to_email=email,
                        sent_at=now,
                        next_action_at=next_action,
                        final_status=final_status,
                        idempotency_key=idempotency_key,
                    )
                    sent.append({"draft_id": draft_id, "to": email, "stage": stage})
                    self._count_send(draft)
                except Exception as exc:
                    self.store.mark_send_failed(draft_id, str(exc))
                    failed.append({"draft_id": draft_id, "error": str(exc)})
            result = {
                "sent": sent,
                "sent_count": len(sent),
                "daily_limit": int(campaign["daily_send_limit"]),
                "already_sent_today": already_sent,
                "remaining_today": max(0, allowance - len(sent)),
                "replies": reply_result,
                "skipped": skipped,
                "failed": failed,
                "send_window": window,
            }
            self.store.add_event(campaign_id, "send_run_completed", result)
            return result

    def import_expert_sources(
        self,
        paths: Iterable[Path],
        *,
        expert_name: str = "",
        tags: str = "",
        source_url: str = "",
        source_type: str = "notes",
        rights_basis: str = "user_provided",
    ) -> dict[str, int]:
        with self._lock:
            result = import_expert_documents(
                self.store,
                paths,
                expert_name=expert_name,
                tags=tags,
                source_url=source_url,
                source_type=source_type,
                rights_basis=rights_basis,
            )
            return {
                "documents": result.documents,
                "chunks_added": result.chunks_added,
                "chunks_skipped": result.chunks_skipped,
            }

    def export_crm(self, campaign_id: str, destination: Path | str) -> Path:
        destination = Path(destination)
        rows = []
        with self._lock:
            for item in self.store.campaign_contacts(campaign_id):
                last = self.store.last_outgoing(str(item["id"])) or {}
                row = {
                        "Checkbox": bool(item.get("checkbox")),
                        "Outreach Date": clean_text(last.get("sent_at")),
                        "POI Name": clean_text(item.get("full_name")),
                        "POI Response": clean_text(item.get("poi_response")),
                        "Follow-Up": clean_text(item.get("next_action_at")),
                        "Meeting Transcript": clean_text(item.get("meeting_transcript")),
                        "Email": clean_text(item.get("email")),
                        "Company": clean_text(item.get("company")),
                        "Title": clean_text(item.get("title")),
                        "Category": clean_text(item.get("category")),
                        "Route": clean_text(item.get("route")),
                        "Variant": clean_text(item.get("variant_id")),
                        "Status": clean_text(item.get("status")),
                        "Current Stage": clean_text(item.get("current_stage")),
                        "Public Hook": clean_text(item.get("public_hook")),
                        "Hook Source": clean_text(item.get("hook_source")),
                        "LinkedIn": clean_text(item.get("linkedin_url")),
                        "Notes": clean_text(item.get("notes")),
                }
                rows.append(
                    {
                        key: self._spreadsheet_safe(value) if isinstance(value, str) else value
                        for key, value in row.items()
                    }
                )
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.suffix.lower() == ".csv":
            with destination.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else [
                    "Checkbox", "Outreach Date", "POI Name", "POI Response", "Follow-Up", "Meeting Transcript"
                ])
                writer.writeheader()
                writer.writerows(rows)
        elif destination.suffix.lower() == ".xlsx":
            pd.DataFrame(rows).to_excel(destination, index=False)
        else:
            raise ValueError("CRM export must be CSV or XLSX")
        return destination

    @staticmethod
    def _spreadsheet_safe(value: str) -> str:
        """Prevent formula execution when an exported file is opened."""
        if value.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + value
        return value

    def backup_database(self, destination: Path | str) -> Path:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self.store.connection.commit()
            with OutreachStore(destination) as target:
                self.store.connection.backup(target.connection)
        return destination
