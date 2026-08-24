"""The eval harness: does orchestration actually beat one good model?

Until this module existed, off_CRM had three run modes and no way to tell which
one was better.  The UI called compare mode "pick the best" and orchestrated
"best for big jobs", but nothing measured either claim.  That is the gap this
closes.

Why it matters more than it sounds: published work on Mixture-of-Agents found
that sampling a *single* strong model several times often beats mixing several
different ones, because a weak model in the blend drags the average down more
than its different perspective lifts it.  So "more models must be better" is not
a safe assumption — it is a hypothesis, and this module is how it gets tested.

Three rules, matching the rest of the AI module:

* **Scoring is deterministic.**  A check is a pure function of the output text.
  Same output, same score, forever.  No model judges anything here, for the same
  reason no model enforces policy: a grader that varies is not a measurement.
* **Nothing bypasses the broker.**  Eval runs are ordinary egress calls with the
  ordinary tier rules, so a case carrying person data cannot reach a provider
  that is not allowed to hold it.  Evaluating the system must not be a hole in
  the system.
* **The suite is config, not code.**  Cases live in ``config/evals.yaml``
  alongside ``providers.yaml``.  Adding a case is a data edit.

What this does *not* do: replace reply rates.  ``ai/context.py`` counts real
replies to real sends, and that is the only ground truth that matters in the
end.  This harness is the fast proxy you can run before shipping, on a fixed set,
without waiting weeks for a campaign to conclude.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import yaml

from .broker import EgressBroker, WorkspaceEgressSettings
from .errors import RegistryError
from .payload import EgressRequest, PersonPublic
from .tiers import DataClass, coerce_data_class

#: Openings that mean the model answered the *instruction* instead of doing the
#: task — "Certainly! Here is the email you asked for:" is not an email.
_PREAMBLE_RE = re.compile(
    r"^\s*(certainly|sure|of course|absolutely|here(?:'s| is)|i(?:'ve| have)\s+(?:written|drafted)|"
    r"below is|as requested|great question)\b",
    re.IGNORECASE,
)

#: Placeholder shapes a finished draft must not contain.  A template that still
#: says ``{{first_name}}`` was not filled in.
_PLACEHOLDER_RE = re.compile(r"\{\{[^}]*\}\}|\[[A-Z_][A-Z0-9_ ]{2,}\]|<[A-Z_]{3,}>|\bXXX+\b")

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)


# Keep the editable config and the installed-package fallback in the same
# order as the provider registry. A source checkout reads ``config/evals.yaml``;
# a wheel or Docker install can still verify output when that source directory
# is absent.
_PACKAGE_DIR = Path(__file__).resolve().parent
_SOURCE_ROOT = _PACKAGE_DIR.parents[1]
PACKAGED_EVALS_PATH = _PACKAGE_DIR / "evals.yaml"
SOURCE_EVALS_PATH = _SOURCE_ROOT / "config" / "evals.yaml"


def default_evals_path() -> Path:
    """Return the first configured, source, or packaged eval suite file."""
    override = os.environ.get("OFFSETX_EVALS_CONFIG", "").strip()
    if override:
        return Path(override)
    for candidate in (
        Path.cwd() / "config" / "evals.yaml",
        SOURCE_EVALS_PATH,
        PACKAGED_EVALS_PATH,
    ):
        if candidate.exists():
            return candidate
    return PACKAGED_EVALS_PATH


# ── check results ───────────────────────────────────────────────────────────


@dataclass(slots=True)
class CheckResult:
    """One deterministic assertion about one output."""

    name: str
    kind: str
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "passed": self.passed,
            "detail": self.detail,
        }


#: A check is ``(text, config) -> (passed, detail)``.  Pure; no I/O, no model.
CheckFn = Callable[[str, dict[str, Any]], tuple[bool, str]]


def _check_forbids_pattern(text: str, config: dict[str, Any]) -> tuple[bool, str]:
    pattern = re.compile(str(config.get("pattern", "")), re.IGNORECASE | re.MULTILINE)
    match = pattern.search(text)
    if match:
        return False, f"found {match.group(0)[:60]!r}"
    return True, ""


def _check_requires_pattern(text: str, config: dict[str, Any]) -> tuple[bool, str]:
    pattern = re.compile(str(config.get("pattern", "")), re.IGNORECASE | re.MULTILINE)
    if pattern.search(text):
        return True, ""
    return False, f"no match for {config.get('pattern')!r}"


def _check_forbids_any(text: str, config: dict[str, Any]) -> tuple[bool, str]:
    """Literal phrase list.  Cheaper to read and edit than one giant regex."""
    lowered = text.lower()
    hits = [
        str(phrase)
        for phrase in config.get("phrases", ())
        if str(phrase).lower() in lowered
    ]
    if hits:
        return False, f"used {', '.join(repr(h) for h in hits[:3])}"
    return True, ""


def _check_word_count(text: str, config: dict[str, Any]) -> tuple[bool, str]:
    words = len(text.split())
    low = int(config.get("min", 0))
    high = int(config.get("max", 10**6))
    if words < low:
        return False, f"{words} words, minimum {low}"
    if words > high:
        return False, f"{words} words, maximum {high}"
    return True, f"{words} words"


def _check_char_count(text: str, config: dict[str, Any]) -> tuple[bool, str]:
    size = len(text)
    low = int(config.get("min", 0))
    high = int(config.get("max", 10**7))
    if size < low:
        return False, f"{size} chars, minimum {low}"
    if size > high:
        return False, f"{size} chars, maximum {high}"
    return True, f"{size} chars"


def _check_no_placeholder(text: str, _config: dict[str, Any]) -> tuple[bool, str]:
    match = _PLACEHOLDER_RE.search(text)
    if match:
        return False, f"unfilled placeholder {match.group(0)[:40]!r}"
    return True, ""


def _check_no_preamble(text: str, _config: dict[str, Any]) -> tuple[bool, str]:
    match = _PREAMBLE_RE.match(text)
    if match:
        return False, f"starts with {match.group(0)!r}"
    return True, ""


def _check_no_email_address(text: str, _config: dict[str, Any]) -> tuple[bool, str]:
    """A model working from tokens must not invent a real-looking address.

    An invented address is worse than a missing one: it looks deliverable.
    """
    match = _EMAIL_RE.search(text)
    if match:
        return False, f"invented an address: {match.group(0)[:40]!r}"
    return True, ""


def _check_valid_json(text: str, _config: dict[str, Any]) -> tuple[bool, str]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\n?|```$", "", stripped).strip()
    try:
        json.loads(stripped)
    except (ValueError, TypeError) as exc:
        return False, f"not JSON: {str(exc)[:60]}"
    return True, ""


def _check_json_has_keys(text: str, config: dict[str, Any]) -> tuple[bool, str]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\n?|```$", "", stripped).strip()
    try:
        loaded = json.loads(stripped)
    except (ValueError, TypeError):
        return False, "not JSON"
    if not isinstance(loaded, dict):
        return False, f"top level is {type(loaded).__name__}, not an object"
    missing = [str(k) for k in config.get("keys", ()) if str(k) not in loaded]
    if missing:
        return False, f"missing {', '.join(missing)}"
    return True, ""


def _check_valid_python(text: str, _config: dict[str, Any]) -> tuple[bool, str]:
    """Parse, do not execute.

    Running model-written code needs the sandbox (§4J), which is not built.
    Parsing catches the common failure — prose where code was asked for — at
    zero risk and zero cost.
    """
    import ast

    source = text.strip()
    fence = re.search(r"```(?:python)?\n(.*?)```", source, re.DOTALL)
    if fence:
        source = fence.group(1)
    try:
        ast.parse(source)
    except SyntaxError as exc:
        return False, f"does not parse: {str(exc)[:60]}"
    return True, ""


def _check_mentions_all(text: str, config: dict[str, Any]) -> tuple[bool, str]:
    lowered = text.lower()
    missing = [
        str(term)
        for term in config.get("terms", ())
        if str(term).lower() not in lowered
    ]
    if missing:
        return False, f"never mentions {', '.join(repr(m) for m in missing[:3])}"
    return True, ""


#: Registry.  Adding a check kind means adding one pure function here and using
#: its name in ``config/evals.yaml`` — no other code changes.
CHECKS: dict[str, CheckFn] = {
    "forbids_pattern": _check_forbids_pattern,
    "requires_pattern": _check_requires_pattern,
    "forbids_any": _check_forbids_any,
    "word_count": _check_word_count,
    "char_count": _check_char_count,
    "no_placeholder": _check_no_placeholder,
    "no_preamble": _check_no_preamble,
    "no_email_address": _check_no_email_address,
    "valid_json": _check_valid_json,
    "json_has_keys": _check_json_has_keys,
    "valid_python": _check_valid_python,
    "mentions_all": _check_mentions_all,
}


def run_checks(text: str, checks: Sequence[dict[str, Any]]) -> list[CheckResult]:
    """Apply every check to one output.  Unknown kinds fail loudly.

    Failing closed matters here as much as anywhere: a typo in a check name that
    silently scored as a pass would quietly inflate every result that used it.
    """
    results: list[CheckResult] = []
    for raw in checks:
        kind = str(raw.get("kind", "")).strip()
        name = str(raw.get("name") or kind or "unnamed")
        fn = CHECKS.get(kind)
        if fn is None:
            results.append(
                CheckResult(
                    name=name,
                    kind=kind,
                    passed=False,
                    detail=(
                        f"Unknown check kind {kind!r}. Known kinds: "
                        f"{', '.join(sorted(CHECKS))}."
                    ),
                )
            )
            continue
        try:
            passed, detail = fn(text, raw)
        except re.error as exc:
            passed, detail = False, f"bad pattern: {exc}"
        results.append(CheckResult(name=name, kind=kind, passed=passed, detail=detail))
    return results


# ── cases and suites ────────────────────────────────────────────────────────


@dataclass(slots=True)
class EvalCase:
    """One task with a known-good shape, and the checks that define it."""

    id: str
    task_type: str
    data_class: DataClass
    instructions: str = ""
    person: PersonPublic | None = None
    public_text: str = ""
    template_text: str = ""
    positioning_line: str = ""
    checks: tuple[dict[str, Any], ...] = ()
    weight: float = 1.0

    def to_request(self) -> EgressRequest:
        """Build the egress request.  The broker applies policy to it as usual —
        an eval is not a privileged caller."""
        return EgressRequest(
            task_type=self.task_type,
            data_class=self.data_class,
            instructions=self.instructions,
            person=self.person,
            public_text=self.public_text,
            template_text=self.template_text,
            positioning_line=self.positioning_line,
        )


@dataclass(slots=True)
class EvalSuite:
    id: str
    title: str
    system_prompt: str
    cases: tuple[EvalCase, ...]
    #: The suite-level rules, kept separately from the merged per-case list so
    #: the verify loop can enforce the same standard the suite measures without
    #: inheriting one case's specifics.
    default_checks: tuple[dict[str, Any], ...] = ()

    def __len__(self) -> int:
        return len(self.cases)


def _person_from(raw: dict[str, Any] | None) -> PersonPublic | None:
    if not raw:
        return None
    return PersonPublic(
        full_name=str(raw.get("full_name", "")),
        first_name=str(raw.get("first_name", "")),
        title=str(raw.get("title", "")),
        company=str(raw.get("company", "")),
        category=str(raw.get("category", "")),
        route=str(raw.get("route", "")),
        public_hook=str(raw.get("public_hook", "")),
        tension=str(raw.get("tension", "")),
        contribution=str(raw.get("contribution", "")),
        questions=[str(q) for q in raw.get("questions", ())],
    )


def load_suites(path: Path | str) -> dict[str, EvalSuite]:
    """Read ``config/evals.yaml``.

    Suite-level ``default_checks`` are prepended to every case, so the rules that
    apply to all drafts are written once.
    """
    source = Path(path)
    if not source.exists():
        raise RegistryError(
            f"No eval suite file at {source}. Create it, or point the runner at "
            "an existing one."
        )
    raw = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    suites: dict[str, EvalSuite] = {}
    for entry in raw.get("suites", ()):
        suite_id = str(entry.get("id", "")).strip()
        if not suite_id:
            raise RegistryError("An eval suite has no id.")
        defaults = list(entry.get("default_checks", ()))
        task_type = str(entry.get("task_type", "eval"))
        data_class = coerce_data_class(entry.get("data_class"), default=DataClass.PUBLIC)
        cases: list[EvalCase] = []
        for case_raw in entry.get("cases", ()):
            case_id = str(case_raw.get("id", "")).strip()
            if not case_id:
                raise RegistryError(f"A case in suite {suite_id!r} has no id.")
            cases.append(
                EvalCase(
                    id=case_id,
                    task_type=str(case_raw.get("task_type", task_type)),
                    data_class=coerce_data_class(
                        case_raw.get("data_class"), default=data_class
                    ),
                    instructions=str(case_raw.get("instructions", "")),
                    person=_person_from(case_raw.get("person")),
                    public_text=str(case_raw.get("public_text", "")),
                    template_text=str(case_raw.get("template_text", "")),
                    positioning_line=str(case_raw.get("positioning_line", "")),
                    checks=tuple(defaults + list(case_raw.get("checks", ()))),
                    weight=float(case_raw.get("weight", 1.0)),
                )
            )
        if not cases:
            raise RegistryError(f"Eval suite {suite_id!r} has no cases.")
        suites[suite_id] = EvalSuite(
            id=suite_id,
            title=str(entry.get("title", suite_id)),
            system_prompt=str(entry.get("system_prompt", "")),
            cases=tuple(cases),
            default_checks=tuple(defaults),
        )
    if not suites:
        raise RegistryError(f"{source} defines no suites.")
    return suites


def checks_for(suite_id: str, path: Path | str) -> tuple[dict[str, Any], ...]:
    """The rules a suite applies to every case.

    This is the seam that keeps measurement and enforcement in agreement: the
    eval harness scores against these, and the verify loop enforces the same
    ones in production. Editing ``config/evals.yaml`` moves both together, so
    they cannot drift into disagreeing about what a good draft looks like.

    An unknown suite returns no checks rather than raising, because a caller
    asking to verify an unconfigured task type should get an unverified run with
    a note, not a failure.
    """
    try:
        suites = load_suites(path)
    except RegistryError:
        return ()
    suite = suites.get(suite_id)
    return suite.default_checks if suite else ()


# ── results ─────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class CaseResult:
    case_id: str
    score: float
    checks: list[CheckResult] = field(default_factory=list)
    text: str = ""
    error: str = ""
    duration_ms: int = 0
    provider_id: str = ""
    model_id: str = ""

    @property
    def passed(self) -> int:
        return sum(1 for item in self.checks if item.passed)

    @property
    def total(self) -> int:
        return len(self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "score": round(self.score, 4),
            "passed": self.passed,
            "total": self.total,
            "checks": [item.to_dict() for item in self.checks],
            "error": self.error,
            "duration_ms": self.duration_ms,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
        }


@dataclass(slots=True)
class EvalReport:
    """What one subject — a model, or a mode — scored on one suite."""

    subject: str
    subject_kind: str  # "model" | "mode"
    suite_id: str
    results: list[CaseResult] = field(default_factory=list)
    duration_ms: int = 0

    @property
    def score(self) -> float:
        """Weight-free mean.  Case weights are applied in :meth:`weighted_score`;
        the plain mean is what most comparisons want and is harder to game."""
        if not self.results:
            return 0.0
        return sum(item.score for item in self.results) / len(self.results)

    @property
    def errors(self) -> int:
        return sum(1 for item in self.results if item.error)

    def score_by_case(self) -> dict[str, float]:
        return {item.case_id: item.score for item in self.results}

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "subject_kind": self.subject_kind,
            "suite_id": self.suite_id,
            "score": round(self.score, 4),
            "cases": len(self.results),
            "errors": self.errors,
            "duration_ms": self.duration_ms,
            "results": [item.to_dict() for item in self.results],
        }


# ── the runner ──────────────────────────────────────────────────────────────


class EvalRunner:
    """Runs suites against models and modes, through the ordinary broker.

    Note what is *not* here: no provider import, no HTTP client, no way to reach
    a model except by asking the broker. An eval is a normal caller.
    """

    def __init__(self, broker: EgressBroker) -> None:
        self.broker = broker

    def run_model(
        self,
        suite: EvalSuite,
        settings: WorkspaceEgressSettings,
        *,
        provider_id: str,
        model_id: str = "",
    ) -> EvalReport:
        """Score one specific provider+model pair."""
        subject = f"{provider_id}:{model_id}" if model_id else provider_id
        started = time.monotonic()
        results = [
            self._run_case(case, settings, provider_id=provider_id, model_id=model_id)
            for case in suite.cases
        ]
        return EvalReport(
            subject=subject,
            subject_kind="model",
            suite_id=suite.id,
            results=results,
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    def run_mode(
        self,
        suite: EvalSuite,
        settings: WorkspaceEgressSettings,
        *,
        mode: str,
        runner: Any,
    ) -> EvalReport:
        """Score a run mode — ``compare`` or ``orchestrated`` — as a whole.

        ``runner`` is a :class:`~offsetx_apollo_builder.ai.modes.ModeRunner`.
        It is passed in rather than constructed so this module does not import
        modes and modes does not import this one.
        """
        started = time.monotonic()
        results: list[CaseResult] = []
        for case in suite.cases:
            case_started = time.monotonic()
            try:
                if mode == "verified":
                    run = runner.run_verified(
                        case.to_request(),
                        settings,
                        system_prompt=suite.system_prompt,
                        checks=case.checks,
                    )
                elif mode == "compare":
                    run = runner.run_compare(
                        case.to_request(), settings, system_prompt=suite.system_prompt
                    )
                elif mode == "orchestrated":
                    run = runner.run_orchestrated(
                        case.to_request(), settings, system_prompt=suite.system_prompt
                    )
                else:
                    run = runner.run_simple(
                        case.to_request(), settings, system_prompt=suite.system_prompt
                    )
                text = run.first_permitted_text
                checks = run_checks(text, case.checks)
                results.append(
                    CaseResult(
                        case_id=case.id,
                        score=_score_of(checks),
                        checks=checks,
                        text=text,
                        duration_ms=int((time.monotonic() - case_started) * 1000),
                    )
                )
            except Exception as exc:  # noqa: BLE001 - a refusal is a real result
                results.append(
                    CaseResult(
                        case_id=case.id,
                        score=0.0,
                        error=str(exc)[:400],
                        duration_ms=int((time.monotonic() - case_started) * 1000),
                    )
                )
        return EvalReport(
            subject=mode,
            subject_kind="mode",
            suite_id=suite.id,
            results=results,
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    def _run_case(
        self,
        case: EvalCase,
        settings: WorkspaceEgressSettings,
        *,
        provider_id: str,
        model_id: str,
    ) -> CaseResult:
        started = time.monotonic()
        pinned = settings
        if model_id:
            pinned = _with_model(settings, provider_id, model_id)
        try:
            result = self.broker.call(
                case.to_request(),
                pinned,
                system_prompt="",
                provider_id=provider_id,
            )
        except Exception as exc:  # noqa: BLE001
            # A policy refusal scores zero rather than crashing the suite: "this
            # model is not allowed to do this task" is a real, reportable result.
            return CaseResult(
                case_id=case.id,
                score=0.0,
                error=str(exc)[:400],
                duration_ms=int((time.monotonic() - started) * 1000),
                provider_id=provider_id,
                model_id=model_id,
            )
        checks = run_checks(result.text, case.checks)
        return CaseResult(
            case_id=case.id,
            score=_score_of(checks),
            checks=checks,
            text=result.text,
            duration_ms=result.duration_ms,
            provider_id=result.provider_id,
            model_id=result.model_id,
        )


def _score_of(checks: Sequence[CheckResult]) -> float:
    if not checks:
        return 0.0
    return sum(1 for item in checks if item.passed) / len(checks)


def _with_model(
    settings: WorkspaceEgressSettings, provider_id: str, model_id: str
) -> WorkspaceEgressSettings:
    """Copy of the settings with exactly one model enabled on one provider.

    Evaluating "which model is best" requires pinning one at a time; leaving the
    workspace's own list in place would let the router pick a different one and
    quietly score the wrong subject.
    """
    from dataclasses import replace

    models = dict(settings.enabled_models)
    models[provider_id] = (model_id,)
    return replace(settings, enabled_models=models)


def suite_summary(reports: Iterable[EvalReport]) -> list[dict[str, Any]]:
    """Leaderboard rows, best first.  Used by the CLI and the API."""
    rows = [
        {
            "subject": report.subject,
            "kind": report.subject_kind,
            "score": round(report.score, 4),
            "cases": len(report.results),
            "errors": report.errors,
            "duration_ms": report.duration_ms,
        }
        for report in reports
    ]
    rows.sort(key=lambda row: (-row["score"], row["duration_ms"]))
    return rows
