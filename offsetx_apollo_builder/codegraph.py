"""Code graph (§4K) — a queryable map of this repository.

Graphify (`graphifyy` on PyPI) parses the repo with tree-sitter and writes a
graph of symbols and the edges between them. You can then ask "what reaches the
egress broker?" and get an answer in a second, instead of reading forty files.

Nothing here is product. It is developer tooling, and the reason it needs a
module rather than a shell command is that **Graphify has a path that sends your
source code to a model, and it is one flag away.**

---

**What this wrapper is for.**

`graphify extract <path>` is, in its own help text, "headless full extraction
(AST + **semantic LLM**)". It picks a backend from whichever API key it finds —
gemini, openai, deepseek, claude, kimi, ollama — and posts chunks of your source
to it. `graphify label` does the same for community naming.

Adding `--code-only` changes it to "index code (**local AST, no API key**)", and
`--no-label` keeps clustering local too. That is the difference between a build
step and an egress event, and it is two flags.

The previous attempt at this put those flags in `scripts/build_code_graph.ps1`:
a PowerShell file, so it ran on one operating system out of three, and a text
file anyone could edit without noticing what they had turned on. This module
constructs the argument list in code, refuses the subcommands and flags that
would change what leaves the machine, and a test asserts the safe flags are
present.

---

**What it refuses, and why each one is a real thing someone would reach for.**

See :data:`FORBIDDEN_USES`. Briefly: the semantic path, `add <url>` (fetches the
internet into your corpus), `--global` (merges this repo's graph into a shared
file in your home directory, outside the project boundary), the `install`
subcommands (they write to `AGENTS.md` and install git hooks), and
`--no-gitignore` (the single flag that would drag `local_data/` in).

---

**Why it verifies instead of trusting.**

`.graphifyignore` lists the directories that hold real contacts, the CRM
database and the encrypted key file. Writing that list is not the same as
knowing it worked. So after every build this module reads the graph back and
**rejects it if any indexed file lives under a runtime-data path**, deleting the
output rather than leaving a graph of your contact database on disk.

The graph itself holds symbol names, file paths and edges — no source text — so
the check is precise and has nothing to false-positive on.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

#: Pinned exactly, for the reason the tool registry pins its images: an
#: unpinned tool is a different tool tomorrow, and this one has a flag that
#: decides whether source code leaves the machine.
GRAPHIFY_PACKAGE = "graphifyy"
GRAPHIFY_VERSION = "0.9.39"

#: Where the graph lands. A build artefact and a cache, so it is gitignored.
OUTPUT_DIRNAME = "graphify-out"
GRAPH_FILENAME = "graph.json"
MANIFEST_FILENAME = "manifest.json"
REPORT_FILENAME = "GRAPH_REPORT.md"
IGNORE_FILENAME = ".graphifyignore"

#: Set to a `graphify` executable to use an existing install instead of `uvx`.
#: Supported for offline machines, and reported as unpinned when used.
BINARY_ENV_VAR = "OFFSETX_GRAPHIFY_BIN"


class CodeGraphError(RuntimeError):
    """Configuration or invocation problem."""


class GraphRejected(CodeGraphError):
    """The built graph indexed something it must not have. Output was deleted."""

    def __init__(self, check: "GraphCheck") -> None:
        super().__init__(
            "The code graph indexed runtime data and was deleted: "
            + check.summary()
        )
        self.check = check


# ─────────────────────────────────────────────────────────────────────────────
# What must never run
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ForbiddenUse:
    """A Graphify capability off_CRM will not invoke, and the reason.

    Written down rather than merely unused. Every one of these is something a
    person would reasonably reach for after reading `graphify --help`, so the
    refusal has to arrive with its reason attached or it just looks like the
    wrapper is incomplete.
    """

    what: str
    why: str

    def to_dict(self) -> dict[str, str]:
        return {"what": self.what, "why": self.why}


FORBIDDEN_USES: tuple[ForbiddenUse, ...] = (
    ForbiddenUse(
        what="`extract` without `--code-only`",
        why=(
            "Runs the semantic extractor, which posts chunks of your source to "
            "whichever backend an API key is set for. Source is internal data; "
            "this is the flag that decides whether it leaves the machine."
        ),
    ),
    ForbiddenUse(
        what="`label`, and `cluster-only` without `--no-label`",
        why=(
            "Names communities with an LLM, sending it the symbol names it is "
            "naming. Cheaper than full extraction and still egress. Communities "
            "keep their numbers instead."
        ),
    ),
    ForbiddenUse(
        what="`add <url>`",
        why=(
            "Fetches a URL and writes it into the corpus. Untrusted external "
            "content entering a corpus a model later reads is the middle term "
            "of the lethal trifecta."
        ),
    ),
    ForbiddenUse(
        what="`--global`, `global add`",
        why=(
            "Merges this repository's graph into ~/.graphify/global-graph.json, "
            "a file shared with every other project on the machine. The graph "
            "stays inside the repo it describes."
        ),
    ),
    ForbiddenUse(
        what="`claude install`, `codex install`, `hook install` and friends",
        why=(
            "Write vendor sections into AGENTS.md and install git hooks. off_CRM "
            "does not edit its own instruction files or your git config as a "
            "side effect of building an index."
        ),
    ),
    ForbiddenUse(
        what="`--no-gitignore`",
        why=(
            "The single flag that would let `local_data/` be indexed. .gitignore "
            "and .graphifyignore are belt and braces; this removes the belt."
        ),
    ),
    ForbiddenUse(
        what="`--postgres <dsn>`",
        why=(
            "Extracts schema from a live database. off_CRM's database holds real "
            "contacts, and a build step is not where you connect to it."
        ),
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# What must never be indexed
# ─────────────────────────────────────────────────────────────────────────────

#: Every path under the repository that can hold real data at runtime. This is
#: the single source of truth: `.graphifyignore` is generated from it, and the
#: post-build check reads the same list. A test cross-references it against
#: `api/config.py` so the two cannot drift apart.
RUNTIME_DATA_PATHS: tuple[str, ...] = (
    "local_data",
    "output",
    "old_pois",
    "poi_file_queue",
    "upload",
    "uploads",
    "exports",
    "backups",
    # Where `graphify add <url>` writes fetched web pages. That subcommand is
    # forbidden, but a hand-run of it must not reach the graph either.
    "raw",
)

#: Tracked directories that look like data and are not. ``email_expert_library``
#: holds shipped default templates the app only ever reads; the owner's own
#: ingested documents go to SQLite under ``local_data``. Listed so the next
#: person to read :data:`RUNTIME_DATA_PATHS` does not add it back.
NOT_RUNTIME_DATA: tuple[str, ...] = ("email_expert_library", "config")

#: Build artefacts and vendored trees. Excluded for size and noise, not safety.
BUILD_ARTEFACT_PATHS: tuple[str, ...] = (
    OUTPUT_DIRNAME,
    "frontend/node_modules",
    "frontend/dist",
    "frontend/coverage",
    "build",
    "dist",
    ".venv",
    ".git",
)

#: File shapes that are data whichever directory they sit in.
DATA_FILE_GLOBS: tuple[str, ...] = (
    "*.csv",
    "*.xlsx",
    "*.xls",
    "*.pdf",
    "*.docx",
    "*.db",
    "*.sqlite",
    "*.env",
    ".env*",
    "*.key",
    "gmail_token*.json",
    "client_secret*.json",
    "credentials*.json",
)

IGNORE_HEADER = """\
# Generated by off_CRM: offsetx-codegraph build
#
# Do not hand-edit. The list lives in offsetx_apollo_builder/codegraph.py so
# that the ignore file and the post-build check read the same source, and so a
# new data directory cannot be added to one and forgotten in the other.
#
# The code graph is build-time code intelligence. Contacts, campaign records,
# the mailbox index and credentials must never enter it, even when an operator
# puts them inside the repository.
"""


def render_ignore_file() -> str:
    """The exact text of `.graphifyignore`."""
    lines = [IGNORE_HEADER, "# Runtime data — the reason this file exists"]
    lines += [f"{path}/" for path in RUNTIME_DATA_PATHS]
    lines += ["", "# Build artefacts and vendored trees"]
    lines += [f"{path}/" for path in BUILD_ARTEFACT_PATHS]
    lines += ["", "# Data shapes, wherever they sit"]
    lines += list(DATA_FILE_GLOBS)
    return "\n".join(lines) + "\n"


def write_ignore_file(root: Path | str) -> Path:
    """Write `.graphifyignore`, overwriting whatever is there.

    Overwriting is deliberate. A hand-edited ignore file is a silent way to add
    a directory to the index, and the point of generating it is that the list
    has one home.
    """
    path = Path(root) / IGNORE_FILENAME
    path.write_text(render_ignore_file(), encoding="utf-8")
    return path


# ─────────────────────────────────────────────────────────────────────────────
# The command
# ─────────────────────────────────────────────────────────────────────────────


def graphify_command(binary: str = "") -> list[str]:
    """The invocation prefix, pinned unless an explicit binary is supplied."""
    override = binary or os.getenv(BINARY_ENV_VAR, "").strip()
    if override:
        return [override]
    return ["uvx", "--from", f"{GRAPHIFY_PACKAGE}=={GRAPHIFY_VERSION}", "graphify"]


def extract_command(
    root: Path | str, *, out_dir: Path | str | None = None, binary: str = "", workers: int = 2
) -> list[str]:
    """Build the extraction command.

    ``--code-only`` is not optional and is not a parameter. It is the flag that
    keeps the whole operation local, so it is welded in and a test asserts it.
    """
    argv = graphify_command(binary) + [
        "extract",
        str(root),
        "--code-only",
        "--no-cluster",
        "--force",
        "--max-workers",
        str(max(1, int(workers))),
    ]
    if out_dir is not None:
        argv += ["--out", str(out_dir)]
    return argv


def cluster_command(
    target: Path | str, *, binary: str = "", graph_path: Path | str | None = None
) -> list[str]:
    """Build the clustering command.

    ``--no-label`` keeps community naming local; ``--no-viz`` skips an HTML
    render that is slow on a graph this size and that nobody asked for.
    """
    argv = graphify_command(binary) + [
        "cluster-only",
        str(target),
        "--no-label",
        "--no-viz",
    ]
    if graph_path is not None:
        argv += ["--graph", str(graph_path)]
    return argv


def graphify_available(*, binary: str = "") -> tuple[bool, str]:
    """Whether the graph can be built here, and what to do if not.

    Checks that the launcher exists rather than that a package is importable:
    the pinned path runs through ``uvx``, so ``uvx`` is what has to be present.
    """
    override = binary or os.getenv(BINARY_ENV_VAR, "").strip()
    if override:
        if shutil.which(override) or Path(override).exists():
            return True, f"using {override} ({BINARY_ENV_VAR}); version not pinned"
        return False, f"{BINARY_ENV_VAR} points at {override}, which does not exist"
    if shutil.which("uvx"):
        return True, f"uvx will fetch {GRAPHIFY_PACKAGE}=={GRAPHIFY_VERSION}"
    return (
        False,
        "uvx not found. Install uv (https://docs.astral.sh/uv/) or set "
        f"{BINARY_ENV_VAR} to a graphify executable.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Verification
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class GraphCheck:
    """The result of reading a built graph back and looking for owner data."""

    files_checked: int = 0
    offending: list[str] = field(default_factory=list)
    reasons: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.offending

    def summary(self) -> str:
        if self.ok:
            return f"{self.files_checked} indexed files, none under a runtime-data path"
        shown = ", ".join(self.offending[:5])
        more = f" (+{len(self.offending) - 5} more)" if len(self.offending) > 5 else ""
        return f"{len(self.offending)} indexed file(s) must not be in the graph: {shown}{more}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "files_checked": self.files_checked,
            "offending": list(self.offending),
            "reasons": dict(self.reasons),
        }


def _is_forbidden(relative: str) -> str:
    """Why this indexed path must not be in the graph, or an empty string."""
    text = relative.replace("\\", "/").strip()
    if not text:
        return ""

    # These two run before any normalisation. Stripping first is how the earlier
    # version of this function lost them: `lstrip("./")` removes the characters
    # `.` and `/`, so "/home/x" became "home/x" and "../x" became "x", and both
    # checks then looked at a path that was no longer the one being reported.
    if text.startswith("/") or text.startswith("~") or ":" in text.split("/")[0]:
        return "indexed a file outside the repository"
    if ".." in text.split("/"):
        return "indexed a path that escapes the repository"

    while text.startswith("./"):
        text = text[2:]
    parts = Path(text).parts
    head = parts[0] if parts else ""
    for guarded in RUNTIME_DATA_PATHS:
        # ``output`` guards ``output/`` and ``output_2026/`` alike, matching the
        # ``output*/`` pattern the repository has always used.
        if head == guarded or (guarded == "output" and head.startswith("output")):
            return f"lives under the runtime-data path {guarded}/"

    name = parts[-1]
    lowered = name.lower()
    for suffix in (".db", ".sqlite", ".csv", ".xlsx", ".xls", ".pdf", ".docx", ".key"):
        if lowered.endswith(suffix):
            return f"is a data file ({suffix})"
    for prefix in ("gmail_token", "client_secret", "credentials"):
        if lowered.startswith(prefix):
            return "is a credential file"
    return ""


def indexed_files(graph: dict[str, Any]) -> list[str]:
    """Every source file the graph refers to, from nodes and edges alike."""
    seen: set[str] = set()
    for collection in ("nodes", "links", "edges"):
        for item in graph.get(collection) or []:
            if isinstance(item, dict):
                value = item.get("source_file")
                if isinstance(value, str) and value:
                    seen.add(value)
    return sorted(seen)


def verify_graph(graph_path: Path | str, *, manifest_path: Path | str | None = None) -> GraphCheck:
    """Read a built graph back and check nothing it indexed is owner data.

    Reads the manifest too when there is one: a file can be scanned and produce
    zero nodes, which leaves it in the manifest and out of the graph. Having
    been *read* is the thing worth knowing about.
    """
    path = Path(graph_path)
    if not path.exists():
        raise CodeGraphError(f"No graph at {path}. Build it first.")
    try:
        graph = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CodeGraphError(f"Could not read the graph at {path}: {exc}") from exc

    files = set(indexed_files(graph))
    manifest = Path(manifest_path) if manifest_path else path.with_name(MANIFEST_FILENAME)
    if manifest.exists():
        try:
            entries = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            entries = {}
        if isinstance(entries, dict):
            files.update(key for key in entries if isinstance(key, str))

    check = GraphCheck(files_checked=len(files))
    for relative in sorted(files):
        reason = _is_forbidden(relative)
        if reason:
            check.offending.append(relative)
            check.reasons[relative] = reason
    return check


# ─────────────────────────────────────────────────────────────────────────────
# Freshness
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GraphStatus:
    """How far the graph has drifted from the working tree."""

    exists: bool
    built_at_commit: str = ""
    head: str = ""
    stale: bool = False
    commits_behind: int = 0
    nodes: int = 0
    edges: int = 0

    def summary(self) -> str:
        if not self.exists:
            return "No graph built yet."
        if not self.built_at_commit:
            return "Built, but it does not record a commit — treat it as stale."
        if not self.stale:
            return f"Fresh: built at {self.built_at_commit[:8]}, which is HEAD."
        behind = f"{self.commits_behind} commit(s)" if self.commits_behind else "an unknown number of commits"
        return (
            f"Stale: built at {self.built_at_commit[:8]}, HEAD is {self.head[:8]} "
            f"— {behind} behind."
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "exists": self.exists,
            "built_at_commit": self.built_at_commit,
            "head": self.head,
            "stale": self.stale,
            "commits_behind": self.commits_behind,
            "nodes": self.nodes,
            "edges": self.edges,
            "summary": self.summary(),
        }


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def graph_status(root: Path | str, *, graph_path: Path | str | None = None) -> GraphStatus:
    """Compare the graph's recorded commit to HEAD.

    Staleness is worth reporting rather than hiding: an answer from a graph two
    hundred commits old is confidently wrong, which is worse than no answer.
    """
    base = Path(root)
    path = Path(graph_path) if graph_path else base / OUTPUT_DIRNAME / GRAPH_FILENAME
    if not path.exists():
        return GraphStatus(exists=False)

    try:
        graph = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return GraphStatus(exists=True)

    built = str(graph.get("built_at_commit") or "")
    head = _git(base, "rev-parse", "HEAD")
    behind = 0
    if built and head and built != head:
        count = _git(base, "rev-list", "--count", f"{built}..{head}")
        behind = int(count) if count.isdigit() else 0

    return GraphStatus(
        exists=True,
        built_at_commit=built,
        head=head,
        stale=bool(built and head and built != head),
        commits_behind=behind,
        nodes=len(graph.get("nodes") or []),
        edges=len(graph.get("links") or graph.get("edges") or []),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Building
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BuildResult:
    """What a build produced, and how it was invoked."""

    graph_path: Path
    report_path: Path
    ignore_path: Path
    commands: tuple[tuple[str, ...], ...]
    check: GraphCheck
    status: GraphStatus
    pinned: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph_path": str(self.graph_path),
            "report_path": str(self.report_path),
            "ignore_path": str(self.ignore_path),
            "commands": [list(item) for item in self.commands],
            "check": self.check.to_dict(),
            "status": self.status.to_dict(),
            "pinned": self.pinned,
        }


class CodeGraph:
    """Builds and inspects the repository's code graph."""

    def __init__(
        self,
        root: Path | str,
        *,
        out_dir: Path | str | None = None,
        binary: str = "",
        timeout: int = 1800,
    ) -> None:
        self.root = Path(root).resolve()
        self.out_root = Path(out_dir).resolve() if out_dir else self.root
        self.binary = binary
        self.timeout = max(30, int(timeout))

    @property
    def output_dir(self) -> Path:
        return self.out_root / OUTPUT_DIRNAME

    @property
    def graph_path(self) -> Path:
        return self.output_dir / GRAPH_FILENAME

    @property
    def report_path(self) -> Path:
        return self.output_dir / REPORT_FILENAME

    def status(self) -> GraphStatus:
        return graph_status(self.root, graph_path=self.graph_path)

    def verify(self) -> GraphCheck:
        return verify_graph(self.graph_path)

    def build(self, *, workers: int = 2) -> BuildResult:
        """Write the ignore file, extract, cluster, then verify or delete.

        The order matters. Verification comes last and can throw away everything
        before it, because a graph that indexed the contact database is not
        something to keep around with a warning printed above it.
        """
        available, note = graphify_available(binary=self.binary)
        if not available:
            raise CodeGraphError(note)

        ignore_path = write_ignore_file(self.root)
        commands: list[tuple[str, ...]] = []

        extract = extract_command(
            self.root,
            out_dir=self.out_root if self.out_root != self.root else None,
            binary=self.binary,
            workers=workers,
        )
        commands.append(tuple(extract))
        self._run(extract)

        cluster = cluster_command(self.out_root, binary=self.binary)
        commands.append(tuple(cluster))
        self._run(cluster)

        check = verify_graph(self.graph_path)
        if not check.ok:
            shutil.rmtree(self.output_dir, ignore_errors=True)
            raise GraphRejected(check)

        return BuildResult(
            graph_path=self.graph_path,
            report_path=self.report_path,
            ignore_path=ignore_path,
            commands=tuple(commands),
            check=check,
            status=self.status(),
            pinned=not (self.binary or os.getenv(BINARY_ENV_VAR, "").strip()),
        )

    def _run(self, argv: Sequence[str]) -> str:
        try:
            result = subprocess.run(
                list(argv),
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise CodeGraphError(
                f"Graphify did not finish within {self.timeout}s: {' '.join(argv)}"
            ) from exc
        except OSError as exc:
            raise CodeGraphError(f"Could not run {argv[0]!r}: {exc}") from exc
        if result.returncode != 0:
            tail = (result.stderr or result.stdout or "").strip().splitlines()[-8:]
            raise CodeGraphError(
                f"Graphify failed ({result.returncode}): {' '.join(argv)}\n"
                + "\n".join(tail)
            )
        return result.stdout


def describe_policy() -> dict[str, Any]:
    """The locked invocation and the refusals, for the CLI and the docs."""
    return {
        "package": f"{GRAPHIFY_PACKAGE}=={GRAPHIFY_VERSION}",
        "extract": extract_command("<repo>"),
        "cluster": cluster_command("<repo>"),
        "forbidden": [item.to_dict() for item in FORBIDDEN_USES],
        "runtime_data_paths": list(RUNTIME_DATA_PATHS),
    }
