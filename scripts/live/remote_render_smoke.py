"""Non-destructive HTTPS smoke against a disposable Render CRM."""
from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class SmokeError(RuntimeError):
    """Live boundary failed its availability or auth contract."""


def _origin(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.hostname.endswith(".onrender.com")
        or parsed.hostname == ".onrender.com"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or parsed.netloc != parsed.hostname
    ):
        raise SmokeError("Supply only the exact HTTPS hostname of a Render QA service")
    return f"https://{parsed.hostname}"


def _request(base_url: str, path: str, *, method: str = "GET",
             data: bytes | None = None) -> tuple[int, dict[str, str], bytes]:
    headers = {"User-Agent": "off-crm-render-qa/1"}
    if data is not None:
        headers.update({"Content-Type": "application/json", "Origin": base_url})
    req = Request(base_url + path, data=data, method=method, headers=headers)
    try:
        with urlopen(req, timeout=30) as response:
            return (response.status,
                    {k.lower(): v for k, v in response.headers.items()},
                    response.read(16_384))
    except HTTPError as error:
        with error:
            return (error.code,
                    {k.lower(): v for k, v in error.headers.items()},
                    error.read(16_384))
    except (URLError, TimeoutError, OSError) as error:
        raise SmokeError(
            f"Render request {method} {path} failed ({type(error).__name__})"
        ) from None


def run_smoke(base_url: str) -> list[str]:
    origin = _origin(base_url)
    checks: list[str] = []
    code, _, body = _request(origin, "/")
    if code != 200 or b"<html" not in body.lower():
        raise SmokeError(f"CRM page failed: HTTP {code} or missing HTML")
    checks.append("root")

    code, _, _ = _request(origin, "/health/ready")
    if code != 200:
        raise SmokeError(f"Readiness failed: HTTP {code}")
    checks.append("ready")

    code, _, body = _request(origin, "/api/v1/auth/session")
    try:
        session = json.loads(body)
    except (ValueError, UnicodeDecodeError, TypeError):
        raise SmokeError("Anonymous session returned invalid JSON") from None
    if (
        code != 200
        or not isinstance(session, dict)
        or session.get("configured") is not True
        or session.get("authenticated") is not False
        or session.get("username") != ""
        or session.get("workspace_id") != ""
    ):
        raise SmokeError(f"Anonymous session contract failed: HTTP {code}")
    checks.append("anonymous_session")

    code, _, _ = _request(origin, "/api/v1/dashboard")
    if code != 401:
        raise SmokeError(f"Anonymous dashboard was not denied: HTTP {code}")
    checks.append("private_dashboard")

    body = json.dumps({
        "username": "unconfigured-qa-probe",
        "password": "not-a-valid-qa-password",
    }).encode()
    code, headers, _ = _request(
        origin, "/api/v1/auth/login", method="POST", data=body,
    )
    if code != 401 or "set-cookie" in headers:
        raise SmokeError(f"Invalid login was not safely denied: HTTP {code}")
    checks.append("wrong_login")
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args(argv)
    try:
        passed = run_smoke(args.base_url)
    except SmokeError as error:
        print(f"RENDER QA FAIL: {error}", file=sys.stderr)
        return 1
    print(f"RENDER QA PASS: {len(passed)} checks: {', '.join(passed)}")
    print("Not tested: authenticated UI, durable data, live providers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
