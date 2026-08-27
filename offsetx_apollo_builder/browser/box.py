"""The browser box: network yes, your files never.

`S-03.01.01`. The container the browser runs in, and the reason an agent holding
real logins is not a terrifying idea.

---

**Why this is not a second sandbox.** `ai/sandbox.py` already builds a hardened
container: read-only root, every capability dropped, no new privileges, runs as
nobody, memory and PID capped, and the CRM's databases and keys *not mounted at
all*. Every one of those flags is as right for a browser as for a code runner.
So this module composes that policy rather than duplicating it — two flag lists
would drift, and the one that drifts is the one that stops protecting anything.

Exactly two things differ from the code box:

**The network is on.** A browser with no network is a very slow way to render
`about:blank`. `SandboxPolicy.network` defaults to `none`, so this box has to
ask for `bridge` explicitly and the code box cannot acquire it by forgetting.

**The state that persists is a Docker named volume, not a host path.** The
profile has to survive a restart or you would sign in to LinkedIn every morning.
A bind mount would put your session cookies at a path on your disk, which is the
thing this box exists to avoid. A named volume is managed by Docker, has no
host path to traverse, and cannot be reached by a relative path out of the
container.

---

**Where the domain rule is actually enforced.** Not here. Docker filters by
address and the rule is about *names* — `--network=bridge` cannot express "only
linkedin.com". `browser/guard.py` enforces it inside the browser, per request,
before Chrome dispatches it.

That is worth being precise about rather than implying a kernel-level wall: the
container is what stops the browser reaching **your machine**, and the guard is
what stops it reaching **the wrong site**. The box runs one process, that process
is Chrome, and `--cap-drop=ALL` means nothing in it can open a raw socket to go
around Chrome's own network stack.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..ai.sandbox import (
    PolicyViolation,
    SandboxPolicy,
    sandbox_available,
    validate_image,
)

#: The image the box runs. Must already be present locally — `--pull=never` is
#: inherited from the sandbox policy, because a crafted image name would
#: otherwise be a way to make a network fetch happen.
DEFAULT_IMAGE = "offcrm/browser:1"

#: A browser is not a shell script. These are above the code box's defaults
#: because Chromium with a few tabs open genuinely needs them, and a box that
#: OOM-kills mid-login is worse than one that is a little generous.
BROWSER_MEMORY = "2g"
BROWSER_CPUS = "2"
BROWSER_PIDS = 512
#: Chromium's shared-memory needs. The classic symptom of leaving this at the
#: default is tabs crashing with no message on any page with images on it.
BROWSER_SHM = "512m"

#: Where the profile lives inside the container.
PROFILE_PATH = "/profile"

#: A Docker volume name: letters, digits, and the three punctuation marks Docker
#: itself allows. Validated because it reaches a command line.
VOLUME_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,127}$")

#: The workspace id itself, checked **before** the prefix is added.
#:
#: Checking only the prefixed name would be checking the prefix: every result
#: starts with `offcrm-`, so the "must begin with a letter or digit" rule would
#: never once fire. Found by a test that expected a leading dash to be refused
#: and watched it sail through.
WORKSPACE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def volume_for(workspace_id: str) -> str:
    """The profile volume for one workspace.

    One volume per workspace, never one shared: two people's session cookies in
    the same place is not a multi-user product, it is one account with two
    users. Refused rather than sanitised — a name that had to be cleaned up is a
    name somebody chose badly, and silently changing it makes two workspaces
    collide.
    """
    identifier = str(workspace_id or "").strip()
    if not WORKSPACE_ID.match(identifier):
        raise PolicyViolation(
            f"{workspace_id!r} does not make a usable volume name. A workspace id "
            "starts with a letter or a digit and then holds only letters, digits, "
            "dot, dash and underscore."
        )
    name = f"offcrm-browser-{identifier}"
    if not VOLUME_NAME.match(name):  # pragma: no cover - unreachable, kept as a belt
        raise PolicyViolation(f"{name!r} is not a usable Docker volume name.")
    return name


@dataclass(slots=True)
class BrowserProfile:
    """The browser's persistent state, and the only thing that survives a run.

    Deliberately shaped like `SandboxWorkspace` — `prepare()`, `mounts()`,
    `workdir` — so `SandboxPolicy.docker_command` can build the invocation for
    either without knowing which it has. Duck-typed rather than given a base
    class: one shared method name is not an inheritance hierarchy.
    """

    volume: str
    workdir: str = PROFILE_PATH

    def prepare(self) -> "BrowserProfile":
        """Nothing to create. Docker makes a named volume on first use.

        Present because the policy calls it, and an empty implementation that
        says why is better than a policy that has to know which kind of box it
        was handed.
        """
        if not VOLUME_NAME.match(self.volume):
            raise PolicyViolation(f"{self.volume!r} is not a usable Docker volume name.")
        return self

    def mounts(self) -> list[str]:
        """One mount, and it is not a host path.

        No `/inbox`, no `/work`, and — as with every box here — no store. The
        browser needs its own profile and nothing else off this machine.
        """
        return ["-v", f"{self.volume}:{PROFILE_PATH}"]


@dataclass(slots=True)
class BrowserBox:
    """A browser box: the policy, the profile, and the rules it runs under."""

    workspace_id: str = "local"
    image: str = DEFAULT_IMAGE
    #: Whether this run has a person watching it. Decides the allow-list rule —
    #: see `guard.py`. Recorded here because it is a property of the *box*, not
    #: of an individual request.
    unattended: bool = False
    #: Domains reachable when unattended. Empty plus unattended means the box can
    #: reach nothing, which is the correct default rather than a broken one.
    allowed_hosts: frozenset[str] = field(default_factory=frozenset)
    port: int = 9776

    @property
    def profile(self) -> BrowserProfile:
        return BrowserProfile(volume=volume_for(self.workspace_id))

    def policy(self) -> SandboxPolicy:
        """The container rules, composed from the hardened sandbox policy."""
        return SandboxPolicy(
            allowed_hosts=self.allowed_hosts,
            network="bridge",
            memory=BROWSER_MEMORY,
            cpus=BROWSER_CPUS,
            pids_limit=BROWSER_PIDS,
        )

    def command(self, *, chrome_args: tuple[str, ...] = ()) -> list[str]:
        """The full `docker run` invocation.

        The port is published on **127.0.0.1 only**. A DevTools port is remote
        control of a logged-in browser; bound to `0.0.0.0` it would be remote
        control of a logged-in browser *for the whole network*, and Docker's
        default publish behaviour is exactly that.
        """
        parts = self.policy().docker_command(
            image=validate_image(self.image),
            command=self._chrome(chrome_args),
            workspace=self.profile.prepare(),
        )
        # Inserted after `docker run` so the flags read in the order the sandbox
        # policy establishes them, with the browser's own additions grouped.
        extra = [
            "--shm-size", BROWSER_SHM,
            "-p", f"127.0.0.1:{int(self.port)}:{int(self.port)}",
        ]
        return parts[:2] + extra + parts[2:]

    def _chrome(self, extra: tuple[str, ...]) -> list[str]:
        """Chrome's own arguments.

        `--user-data-dir` is named explicitly even though it is the only profile
        in the container: Chrome refuses to open a debugging port on a *default*
        profile, a deliberate change that stopped malware reading cookies out of
        a running browser.
        """
        return [
            "chrome",
            f"--remote-debugging-port={int(self.port)}",
            # Without this the port is bound to the container's loopback, which
            # the published port cannot reach.
            "--remote-debugging-address=0.0.0.0",
            f"--user-data-dir={PROFILE_PATH}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-session-crashed-bubble",
            *extra,
        ]

    def describe(self) -> dict[str, Any]:
        """What the owner sees before anything starts.

        `unmounted` is the line that matters and it is stated positively: the
        databases, the keys and the egress log are not read-only inside this
        box, they are absent from its filesystem entirely.
        """
        available, reason = sandbox_available()
        return {
            "available": available,
            "blocked_reason": reason,
            "image": self.image,
            "network": "bridge",
            "unattended": self.unattended,
            "allowed_hosts": sorted(self.allowed_hosts),
            "profile_volume": self.profile.volume,
            "mounted": [f"{self.profile.volume} → {PROFILE_PATH} (a Docker volume, not a path on your disk)"],
            "unmounted": [
                "your home directory",
                "the CRM databases",
                "the encrypted keys",
                "the egress log",
                "every other path on this machine",
            ],
            "devtools_port": f"127.0.0.1:{self.port}",
            "runs_as": "65534:65534 (nobody)",
            "memory": BROWSER_MEMORY,
        }
