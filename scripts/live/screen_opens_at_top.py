"""Run S-06.02.25 through the real web entry point with disposable local data.

Build the frontend first. Install Playwright separately, or set PLAYWRIGHT_MODULE
to its module path. Optional CHROMIUM_EXECUTABLE_PATH / CHROMIUM_ARGS_JSON select
an installed Chromium. No provider calls, persistent credentials or hosted DB.

    uv run python scripts/live/screen_opens_at_top.py
"""
from __future__ import annotations

import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="offcrm-screen-top-") as directory:
        token = secrets.token_urlsafe(40)
        environment = os.environ.copy()
        environment.update(
            OFFSETX_DATA_DIR=directory,
            OFFSETX_OUTREACH_DB=str(Path(directory) / "crm.db"),
            OFFSETX_DATABASE_URL="",
            OFFSETX_SECRETS_KEY="",
            OFFSETX_GMAIL_TOKEN="",
            OFFSETX_GMAIL_CLIENT_SECRETS="",
            OFFSETX_OWN_EMAIL="",
            OFFSETX_LOCAL_API_TOKEN=token,
            OFFSETX_DEMO_USERNAME="",
            OFFSETX_DEMO_PASSWORD="",
            OFFSETX_PRODUCTION="0",
            OFFSETX_TEST_API_TOKEN=token,
            OFFSETX_TEST_BASE_URL=f"http://127.0.0.1:{port}",
            OFFSETX_ALLOWED_HOSTS="127.0.0.1,localhost",
        )
        # The local CLI prints its token. Keep server output out of the evidence.
        with subprocess.Popen(
            ["uv", "run", "python", "run_offsetx_web.py", "--host", "127.0.0.1", "--port", str(port)],
            cwd=root, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ) as server:
            try:
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    if server.poll() is not None:
                        raise RuntimeError("Disposable CRM server stopped before becoming ready")
                    try:
                        with urllib.request.urlopen(
                            f"http://127.0.0.1:{port}/health/live", timeout=1,
                        ):
                            break
                    except (urllib.error.URLError, TimeoutError):
                        time.sleep(0.1)
                else:
                    raise RuntimeError("Disposable CRM server did not become ready within 30 seconds")
                return subprocess.run(
                    ["node", "scripts/live/screen_opens_at_top.mjs"],
                    cwd=root, env=environment, check=False, timeout=180,
                ).returncode
            finally:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


if __name__ == "__main__":
    raise SystemExit(main())
