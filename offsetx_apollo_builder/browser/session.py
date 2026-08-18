"""Finding a browser, starting it against the owner's own profile, attaching.

This is the file that replaces a Chromium fork.

Strawberry ships a rebuilt browser so the agent runs inside your session. The
same property is available without the fork: start *your* Chrome, pointed at
*your* profile directory, with a debugging port open, and drive it over CDP. The
cookies are yours because it is your profile. The passkeys are yours because it
is your browser.

---

**Two honest constraints, both stated in the setup screen rather than hidden.**

*Chrome will not open a debugging port on the default profile.* A 2024 security
change: `--remote-debugging-port` is ignored unless `--user-data-dir` names a
path explicitly. That change exists because malware was reading cookies out of
running browsers, and it is a good change. The consequence here is that the
owner has to tell off_CRM where their profile is, once.

*Chrome allows one process per profile directory.* So a Chrome already open on
that profile has to be closed before off_CRM starts one. This module detects
that case and says so, rather than launching a second process that silently
opens a new empty profile — which is the failure that looks like "the agent is
not logged in to anything".

---

**Attach before launch, always.** If something is already listening on the port,
off_CRM uses it. Restarting a browser the owner is working in would be rude and
would lose their tabs.

**A profile is never copied.** Copying gives an agent a snapshot of your cookies
that lives somewhere else on disk, which is a security problem wearing a
convenience hat. This uses the real directory or it does not run.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .cdp import CDPConnection, connect

#: Where Chrome and its relatives usually are, per platform. Checked in order,
#: and the owner can always name a path instead.
BROWSER_CANDIDATES: dict[str, tuple[str, ...]] = {
    "darwin": (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    ),
    "win32": (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ),
    "linux": (
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/microsoft-edge",
        "/usr/bin/brave-browser",
    ),
}

#: Where each platform keeps a default Chrome profile. Offered as a suggestion
#: in the setup screen; never used without the owner choosing it, because
#: "off_CRM found your profile and started driving it" is not a thing software
#: should do on its own.
DEFAULT_PROFILE_HINTS: dict[str, tuple[str, ...]] = {
    "darwin": ("~/Library/Application Support/Google/Chrome",),
    "win32": (r"~\AppData\Local\Google\Chrome\User Data",),
    "linux": ("~/.config/google-chrome", "~/.config/chromium"),
}

#: The port off_CRM asks for. Not 9222: that is the documented default and
#: therefore the one every other tool on the machine also grabs.
DEFAULT_PORT = 9776

#: Flags off_CRM adds, and why each one is here.
LAUNCH_FLAGS = (
    # Chrome's first-run flow steals focus and blocks automation behind a modal.
    "--no-first-run",
    "--no-default-browser-check",
    # A crash bubble from a previous session sits on top of the page and every
    # click lands on it instead.
    "--disable-session-crashed-bubble",
    "--restore-last-session=false",
)


class BrowserUnavailable(RuntimeError):
    """No browser could be found, started or attached to. Carries what to do."""


def find_browser(explicit: str = "") -> str:
    """The browser to drive: the owner's choice, then the usual places.

    Chromium from a Playwright install is deliberately *last* — it is a real
    browser and it works, but it has none of the owner's logins, so a setup that
    silently picked it would produce an agent that cannot reach anything and no
    obvious reason why.
    """
    if explicit:
        if Path(explicit).exists():
            return explicit
        raise BrowserUnavailable(
            f"No browser at {explicit!r}. Point off_CRM at the Chrome, Edge, "
            "Brave or Chromium you actually use — the whole point is that it "
            "already has your logins."
        )
    for candidate in BROWSER_CANDIDATES.get(sys.platform, BROWSER_CANDIDATES["linux"]):
        if Path(candidate).exists():
            return candidate
    for name in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge"):
        found = shutil.which(name)
        if found:
            return found
    bundled = os.getenv("PLAYWRIGHT_BROWSERS_PATH", "")
    if bundled:
        for chrome in sorted(Path(bundled).glob("chromium-*/chrome-linux/chrome")):
            return str(chrome)
        for chrome in sorted(Path(bundled).glob("chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium")):
            return str(chrome)
    raise BrowserUnavailable(
        "No Chrome, Edge, Brave or Chromium found. Install one, or point "
        "off_CRM at the browser you use — it needs to be the one holding your "
        "logins, not a fresh copy."
    )


def profile_hints() -> list[str]:
    """Profile directories that exist on this machine, for the setup screen."""
    found: list[str] = []
    for hint in DEFAULT_PROFILE_HINTS.get(sys.platform, DEFAULT_PROFILE_HINTS["linux"]):
        path = Path(hint).expanduser()
        if path.exists():
            found.append(str(path))
    return found


def free_port() -> int:
    """A port nothing is using.

    Needed because the configured port can be taken by something that is *not*
    a browser — another tool, a leftover process, a test that has not finished
    shutting down. Attaching is only right when what is listening is a browser;
    anything else and off_CRM needs its own port rather than a confusing error.
    """
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def port_is_free(port: int) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", int(port)))
            return True
        except OSError:
            return False


def _version_url(port: int) -> str:
    return f"http://127.0.0.1:{int(port)}/json/version"


def probe(port: int, *, timeout: float = 1.0) -> dict[str, Any] | None:
    """Is a debuggable browser already listening? Returns its handshake or None.

    Tried before launching anything. A browser the owner is already working in
    is one off_CRM should join, not replace.
    """
    try:
        with urllib.request.urlopen(_version_url(port), timeout=timeout) as response:
            return json.loads(response.read() or b"{}")
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None


def profile_is_locked(profile_dir: Path) -> bool:
    """Whether a browser already has this profile open.

    Chrome writes a `SingletonLock` while a profile is in use. Launching a
    second process against it does not fail loudly — it hands off to the running
    one and exits, and off_CRM would then wait forever for a port that never
    opens. Detecting it here turns a hang into a sentence.
    """
    for name in ("SingletonLock", "SingletonSocket", "lockfile"):
        if (profile_dir / name).exists():
            return True
    return False


def _stop_tree(process: subprocess.Popen) -> None:
    """Stop a browser and everything it started.

    Chromium is not one process. It forks a zygote, a GPU process and a renderer
    per tab, and `Popen.terminate` signals only the one we hold. Because the
    browser is launched with ``start_new_session=True`` — so it survives off_CRM
    being interrupted — it is its own process-group leader, and signalling the
    *group* is what actually reaches the children.

    Found by counting `chrome` processes after a test run and getting thirteen.
    """
    if process.poll() is not None:
        return
    try:
        if hasattr(os, "killpg"):
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        else:  # Windows has no process groups in this sense
            process.terminate()
    except (ProcessLookupError, PermissionError, OSError):
        process.terminate()
    try:
        process.wait(timeout=10)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        if hasattr(os, "killpg"):
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        else:
            process.kill()
    except (ProcessLookupError, PermissionError, OSError):
        process.kill()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def _tail(log_path: str, lines: int = 3) -> str:
    """The last thing the browser said before it stopped."""
    try:
        content = Path(log_path).read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""
    if not content:
        return ""
    return " / ".join(content.splitlines()[-lines:])[:400]


def _why_it_died(code: int | None, log_path: str) -> str:
    """Turn an exit code into a sentence with a fix in it.

    Two failures account for almost all of them and neither is obvious from the
    code alone, so both are named rather than left for the owner to search.
    """
    detail = _tail(log_path)
    if "Running as root without --no-sandbox" in detail:
        return (
            "The browser refuses to run as root with its sandbox on, which is "
            "correct of it. This only happens in a container — pass "
            "extra_flags=('--no-sandbox',) if that is deliberate. Never do it "
            "on a machine somebody uses: the sandbox is what stops a page "
            "reaching the rest of the computer."
        )
    if "SingletonLock" in detail or "profile appears to be in use" in detail.lower():
        return (
            "Another browser already has that profile open. Chrome allows one "
            "process per profile; close it and try again."
        )
    return (
        f"The browser exited immediately (code {code}). "
        + (detail or "It said nothing about why.")
    )


@dataclass
class BrowserSession:
    """A live connection to a browser, and the tabs inside it."""

    connection: CDPConnection
    endpoint: str
    port: int
    #: The process off_CRM started, or None when it attached to a running one.
    #: Only what we launched is ever shut down.
    process: subprocess.Popen | None = None
    profile_dir: str = ""
    browser_path: str = ""
    version: dict[str, Any] = field(default_factory=dict)

    @property
    def launched_by_us(self) -> bool:
        return self.process is not None

    async def targets(self) -> list[dict[str, Any]]:
        """Every open tab, in the browser's own order."""
        result = await self.connection.send("Target.getTargets")
        return [
            target
            for target in result.get("targetInfos", [])
            if target.get("type") == "page"
        ]

    async def attach(self, target_id: str) -> str:
        """Attach to one tab and get the session id every later command needs.

        ``flatten`` is not optional in practice: without it the protocol wraps
        every message from the target in an envelope and half the client has to
        learn about it. With it a session id is just a field.
        """
        result = await self.connection.send(
            "Target.attachToTarget", {"targetId": target_id, "flatten": True}
        )
        return str(result["sessionId"])

    async def new_tab(self, url: str = "about:blank") -> tuple[str, str]:
        """Open a tab and attach to it. Returns ``(target_id, session_id)``."""
        created = await self.connection.send("Target.createTarget", {"url": url})
        target_id = str(created["targetId"])
        return target_id, await self.attach(target_id)

    async def close_tab(self, target_id: str) -> None:
        try:
            await self.connection.send("Target.closeTarget", {"targetId": target_id})
        except Exception:  # noqa: BLE001 - a tab the owner already closed is fine
            pass

    async def close(self, *, quit_browser: bool = False) -> None:
        """Let go.

        ``quit_browser`` only ever applies to a browser off_CRM started. Closing
        one the owner was working in would throw away their tabs, and no agent
        run is worth that.
        """
        await self.connection.close()
        if quit_browser and self.process is not None:
            _stop_tree(self.process)


async def open_session(
    *,
    profile_dir: str,
    browser_path: str = "",
    port: int = DEFAULT_PORT,
    headless: bool = False,
    extra_flags: tuple[str, ...] = (),
    launch_timeout: float = 30.0,
) -> BrowserSession:
    """Attach to a debuggable browser, starting one against ``profile_dir`` if
    there is not one already.

    The order is attach-then-launch on purpose. A browser already listening is
    one the owner may be using, and restarting it to gain control of it is the
    wrong trade every time.
    """
    existing = probe(port)
    if existing is not None:
        connection = await connect(str(existing["webSocketDebuggerUrl"]))
        return BrowserSession(
            connection=connection,
            endpoint=str(existing["webSocketDebuggerUrl"]),
            port=port,
            process=None,
            profile_dir=profile_dir,
            browser_path=str(existing.get("Browser") or ""),
            version=existing,
        )

    if not profile_dir:
        raise BrowserUnavailable(
            "No profile directory. off_CRM drives *your* browser session, so it "
            "needs to know where your profile lives — that is what makes it able "
            "to open a site you are already signed in to."
        )
    directory = Path(profile_dir).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    if profile_is_locked(directory):
        raise BrowserUnavailable(
            f"A browser already has {directory} open. Chrome allows one process "
            "per profile, and starting a second one would quietly open an empty "
            "profile with none of your logins in it. Close that browser and try "
            "again — off_CRM will reopen it with the same tabs it had."
        )

    # Something is on the port and it did not answer the DevTools handshake, so
    # it is not a browser. Launching against it would fail with a message about
    # a debugging port that says nothing about the real cause.
    if not port_is_free(port):
        port = free_port()

    executable = find_browser(browser_path)
    command = [
        executable,
        f"--remote-debugging-port={int(port)}",
        # Explicit even when it is the default path: Chrome refuses to open a
        # debugging port on the default profile unless the directory is named.
        f"--user-data-dir={directory}",
        *LAUNCH_FLAGS,
        *extra_flags,
    ]
    if headless:
        command.append("--headless=new")

    # Chrome's reason for refusing to start is on stderr and nowhere else, so
    # it is captured rather than discarded. "The browser exited immediately
    # (code 1)" is not a message anybody can act on; the line Chrome wrote is.
    log = tempfile.NamedTemporaryFile("w+", suffix=".log", delete=False)
    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=log,
        start_new_session=True,
    )

    handshake: dict[str, Any] | None = None
    deadline = asyncio.get_running_loop().time() + launch_timeout
    while asyncio.get_running_loop().time() < deadline:
        if process.poll() is not None:
            raise BrowserUnavailable(_why_it_died(process.returncode, log.name))
        handshake = probe(port)
        if handshake is not None:
            break
        await asyncio.sleep(0.15)

    if handshake is None:
        process.terminate()
        raise BrowserUnavailable(
            f"The browser started but never opened a debugging port on {port} "
            f"within {launch_timeout:.0f}s. "
            + _tail(log.name)
        )

    connection = await connect(str(handshake["webSocketDebuggerUrl"]))
    return BrowserSession(
        connection=connection,
        endpoint=str(handshake["webSocketDebuggerUrl"]),
        port=port,
        process=process,
        profile_dir=str(directory),
        browser_path=executable,
        version=handshake,
    )
