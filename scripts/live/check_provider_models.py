"""Call every model a provider lists in config/providers.yaml, for real.

Why this exists: on 2026-11-13 ten of NVIDIA's eleven configured chat models,
the default among them, answered 410 Gone or 404 for a valid key (D-440). The
1,400+ unit tests were green the whole time, because every one of them uses a
stub provider. Only a real call shows that a vendor retired a model.

This is operator tooling, not product code: it never imports the broker or
`create_provider`, sends one fixed public sentence ("Reply with exactly the
word PONG.") and nothing from the CRM. The key is read with a hidden prompt,
or from the environment variable named by --key-env for CI. It is never
printed or written anywhere.

    uv run python scripts/live/check_provider_models.py nvidia
    uv run python scripts/live/check_provider_models.py nvidia --key-env NVIDIA_API_KEY

Exit code 0 when no listed model is gone, 1 when any is retired, missing or
erroring, 2 for a usage error. A model that does not answer in time is
reported as SLOW but does not fail the run: silence is not proof. Image models are reported but only probed with
--images, since one picture can take minutes.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PROMPT = "Reply with exactly the word PONG."


def _post(url: str, key: str, body: dict, timeout: float) -> tuple[int, str]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - https from config
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, f"{type(exc).__name__}: {exc}"


def _verdict(status: int, text: str) -> str:
    if status == 200:
        return "ok"
    if status == 410 or "end of life" in text.lower():
        return "RETIRED"
    if status == 404:
        return "NOT FOUND"
    if status == 0:
        return "SLOW"
    return f"HTTP {status}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("provider")
    parser.add_argument("--key-env", default="", help="read the key from this environment variable")
    parser.add_argument("--timeout", type=float, default=60.0, help="seconds per call (the broker uses 60)")
    parser.add_argument("--images", action="store_true", help="also generate one picture per image model")
    args = parser.parse_args(argv)

    document = yaml.safe_load((ROOT / "config" / "providers.yaml").read_text(encoding="utf-8"))
    entry = next((p for p in document["providers"] if p["id"] == args.provider), None)
    if entry is None:
        print(f"No provider {args.provider!r} in config/providers.yaml.", file=sys.stderr)
        return 2
    key = os.environ.get(args.key_env, "") if args.key_env else getpass.getpass(f"{entry['name']} key: ")
    if not key.strip():
        print("No key given; nothing was called.", file=sys.stderr)
        return 2

    failed = slow = 0
    default = entry.get("default_model", "")
    for model in entry.get("models", []):
        is_image = model.get("kind") == "image"
        options = dict(model.get("request_options") or {})
        if is_image and not args.images:
            print(f"  skip   {model['id']}  (image; pass --images)")
            continue
        started = time.monotonic()
        if is_image:
            url = options.pop("genai_url", "") or f"{entry['base_url']}/images/generations"
            status, text = _post(url, key, {"prompt": "a plain blue square", **options}, args.timeout)
        else:
            options.pop("max_tokens", None)
            body = {"model": model["id"], "messages": [{"role": "user", "content": PROMPT}], "max_tokens": 600, **options}
            status, text = _post(f"{entry['base_url']}/chat/completions", key, body, args.timeout)
        verdict = _verdict(status, text)
        # A timeout is not proof a model is gone (NVIDIA's free queue can take
        # minutes); a 410 or 404 is. Only proof fails the run.
        slow += verdict == "SLOW"
        failed += verdict not in ("ok", "SLOW")
        mark = " (default)" if model["id"] == default else ""
        print(f"  {verdict:<9} {time.monotonic() - started:6.1f}s  {model['id']}{mark}")
    if slow:
        print(f"{slow} model(s) gave no answer within {args.timeout:.0f}s: the app would time out and fail over.")
    print("No listed model is gone." if not failed else f"{failed} model(s) are gone or broken; fix config/providers.yaml.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
