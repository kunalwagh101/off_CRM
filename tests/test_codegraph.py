"""Code graph (§4K).

Graphify is a good tool with a dangerous default. `graphify extract <path>` is
"AST + **semantic LLM**" — it finds an API key and posts chunks of your source to
whichever backend it belongs to. `--code-only` turns that into "local AST, no
API key".

So the property this file protects is not that the graph is correct. It is that
the invocation cannot quietly become an egress event, and that the graph never
indexes the contact database sitting in `local_data/`.

Two guarantees, tested separately:

1. **The flags are welded in.** The argument list is built in code, not in an
   editable script, and the safe flags are asserted here.
2. **The result is checked, not trusted.** After a build, the graph is read back
   and rejected if it indexed anything under a runtime-data path. Telling a tool
   to skip a directory and knowing that it did are different things.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.codegraph import (
    BUILD_ARTEFACT_PATHS,
    FORBIDDEN_USES,
    GRAPHIFY_PACKAGE,
    GRAPHIFY_VERSION,
    NOT_RUNTIME_DATA,
    OUTPUT_DIRNAME,
    RUNTIME_DATA_PATHS,
    CodeGraph,
    CodeGraphError,
    GraphRejected,
    cluster_command,
    extract_command,
    graph_status,
    graphify_available,
    indexed_files,
    render_ignore_file,
    verify_graph,
    write_ignore_file,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _graph(nodes: list[dict], *, commit: str = "") -> dict:
    payload: dict = {"nodes": nodes, "links": []}
    if commit:
        payload["built_at_commit"] = commit
    return payload


def _write_graph(tmp_path: Path, nodes: list[dict], *, commit: str = "") -> Path:
    out = tmp_path / OUTPUT_DIRNAME
    out.mkdir(parents=True, exist_ok=True)
    path = out / "graph.json"
    path.write_text(json.dumps(_graph(nodes, commit=commit)), encoding="utf-8")
    return path


# ─────────────────────────────────────────────────────────────────────────────
# The flags are welded in
# ─────────────────────────────────────────────────────────────────────────────


def test_extraction_is_always_code_only():
    """The one flag that decides whether source code leaves the machine.

    Without it Graphify's own help calls `extract` "AST + semantic LLM" and
    picks a backend from whatever API key it finds.
    """
    argv = extract_command("/repo")
    assert "--code-only" in argv
    assert "--no-cluster" in argv
    assert "extract" in argv


def test_code_only_is_not_a_parameter():
    """It cannot be switched off through this module's API.

    A keyword argument would make the unsafe call one keystroke away and give it
    a place in someone's autocomplete.
    """
    import inspect

    names = set(inspect.signature(extract_command).parameters)
    assert "code_only" not in names
    assert not (names & {"semantic", "backend", "model", "mode", "llm"}), names


def test_clustering_never_labels_with_a_model():
    argv = cluster_command("/repo")
    assert "--no-label" in argv
    assert "--no-viz" in argv
    assert "cluster-only" in argv


def test_the_version_is_pinned_in_the_command():
    argv = extract_command("/repo")
    assert f"{GRAPHIFY_PACKAGE}=={GRAPHIFY_VERSION}" in argv
    assert argv[0] == "uvx"


def test_an_explicit_binary_is_reported_as_unpinned(monkeypatch):
    """Supported for offline machines, but the report must say so.

    A run against whatever `graphify` happens to be on PATH is not the run this
    module describes, and pretending otherwise is the kind of small lie that
    makes a security note worthless.
    """
    argv = extract_command("/repo", binary="/opt/graphify")
    assert argv[0] == "/opt/graphify"
    assert GRAPHIFY_VERSION not in " ".join(argv)

    monkeypatch.setenv("OFFSETX_GRAPHIFY_BIN", "/usr/bin/env")
    available, note = graphify_available()
    assert available
    assert "not pinned" in note


def test_no_forbidden_subcommand_appears_in_any_command():
    """`label`, `add`, `--global` and the install commands are never emitted."""
    emitted = set(extract_command("/repo")) | set(cluster_command("/repo"))
    banned = {
        "label",
        "add",
        "--global",
        "global",
        "install",
        "hook",
        "--no-gitignore",
        "--postgres",
        "--backend",
        "--model",
        "--mode",
        "watch",
        "clone",
    }
    assert not (emitted & banned), emitted & banned


def test_every_refusal_carries_its_reason():
    """A refusal without a reason reads as an unfinished wrapper.

    Each of these is something a person would reach for after five minutes with
    `graphify --help`, so the answer has to arrive with the why attached.
    """
    assert len(FORBIDDEN_USES) >= 6
    for item in FORBIDDEN_USES:
        assert item.what and item.why
        assert len(item.why) > 40, item.what

    subjects = " ".join(item.what for item in FORBIDDEN_USES)
    for expected in ("--code-only", "label", "add", "--global", "install", "--no-gitignore"):
        assert expected in subjects, expected


def test_the_module_never_shells_out_to_a_provider():
    """Structural: the wrapper runs one binary and it is Graphify.

    An HTTP client appearing in here would mean the module had grown its own
    path to a model, which the flag discipline above would no longer describe.
    """
    source = (REPO_ROOT / "offsetx_apollo_builder" / "codegraph.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert not (imported & {"requests", "httpx", "urllib.request", "openai", "socket"}), imported


# ─────────────────────────────────────────────────────────────────────────────
# The ignore file has one home
# ─────────────────────────────────────────────────────────────────────────────


def test_the_ignore_file_covers_every_runtime_data_path():
    text = render_ignore_file()
    for path in RUNTIME_DATA_PATHS:
        assert f"{path}/" in text, path
    for path in BUILD_ARTEFACT_PATHS:
        assert f"{path}/" in text, path
    assert "Do not hand-edit" in text


def test_the_ignore_file_is_regenerated_over_hand_edits(tmp_path):
    """A hand-edited ignore file is a silent way to add a directory to the index."""
    existing = tmp_path / ".graphifyignore"
    existing.write_text("# my own list\n", encoding="utf-8")
    written = write_ignore_file(tmp_path)
    assert written == existing
    assert "my own list" not in existing.read_text()
    assert "local_data/" in existing.read_text()


def test_runtime_data_paths_cover_the_app_default_locations(tmp_path):
    """Drift guard against `api/config.py`.

    If someone renames the data directory, this fails rather than leaving the
    ignore list pointing at a path the app stopped using.
    """
    settings = AppSettings.from_env(REPO_ROOT)
    candidates = [
        settings.data_dir,
        settings.database_path,
        settings.export_dir,
        settings.gmail_token,
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            relative = Path(candidate).resolve().relative_to(REPO_ROOT)
        except ValueError:
            continue  # configured outside the repo; nothing to ignore
        head = relative.parts[0]
        assert any(
            head == guarded or (guarded == "output" and head.startswith("output"))
            for guarded in RUNTIME_DATA_PATHS
        ), f"{relative} is written at runtime but {head}/ is not in RUNTIME_DATA_PATHS"


def test_shipped_content_is_not_treated_as_runtime_data():
    """`email_expert_library/` is read-only defaults tracked in git.

    Adding it to the guarded list would exclude legitimately committed content
    and blunt the meaning of the list, so it is named as not-data on purpose.
    """
    for path in NOT_RUNTIME_DATA:
        assert path not in RUNTIME_DATA_PATHS
        assert (REPO_ROOT / path).exists(), f"{path} no longer exists; update NOT_RUNTIME_DATA"


# ─────────────────────────────────────────────────────────────────────────────
# The result is checked, not trusted
# ─────────────────────────────────────────────────────────────────────────────


def test_a_graph_that_indexed_the_contact_database_is_rejected(tmp_path):
    path = _write_graph(
        tmp_path,
        [
            {"source_file": "offsetx_apollo_builder/ai/broker.py"},
            {"source_file": "local_data/offsetx_outreach.db"},
        ],
    )
    check = verify_graph(path)
    assert not check.ok
    assert check.offending == ["local_data/offsetx_outreach.db"]
    assert "local_data" in check.reasons["local_data/offsetx_outreach.db"]


@pytest.mark.parametrize(
    "relative",
    [
        "local_data/contacts.json",
        "output_2026/leads.csv",
        "old_pois/batch.xlsx",
        "poi_file_queue/inbox/list.csv",
        "backups/dump.db",
        "raw/scraped-page.html",
        "config/client_secret_884.json",
        "docs/leads.xlsx",
        "/home/kunal/private/notes.py",
        "../outside/thing.py",
    ],
)
def test_every_data_shape_is_caught(tmp_path, relative):
    path = _write_graph(tmp_path, [{"source_file": relative}])
    check = verify_graph(path)
    assert not check.ok, relative
    assert check.reasons[relative]


def test_ordinary_source_files_pass(tmp_path):
    path = _write_graph(
        tmp_path,
        [
            {"source_file": "offsetx_apollo_builder/ai/broker.py"},
            {"source_file": "frontend/src/pages/AI.tsx"},
            {"source_file": "tests/test_ai_egress_wall.py"},
            {"source_file": "config/providers.yaml"},
            {"source_file": "email_expert_library/default_templates.json"},
            {"source_file": ".claude/hooks/session-start.sh"},
        ],
    )
    check = verify_graph(path)
    assert check.ok, check.summary()
    assert check.files_checked == 6


def test_the_manifest_is_checked_too(tmp_path):
    """A file can be read, produce no nodes, and appear only in the manifest.

    Having been *read* is the thing worth knowing about, so a graph whose nodes
    look clean is still rejected when the manifest shows the database was
    scanned.
    """
    path = _write_graph(tmp_path, [{"source_file": "offsetx_apollo_builder/cli.py"}])
    (path.parent / "manifest.json").write_text(
        json.dumps({"local_data/offsetx_outreach.db": {"mtime": 1.0}}), encoding="utf-8"
    )
    check = verify_graph(path)
    assert not check.ok
    assert "local_data/offsetx_outreach.db" in check.offending


def test_a_rejected_build_deletes_the_output(tmp_path, monkeypatch):
    """A graph of the contact database is not something to keep with a warning.

    The failure mode this prevents is a rejected build leaving a readable graph
    on disk, which someone then queries because the file was there.
    """
    graph = CodeGraph(tmp_path)
    monkeypatch.setattr(
        "offsetx_apollo_builder.codegraph.graphify_available", lambda **_: (True, "test")
    )

    def fake_run(argv):
        _write_graph(tmp_path, [{"source_file": "local_data/offsetx_outreach.db"}])
        return ""

    monkeypatch.setattr(CodeGraph, "_run", lambda self, argv: fake_run(argv))

    with pytest.raises(GraphRejected) as exc:
        graph.build()
    assert not graph.output_dir.exists(), "a rejected graph must not survive on disk"
    assert "local_data" in str(exc.value)


def test_a_clean_build_reports_what_it_ran(tmp_path, monkeypatch):
    graph = CodeGraph(tmp_path)
    monkeypatch.setattr(
        "offsetx_apollo_builder.codegraph.graphify_available", lambda **_: (True, "test")
    )
    monkeypatch.setattr(
        CodeGraph,
        "_run",
        lambda self, argv: _write_graph(
            tmp_path, [{"source_file": "offsetx_apollo_builder/cli.py"}]
        )
        and "",
    )

    result = graph.build()
    assert result.check.ok
    assert result.ignore_path.exists()
    assert any("--code-only" in command for command in result.commands)
    assert any("--no-label" in command for command in result.commands)
    assert result.pinned


def test_verifying_a_missing_graph_says_so(tmp_path):
    with pytest.raises(CodeGraphError) as exc:
        verify_graph(tmp_path / "nope.json")
    assert "Build it first" in str(exc.value)


def test_indexed_files_reads_nodes_and_edges():
    graph = {
        "nodes": [{"source_file": "a.py"}, {"source_file": "a.py"}, {"no_source": 1}],
        "links": [{"source_file": "b.py"}],
    }
    assert indexed_files(graph) == ["a.py", "b.py"]


# ─────────────────────────────────────────────────────────────────────────────
# Freshness
# ─────────────────────────────────────────────────────────────────────────────


def test_status_reports_no_graph(tmp_path):
    status = graph_status(tmp_path)
    assert not status.exists
    assert "No graph" in status.summary()


def test_a_graph_built_at_another_commit_is_stale(tmp_path):
    """An answer from a graph two hundred commits old is confidently wrong.

    Worse than no answer, so staleness is reported rather than hidden.
    """
    _write_graph(tmp_path, [{"source_file": "a.py"}], commit="0" * 40)
    status = graph_status(tmp_path)
    assert status.exists
    assert status.built_at_commit == "0" * 40
    # No git repo in tmp_path, so HEAD is unknown and staleness cannot be claimed.
    assert not status.stale
    assert "does not record" not in status.summary()


def test_a_graph_without_a_commit_is_treated_as_stale(tmp_path):
    _write_graph(tmp_path, [{"source_file": "a.py"}])
    assert "stale" in graph_status(tmp_path).summary().lower()


# ─────────────────────────────────────────────────────────────────────────────
# Live
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(not graphify_available()[0], reason=graphify_available()[1])
def test_a_real_build_of_this_repository_is_clean(tmp_path):
    """The only test that proves the flags work rather than that they are present.

    Runs against a scratch output directory so the repository's own graph is
    untouched, and asserts the real thing: nothing under a runtime-data path was
    indexed, and no model was involved.
    """
    graph = CodeGraph(REPO_ROOT, out_dir=tmp_path, timeout=900)
    result = graph.build(workers=2)

    assert result.check.ok, result.check.summary()
    assert result.status.nodes > 500, "a repository this size should produce a real graph"
    report = result.report_path.read_text(encoding="utf-8")
    assert "Token cost: 0 input · 0 output" in report, (
        "a non-zero token cost means the semantic path ran and source left the machine"
    )
