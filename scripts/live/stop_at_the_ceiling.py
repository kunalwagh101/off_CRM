"""The live check for `S-11.01.04` — a real run stops at the money it agreed to.

Real: the browser, the page, the accessibility tree, the trace on disk, the
ceiling check, and the resume that reads the ceiling back off that trace.
Scripted: the model's decisions, priced so the arithmetic is checkable by hand.

It runs the whole story:

    1. a run with a $0.20 ceiling and decisions costing $0.05 each
    2. it makes four, and the fifth is never asked for
    3. resumed with no argument, it stops again — the ceiling survived
    4. resumed with the ceiling raised on purpose, it finishes

Run it with ``python scripts/live/stop_at_the_ceiling.py``. Exit 0 means all
four held.
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
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from offsetx_apollo_builder.agent import AgentRun  # noqa: E402
from offsetx_apollo_builder.agent.run import replay  # noqa: E402
from offsetx_apollo_builder.ai.broker import WorkspaceEgressSettings  # noqa: E402
from offsetx_apollo_builder.ai.tiers import TrustTier  # noqa: E402
from offsetx_apollo_builder.browser.page import Page  # noqa: E402
from offsetx_apollo_builder.browser.session import free_port, open_session  # noqa: E402
from offsetx_apollo_builder.browser.trace import Trace  # noqa: E402

#: Priced so one typical decision is exactly five cents, estimate and actual
#: agreeing:  (3000/1e6)*16 + (100/1e6)*20 = 0.048 + 0.002 = 0.05
PER_1M_IN, PER_1M_OUT = 16.0, 20.0
TOKENS_IN, TOKENS_OUT = 3_000, 100
PER_DECISION = 0.05
CEILING = 0.20

EXTRA_FLAGS: tuple[str, ...] = ("--no-sandbox",) if os.geteuid() == 0 else ()


def serve() -> str:
    site = Path(tempfile.mkdtemp(prefix="ceiling-site-"))
    (site / "index.html").write_text(
        "<html><head><title>Acme</title></head><body><h1>Acme</h1>"
        "<p>Our office is at 14 Mill Road, Cambridge.</p></body></html>",
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
    return f"http://127.0.0.1:{port}/index.html"


class _Registry:
    def get(self, provider_id):
        model = SimpleNamespace(id="planner", cost_per_1m_input_usd=PER_1M_IN,
                                cost_per_1m_output_usd=PER_1M_OUT)
        return SimpleNamespace(model=lambda model_id="": model)


class _Broker:
    def __init__(self, answers):
        self.answers = list(answers)
        self.registry = _Registry()
        self.calls = 0

    def plan(self, request, settings, *, provider_id=""):
        return [SimpleNamespace(id="trusted", model_id="planner",
                                tier=TrustTier.A, cost=1.0)], []

    def call(self, request, settings, *, system_prompt, provider_id="",
             expect_json=False):
        self.calls += 1
        if not self.answers:
            raise AssertionError("asked for a decision past the ceiling")
        return SimpleNamespace(
            text=self.answers.pop(0), provider_id="trusted",
            provider_name="Trusted", model_id="planner", tier="A", policy="full",
            data_class=request.data_class.value, duration_ms=7,
            payload_fields=["instructions"], attempts=[], rejected=[], log_id="e1",
            tokens_in=TOKENS_IN, tokens_out=TOKENS_OUT, cost_usd=PER_DECISION,
            usage_source="provider",
        )


def _read():
    return json.dumps({"state": "act", "action": "read", "args": {},
                       "reason": "look at the page"})


def _done():
    return json.dumps({"state": "done", "reason": "found it",
                       "result": "14 Mill Road, Cambridge"})


def _check(label: str, passed: bool, detail: str = "") -> bool:
    print(f"  [{'ok' if passed else 'NO'}] {label}{(' — ' + detail) if detail else ''}")
    return passed


async def main() -> int:
    url = serve()
    print(f"serving a real page at {url}")
    print(f"ceiling ${CEILING:.2f}, decisions ${PER_DECISION:.2f} each "
          f"→ four fit, the fifth does not\n")

    profile = Path(tempfile.mkdtemp(prefix="ceiling-profile-"))
    session = await open_session(profile_dir=str(profile), headless=True,
                                 port=free_port(), extra_flags=EXTRA_FLAGS)
    target_id, session_id = await session.new_tab(url)
    page = Page(connection=session.connection, session_id=session_id)
    await page.start()

    trace = Trace.open(Path(tempfile.mkdtemp(prefix="ceiling-trace-")) / "run")
    ok = True

    def agent(answers):
        return AgentRun(
            broker=_Broker(answers),
            settings=WorkspaceEgressSettings(
                workspace_id="live", enabled_models={"trusted": ("planner",)}),
            page=page, trace=trace, planner_provider_id="trusted",
        )

    try:
        print("1. the run spends up to its ceiling")
        first = agent([_read()] * 4)
        outcome = await first.run("find the office address", step_budget=30,
                                  spend_ceiling_usd=CEILING)
        ok &= _check("status is over_budget", outcome.status == "over_budget",
                     outcome.status)
        ok &= _check("it used the whole ceiling",
                     abs(outcome.spend_usd - CEILING) < 1e-9,
                     f"${outcome.spend_usd:.4f} of ${CEILING:.2f}")
        ok &= _check("four decisions, not three and not five",
                     outcome.decisions == 4, str(outcome.decisions))

        print("\n2. the decision that would have crossed was never asked for")
        ok &= _check("the model was called exactly four times",
                     first.broker.calls == 4, f"{first.broker.calls} calls")
        ok &= _check("so stopping cost nothing",
                     outcome.spend_usd <= CEILING,
                     f"${outcome.spend_usd:.4f} ≤ ${CEILING:.2f}")

        print("\n3. resumed with no argument, the ceiling is still there")
        ok &= _check("the trace remembers it",
                     abs(replay(trace).spend_ceiling_usd - CEILING) < 1e-9,
                     f"${replay(trace).spend_ceiling_usd:.4f}")
        second = agent([_done()])
        again = await second.resume()
        ok &= _check("it stops again rather than spending freely",
                     again.status == "over_budget", again.status)
        ok &= _check("without asking the model anything",
                     second.broker.calls == 0, f"{second.broker.calls} calls")

        print("\n4. raised on purpose, it carries on")
        third = agent([_done()])
        finished = await third.resume(spend_ceiling_usd=5.00)
        ok &= _check("it completes", finished.status == "completed", finished.status)
        ok &= _check("with the answer", "Mill Road" in (finished.result or ""),
                     finished.result or "")
        ok &= _check("and the run's whole spend is counted, not just this part",
                     finished.spend_usd > CEILING,
                     f"${finished.spend_usd:.4f} across the whole run")
    finally:
        await session.close_tab(target_id)
        await session.close(quit_browser=True)

    kinds = [step.kind for step in trace.read()]
    ok &= _check("one continuous trace", kinds.count("over_budget") == 2
                 and kinds[-1] == "completed", " → ".join(kinds[-6:]))

    print(f"\n{'all four held' if ok else 'SOMETHING DID NOT HOLD'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
