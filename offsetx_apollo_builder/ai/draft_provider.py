"""The email expert's provider protocol over the one configured egress broker."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..observability import report_failure
from ..outreach.email_expert import OFFSETX_SIGNATURE, _extract_json_object
from .payload import COMPANY_TOKEN, PERSON_TOKEN, EgressRequest, PersonPublic
from .tiers import DataClass, DataPolicy


_IDENTITY_REFERENCE = re.compile(r"\b(?:PERSON|COMPANY)_\d+\b")


def _restore_identity(text: str, person: PersonPublic, maximum: int) -> str:
    replacements = {PERSON_TOKEN: person.full_name, COMPANY_TOKEN: person.company}
    size = len(text)
    for match in _IDENTITY_REFERENCE.finditer(text):
        if match.group() not in replacements:
            raise ValueError("The draft refers to an unknown recipient")
        size += len(replacements[match.group()]) - len(match.group())
    if size > maximum:
        raise ValueError("Restored draft exceeds its size limit")
    result = _IDENTITY_REFERENCE.sub(lambda match: replacements[match.group()], text).strip()
    if not result:
        raise ValueError("Restored draft is empty")
    return result


class ConnectorDraftError(ValueError):
    """A safe drafting failure; the reference links to the existing failure log."""


class ConnectorDraftProvider:
    def __init__(self, broker: Any, settings: Any, *, data_dir: Path | None = None):
        self.broker = broker
        self.settings = settings
        self.data_dir = data_dir
        self.last_run: dict[str, Any] = {}

    def preflight(self) -> None:
        self.broker.plan(EgressRequest(task_type="draft_email", data_class=DataClass.CAMPAIGN,
                                     minimum_policy=DataPolicy.STANDARD), self.settings)

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        self.last_run = {}
        try:
            offered = json.loads(user_prompt)
            recipient = offered.get("recipient") or {}
            blueprint = offered.get("template_blueprint") or {}
            # Recipient addresses have no slot in PersonPublic. Owner templates,
            # guidance and approved facts stay in policy-controlled fields.
            person = PersonPublic.from_contact(recipient)
            template = {
                "subject": str(blueprint.get("subject") or ""),
                "body": str(blueprint.get("body") or "").removesuffix(OFFSETX_SIGNATURE).strip(),
            }
            rules = offered.get("hard_rules") or {}
            notes = {
                "stage": str(offered.get("stage") or ""),
                "guidance": str(offered.get("retrieved_guidance") or ""),
                "approved_memory": str(offered.get("approved_memory") or ""),
                "hard_rules": {name: rules[name] for name in (
                    "one_question_mark", "exact_day4_sentence", "exact_day10_sentence",
                    "future_client_first_touch_has_no_time_ask",
                ) if name in rules},
            }
            request = EgressRequest(
                task_type="draft_email", data_class=DataClass.CAMPAIGN,
                instructions=(
                    "Write a calm, technical, plain-language outreach email using only supplied facts. "
                    "Do not invent a hook, claim, relationship, quote or result. Follow the supplied "
                    "stage and hard rules. Return a JSON object with subject and body strings only. "
                    "Do not include a signature; the application adds its exact approved signature locally."
                ),
                minimum_policy=DataPolicy.STANDARD,
                person=person, template_text=json.dumps(template, ensure_ascii=False),
                campaign_notes=json.dumps(notes, ensure_ascii=False),
            )
            result = self.broker.call(
                request, self.settings,
                system_prompt="Write a factual outreach draft from the supplied payload. Return only JSON subject and body strings. Never include a signature.",
                expect_json=True,
            )
            document = _extract_json_object(str(result.text or ""))
            # The broker's JSON normalizer adds its versioned envelope.
            if document.get("schema_version") == 1:
                document.pop("schema_version")
            if set(document) != {"subject", "body"}:
                raise ValueError("Draft output must contain only subject and body")
            subject, body = document["subject"], document["body"]
            if not isinstance(subject, str) or not isinstance(body, str):
                raise ValueError("Draft subject and body must be text")
            if not 1 <= len(subject.strip()) <= 200 or not 1 <= len(body.strip()) <= 8000:
                raise ValueError("Draft output is empty or exceeds its size limit")
            subject = _restore_identity(subject, person, 200)
            body = _restore_identity(body, person, 8000)
            body = body.strip() + "\n\n" + OFFSETX_SIGNATURE
            self.last_run = {
                "routing": "connectors", "provider_id": result.provider_id,
                "model_id": result.model_id, "policy": result.policy, "log_id": result.log_id,
                "attempts": [
                    {key: attempt[key] for key in ("provider_id", "model_id", "status", "log_id", "failure_kind") if key in attempt}
                    for attempt in getattr(result, "attempts", [])[:100]
                ],
            }
            return json.dumps({"subject": subject.strip(), "body": body}, ensure_ascii=False)
        except Exception as exc:
            reference = report_failure(exc, operation="draft.connectors", data_dir=self.data_dir,
                                       workspace=self.settings.workspace_id)
            self.last_run = {"routing": "connectors", "status": "failed", "error_id": reference}
            raise ConnectorDraftError(
                "AI drafting could not complete. Open Connectors to check provider access, "
                "data policy and quota, then retry explicitly. Reference: " + reference
            ) from None
