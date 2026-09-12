"""The live check for `S-02.02.04` — a real click, held and then stopped.

Real: the browser, the page, the accessibility tree, the policy decision that
this button is consequential, the countdown, and the mouse events that do or do
not reach the page. The page records every click it receives in its own DOM, so
"nothing was sent" is answered by asking the page rather than by trusting the
return value.

The page is a `data:` URL, the way `tests/test_browser_signin.py` does it — the
loopback rule in `policy.py` refuses actions on 127.0.0.1, correctly, so a
served page cannot be clicked at all.

    1. a harmless link is clicked with no delay at all
    2. a Send button with the countdown cancelled — the page is untouched
    3. the same button with the countdown left alone — the click lands
    4. an unattended run is refused the countdown entirely

Run it with ``python scripts/live/cancel_the_countdown.py``. Exit 0 means all
four held.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from offsetx_apollo_builder.browser.countdown import Countdown  # noqa: E402
from offsetx_apollo_builder.browser.page import Page  # noqa: E402
from offsetx_apollo_builder.browser.session import free_port, open_session  # noqa: E402

EXTRA_FLAGS: tuple[str, ...] = ("--no-sandbox",) if os.geteuid() == 0 else ()

PAGE = """<html><head><title>Contact Acme</title></head><body>
<h1>Contact us</h1>
<a id="about" href="#about">About us</a>
<button id="send" onclick="document.title = 'SENT'">Send</button>
<p id="log">nothing sent</p>
<script>
document.getElementById('send').addEventListener('click', function () {
  document.getElementById('log').textContent = 'SENT';
});
</script>
</body></html>"""


def _check(label: str, passed: bool, detail: str = "") -> bool:
    print(f"  [{'ok' if passed else 'NO'}] {label}{(' — ' + detail) if detail else ''}")
    return passed


async def _page_says(page: Page) -> str:
    got = await page.connection.send(
        "Runtime.evaluate",
        {"expression": "document.getElementById('log').textContent",
         "returnByValue": True},
        session_id=page.session_id,
    )
    return str(got.get("result", {}).get("value") or "")


async def _handle_for(page: Page, name: str) -> int:
    snapshot = await page.snapshot()
    for node in snapshot.nodes:
        if node.name.strip().lower() == name.lower():
            return node.handle
    raise AssertionError(f"no {name!r} on the page: "
                         f"{[n.name for n in snapshot.nodes]}")


async def main() -> int:
    url = "data:text/html," + quote(PAGE)
    profile = Path(tempfile.mkdtemp(prefix="countdown-profile-"))
    session = await open_session(profile_dir=str(profile), headless=True,
                                 port=free_port(), extra_flags=EXTRA_FLAGS)
    target_id, session_id = await session.new_tab(url)
    page = Page(connection=session.connection, session_id=session_id)
    await page.start()
    page.url = url
    ok = True

    try:
        print("1. a harmless link does not wait for anything")
        about = await _handle_for(page, "About us")
        started = time.monotonic()
        result = await page.click(about, countdown=Countdown(seconds=5.0))
        elapsed = time.monotonic() - started
        ok &= _check("it clicked", result.ok, result.detail)
        # Every click pays `_settle`, about 1.5s, whether or not it is
        # sensitive. So the claim is "it did not wait the five seconds it was
        # offered", not "it was instant" — the offered countdown was ignored
        # because a link is not a consequential action.
        ok &= _check("the five-second countdown it was offered was not used",
                     elapsed < 5.0, f"{elapsed:.2f}s, against a 5.0s countdown")

        print("\n2. a Send button, with the countdown cancelled")
        send = await _handle_for(page, "Send")
        countdown = Countdown(seconds=30.0, label="Send the message")
        seen: list[int] = []
        countdown.on_tick = seen.append

        async def cancel_shortly():
            await asyncio.sleep(0.4)
            countdown.cancel("the owner reached for the button")

        asyncio.get_running_loop().create_task(cancel_shortly())
        started = time.monotonic()
        result = await page.click(send, countdown=countdown)
        elapsed = time.monotonic() - started

        ok &= _check("the click was refused", not result.ok, result.detail[:70])
        ok &= _check("promptly, not after 30 seconds", elapsed < 2.0, f"{elapsed:.2f}s")
        ok &= _check("the owner could see it counting", len(seen) >= 1,
                     f"ticks: {seen[:5]}")
        says = await _page_says(page)
        ok &= _check("and the page never heard a thing", says == "nothing sent",
                     f"the page says {says!r}")

        print("\n3. the same button, left alone")
        started = time.monotonic()
        result = await page.click(send, countdown=Countdown(seconds=1.0))
        elapsed = time.monotonic() - started
        ok &= _check("it waited", elapsed >= 1.0, f"{elapsed:.2f}s")
        ok &= _check("then clicked", result.ok, result.detail)
        says = await _page_says(page)
        ok &= _check("and the page got it", says == "SENT", f"the page says {says!r}")

        print("\n4. an unattended run cannot use a countdown at all")
        unattended = Page(connection=session.connection, session_id=session_id,
                          unattended=True)
        unattended.url = url
        await unattended.start()
        send = await _handle_for(unattended, "Send")
        result = await unattended.click(send, countdown=Countdown(seconds=0.1))
        ok &= _check("refused, and sent back to the owner",
                     not result.ok and result.needs_confirmation,
                     result.detail[:70])
    finally:
        await session.close_tab(target_id)
        await session.close(quit_browser=True)

    print(f"\n{'all four held' if ok else 'SOMETHING DID NOT HOLD'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
