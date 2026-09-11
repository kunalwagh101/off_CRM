"""The live check for `S-11.04.02` — a real run on a real browser, watched.

Real: the browser, the page it is served, the accessibility snapshot, the trace
on disk, and the whole watcher path from `Trace.append` to the terminal.
Scripted: the model's decisions, because a box with no provider credentials
cannot plan, and this is about *seeing* a run rather than about planning one.

What it shows: every line is printed by `console()`-style output from inside
`Trace.append`, and the `t+` stamp is when it was printed. A spread of 0.00s
would mean progress had been batched to the end, which is the thing this story
exists to stop.

The click is *expected to be refused*. The page is served on loopback, and
`policy.py` will not act on loopback — that rule is the SSRF boundary and is not
relaxed to make a demo look tidier. A refused step printed live, marked `!`, is
the case this feature exists for.

Run it with ``python scripts/live/watch_a_run.py``. Exit status 0 means the run
completed and its steps arrived spread out over time rather than in a batch.
"""

from __future__ import annotations

import asyncio
import functools
import http.server
import json
import os
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from offsetx_apollo_builder.agent import AgentRun  # noqa: E402
from offsetx_apollo_builder.agent.watch import Progress  # noqa: E402
from offsetx_apollo_builder.ai.broker import WorkspaceEgressSettings  # noqa: E402
from offsetx_apollo_builder.ai.tiers import TrustTier  # noqa: E402
from offsetx_apollo_builder.browser.page import Page  # noqa: E402
from offsetx_apollo_builder.browser.session import free_port, open_session  # noqa: E402
from offsetx_apollo_builder.browser.trace import Trace  # noqa: E402

ADDRESS = "Acme Ltd, 14 Mill Road, Cambridge CB1 2AA"

#: Chrome refuses to run as root with its sandbox on, which is correct of it.
#: Root here means a container, and nowhere else does this flag get added.
EXTRA_FLAGS: tuple[str, ...] = ("--no-sandbox",) if os.geteuid() == 0 else ()


def serve() -> str:
    """A two-page site on a loopback port. Returns its base URL."""
    site = Path(tempfile.mkdtemp(prefix="watch-site-"))
    (site / "index.html").write_text(
        "<html><head><title>Contact Acme</title></head><body>"
        f"<h1>Acme</h1><p>Our office is at {ADDRESS}.</p>"
        "<a href='/opening-hours.html'>Opening hours</a></body></html>",
        encoding="utf-8",
    )
    (site / "opening-hours.html").write_text(
        "<html><head><title>Opening hours</title></head><body>"
        "<h1>Opening hours</h1><p>Weekdays, 9 to 5.</p></body></html>",
        encoding="utf-8",
    )

    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()

    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(site))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"serving {site} at http://127.0.0.1:{port}\n")
    return f"http://127.0.0.1:{port}"


class _Registry:
    def get(self, provider_id):
        model = SimpleNamespace(id="planner", cost_per_1m_input_usd=2.0,
                                cost_per_1m_output_usd=8.0)
        return SimpleNamespace(model=lambda model_id="": model)


class _Broker:
    """A model that always says the same things, so the run is reproducible."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.registry = _Registry()

    def plan(self, request, settings, *, provider_id=""):
        return [SimpleNamespace(id="trusted", model_id="planner",
                                tier=TrustTier.A, cost=1.0)], []

    def call(self, request, settings, *, system_prompt, provider_id="",
             expect_json=False):
        time.sleep(0.4)  # a real model call is not instant, and that is the point
        return SimpleNamespace(
            text=self.answers.pop(0), provider_id="trusted",
            provider_name="Trusted", model_id="planner", tier="A", policy="full",
            data_class=request.data_class.value, duration_ms=400,
            payload_fields=["instructions"], attempts=[], rejected=[], log_id="e1",
        )


def _act(action: str, **args) -> str:
    return json.dumps({"state": "act", "action": action, "args": args,
                       "reason": "step"})


async def main() -> int:
    base = serve()

    profile = Path(tempfile.mkdtemp(prefix="watch-profile-"))
    session = await open_session(profile_dir=str(profile), headless=True,
                                 port=free_port(), extra_flags=EXTRA_FLAGS)
    target_id, session_id = await session.new_tab(f"{base}/index.html")
    page = Page(connection=session.connection, session_id=session_id)
    await page.start()

    trace = Trace.open(Path(tempfile.mkdtemp(prefix="watch-trace-")) / "run")
    started = time.monotonic()
    stamps: list[float] = []

    def watch(update: Progress) -> None:
        stamps.append(time.monotonic() - started)
        print(f"t+{stamps[-1]:6.2f}s  {update.line()}", flush=True)

    agent = AgentRun(
        broker=_Broker([
            _act("read"),
            _act("click", handle=1),
            _act("read"),
            json.dumps({"state": "done", "reason": "the address was on the page",
                        "result": ADDRESS}),
        ]),
        settings=WorkspaceEgressSettings(
            workspace_id="live", enabled_models={"trusted": ("planner",)}),
        page=page, trace=trace, planner_provider_id="trusted",
    )
    try:
        outcome = await agent.run("find Acme's office address", step_budget=12,
                                  on_progress=watch)
    finally:
        await session.close_tab(target_id)
        await session.close(quit_browser=True)

    if not stamps:
        print("\nnothing reached the watcher at all.")
        return 1

    spread = max(stamps) - min(stamps)
    print(f"\nstatus       : {outcome.status}")
    print(f"result       : {outcome.result}")
    print(f"steps watched: {len(stamps)}")
    print(f"first at     : t+{min(stamps):.2f}s")
    print(f"last at      : t+{max(stamps):.2f}s")
    print(f"spread       : {spread:.2f}s  (0.00s would mean a batch at the end)")
    print(f"trace on disk: {sum(1 for _ in trace.read())} steps")
    return 0 if outcome.status == "completed" and spread > 0.5 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
