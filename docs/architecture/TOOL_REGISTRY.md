# The tool registry (§4J)

`ai/sandbox.py` is the locked room. This is the list of who may enter.

---

## The one sentence

> **A model names a tool that already exists. It cannot describe a new one.**

That is the difference between a **catalogue** and a **constructor**.

If a model could supply an image and a command at run time, the sandbox flags
would be the only thing between a prompt injection and arbitrary code execution.
Flags are a last line of defence. The registry is the first one.

Look at the signature — it is the whole security argument:

```python
registry.run(tool_id, workspace=..., extra_arguments=[...])
#            ^^^^^^^ a name. Not an image. Not a command.
```

A test asserts this at the signature level: if `run` ever grows an `image=` or
`command=` parameter, the registry has stopped being a registry and the build
fails.

---

## Three pins, all mandatory

| Field | Rule | Why |
|---|---|---|
| `repository_url` | `https://github.com/owner/repo` only | An arbitrary host is an arbitrary payload |
| `commit_sha` | full 40-character SHA | **Not a branch or tag** — those move. You reviewed a commit, not a name currently pointing at one. |
| `image` | pinned tag or digest, never `:latest` | Same reason. `:latest` means the image you reviewed is not necessarily the image that runs. |

Nothing defaults. A registration missing any of these is refused with a sentence
saying which one and why.

---

## What a model sees vs. what you see

**The catalogue** — everything a model gets:

```json
{"id": "6b9ce4df…", "name": "run-tests",
 "description": "Runs the project test suite.", "accepts_arguments": false}
```

No image. No command. No repository. A model choosing a tool needs to know *what
it does*, not *how to rebuild it* — so a leaked catalogue is not a leaked attack
surface.

**Your view** carries the full record: repo, commit, image, command.

A **disabled** tool is *absent* from the catalogue rather than marked, so a model
cannot notice it exists at all.

---

## Arguments are opt-in

Off by default. Arbitrary arguments are arbitrary code paths, and the point of
pinning is that the executable surface was fixed in advance.

A tool that genuinely takes a parameter says so at registration
(`--allow-arguments`), and even then:

- at most 8 extra arguments,
- values only — anything starting with `-` is refused, so a caller cannot change
  *how* the tool behaves,
- same shape rules as the base command: bounded length, no null bytes.

---

## Why the source is fetched on the host

The container runs with `--network=none`, so **it cannot clone anything**. That
is the point.

So off_CRM materialises the source *before* the container starts, on the host
where network is allowed, then proves what landed is the pinned commit:

```
git init → remote add → fetch --depth 1 <sha> → checkout FETCH_HEAD
→ rev-parse HEAD must equal the registered SHA, or nothing runs
```

This is the same rule as everywhere else in the module — **off_CRM pushes, the
sandbox never pulls** — and it puts the integrity check somewhere a compromised
tool cannot reach.

Source lands in `inbox/`, which mounts **read-only**, so a tool cannot rewrite
its own source mid-run.

---

## Using it

```bash
offsetx-tools register --name run-tests \
    --repo https://github.com/you/thing \
    --commit 1a2b3c…40chars \
    --image python:3.12-slim \
    --description "Runs the project test suite." \
    -- pytest -q

offsetx-tools list          # your view: repo, commit, image, command
offsetx-tools catalogue     # exactly what a model would be shown
offsetx-tools run run-tests
offsetx-tools runs          # history, with the commit each run used
offsetx-tools disable run-tests
```

Everything after `--` is the command that runs inside the container.

---

## The audit trail

Every run is recorded with the **commit and image it actually used** — not just
the tool name. "run-tests failed" is not a useful record six weeks later;
"run-tests at `1a2b3c` on `python:3.12-slim` exited 3" is.

A timeout is recorded as a run with `status: timeout`, not raised as an
exception, so a tool that hangs still leaves a trace.

---

## One thing fixed while building this

`sandbox_available()` originally checked for the **docker binary** via
`shutil.which`. That is not the same as a **running daemon** — this development
machine has the binary and no engine, and the first CLI run sailed past the
check and failed several steps later inside a git fetch, with a much worse
message.

It now probes the engine:

```bash
docker version --format {{.Server.Version}}
```

`docker info` is not usable for this — **it exits zero even when the server half
fails**. The probe requires both a zero exit *and* a non-empty server version,
and there is a parametrised test covering all four combinations.

`sandbox_available(check_daemon=False)` skips the subprocess where the answer is
only advisory, such as a UI badge.

---

## Still open

The registry stores, validates, fetches, runs and logs. What is **not** built:

- **A model-facing path.** Nothing currently hands the catalogue to a model or
  lets an orchestrated plan call a tool. That is deliberate — the storage and
  isolation should be solid before anything automated can reach them.
- **A UI screen.** CLI only for now.
- **Live verification.** The container flags still need confirming against a
  real daemon:

  ```bash
  docker pull python:3.12-slim
  OFF_CRM_SANDBOX_TEST_IMAGE=python:3.12-slim uv run pytest tests/test_ai_sandbox.py -v
  ```
