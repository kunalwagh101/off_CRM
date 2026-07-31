# Sandbox design (§4J)

The open item in `BUILD_STATE.md` §4. Nothing here is built yet — this is the
design, written so it can be implemented directly.

It also unblocks the one acceptance case the security suite cannot currently
cover: §5.12(c), *sandboxed code cannot reach an arbitrary external host*.
`tests/test_ai_egress_wall.py` says so honestly in its own docstring today.

---

## The question that was asked

> Campaigns are one thing. The sandbox is for building software. I'm guessing
> it falls under the same context layer — correct me on this.

**Correct, with one precision:**

> **Same policy engine, same context layer. Two runtimes, opposite capability
> grants.**

They are mirror images of each other:

| | Sandbox | Campaign runner (`outreach/engine.py`) |
|---|---|---|
| Runs AI-written code | ✔ yes | ✖ never |
| Network | ✖ **none** | ✔ SMTP only |
| Real contact data | ✖ never | ✔ yes |
| Credentials | ✖ never | ✔ yes |
| Makes decisions | ✔ yes | ✖ never |
| Imports `ai/` | ✖ no | ✖ no (verified) |

Neither holds all three legs of the lethal trifecta — private data, untrusted
content, outbound network. That is the security argument in one line.

---

## Where it sits

```
┌──────────────────────────────────────────────────────────────┐
│  ZONE 0 — PRIVATE                                            │
│  Gmail token · raw inbox · store.py · context.py · recall.py │
│  NO MODEL RUNS HERE. NO SANDBOX MOUNTS THIS.                 │
└──────────────────────────────────────────────────────────────┘
                    │ push only, never pull
                    ▼
┌──────────────────────────────────────────────────────────────┐
│  ZONE 1 — WORK                                               │
│  ai/broker.py · ai/modes.py · payload · scanner              │
└──────────────────────────────────────────────────────────────┘
          │                              │
          ▼                              ▼
 ┌──────────────────┐          ┌──────────────────────┐
 │  SANDBOX (§4J)   │          │  CAMPAIGN RUNNER     │
 │  --network=none  │          │  cron · idempotent   │
 │  no store mount  │          │  no AI import        │
 └──────────────────┘          └──────────────────────┘
```

---

## Data class

Sandbox work is `DataClass.PUBLIC`. Source code, schemas and tests identify
nobody. This matters for cost: after the cross-tier public routing fix (see
`FINDINGS.md`), **all software work routes to the cheapest permitted model** —
which is exactly where the free open-weight models belong.

A sandbox job must never be given a higher data class. If a task genuinely needs
contact data, it is not a sandbox task.

---

## Folder layout

```
workspace/<workspace_id>/sandbox/<job_id>/
├── inbox/   ← what off_CRM pushed in for this job   (mounted read-only)
└── work/    ← the tool's desk                        (mounted read-write, capped)
```

**`local_data/` and the SQLite stores are never mounted.** Not read-only —
absent. The context layer, the recall index and the egress log do not exist
inside the container's filesystem view.

---

## Container settings

```
--network=none                    ← the single most important flag
--read-only                       ← immutable root filesystem
--cap-drop=ALL
--security-opt=no-new-privileges
--user 10001:10001                ← never root
--pids-limit=256                  ← no fork bombs
--memory=2g --memory-swap=2g      ← equal, so swap cannot be used to exceed it
--cpus=2
--tmpfs /tmp:size=512m,noexec,nosuid
mount inbox/ :ro
mount work/  :rw   (size-capped)
```

`--network=none` removes the third leg of the trifecta. Even if the code is
hostile and escapes its process, it has nowhere to send anything.

### Isolation strength, honestly

| Approach | Real isolation | Verdict |
|---|---|---|
| Python `exec` with restricted builtins | **none** | Dozens of documented escapes. Never use. |
| Plain Docker | shared kernel | A kernel bug is a full escape |
| Docker + the flags above | good | **Start here** |
| gVisor (user-space kernel) | better | Modal uses it |
| Firecracker microVM (own kernel each) | best | E2B uses it, ~150ms boot |

Recommendation: hardened Docker behind a `SandboxRuntime` interface, so E2B or
Daytona can be swapped in later without touching callers. **Do not write a
sandbox from scratch** — getting it wrong fails silently, which is the worst
category of bug.

---

## Two constraints to design around now

**1. This will not run on Render.** Render already runs the app inside a
container and standard plans do not permit nesting. The feature must detect this
and disable itself with a clear message rather than failing mysteriously.

```python
def sandbox_available() -> tuple[bool, str]:
    if os.environ.get("RENDER"):
        return False, ("Sandboxed tools need to start a container, which this host "
                       "does not allow. Run off_CRM locally to use them.")
    ...
```

This mirrors how the module already handles refusals: a readable sentence with a
next step, never a raw status code (§4L).

**2. Container isolation cannot be verified in a cloud dev session.** There is
no Docker daemon in this environment. Everything around the runtime can be
unit-tested; the isolation flags themselves need confirming on real hardware.
That is why §5.12(c) stays open in `BUILD_STATE.md` until someone runs it.

---

## Tests §4J must ship with

| Test | Asserts |
|---|---|
| `test_sandbox_has_no_network` | An HTTP request from inside fails. **Closes §5.12(c).** |
| `test_sandbox_cannot_read_the_store` | `local_data/`, the context DB and the recall index are absent |
| `test_sandbox_cannot_read_credentials` | No key file, no `OFFSETX_*` env var |
| `test_sandbox_runs_as_non_root` | `os.getuid() != 0` |
| `test_sandbox_disk_cap_enforced` | Writing past the cap fails; host disk unaffected |
| `test_sandbox_job_is_public_data_class` | A job with a higher class is refused before it starts |
| `test_sandbox_disabled_on_render` | Clear refusal, not a crash |
| `test_no_sandbox_module_imports_a_provider` | AST walk, same technique as `test_ai_egress_wall.py:412` |

That last one is the pattern already proven in this repo: architecture rules
written only in prose rot, and a test that walks the AST fails the build the day
someone breaks the rule.

---

## Why the quality loop belongs here

The sandbox is what makes "better than any single model" real for software work,
and it costs almost nothing:

1. Tests are written **first**, by a different model than the implementer.
2. Implementation runs in the sandbox.
3. `pytest` + type checker + linter run. **Cost $0, reliability 100%.**
4. Failures loop back with the exact error text. Cap the loop (~5 rounds);
   published work on verification loops finds rounds 1–2 capture most of the
   gain.
5. A strong model reviews the final diff — mostly input tokens, 3–5× cheaper
   than generation.

The quality does not come from several models voting. It comes from **cheap
models plus a judge that cannot be fooled.** The judge here is the test suite.
