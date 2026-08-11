# Code graph (§4K)

A queryable map of this repository. Ask *"what reaches the egress broker?"* and
get an answer in a second instead of reading forty files.

Developer tooling, not product. It touches no campaign and no contact.

```
offsetx-codegraph policy    # the locked invocation, and what is refused
offsetx-codegraph build     # ignore file → extract → cluster → verify
offsetx-codegraph status    # how stale the graph is against HEAD
offsetx-codegraph verify    # re-check an existing graph without rebuilding
```

---

## Why this needs a module and not a shell command

Graphify (`graphifyy` on PyPI) parses with tree-sitter and is genuinely fast —
**seven seconds** for this repo, 3,047 nodes, 7,935 edges. It is also one flag
away from being an egress event.

From its own help text:

| Invocation | What it does |
|---|---|
| `graphify extract <path>` | "headless full extraction (AST + **semantic LLM**)" — picks a backend from whichever API key it finds (gemini, openai, deepseek, claude, kimi, ollama) and posts chunks of your source to it |
| `graphify extract <path> --code-only` | "index code (**local AST, no API key**)" |
| `graphify cluster-only <path>` | names communities with an LLM |
| `graphify cluster-only <path> --no-label` | keeps `Community 7` and stays local |

That is the difference between a build step and sending your source code to a
third party, and it is two flags.

**The previous attempt put those flags in `scripts/build_code_graph.ps1`** — a
PowerShell file, so it ran on one operating system out of three, and a text file
anyone could edit without noticing what they had switched on.

This module builds the argument list in code, and a test asserts the safe flags
are in it. `--code-only` is not even a parameter: a keyword argument would put
the unsafe call one keystroke away and give it a place in someone's
autocomplete.

---

## What is refused, and why

Each of these is something a person would reach for after five minutes with
`graphify --help`, so the refusal ships with its reason attached.

| Refused | Why |
|---|---|
| `extract` without `--code-only` | The semantic path. Source is internal data. |
| `label`, `cluster-only` without `--no-label` | Sends symbol names to a model for naming. Cheaper than full extraction and still egress. |
| `add <url>` | Fetches a URL into the corpus. Untrusted external content entering a corpus a model later reads is the middle term of the lethal trifecta. |
| `--global`, `global add` | Merges this repo's graph into `~/.graphify/global-graph.json`, shared with every other project on the machine. The graph stays inside the repo it describes. |
| `claude install`, `codex install`, `hook install` | Write vendor sections into `AGENTS.md` and install git hooks. off_CRM does not edit its own instruction files or your git config as a side effect of building an index. |
| `--no-gitignore` | The single flag that would let `local_data/` be indexed. |
| `--postgres <dsn>` | Connects to a live database. Ours holds real contacts. |

`query`, `path`, `explain`, `affected` and `god-nodes` are **local BFS over
`graph.json`** — no model, no network. Those are the ones worth using.

---

## Verified, not asserted

`.graphifyignore` lists the directories holding real contacts, the CRM database
and the encrypted key file. Writing that list is not the same as knowing it
worked.

So after every build the graph is **read back**, and if any indexed file lives
under a runtime-data path the graph is **deleted** and the build fails. Not kept
with a warning printed above it — someone would query it anyway, because the
file was there.

The graph holds symbol names, file paths and edges — **no source text** — so the
check is precise and has nothing to false-positive on.

### The probe, run on this repo

A `local_data/leak_probe.py` was planted with a contact name and an address in
it, then extraction was run three ways:

| Layers active | Leaked nodes | Checker |
|---|---|---|
| `.gitignore` only | **0** | clean |
| `.graphifyignore` only (`--no-gitignore`) | **0** | clean |
| **both bypassed** | **2** | **rejected: `local_data/leak_probe.py`** |

Each layer holds on its own, and when both are defeated the backstop fires. That
is why the check exists: the two ignore files are the belt and braces, and the
verifier is what happens when someone cuts through both.

Reproduce it with a scratch output directory so your real graph is untouched:

```bash
mkdir -p local_data && echo 'X = "Ana Silva"' > local_data/leak_probe.py
rm .graphifyignore
uvx --from graphifyy==0.9.39 graphify extract . --code-only --no-cluster \
    --force --no-gitignore --out /tmp/probe
offsetx-codegraph --out /tmp/probe verify     # expect: rejected
rm -rf local_data && offsetx-codegraph build  # restores .graphifyignore
```

---

## The ignore list has one home

`RUNTIME_DATA_PATHS` lives in `codegraph.py`. `.graphifyignore` is **generated**
from it on every build, overwriting hand edits — a hand-edited ignore file is a
silent way to add a directory to the index.

A test cross-references the list against `api/config.py`: every default path the
app writes to must be covered. Rename the data directory and the test fails
rather than leaving the ignore list pointing at a path nothing uses any more.

`email_expert_library/` is deliberately **not** on the list. It holds shipped
default templates the app only reads; the owner's own ingested documents go to
SQLite under `local_data/`. It is named in `NOT_RUNTIME_DATA` so the next person
does not add it back.

---

## Pinning

`graphifyy==0.9.39`, exact, run through `uvx` so it never enters the project's
virtualenv (it pulls about thirty tree-sitter grammars). Same reasoning as the
tool registry pinning its images: an unpinned tool is a different tool tomorrow,
and this one has a flag that decides whether source code leaves the machine.

`OFFSETX_GRAPHIFY_BIN` points at an existing install for offline machines. When
used, the build reports **"version NOT pinned"** — a run against whatever
`graphify` happens to be on `PATH` is not the run this document describes.

---

## Staleness

`graph.json` records `built_at_commit`. `status` compares it to `HEAD`:

```
Fresh: built at 8ac02a79, which is HEAD.
3047 nodes, 7935 edges
```

An answer from a graph two hundred commits old is confidently wrong, which is
worse than no answer, so staleness is reported rather than hidden. A graph that
records no commit at all is treated as stale.

`graphify update .` re-extracts changed files with no LLM and no API cost;
`offsetx-codegraph build` is the full rebuild.

---

## What is not built

- **No CI job.** Building on every push is plausible; nobody asked for it.
- **No automatic rebuild on commit.** Graphify offers git hooks; installing them
  is on the refused list, because off_CRM does not edit your git config as a
  side effect.
- **Nothing in off_CRM reads the graph.** It is for you and for whatever coding
  agent you point at it. Wiring it into the AI layer would mean handing a model
  a map of the codebase, which is a separate decision with its own answer.
- **`graphify-out/` is gitignored.** It is a build artefact plus a 4.6 MB cache,
  and it is rebuilt in seconds.
