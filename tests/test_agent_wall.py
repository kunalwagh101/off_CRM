"""A wall the agent must not climb pauses the run and asks.  `S-11.03.01`

Three acceptance criteria, and the third one is a promise rather than a
behaviour: off_CRM **never** attempts to solve, evade or fingerprint around a
challenge. That was decided on 2026-09-06 and the test for it is the shape of
the module — it reports and stops, and has no code that could do anything else.

The rest is a detector that is allowed to **stop a run**, which `injection.py`
is deliberately not. So the false-positive tests come first in this file, and
they were written first: a detector that pauses on a marketing homepage with a
"Sign in" link in the header is worse than no detector, because the owner learns
to ignore it.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from offsetx_apollo_builder.agent import AgentRun
from offsetx_apollo_builder.agent.run import replay
from offsetx_apollo_builder.agent.wall import Wall, look
from offsetx_apollo_builder.ai.broker import WorkspaceEgressSettings
from offsetx_apollo_builder.ai.tiers import TrustTier
from offsetx_apollo_builder.browser.page import ActionResult
from offsetx_apollo_builder.browser.perceive import Node, Snapshot
from offsetx_apollo_builder.browser.trace import Step, Trace


def _page(url: str, title: str, *nodes: tuple[str, str]) -> Snapshot:
    """A snapshot from (role, name) pairs, numbered the way the real one is."""
    return Snapshot(
        url=url, title=title,
        nodes=[Node(handle=index, role=role, name=name)
               for index, (role, name) in enumerate(nodes, start=1)],
    )


# ── pages that must NOT pause a run ─────────────────────────────────────────


def test_a_marketing_page_with_a_sign_in_link_is_not_a_wall():
    """Every site on the web has this header. If it pauses, nothing works."""
    assert look(_page(
        "https://acme.test/", "Acme — software for teams",
        ("link", "Sign in"), ("link", "Start free trial"),
        ("heading", "Software for teams"),
        ("textbox", "Your work email"), ("button", "Get a demo"),
    )) is None


def test_a_help_article_about_two_factor_is_not_a_wall():
    """It says every 2FA phrase there is, and it has a search box."""
    assert look(_page(
        "https://acme.test/help/two-factor-authentication",
        "How two-factor authentication works",
        ("searchbox", "Search the help centre"),
        ("heading", "How two-factor authentication works"),
        ("StaticText", "Two-step verification protects your account."),
        ("link", "Turn on 2-factor authentication"),
    )) is None


def test_a_forgot_password_link_is_not_a_password_field():
    assert look(_page(
        "https://acme.test/pricing", "Pricing",
        ("link", "Forgot password?"), ("button", "Show password"),
        ("StaticText", "Password requirements"),
        ("textbox", "Coupon code please"),
    )) is None


def test_a_search_results_page_is_not_a_wall():
    assert look(_page(
        "https://acme.test/search?q=widgets", "Search",
        ("searchbox", "Search"), ("button", "Go"),
        ("link", "Widgets Ltd"), ("link", "Widget Co"),
    )) is None


def test_a_page_about_a_code_of_conduct_is_not_a_two_factor_prompt():
    """`code` counts only as the whole name of something you type into."""
    assert look(_page(
        "https://acme.test/community", "Community",
        ("heading", "Code of conduct"), ("link", "Read the code"),
        ("searchbox", "Search"),
    )) is None


def test_a_disabled_password_field_is_not_asking_for_anything():
    snapshot = _page("https://acme.test/settings", "Settings",
                     ("textbox", "Password"))
    snapshot.nodes[0].disabled = True
    assert look(snapshot) is None


# ── pages that must pause a run ─────────────────────────────────────────────


def test_a_sign_in_form_is_a_wall():
    wall = look(_page(
        "https://acme.test/login", "Sign in to Acme",
        ("textbox", "Email address"), ("textbox", "Password"),
        ("button", "Sign in"), ("link", "Forgot password?"),
    ))
    assert wall is not None
    assert wall.kind == "sign_in"
    assert wall.rule == "password_field"


def test_a_recaptcha_is_a_wall():
    wall = look(_page(
        "https://acme.test/results", "Results",
        ("checkbox", "I'm not a robot"), ("StaticText", "reCAPTCHA"),
    ))
    assert wall is not None
    assert wall.kind == "captcha"


def test_a_cloudflare_interstitial_with_no_named_nodes_is_a_wall():
    """It is a title and one line. Reading only named nodes would miss it."""
    wall = look(_page(
        "https://acme.test/", "Just a moment…",
        ("StaticText", "Checking your browser before accessing acme.test"),
    ))
    assert wall is not None
    assert wall.kind == "captcha"


def test_a_two_factor_prompt_is_a_wall_and_is_not_called_a_sign_in():
    """A 2FA page carries sign-in furniture too. Reporting it as a sign-in form
    sends the owner looking for the wrong thing."""
    wall = look(_page(
        "https://acme.test/login/challenge", "Verify it's you",
        ("StaticText", "Enter the code we sent to your phone"),
        ("textbox", "Verification code"), ("button", "Verify"),
        ("link", "Sign in a different way"),
    ))
    assert wall is not None
    assert wall.kind == "two_factor"


def test_a_passwordless_sign_in_page_is_still_a_wall():
    """No password field at all — an email box, a button and a login URL."""
    wall = look(_page(
        "https://acme.test/sessions/new", "Sign in",
        ("textbox", "Email address"), ("button", "Sign in"),
    ))
    assert wall is not None
    assert wall.kind == "sign_in"
    assert wall.rule == "sign_in_page"


def test_what_the_owner_is_told_names_the_wall_and_not_the_page():
    """The sentence is reused in the log, the report and any notification, so it
    must carry no page text — `trace.jsonl` never holds page content."""
    wall = Wall(kind="captcha", rule="challenge_widget",
                evidence="i'm not a robot", url="https://acme.test/")
    said = wall.describe()
    assert "CAPTCHA" in said
    assert "resume" in said
    assert "i'm not a robot" not in said


def test_nothing_in_this_module_could_solve_a_challenge():
    """The 2026-09-06 refusal, tested as the shape of the module rather than
    asserted in a comment.

    Not a search for suspicious words — prose is not evidence. This reads what
    the module *imports*: a snapshot and a regex engine. It holds no browser, no
    connection and no network client, so there is nothing here that could send,
    fetch, type or click even if a later edit wanted it to.
    """
    import ast
    from offsetx_apollo_builder.agent import wall as module

    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").lstrip("."))

    assert imported <= {"re", "dataclasses", "__future__", "browser.perceive"}, (
        f"wall.py reached for something that can act on the world: {imported}"
    )


# ── through a real run ──────────────────────────────────────────────────────


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
            raise AssertionError("the run asked for more decisions than were scripted")
        return SimpleNamespace(
            text=self.answers.pop(0), provider_id="trusted", provider_name="Trusted",
            model_id="planner", tier="A", policy="full",
            data_class=request.data_class.value, duration_ms=7,
            payload_fields=["instructions"], attempts=[], rejected=[], log_id="e1",
        )


class _Page:
    """A page that is a wall until somebody deals with it."""

    def __init__(self, pages):
        self.pages = list(pages)
        self.url = self.pages[0].url
        self.navigations = 0

    async def snapshot(self):
        current = self.pages[0]
        self.url = current.url
        return current

    def clear_the_wall(self):
        if len(self.pages) > 1:
            self.pages.pop(0)
        self.url = self.pages[0].url

    async def read(self, limit=20_000):
        return ActionResult(action="read", ok=True, url=self.url,
                            detail="read the page", text="the address is 14 Mill Road")

    async def goto(self, url):
        self.navigations += 1
        self.url = url
        return ActionResult(action="goto", ok=True, url=url, detail=f"opened {url}")


WALL = Snapshot(url="https://acme.test/login", title="Sign in",
                nodes=[Node(handle=1, role="textbox", name="Password"),
                       Node(handle=2, role="button", name="Sign in")])
OPEN = Snapshot(url="https://acme.test/contact", title="Contact",
                nodes=[Node(handle=1, role="heading", name="Contact us")])


def _act(action, **args):
    return json.dumps({"state": "act", "action": action, "args": args, "reason": "step"})


def _agent(trace, page, answers):
    return AgentRun(
        broker=_Broker(answers),
        settings=WorkspaceEgressSettings(workspace_id="w",
                                         enabled_models={"trusted": ("planner",)}),
        page=page, trace=trace, planner_provider_id="trusted",
    )


def test_a_wall_pauses_the_run_and_spends_nothing_deciding_what_to_do(tmp_path):
    trace = Trace.open(tmp_path / "t")
    page = _Page([WALL])
    agent = _agent(trace, page, [])

    outcome = asyncio.run(agent.run("find the address", step_budget=8))

    assert outcome.status == "needs_human"
    assert "sign-in" in outcome.message.lower()
    assert agent.broker.calls == 0, "a model was asked what to do about a locked door"
    assert outcome.decisions == 0


def test_the_browser_is_left_on_the_page_the_owner_has_to_deal_with(tmp_path):
    trace = Trace.open(tmp_path / "t")
    page = _Page([WALL])
    asyncio.run(_agent(trace, page, []).run("find the address", step_budget=8))

    assert page.url == WALL.url, "the run navigated away from the wall"
    assert page.navigations == 0


def test_the_pause_is_in_the_trace_without_putting_the_page_in_it(tmp_path):
    trace = Trace.open(tmp_path / "t")
    asyncio.run(_agent(trace, _Page([WALL]), []).run("find the address", step_budget=8))

    kinds = [step.kind for step in trace.read()]
    assert "needs_human" in kinds
    paused = next(step for step in trace.read() if step.kind == "needs_human")
    assert "sign_in" in paused.detail and "password_field" in paused.detail
    # The matched page text lives in the artefact beside the log, never in it.
    assert "Password" not in trace.path.read_text(encoding="utf-8")
    assert "password" in json.loads(trace.captured_text(paused))["evidence"].lower()


def test_the_owner_deals_with_it_and_the_run_carries_on_from_the_same_step(tmp_path):
    trace = Trace.open(tmp_path / "t")
    page = _Page([WALL, OPEN])
    paused = asyncio.run(_agent(trace, page, []).run("find the address", step_budget=8))
    assert paused.status == "needs_human"

    page.clear_the_wall()  # the person signs in, in the browser
    resumed = asyncio.run(
        _agent(trace, page, [_act("read"),
                             json.dumps({"state": "done", "reason": "found it",
                                         "result": "14 Mill Road"})]).resume()
    )

    assert resumed.status == "completed"
    assert resumed.result == "14 Mill Road"


def test_pausing_spends_no_budget_so_the_resumed_run_has_all_of_it(tmp_path):
    trace = Trace.open(tmp_path / "t")
    asyncio.run(_agent(trace, _Page([WALL]), []).run("find the address", step_budget=8))

    assert replay(trace).steps_remaining == 8


def test_a_run_that_meets_a_wall_halfway_keeps_what_it_already_found(tmp_path):
    trace = Trace.open(tmp_path / "t")
    page = _Page([OPEN, WALL])
    agent = _agent(trace, page, [_act("read")])

    def raise_the_wall():
        page.pages.pop(0)

    original = page.read

    async def read_then_wall(limit=20_000):
        result = await original(limit)
        raise_the_wall()
        return result

    page.read = read_then_wall
    outcome = asyncio.run(agent.run("find the address", step_budget=8,
                                    result_schema=["address"]))

    assert outcome.status == "needs_human"
    assert outcome.actions == 1, "the work done before the wall was thrown away"
