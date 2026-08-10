"""Two-mode campaign intake (§4D).

There are exactly two ways a campaign gets its people, and they are different
enough that conflating them is how mistakes happen:

**Generate** — you describe who you want and off_CRM goes and finds them.
Discovery and Apollo produce the rows; a model may help phrase the *search*, but
it never invents a contact.

**Parse** — you already have the list. A CSV, a spreadsheet, or a PDF someone
sent you. off_CRM reads it and that is all.

---

**Why this module is not in ``ai/``.**

A contact list is the densest possible concentration of exactly the material the
whole system exists to protect: real names, real addresses, real companies. If a
model parsed it, that single feature would leak more than every other path
combined.

So parsing is **deterministic and local**. ``pypdf`` extracts text on your
machine, patterns find the fields, and nothing about the file leaves. The import
rules are enforced by a test: this module may not import ``ai`` and may not
import a provider. Living outside the ``ai`` package is the structural reminder.

It is the same rule the campaign runner follows. The parts that touch real
contacts have no AI; the parts with AI have no real contacts.

---

**On PDFs, honestly.**

CSV and XLSX are structured — a column is a column, and reading one is exact.
A PDF is a picture of a table that happens to contain text. Extraction is
genuinely lossy: columns run together, a name may sit two lines above its
address, and a scanned page contains no text at all.

So PDF rows arrive marked ``needs_review`` and **cannot be sent without the
owner confirming them**. That is not a placeholder for better parsing later. It
is the correct behaviour: guessing which name belongs to which address, and
being wrong, means emailing a real person by the wrong name.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from .dedupe import norm_email, split_name
from .input_loader import normalize_input_rows, read_input_table

#: Suffixes each mode understands.
TABLE_SUFFIXES = frozenset({".csv", ".xlsx", ".xls"})
PDF_SUFFIXES = frozenset({".pdf"})

#: Pages read from a PDF. A contact list longer than this is a spreadsheet
#: someone printed, and should be re-exported rather than scraped.
MAX_PDF_PAGES = 200

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)

#: Words that mean a "name" is really a column header or a footer.
_NOT_A_NAME = frozenset(
    {
        "name", "full name", "contact", "contacts", "email", "e-mail", "address",
        "company", "organisation", "organization", "title", "position", "role",
        "page", "total", "confidential", "sheet", "list", "phone", "mobile",
    }
)


class IntakeMode(str, Enum):
    """How a campaign gets its people."""

    GENERATE = "generate"
    PARSE = "parse"

    @property
    def label(self) -> str:
        return {
            IntakeMode.GENERATE: "Find people for me",
            IntakeMode.PARSE: "I already have the list",
        }[self]

    @property
    def description(self) -> str:
        return {
            IntakeMode.GENERATE: (
                "Describe who you want to reach. off_CRM searches for matching "
                "people and builds the list. Nothing is sent until you approve it."
            ),
            IntakeMode.PARSE: (
                "Upload a CSV, spreadsheet or PDF you already have. off_CRM reads "
                "it on this machine — no AI model sees the file, ever."
            ),
        }[self]


class IntakeError(RuntimeError):
    """A file could not be read at all."""


@dataclass(slots=True)
class IntakeRow:
    """One person found in a file, and how much to trust the reading."""

    email: str = ""
    full_name: str = ""
    first_name: str = ""
    last_name: str = ""
    company: str = ""
    title: str = ""
    source_line: str = ""
    page: int = 0
    needs_review: bool = False
    notes: tuple[str, ...] = ()

    @property
    def usable(self) -> bool:
        """Has an address, so it could in principle be sent to."""
        return bool(self.email)

    def to_dict(self) -> dict[str, Any]:
        return {
            "email": self.email,
            "full_name": self.full_name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "company": self.company,
            "title": self.title,
            "page": self.page,
            "needs_review": self.needs_review,
            "notes": list(self.notes),
            "usable": self.usable,
        }


@dataclass(slots=True)
class IntakeResult:
    """What came out of a file, and what the owner still has to decide."""

    mode: IntakeMode
    source_name: str
    rows: list[IntakeRow] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    parsed_with: str = ""

    @property
    def usable_rows(self) -> list[IntakeRow]:
        return [row for row in self.rows if row.usable]

    @property
    def review_rows(self) -> list[IntakeRow]:
        return [row for row in self.rows if row.needs_review]

    @property
    def ready_to_send(self) -> bool:
        """Whether this could go straight into a campaign.

        False whenever anything needs review. A PDF never returns True on its
        own, by design — see the module docstring.
        """
        return bool(self.usable_rows) and not self.review_rows

    def summary(self) -> str:
        """One sentence for the screen, saying what happens next."""
        if not self.rows:
            return f"No contacts found in {self.source_name}."
        found = len(self.usable_rows)
        review = len(self.review_rows)
        if not found:
            return (
                f"Read {len(self.rows)} rows from {self.source_name} but none had "
                "an email address, so none can be sent to."
            )
        if review:
            return (
                f"Found {found} contacts in {self.source_name}. "
                f"{review} need checking before anything is sent — the reading was "
                "not certain enough to trust unseen."
            )
        return f"Found {found} contacts in {self.source_name}, ready to review."

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "source_name": self.source_name,
            "parsed_with": self.parsed_with,
            "rows": [row.to_dict() for row in self.rows],
            "rejected": self.rejected,
            "warnings": self.warnings,
            "counts": {
                "total": len(self.rows),
                "usable": len(self.usable_rows),
                "needs_review": len(self.review_rows),
            },
            "ready_to_send": self.ready_to_send,
            "summary": self.summary(),
        }


# ── the entry point ─────────────────────────────────────────────────────────


def supported_suffixes() -> tuple[str, ...]:
    return tuple(sorted(TABLE_SUFFIXES | PDF_SUFFIXES))


def parse_file(
    path: Path | str, *, default_category: str = "", max_pages: int = MAX_PDF_PAGES
) -> IntakeResult:
    """Read a contact list. Deterministic, local, no model involved.

    Dispatches on the suffix rather than sniffing content, so an unexpected file
    is refused with a readable sentence instead of being half-parsed.
    """
    source = Path(path)
    if not source.exists():
        raise IntakeError(f"There is no file at {source}.")
    suffix = source.suffix.lower()
    if suffix in TABLE_SUFFIXES:
        return _parse_table(source, default_category=default_category)
    if suffix in PDF_SUFFIXES:
        return _parse_pdf(source, max_pages=max_pages)
    raise IntakeError(
        f"off_CRM cannot read {suffix or 'a file with no extension'}. "
        f"Supported: {', '.join(supported_suffixes())}."
    )


# ── tables: exact ───────────────────────────────────────────────────────────


def _parse_table(source: Path, *, default_category: str) -> IntakeResult:
    """CSV and XLSX go through the existing loader.

    A column is a column. There is nothing to guess, so nothing is flagged for
    review — the header told us what each field is.
    """
    result = IntakeResult(
        mode=IntakeMode.PARSE, source_name=source.name, parsed_with="table"
    )
    try:
        frame = read_input_table(source)
    except Exception as exc:  # noqa: BLE001 - reported, not raised through
        raise IntakeError(f"Could not read {source.name}: {exc}") from exc

    normalised = normalize_input_rows(
        frame, source_file=source, default_category=default_category
    )
    for index, row in enumerate(normalised, start=1):
        email = norm_email(str(row.get("email", "")))
        # `normalize_input_rows` emits the CRM's own field names — `name` and
        # `organization_name` — rather than the header text. Reading the wrong
        # keys here silently produced rows with no name at all, which looked
        # like a parsing failure and was really a mapping one.
        entry = IntakeRow(
            email=email,
            full_name=str(row.get("name", "")).strip(),
            first_name=str(row.get("first_name", "")).strip(),
            last_name=str(row.get("last_name", "")).strip(),
            company=str(row.get("organization_name", "")).strip(),
            title=str(row.get("title", "")).strip(),
            page=0,
            needs_review=False,
        )
        if not entry.email:
            result.rejected.append(
                {
                    "row": index,
                    "reason": "no_email",
                    "detail": "This row has no email address, so nothing can be sent to it.",
                }
            )
            continue
        result.rows.append(entry)

    if not result.rows:
        result.warnings.append(
            "No row in this file had an email address. Check that the column is "
            "named something off_CRM recognises, such as 'email' or 'work email'."
        )
    return result


# ── PDFs: best effort, and honest about it ─────────────────────────────────


def extract_pdf_lines(source: Path, *, max_pages: int = MAX_PDF_PAGES) -> list[tuple[int, str]]:
    """``(page_number, line)`` for every non-empty line.

    Text extraction only. No OCR: a scanned page has no text layer, and
    pretending otherwise would produce confident nonsense.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - pypdf is a hard dependency
        raise IntakeError(
            "Reading PDFs needs pypdf, which is not installed."
        ) from exc

    try:
        reader = PdfReader(str(source))
    except Exception as exc:  # noqa: BLE001
        raise IntakeError(
            f"{source.name} could not be opened as a PDF: {str(exc)[:120]}"
        ) from exc

    lines: list[tuple[int, str]] = []
    for number, page in enumerate(reader.pages[:max_pages], start=1):
        try:
            text = page.extract_text() or ""
        except Exception:  # noqa: BLE001 - one bad page is not a bad file
            continue
        for raw in text.splitlines():
            cleaned = re.sub(r"\s+", " ", raw).strip()
            if cleaned:
                lines.append((number, cleaned))
    return lines


def _looks_like_a_name(candidate: str) -> bool:
    """Two to four capitalised words, and not a column header."""
    text = candidate.strip(" .,;:|-\t")
    if not text or text.lower() in _NOT_A_NAME:
        return False
    words = text.split()
    if not 2 <= len(words) <= 4:
        return False
    if any(_EMAIL_RE.search(word) or any(ch.isdigit() for ch in word) for word in words):
        return False
    return all(word[:1].isupper() for word in words if word)


def _name_near(lines: list[tuple[int, str]], index: int, line: str) -> tuple[str, str]:
    """Find a name for the address on ``line``.

    Looks on the line itself first, then the line above — the two layouts a
    printed contact table actually uses. Returns ``("", reason)`` when nothing
    convincing is there, because a wrong name is worse than a missing one: it
    gets sent to a real person.
    """
    without_email = _EMAIL_RE.sub(" ", line)
    for chunk in re.split(r"[|,;\t]|\s{2,}", without_email):
        if _looks_like_a_name(chunk):
            return chunk.strip(" .,;:|-"), ""

    if index > 0:
        previous = lines[index - 1][1]
        if not _EMAIL_RE.search(previous):
            for chunk in re.split(r"[|,;\t]|\s{2,}", previous):
                if _looks_like_a_name(chunk):
                    return chunk.strip(" .,;:|-"), "name taken from the line above"
    return "", "no name found near this address"


def _parse_pdf(source: Path, *, max_pages: int) -> IntakeResult:
    """Pull addresses out of a PDF and flag every row for review.

    The addresses themselves are reliable — an email address has a shape a
    regex matches exactly. Everything *around* them is a guess about layout, and
    that is what the review flag is for.
    """
    result = IntakeResult(
        mode=IntakeMode.PARSE, source_name=source.name, parsed_with="pdf"
    )
    lines = extract_pdf_lines(source, max_pages=max_pages)
    if not lines:
        result.warnings.append(
            f"{source.name} has no readable text. If it is a scan or a photo, "
            "off_CRM cannot read it — export the original as CSV instead."
        )
        return result

    seen: set[str] = set()
    for index, (page, line) in enumerate(lines):
        for match in _EMAIL_RE.finditer(line):
            email = norm_email(match.group(0))
            if not email or email in seen:
                continue
            seen.add(email)
            name, note = _name_near(lines, index, line)
            first, last = split_name(name) if name else ("", "")
            notes = [note] if note else []
            notes.append(
                "Read from a PDF, so the pairing of name to address is a guess. "
                "Check it before sending."
            )
            result.rows.append(
                IntakeRow(
                    email=email,
                    full_name=name,
                    first_name=first,
                    last_name=last,
                    source_line=line[:300],
                    page=page,
                    needs_review=True,
                    notes=tuple(notes),
                )
            )

    if not result.rows:
        result.warnings.append(
            f"No email addresses were found in {source.name}. If the contacts are "
            "there but off_CRM cannot see them, the file may be a scan."
        )
    else:
        result.warnings.append(
            f"{len(result.rows)} contacts read from a PDF. Every one needs checking "
            "before it can be sent to — a PDF is a picture of a table, and which "
            "name belongs to which address is guessed from the layout."
        )
    return result


# ── generate mode ───────────────────────────────────────────────────────────


@dataclass(slots=True)
class GenerateBrief:
    """What the owner asked for, before any searching happens.

    Deliberately plain data. Discovery turns this into a search; no contact in
    the result was invented by a model, because a model is not what produces
    them — the data source is.
    """

    description: str
    category: str = ""
    country: str = ""
    seniority: str = ""
    limit: int = 100

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not self.description.strip():
            problems.append("Say who you want to reach, in a sentence.")
        if self.limit < 1:
            problems.append("Ask for at least one person.")
        if self.limit > 5000:
            problems.append(
                "That is a very large batch. Ask for 5,000 or fewer at a time so "
                "the list stays reviewable."
            )
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "category": self.category,
            "country": self.country,
            "seniority": self.seniority,
            "limit": self.limit,
        }


def describe_modes() -> list[dict[str, str]]:
    """For the intake screen: the two choices, and what each one means."""
    return [
        {
            "value": mode.value,
            "label": mode.label,
            "description": mode.description,
        }
        for mode in IntakeMode
    ]
