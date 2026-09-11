"""The live check for `S-11.03.01` — a real run meets a real wall and stops.

Real: the browser, the pages it is served, the accessibility tree the wall is
read out of, the trace on disk, the pause, and the resume that reads the trace
back. Scripted: the model's decisions, because a box with no provider
credentials cannot plan.

It runs the whole story end to end:

    1. the agent opens a portal that wants a password
    2. it stops, says what is in the way, and leaves the tab exactly there
    3. a person signs in — here, the server starts serving the page behind it
       and the tab is reloaded, the way a person would
    4. the run resumes and finishes, from the same step, with its full budget

Run it with ``python scripts/live/pause_at_a_wall.py``. Exit status 0 means all
four happened.
"""

from __future__ import annotations

import asyncio
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
from offsetx_apollo_builder.agent.run import replay  # noqa: E402
from offsetx_apollo_builder.ai.broker import WorkspaceEgressSettings  # noqa: E402
from offsetx_apollo_builder.ai.tiers import TrustTier  # noqa: E402
from offsetx_apollo_builder.browser.page import Page  # noqa: E402
from offsetx_apollo_builder.browser.session import free_port, open_session  # noqa: E402
from offsetx_apollo_builder.browser.trace import Trace  # noqa: E402

ADDRESS = "Acme Ltd, 14 Mill Road, Cambridge CB1 2AA"

#: Chrome refuses to run as root with its sandbox on, which is correct of it.
#: Root here means a container, and nowhere else does this flag get added.
EXTRA_FLAGS: tuple[str, ...] = ("--no-sandbox",) if os.geteuid() == 0 else ()

WALL = (
    "<html><head><title>Sign in to Acme</title></head><body>"
    "<h1>Sign in</h1>"
    "<label for='u'>Email address</label><input id='u' type='email'>"
    "<label for='p'>Password</label><input id='p' type='password'>"
    "<button>Sign in</button><a href='#'>Forgot password?</a>"
    "</body></html>"
)
BEHIND_IT = (
    "<html><head><title>Acme — office</title></head><body>"
    f"<h1>Office details</h1><p>Our office is at {ADDRESS}.</p>"
    "</body></html>"
)

#: Flipped by the "person" in step 3. The server is the login state.
signed_in = threading.Event()


def serve() -> str:
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = (BEHIND_IT if signed_in.is_set() else WALL).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{port}/portal"


class _Registry:
    def get(self, provider_id):
        model = SimpleNamespace(id="planner", cost_per_1m_input_usd=2.0,
                                cost_per_1m_output_usd=8.0)
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
            raise AssertionError("the run asked for a decision that was not scripted")
        return SimpleNamespace(
            text=self.answers.pop(0), provider_id="trusted",
            provider_name="Trusted", model_id="planner", tier="A", policy="full",
            data_class=request.data_class.value, duration_ms=7,
            payload_fields=["instructions"], attempts=[], rejected=[], log_id="e1",
        )


def _check(label: str, passed: bool, detail: str = "") -> bool:
    print(f"  [{'ok' if passed else 'NO'}] {label}{(' — ' + detail) if detail else ''}")
    return passed


async def main() -> int:
    url = serve()
    print(f"serving a sign-in wall at {url}\n")

    profile = Path(tempfile.mkdtemp(prefix="wall-profile-"))
    session = await open_session(profile_dir=str(profile), headless=True,
                                 port=free_port(), extra_flags=EXTRA_FLAGS)
    target_id, session_id = await session.new_tab(url)
    page = Page(connection=session.connection, session_id=session_id)
    await page.start()

    root = Path(tempfile.mkdtemp(prefix="wall-trace-"))
    trace = Trace.open(root / "run")
    ok = True
    try:
        broker = _Broker([])  # nothing scripted: a wall must cost no decision
        agent = AgentRun(
            broker=broker,
            settings=WorkspaceEgressSettings(
                workspace_id="live", enabled_models={"trusted": ("planner",)}),
            page=page, trace=trace, planner_provider_id="trusted",
        )
        paused = await agent.run("find Acme's office address", step_budget=10)

        print("1. the agent meets the wall")
        ok &= _check("status is needs_human", paused.status == "needs_human",
                     paused.status)
        ok &= _check("it names what is in the way", "sign-in" in paused.message.lower(),
                     paused.message.split(".")[0])
        ok &= _check("no model was asked what to do about it", broker.calls == 0,
                     f"{broker.calls} call(s)")
        ok &= _check("no budget was spent", replay(trace).steps_remaining == 10,
                     f"{replay(trace).steps_remaining} of 10 left")

        print("\n2. the browser is left where the person needs it")
        where = await session.connection.send(
            "Runtime.evaluate", {"expression": "location.href", "returnByValue": True},
            session_id=session_id)
        live_url = str(where.get("result", {}).get("value") or "")
        ok &= _check("the tab is still on the wall", live_url == url, live_url)
        ok &= _check("the page text stayed out of trace.jsonl",
                     "Password" not in trace.path.read_text(encoding="utf-8"))

        print("\n3. a person signs in, in the browser")
        signed_in.set()
        await session.connection.send("Page.reload", {"ignoreCache": True},
                                      session_id=session_id)
        await asyncio.sleep(1.0)

        print("\n4. the run resumes from the same step")
        resumed_agent = AgentRun(
            broker=_Broker([
                json.dumps({"state": "act", "action": "read", "args": {},
                            "reason": "read the page now it is reachable"}),
                json.dumps({"state": "done", "reason": "the address was on the page",
                            "result": ADDRESS}),
            ]),
            settings=WorkspaceEgressSettings(
                workspace_id="live", enabled_models={"trusted": ("planner",)}),
            page=page, trace=trace, planner_provider_id="trusted",
        )
        outcome = await resumed_agent.resume()
        ok &= _check("it completed", outcome.status == "completed", outcome.status)
        ok &= _check("with the answer that was behind the wall",
                     outcome.result == ADDRESS, outcome.result)

        kinds = [step.kind for step in trace.read()]
        ok &= _check("one continuous trace: paused, resumed, finished",
                     kinds.count("needs_human") == 1 and "resumed" in kinds
                     and kinds[-1] == "completed", " → ".join(kinds))
    finally:
        await session.close_tab(target_id)
        await session.close(quit_browser=True)

    print(f"\n{'all four steps happened' if ok else 'SOMETHING DID NOT HAPPEN'}")
    print(f"trace: {trace.path}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
