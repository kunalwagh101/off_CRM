"""Bring-your-own tools: the registry that sits on top of the sandbox (§4J).

``ai/sandbox.py`` is the locked room.  This is the list of who may enter.

The whole design turns on one sentence:

    **A model names a tool that already exists. It cannot describe a new one.**

That is the difference between a catalogue and a constructor.  If a model could
supply an image and a command, the sandbox flags would be the only thing
standing between a prompt injection and arbitrary code execution — and flags are
a last line, not a first one.  Here the model passes a ``tool_id`` and nothing
else that reaches Docker.  Everything executable was pinned by the owner, in
advance, in a separate act.

Three pins, all mandatory, none of them defaultable:

``repository_url``
    An ``https://github.com/owner/repo`` URL and nothing else.
``commit_sha``
    A full 40-character SHA. **Not a branch or a tag**, because those move: you
    reviewed a commit, not a name that currently points at one.
``image``
    Version-pinned, validated by :func:`~offsetx_apollo_builder.ai.sandbox.validate_image`.

**Why the source is fetched on the host.**  The container runs with
``--network=none``, so it cannot clone anything — which is the point.  off_CRM
therefore materialises the source *before* the container starts, on the host
where network is allowed, and then verifies that what landed is the exact commit
that was registered.  That is the same rule the rest of the module follows:
off_CRM pushes, the sandbox never pulls.  It also puts the integrity check
somewhere a compromised tool cannot reach it.
"""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from contextlib import closing
from typing import Any, Iterable, Sequence

from ..outreach.models import to_utc_iso
from ..outreach.store import names_a_url
from ..db import open_database, is_postgres_url
from ..db.schema import ensure_initial_sql_schema
from ..db.store_connection import CachedStoreConnection
from .errors import AIModuleError, PolicyViolation
from .sandbox import (
    SandboxPolicy,
    SandboxWorkspace,
    assert_sandbox_available,
    validate_command,
    validate_image,
)
from .tiers import DataClass

#: GitHub only, and only the canonical form.  A permissive URL rule here would
#: undo the pinning: an arbitrary host is an arbitrary payload.
_REPO_RE = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,48}$")

#: Extra arguments a caller may append, when a tool opts in.  Bounded hard: a
#: tool that needs more than this is not being parameterised, it is being
#: rewritten, and that belongs in a new registration.
MAX_EXTRA_ARGS = 8

SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_tools (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    repository_url TEXT NOT NULL,
    commit_sha TEXT NOT NULL,
    image TEXT NOT NULL,
    command TEXT NOT NULL,
    allows_arguments INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    registered_at TEXT NOT NULL,
    registered_by TEXT NOT NULL DEFAULT 'owner'
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_ai_tools_name
    ON ai_tools(workspace_id, name);

CREATE TABLE IF NOT EXISTS ai_tool_runs (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    tool_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    commit_sha TEXT NOT NULL,
    image TEXT NOT NULL,
    argv TEXT NOT NULL DEFAULT '[]',
    exit_code INTEGER NOT NULL DEFAULT -1,
    stdout TEXT NOT NULL DEFAULT '',
    stderr TEXT NOT NULL DEFAULT '',
    duration_ms INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'ran',
    started_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_ai_tool_runs_lookup
    ON ai_tool_runs(workspace_id, tool_id, started_at DESC);
"""

LARGE_INTEGER_COLUMNS = {'ai_tool_runs': ('duration_ms',)}


class ToolError(AIModuleError):
    """A tool could not be registered, found, or prepared."""


def _stop_run_container(name: str) -> bool:
    """Stop only the trusted random name assigned to this invocation.

    Killing an attached Docker client does not stop its container. No name or
    cleanup target comes from a model, registration, output or writable mount.
    """
    try:
        removed = subprocess.run(['docker', 'rm', '--force', '--volumes', name],
            capture_output=True, text=True, check=False, timeout=10)
        if removed.returncode == 0:
            return True
        # The daemon may already have removed an exited --rm container. A
        # successful empty query distinguishes absence from a daemon failure.
        remaining = subprocess.run(['docker', 'ps', '--all', '--quiet', '--filter', 'name=^/'+name+'$'],
            capture_output=True, text=True, check=False, timeout=10)
        return remaining.returncode == 0 and not remaining.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return False


_CLEANUP_ERROR = re.compile(
    r'The tool exceeded [0-9]+s; container cleanup could not be confirmed\. '
    r'Container: (offsetx-tool-[a-f0-9]{32})\. '
    r'Inspect this container on the sandbox host before rerunning this tool\.')


def _safe_cleanup_diagnostic(stderr: str) -> str:
    # Imported history is untrusted. A status value cannot make arbitrary
    # old stderr safe to expose as operational metadata.
    matched = _CLEANUP_ERROR.fullmatch(str(stderr))
    if matched is None:
        return ('Container cleanup is unconfirmed and its identity is unavailable. '
                'Inspect the sandbox host before rerunning this tool.')
    return ('Container cleanup is unconfirmed for '+matched.group(1)+'. '
            'Inspect this container on the sandbox host before rerunning this tool.')


@dataclass(slots=True)
class RegisteredTool:
    """One owner-approved tool.  Every executable field was pinned by a human."""

    id: str
    name: str
    description: str
    repository_url: str
    commit_sha: str
    image: str
    command: tuple[str, ...]
    allows_arguments: bool = False
    enabled: bool = True
    registered_at: str = ""
    registered_by: str = "owner"
    workspace_id: str = "local"

    def to_dict(self) -> dict[str, Any]:
        """The full record — for the owner's screens, not for a model."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "repository_url": self.repository_url,
            "commit_sha": self.commit_sha,
            "image": self.image,
            "command": list(self.command),
            "allows_arguments": self.allows_arguments,
            "enabled": self.enabled,
            "registered_at": self.registered_at,
            "registered_by": self.registered_by,
        }

    def catalogue_entry(self) -> dict[str, Any]:
        """What a **model** is allowed to see.

        Name, description, id, and whether it takes arguments.  Deliberately no
        image, no command, no repository: a model choosing a tool needs to know
        what it does, not how to rebuild it.  Withholding the recipe means a
        leaked catalogue is not a leaked attack surface.
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "accepts_arguments": self.allows_arguments,
        }


@dataclass(slots=True)
class ToolRun:
    """What happened when a tool ran."""

    id: str
    tool_id: str
    tool_name: str
    argv: list[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    status: str = "ran"

    @property
    def ok(self) -> bool:
        return self.status == "ran" and self.exit_code == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tool_id": self.tool_id,
            "tool_name": self.tool_name,
            "argv": self.argv,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "ok": self.ok,
        }


# ── validation ──────────────────────────────────────────────────────────────


def validate_repository_url(value: str) -> str:
    url = str(value or "").strip()
    if url.endswith(".git"):
        url = url[: -len(".git")]
    if not _REPO_RE.fullmatch(url):
        raise ToolError(
            f"{value!r} is not a GitHub repository URL. Use "
            "https://github.com/owner/repo — other hosts are not accepted, "
            "because an arbitrary host is an arbitrary payload."
        )
    return url


def validate_commit_sha(value: str) -> str:
    sha = str(value or "").strip().lower()
    if not _SHA_RE.fullmatch(sha):
        raise ToolError(
            f"{value!r} is not a full 40-character commit SHA. Branches and tags "
            "are not accepted: they move, and you reviewed a commit rather than "
            "a name that currently points at one."
        )
    return sha


def validate_tool_name(value: str) -> str:
    name = str(value or "").strip().lower()
    if not _NAME_RE.fullmatch(name):
        raise ToolError(
            f"{value!r} is not a usable tool name. Use 2-49 characters: lower "
            "case letters, digits, hyphen or underscore, starting with a letter "
            "or digit."
        )
    return name


def validate_extra_arguments(
    tool: RegisteredTool, extra: Sequence[str]
) -> list[str]:
    """Caller-supplied arguments, refused unless the tool opted in.

    Off by default on purpose. Arbitrary arguments are arbitrary code paths, and
    the point of the registry is that the executable surface was fixed in
    advance. A tool that genuinely takes a parameter says so at registration.
    """
    parts = [str(part) for part in extra]
    if not parts:
        return []
    if not tool.allows_arguments:
        raise PolicyViolation(
            f"Tool {tool.name!r} does not accept arguments. It runs exactly the "
            "command it was registered with. Register a second tool if you need "
            "a different invocation."
        )
    if len(parts) > MAX_EXTRA_ARGS:
        raise PolicyViolation(
            f"At most {MAX_EXTRA_ARGS} extra arguments are allowed; "
            f"{len(parts)} were supplied."
        )
    # Same shape rules as the base command: bounded, non-empty, null-free.
    validate_command(parts)
    for part in parts:
        if part.startswith("-"):
            raise PolicyViolation(
                f"Extra argument {part!r} looks like a flag. Only values are "
                "accepted, so a caller cannot change how the tool behaves."
            )
    return parts


# ── the registry ────────────────────────────────────────────────────────────


class ToolRegistry:
    """Owner-registered tools, and the only way to run one.

    There is no method here that takes an image or a command from a caller at
    run time. ``run`` takes a ``tool_id``. That asymmetry is the security
    property, and ``tests/test_ai_tools.py`` asserts it structurally.
    """

    def __init__(self, database_path: Path | str, *, database_target: str | None = None) -> None:
        if any(value is not None and not is_postgres_url(value) and names_a_url(value)
               for value in (database_path, database_target)):
            raise ToolError('Use a SQLite tool file or a supported PostgreSQL URL; do not fold a database URL into a Path')
        self.path = None if is_postgres_url(database_path) else Path(database_path)
        self.target = str(database_target or database_path)
        self._hosted = database_target is not None or is_postgres_url(database_path)
        if self._hosted and self.path is not None:
            if self.path.is_symlink():
                raise ToolError('Preserve and review the symbolic link at the local tool source before hosted startup')
            if not is_postgres_url(self.target):
                target = Path(self.target).expanduser().resolve()
                if target == self.path.resolve() or (target.exists() and self.path.exists() and target.samefile(self.path)):
                    raise ToolError('Hosted tool target and legacy local source must be different files')
        if self.path is not None and not self._hosted:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        if self._hosted and self.path is not None and self.path.exists():
            with closing(sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro', uri=True)) as local:
                for table in ('ai_tools', 'ai_tool_runs'):
                    present = local.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", [table]).fetchone()
                    if present and local.execute(f'SELECT count(*) FROM {table}').fetchone()[0]:
                        raise ToolError('Local tool pins or run history require an explicit offsetx-db import-content --kind tools migration')
        self._lock = threading.Lock()
        self._local = threading.local()
        # Every thread's connection, so `close` reaches all of them: a restore
        # closes this store from one thread, and the connections the companion
        # routes and the readiness probe opened on others stayed on the old
        # workspace until garbage collection (D-131). As `ai/cache.py` does.
        self._connection_lock = threading.RLock()
        self._connections: set[Any] = set()
        self._generation = 0
        if self._hosted:
            with open_database(self.target) as database:
                ensure_initial_sql_schema(database, 'tools', SCHEMA,
                    large_integer_columns=LARGE_INTEGER_COLUMNS)
        else:
            with self.connection() as conn:
                conn.executescript(SCHEMA)

    def connection(self) -> Any:
        with self._connection_lock:
            conn = getattr(self._local, "conn", None)
            if conn is None or getattr(self._local, "generation", -1) != self._generation:
                if self._hosted:
                    conn = CachedStoreConnection(self.target)
                else:
                    conn = sqlite3.connect(self.path, check_same_thread=False)
                    conn.row_factory = sqlite3.Row
                    conn.execute("PRAGMA journal_mode=WAL")
                self._local.conn = conn
                self._local.generation = self._generation
                self._connections.add(conn)
            return conn

    def close(self) -> None:
        with self._connection_lock:
            for conn in self._connections:
                conn.close()
            self._connections.clear()
            self._generation += 1

    # ── registration: owner only ────────────────────────────────────────────

    def register(
        self,
        *,
        name: str,
        repository_url: str,
        commit_sha: str,
        image: str,
        command: Sequence[str],
        description: str = "",
        allows_arguments: bool = False,
        workspace_id: str = "local",
    ) -> RegisteredTool:
        """Pin a tool.  Every argument is validated; nothing defaults.

        This is the owner's act. No model reaches it — there is no tool
        definition, no function schema and no API path that exposes it to a
        provider, and a test walks the module to keep that true.
        """
        tool = RegisteredTool(
            id=uuid.uuid4().hex,
            name=validate_tool_name(name),
            description=str(description or "").strip()[:500],
            repository_url=validate_repository_url(repository_url),
            commit_sha=validate_commit_sha(commit_sha),
            image=validate_image(image),
            command=tuple(validate_command(command)),
            allows_arguments=bool(allows_arguments),
            registered_at=to_utc_iso(),
            registered_by="owner",
            workspace_id=workspace_id,
        )
        with self._lock, self.connection() as conn:
            existing = conn.execute(
                "SELECT id FROM ai_tools WHERE workspace_id = ? AND name = ?",
                (workspace_id, tool.name),
            ).fetchone()
            if existing:
                raise ToolError(
                    f"A tool named {tool.name!r} is already registered. Remove it "
                    "first, or choose another name."
                )
            conn.execute(
                """
                INSERT INTO ai_tools
                    (id, workspace_id, name, description, repository_url, commit_sha,
                     image, command, allows_arguments, enabled, registered_at, registered_by)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    tool.id,
                    workspace_id,
                    tool.name,
                    tool.description,
                    tool.repository_url,
                    tool.commit_sha,
                    tool.image,
                    json.dumps(list(tool.command)),
                    int(tool.allows_arguments),
                    1,
                    tool.registered_at,
                    tool.registered_by,
                ),
            )
        return tool

    def remove(self, tool_id: str, *, workspace_id: str = "local") -> bool:
        with self._lock, self.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM ai_tools WHERE id = ? AND workspace_id = ?",
                (tool_id, workspace_id),
            )
        return cursor.rowcount > 0

    def set_enabled(
        self, tool_id: str, enabled: bool, *, workspace_id: str = "local"
    ) -> bool:
        with self._lock, self.connection() as conn:
            cursor = conn.execute(
                "UPDATE ai_tools SET enabled = ? WHERE id = ? AND workspace_id = ?",
                (int(bool(enabled)), tool_id, workspace_id),
            )
        return cursor.rowcount > 0

    # ── reading ─────────────────────────────────────────────────────────────

    def get(self, tool_id: str, *, workspace_id: str = "local") -> RegisteredTool | None:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM ai_tools WHERE id = ? AND workspace_id = ?",
                (tool_id, workspace_id),
            ).fetchone()
        return _tool_from_row(row) if row else None

    def by_name(self, name: str, *, workspace_id: str = "local") -> RegisteredTool | None:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM ai_tools WHERE name = ? AND workspace_id = ?",
                (str(name).strip().lower(), workspace_id),
            ).fetchone()
        return _tool_from_row(row) if row else None

    def list(self, *, workspace_id: str = "local") -> list[RegisteredTool]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM ai_tools WHERE workspace_id = ? ORDER BY name",
                (workspace_id,),
            ).fetchall()
        return [_tool_from_row(row) for row in rows]

    def catalogue(self, *, workspace_id: str = "local") -> list[dict[str, Any]]:
        """What a model may be shown: enabled tools, names and descriptions only.

        Disabled tools are absent rather than marked, so a model cannot ask why
        one is unavailable or notice that it exists at all.
        """
        return [
            tool.catalogue_entry()
            for tool in self.list(workspace_id=workspace_id)
            if tool.enabled
        ]

    # ── running ─────────────────────────────────────────────────────────────

    def prepare_source(self, tool: RegisteredTool, destination: Path) -> Path:
        """Fetch the pinned commit onto the host, and prove it is that commit.

        The container has no network, so this cannot happen inside it — which is
        deliberate. Doing it here means the integrity check runs somewhere a
        compromised tool cannot reach, and the container receives a directory
        rather than the ability to fetch one.
        """
        if shutil.which("git") is None:
            raise ToolError("git is not installed, so tool source cannot be fetched.")
        destination.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                ["git", "init", "--quiet"],
                cwd=destination, check=True, capture_output=True, timeout=60,
            )
            subprocess.run(
                ["git", "remote", "add", "origin", tool.repository_url],
                cwd=destination, check=True, capture_output=True, timeout=60,
            )
            # Fetch the one commit, not the history. Refuses outright if the
            # server will not serve that SHA directly.
            subprocess.run(
                ["git", "fetch", "--depth", "1", "--quiet", "origin", tool.commit_sha],
                cwd=destination, check=True, capture_output=True, timeout=300,
            )
            subprocess.run(
                ["git", "checkout", "--quiet", "FETCH_HEAD"],
                cwd=destination, check=True, capture_output=True, timeout=60,
            )
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or b"").decode("utf-8", "replace")[:300]
            raise ToolError(
                f"Could not fetch {tool.commit_sha[:12]} from {tool.repository_url}: "
                f"{detail.strip() or 'git failed'}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ToolError(
                f"Fetching {tool.repository_url} timed out."
            ) from exc

        landed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=destination, check=False, capture_output=True, text=True, timeout=30,
        ).stdout.strip().lower()
        if landed != tool.commit_sha:
            # Belt and braces. Fetching a SHA should give that SHA, but the whole
            # value of pinning is that this is checked rather than assumed.
            raise ToolError(
                f"Integrity check failed for {tool.name!r}: expected commit "
                f"{tool.commit_sha}, got {landed or 'nothing'}. Nothing was run."
            )
        return destination

    def run(
        self,
        tool_id: str,
        *,
        workspace: SandboxWorkspace,
        extra_arguments: Sequence[str] = (),
        data_class: DataClass = DataClass.PUBLIC,
        policy: SandboxPolicy | None = None,
        workspace_id: str = "local",
        timeout_seconds: int = 600,
        fetch_source: bool = True,
    ) -> ToolRun:
        """Run a registered tool in the sandbox.

        Note the signature: a ``tool_id``, not an image and a command. A caller —
        including a model-driven one — can choose *which* pinned tool runs and
        nothing about *how*.
        """
        from .sandbox import assert_public

        assert_public(data_class)
        timeout_seconds = max(1, int(timeout_seconds))
        tool = self.get(tool_id, workspace_id=workspace_id)
        if tool is None:
            raise ToolError(
                f"No tool with id {tool_id!r} is registered. Tools must be "
                "registered by the owner before they can run."
            )
        if not tool.enabled:
            raise PolicyViolation(
                f"Tool {tool.name!r} is disabled. Re-enable it before running it."
            )
        assert_sandbox_available()
        arguments = validate_extra_arguments(tool, extra_arguments)
        workspace.prepare()
        workspace.assert_within_budget()

        if fetch_source:
            self.prepare_source(tool, workspace.inbox / "source")

        sandbox = policy or SandboxPolicy()
        argv = sandbox.docker_command(
            image=tool.image,
            command=[*tool.command, *arguments],
            workspace=workspace,
        )
        container_name = 'offsetx-tool-'+uuid.uuid4().hex
        argv[2:2] = ['--name', container_name]

        started = time.monotonic()
        status = "ran"
        try:
            completed = subprocess.run(
                argv, capture_output=True, text=True, check=False,
                timeout=max(1, int(timeout_seconds)),
            )
            exit_code = completed.returncode
            stdout, stderr = completed.stdout, completed.stderr
        except subprocess.TimeoutExpired:
            stopped = _stop_run_container(container_name)
            status = 'timeout' if stopped else 'timeout_cleanup_unknown'
            exit_code = -1
            stdout = ''
            stderr = (f'The tool exceeded {timeout_seconds}s and its container was stopped.' if stopped else
                f'The tool exceeded {timeout_seconds}s; container cleanup could not be confirmed. '
                f'Container: {container_name}. Inspect this container on the sandbox host before rerunning this tool.')
        except BaseException:
            _stop_run_container(container_name)
            raise
        duration_ms = int((time.monotonic() - started) * 1000)

        run = ToolRun(
            id=uuid.uuid4().hex,
            tool_id=tool.id,
            tool_name=tool.name,
            argv=[*tool.command, *arguments],
            exit_code=exit_code,
            stdout=stdout[-20000:],
            stderr=stderr[-20000:],
            duration_ms=duration_ms,
            status=status,
        )
        self._record_run(run, tool, workspace_id=workspace_id)
        workspace.assert_within_budget()
        return run

    def _record_run(
        self, run: ToolRun, tool: RegisteredTool, *, workspace_id: str
    ) -> None:
        with self._lock, self.connection() as conn:
            conn.execute(
                """
                INSERT INTO ai_tool_runs
                    (id, workspace_id, tool_id, tool_name, commit_sha, image, argv,
                     exit_code, stdout, stderr, duration_ms, status, started_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    run.id, workspace_id, tool.id, tool.name, tool.commit_sha,
                    tool.image, json.dumps(run.argv), run.exit_code,
                    run.stdout, run.stderr, run.duration_ms, run.status,
                    to_utc_iso(),
                ),
            )

    def runs(
        self, *, workspace_id: str = "local", tool_id: str = "", limit: int = 50
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM ai_tool_runs WHERE workspace_id = ?"
        params: list[Any] = [workspace_id]
        if tool_id:
            sql += " AND tool_id = ?"
            params.append(tool_id)
        sql += " ORDER BY started_at DESC LIMIT ?"
        params.append(int(limit))
        with self.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            {
                "id": row["id"],
                "tool_id": row["tool_id"],
                "tool_name": row["tool_name"],
                "commit_sha": row["commit_sha"],
                "image": row["image"],
                "argv": json.loads(row["argv"]),
                "exit_code": row["exit_code"],
                "duration_ms": row["duration_ms"],
                "status": row["status"],
                "started_at": row["started_at"],
                "error": _safe_cleanup_diagnostic(row['stderr']) if row['status'] == 'timeout_cleanup_unknown' else '',
            }
            for row in rows
        ]

    def stats(self, *, workspace_id: str = "local") -> dict[str, Any]:
        with self.connection() as conn:
            tools = conn.execute(
                "SELECT COUNT(*) AS n FROM ai_tools WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchone()["n"]
            enabled = conn.execute(
                "SELECT COUNT(*) AS n FROM ai_tools WHERE workspace_id = ? AND enabled = 1",
                (workspace_id,),
            ).fetchone()["n"]
            runs = conn.execute(
                "SELECT COUNT(*) AS n FROM ai_tool_runs WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchone()["n"]
        return {"tools": tools, "enabled": enabled, "runs": runs}


def _tool_from_row(row: sqlite3.Row) -> RegisteredTool:
    return RegisteredTool(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        repository_url=row["repository_url"],
        commit_sha=row["commit_sha"],
        image=row["image"],
        command=tuple(json.loads(row["command"])),
        allows_arguments=bool(row["allows_arguments"]),
        enabled=bool(row["enabled"]),
        registered_at=row["registered_at"],
        registered_by=row["registered_by"],
        workspace_id=row["workspace_id"],
    )
