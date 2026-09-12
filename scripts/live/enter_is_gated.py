"""The live check for `S-11.03.03` — Enter in a real form, on a real browser.

Real: the browser, a real `<form>` with a real submit button, real focus, real
key events, and the page's own record of what it received. The page writes down
every submit it gets, so "nothing was sent" is answered by the page rather than
by the return value.

`D-25` was that `press` never asked the consequential-action gate anything. The
dangerous half of this fix is not the gating — it is *not* gating everything
else, so the four checks are two of each:

    0. with the gate waived, Enter really does submit the form
    1. Enter in a compose form is refused, and the form is not submitted
    2. Tab, the arrows and Escape are untouched
    3. Enter in a textarea is ordinary — it makes a newline, it cannot submit
    4. Enter in a search box is ordinary
    5. cleared by a countdown, Enter goes through and the form submits

Run it with ``python scripts/live/enter_is_gated.py``. Exit 0 means all six.
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

<form id="compose" onsubmit="log('COMPOSE SUBMITTED'); return false;">
  <input id="message" type="text" aria-label="Message">
  <button type="submit">Send</button>
</form>

<form id="notes" onsubmit="log('NOTES SUBMITTED'); return false;">
  <textarea id="longhand" aria-label="Notes"></textarea>
  <button type="submit">Send</button>
</form>

<form id="finder" onsubmit="log('SEARCHED'); return false;">
  <input id="q" type="text" aria-label="Search the site">
  <button type="submit">Search</button>
</form>

<p id="log">nothing happened</p>
<script>
function log(what) { document.getElementById('log').textContent = what; }
</script>
</body></html>"""


def _check(label: str, passed: bool, detail: str = "") -> bool:
    print(f"  [{'ok' if passed else 'NO'}] {label}{(' — ' + detail) if detail else ''}")
    return passed


async def _evaluate(page: Page, expression: str):
    got = await page.connection.send(
        "Runtime.evaluate", {"expression": expression, "returnByValue": True},
        session_id=page.session_id)
    return (got.get("result") or {}).get("value")


async def _focus(page: Page, element_id: str) -> None:
    await _evaluate(page, f"document.getElementById({element_id!r}).focus()")


async def _page_says(page: Page) -> str:
    return str(await _evaluate(page, "document.getElementById('log').textContent"))


async def _reset(page: Page) -> None:
    await _evaluate(page, "log('nothing happened')")


async def main() -> int:
    url = "data:text/html," + quote(PAGE)
    profile = Path(tempfile.mkdtemp(prefix="enter-profile-"))
    session = await open_session(profile_dir=str(profile), headless=True,
                                 port=free_port(), extra_flags=EXTRA_FLAGS)
    target_id, session_id = await session.new_tab(url)
    page = Page(connection=session.connection, session_id=session_id)
    await page.start()
    page.url = url
    # `new_tab` returns as soon as the target exists, not when the document has
    # parsed. Without this, `focus()` runs against a page with no elements in
    # it yet and silently does nothing — which reads exactly like a broken
    # gate, and cost half an hour of chasing the wrong thing.
    await asyncio.sleep(1.0)
    ok = True

    try:
        print("0. the hole this closes is real")
        await _focus(page, "message")
        ungated = await page.press("Enter", confirmed=True)
        says = await _page_says(page)
        ok &= _check("with the gate waived, Enter does submit the form",
                     ungated.ok and says == "COMPOSE SUBMITTED",
                     f"the page says {says!r}")
        await _reset(page)

        print("\n1. Enter in the compose form")
        await _focus(page, "message")
        result = await page.press("Enter")
        ok &= _check("refused and sent back to the owner",
                     not result.ok and result.needs_confirmation,
                     result.detail[:72])
        says = await _page_says(page)
        ok &= _check("the form was never submitted", says == "nothing happened",
                     f"the page says {says!r}")

        print("\n2. the keys that cannot submit anything")
        for key in ("Tab", "ArrowDown", "Escape"):
            result = await page.press(key)
            ok &= _check(f"{key} went straight through", result.ok,
                         result.detail)
        says = await _page_says(page)
        ok &= _check("and still nothing was submitted", says == "nothing happened",
                     f"the page says {says!r}")

        print("\n3. Enter in a textarea, next to a Send button")
        await _reset(page)
        await _focus(page, "longhand")
        result = await page.press("Enter")
        ok &= _check("not gated — Enter there makes a newline", result.ok,
                     result.detail)
        says = await _page_says(page)
        ok &= _check("and submitted nothing", says == "nothing happened",
                     f"the page says {says!r}")

        print("\n4. Enter in the search box")
        await _focus(page, "q")
        result = await page.press("Enter")
        ok &= _check("ordinary, no question asked", result.ok, result.detail)
        says = await _page_says(page)
        ok &= _check("and the search actually ran", says == "SEARCHED",
                     f"the page says {says!r}")

        print("\n5. Enter in the compose form, cleared by a countdown")
        await _reset(page)
        await _focus(page, "message")
        started = time.monotonic()
        result = await page.press("Enter", countdown=Countdown(seconds=1.0))
        elapsed = time.monotonic() - started
        ok &= _check("it waited", elapsed >= 1.0, f"{elapsed:.2f}s")
        ok &= _check("then went through", result.ok, result.detail)
        says = await _page_says(page)
        ok &= _check("and the form submitted", says == "COMPOSE SUBMITTED",
                     f"the page says {says!r}")
    finally:
        await session.close_tab(target_id)
        await session.close(quit_browser=True)

    print(f"\n{'all six held' if ok else 'SOMETHING DID NOT HOLD'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
