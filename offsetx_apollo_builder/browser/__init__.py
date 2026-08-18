"""The browser agent: off_CRM's hands on the web.

Read `docs/architecture/BROWSER_AGENT_BLUEPRINT.md` first. The short version:
this drives *your* browser, against *your* profile, over the Chrome DevTools
Protocol — which gets the property a Chromium fork would buy (your cookies, your
SSO, your passkeys) without shipping a browser.
"""

from .cdp import CDPClosed, CDPError, CDPTimeout, connect
from .page import ACTIONS, ActionRefused, ActionResult, Page
from .perceive import Node, Snapshot, build, capture
from .policy import Refused, catalogue, check_action, check_navigation, rule_for
from .trace import Step, Trace
from .session import BrowserSession, BrowserUnavailable, find_browser, open_session, profile_hints

__all__ = [
    "ACTIONS", "ActionRefused", "ActionResult", "BrowserSession",
    "BrowserUnavailable", "CDPClosed", "CDPError", "CDPTimeout", "Node", "Page",
    "Refused", "Snapshot", "build", "capture", "catalogue", "check_action",
    "check_navigation", "connect", "find_browser", "open_session",
    "profile_hints", "rule_for", "Step", "Trace",
]
