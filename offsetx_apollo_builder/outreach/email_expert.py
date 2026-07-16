from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from ..locked_categories import LOCKED_CATEGORIES
from .models import (
    AIProvider,
    CLIENT_ROUTE,
    EXPERT_ROUTE,
    FOLLOWUP_1,
    FOLLOWUP_2,
    INITIAL,
    DraftAudit,
    DraftContent,
    clean_text,
)
from .store import OutreachStore

OFFSETX_SIGNATURE = """Best,
Kunal Wagh
Building OffsetX - carbon-market infrastructure in India
Email: waghkunal1997@gmail.com
LinkedIn: https://www.linkedin.com/in/kunal-wagh-982411184/"""

FOLLOWUP_1_REQUIRED = (
    "This is my current understanding. I may be wrong. "
    "Would you be open to 15 minutes to pressure-test it?"
)
FOLLOWUP_2_REQUIRED = "Even a one-line take would help."

FORBIDDEN_PHRASES = (
    "no pressure",
    "in exchange",
    "better price points",
    "quick call",
    "quick question",
    "just following up",
    "checking in",
    "touching base",
    "whichever is easier",
    "whichever's easier",
    "no-strings",
    "before you spend a rupee",
    "have you given up",
    "i came across your impressive profile",
    "this is not a sales pitch",
    "not selling anything",
    "out of india",
)

CONFIDENTIAL_TERMS = (
    "registry-normalisation",
    "registry normalization",
    "internal identifier",
    "customer list",
    "lead source",
    "our pricing",
    "our data model",
    "our architecture",
)

RIGHTS_BASES = {
    "user_provided",
    "owned",
    "licensed",
    "public_domain",
    "permission_granted",
    "fair_use_notes",
}


class _SafeFormat(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


@dataclass(slots=True)
class ImportResult:
    documents: int = 0
    chunks_added: int = 0
    chunks_skipped: int = 0


def route_for_category(category: str) -> str:
    if category in {
        "Consultants / Advisors",
        "Policy / Government / Think Tanks",
        "Verification / Audit / MRV",
    }:
        return EXPERT_ROUTE
    return CLIENT_ROUTE


def _body_word_count(body: str) -> int:
    content = body.split("Best,", 1)[0]
    return len(re.findall(r"\b[\w'-]+\b", content))


def audit_draft(
    *,
    stage: str,
    route: str,
    category: str,
    public_hook: str,
    hook_source: str,
    subject: str,
    body: str,
) -> DraftAudit:
    errors: list[str] = []
    warnings: list[str] = []
    lowered = body.lower()
    word_count = _body_word_count(body)
    question_count = body.count("?")

    if not subject.strip():
        errors.append("Subject is empty")
    if len(subject.split()) > 7 and not subject.lower().startswith("re:"):
        warnings.append("Subject is longer than seven words")
    if OFFSETX_SIGNATURE not in body:
        errors.append("Exact OffsetX signature is missing")
    if "—" in body or "–" in body or "—" in subject or "–" in subject:
        errors.append("Em dash or en dash is not allowed")
    unresolved = sorted(set(re.findall(r"\{[a-zA-Z0-9_]+\}", subject + "\n" + body)))
    if unresolved:
        errors.append("Unresolved template fields: " + ", ".join(unresolved))
    for phrase in FORBIDDEN_PHRASES:
        if phrase in lowered:
            errors.append(f"Forbidden phrase: {phrase}")
    for phrase in CONFIDENTIAL_TERMS:
        if phrase in lowered:
            errors.append(f"Confidential detail risk: {phrase}")

    if stage == INITIAL:
        if category not in LOCKED_CATEGORIES:
            errors.append("Category is not one of the nine locked categories")
        if route not in {EXPERT_ROUTE, CLIENT_ROUTE}:
            errors.append("Recipient route is invalid")
        if not clean_text(public_hook):
            errors.append("A verified public hook is required")
        if not clean_text(hook_source):
            errors.append("A public hook source is required")
        if question_count != 1:
            errors.append("First touch must contain exactly one question mark")
        if word_count < 65:
            warnings.append("First touch may be too short to carry enough context")
        if word_count > 125:
            errors.append("First touch exceeds 125 words before the signature")
        if route == CLIENT_ROUTE and "15 minutes" in lowered:
            errors.append("Cold future-client first touch must use an interest-first CTA")
        if route == EXPERT_ROUTE and "15 minutes" not in lowered:
            warnings.append("Expert first touch does not use the expected 15-minute comparison")
    elif stage == FOLLOWUP_1:
        if FOLLOWUP_1_REQUIRED not in body:
            errors.append("Day 4 follow-up is missing the required pressure-test sentence")
        if question_count != 1:
            errors.append("Day 4 follow-up must contain exactly one question mark")
        if word_count > 100:
            warnings.append("Day 4 follow-up is longer than needed")
    elif stage == FOLLOWUP_2:
        if FOLLOWUP_2_REQUIRED not in body:
            errors.append("Day 10 follow-up is missing the one-line-take close")
        if question_count > 1:
            errors.append("Day 10 follow-up contains too many questions")
        if word_count > 100:
            warnings.append("Day 10 follow-up is longer than needed")
    else:
        errors.append(f"Unknown message stage: {stage}")

    score = max(0, 100 - 25 * len(errors) - 5 * len(warnings))
    return DraftAudit(
        score=score,
        errors=errors,
        warnings=warnings,
        checks={
            "word_count_before_signature": word_count,
            "question_count": question_count,
            "route": route,
            "category": category,
            "hook_source": hook_source,
        },
    )


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("AI provider did not return a JSON object")
        value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("AI provider output must be a JSON object")
    return value


def normalize_email_body(body: str) -> str:
    lines = [line.rstrip() for line in body.replace("\r\n", "\n").split("\n")]
    output: list[str] = []
    previous_blank = False
    for line in lines:
        blank = not line.strip()
        if blank and previous_blank:
            continue
        output.append(line)
        previous_blank = blank
    return "\n".join(output).strip()


class LocalEmailExpert:
    """Local template retrieval plus optional provider-based personalisation."""

    def __init__(self, store: OutreachStore):
        self.store = store

    def seed_templates(self, path: Path | str) -> int:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        templates = payload.get("templates", payload) if isinstance(payload, dict) else payload
        if not isinstance(templates, list):
            raise ValueError("Template file must contain a list or a templates list")
        for item in templates:
            if not isinstance(item, dict):
                raise ValueError("Every template must be an object")
            self.store.upsert_template(item)
        return len(templates)

    def create_draft(
        self,
        *,
        contact: dict[str, Any],
        stage: str,
        variant_id: str,
        provider: AIProvider | None = None,
        original_subject: str = "",
    ) -> DraftContent:
        route = clean_text(contact.get("route")) or route_for_category(
            clean_text(contact.get("category"))
        )
        category = clean_text(contact.get("category"))
        templates = self.store.matching_templates(
            stage=stage,
            route=route,
            category=category,
            variant_id=variant_id,
        )
        if not templates:
            raise LookupError(
                f"No active template for stage={stage}, route={route}, "
                f"category={category}, variant={variant_id}"
            )
        template = templates[0]
        try:
            questions = json.loads(contact.get("questions_json") or "[]")
        except json.JSONDecodeError:
            questions = []
        values = _SafeFormat(
            first_name=clean_text(contact.get("first_name"))
            or clean_text(contact.get("full_name")).split(" ", 1)[0],
            full_name=clean_text(contact.get("full_name")),
            company=clean_text(contact.get("company")) or "your team",
            title=clean_text(contact.get("title")),
            category=category,
            route=route,
            public_hook=clean_text(contact.get("public_hook")),
            hook_source=clean_text(contact.get("hook_source")),
            tension=clean_text(contact.get("tension")),
            identity_line=clean_text(contact.get("identity_line")),
            contribution=clean_text(contact.get("contribution")),
            question_1=questions[0] if len(questions) > 0 else "",
            question_2=questions[1] if len(questions) > 1 else "",
            question_3=questions[2] if len(questions) > 2 else "",
            original_subject=original_subject or "the evidence handoff",
            signature=OFFSETX_SIGNATURE,
        )
        subject = str(template["subject_template"]).format_map(values).strip()
        body = normalize_email_body(str(template["body_template"]).format_map(values))

        retrieval_query = " ".join(
            filter(
                None,
                [category, route, values["tension"], values["public_hook"], values["company"]],
            )
        )
        chunks = self.store.search_expert_chunks(retrieval_query, limit=4)
        retrieval_refs = [
            f"{chunk.get('document_name', '')}#{str(chunk.get('id', ''))[:8]}"
            for chunk in chunks
        ]

        if provider is not None:
            source_material = "\n\n".join(
                f"Reference {index + 1}: {str(chunk.get('content', ''))[:900]}"
                for index, chunk in enumerate(chunks)
            )
            system_prompt = (
                "You are the OffsetX email expert. Write in a calm, technical, human voice. "
                "Use the supplied structure and facts only. Do not imitate any named writer's "
                "distinctive voice. Never invent a hook, claim, relationship, quote or result. "
                "Preserve the exact signature. Return JSON with subject and body only."
            )
            user_prompt = json.dumps(
                {
                    "schema_version": 1,
                    "stage": stage,
                    "recipient": dict(values),
                    "selected_template": {"subject": subject, "body": body},
                    "retrieved_guidance": source_material,
                    "hard_rules": {
                        "one_question_mark": stage != FOLLOWUP_2,
                        "exact_day4_sentence": FOLLOWUP_1_REQUIRED if stage == FOLLOWUP_1 else "",
                        "exact_day10_sentence": FOLLOWUP_2_REQUIRED if stage == FOLLOWUP_2 else "",
                        "future_client_first_touch_has_no_time_ask": route == CLIENT_ROUTE
                        and stage == INITIAL,
                        "signature": OFFSETX_SIGNATURE,
                    },
                },
                ensure_ascii=False,
            )
            generated = _extract_json_object(
                provider.generate(system_prompt=system_prompt, user_prompt=user_prompt)
            )
            subject = clean_text(generated.get("subject"))
            body = normalize_email_body(str(generated.get("body", "")))

        audit = audit_draft(
            stage=stage,
            route=route,
            category=category,
            public_hook=clean_text(contact.get("public_hook")),
            hook_source=clean_text(contact.get("hook_source")),
            subject=subject,
            body=body,
        )
        return DraftContent(
            subject=subject,
            body=body,
            stage=stage,
            variant_id=variant_id,
            template_id=str(template["id"]),
            audit=audit,
            retrieval_refs=retrieval_refs,
        )

    def audit_edited_draft(
        self,
        *,
        contact: dict[str, Any],
        stage: str,
        variant_id: str,
        template_id: str,
        subject: str,
        body: str,
        retrieval_refs: Iterable[str] = (),
    ) -> DraftContent:
        route = clean_text(contact.get("route")) or route_for_category(
            clean_text(contact.get("category"))
        )
        audit = audit_draft(
            stage=stage,
            route=route,
            category=clean_text(contact.get("category")),
            public_hook=clean_text(contact.get("public_hook")),
            hook_source=clean_text(contact.get("hook_source")),
            subject=subject.strip(),
            body=normalize_email_body(body),
        )
        return DraftContent(
            subject=subject.strip(),
            body=normalize_email_body(body),
            stage=stage,
            variant_id=variant_id,
            template_id=template_id,
            audit=audit,
            retrieval_refs=list(retrieval_refs),
        )


def _chunk_text(text: str, *, target_chars: int = 1200) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_size = 0
    for paragraph in paragraphs:
        if current and current_size + len(paragraph) + 2 > target_chars:
            chunks.append("\n\n".join(current))
            current = []
            current_size = 0
        if len(paragraph) > target_chars * 2:
            sentences = re.split(r"(?<=[.!?])\s+", paragraph)
            for sentence in sentences:
                if current and current_size + len(sentence) + 1 > target_chars:
                    chunks.append(" ".join(current))
                    current = []
                    current_size = 0
                current.append(sentence)
                current_size += len(sentence) + 1
        else:
            current.append(paragraph)
            current_size += len(paragraph) + 2
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def import_expert_documents(
    store: OutreachStore,
    paths: Iterable[Path],
    *,
    expert_name: str = "",
    tags: str = "",
    source_url: str = "",
    source_type: str = "notes",
    rights_basis: str = "user_provided",
) -> ImportResult:
    if rights_basis not in RIGHTS_BASES:
        raise ValueError("Unsupported rights_basis")
    result = ImportResult()
    expanded: list[Path] = []
    for path in paths:
        if path.is_dir():
            expanded.extend(
                candidate
                for candidate in path.rglob("*")
                if candidate.is_file() and candidate.suffix.lower() in {".md", ".txt"}
            )
        elif path.suffix.lower() in {".md", ".txt"}:
            expanded.append(path)
    for path in sorted(set(expanded)):
        text = path.read_text(encoding="utf-8")
        chunks = _chunk_text(text)
        result.documents += 1
        for chunk in chunks:
            inserted = store.add_expert_chunk(
                document_name=path.name,
                content=chunk,
                expert_name=expert_name,
                tags=tags,
                source_ref=str(path),
                source_url=source_url,
                source_type=source_type,
                rights_basis=rights_basis,
            )
            if inserted:
                result.chunks_added += 1
            else:
                result.chunks_skipped += 1
    return result
