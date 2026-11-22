"""A26: verify that the *running production image* matches its locked extras.

Run inside the container after startup. Pure checks are also unit tested.
No provider traffic, credentials, or customer records are needed.
"""
from __future__ import annotations

import importlib
from importlib import metadata
from pathlib import Path
import re
import sys
from typing import Mapping


# Distribution name: imported module. These are the actual production wires,
# not just packages that happened to be available on the CI host.
REQUIRED = {
    "boto3": "boto3",                  # SES/mail integration
    "psycopg": "psycopg",              # hosted SQL
    "psycopg-binary": "psycopg_binary",  # usable libpq runtime
    "fastapi": "fastapi",              # API
    "uvicorn": "uvicorn",              # web process
}
DEV_ONLY = ("pytest", "ruff", "playwright")


class ContractError(RuntimeError):
    """A release image is missing or drifting from a locked dependency."""


def _lock_versions(contents: str) -> dict[str, set[str]]:
    """Read only the standard uv.lock [[package]] name/version records.

    Parsing minimal fields permits this standalone gate to run under all CI
    interpreters without introducing a TOML parser as a runtime dependency.
    """
    result: dict[str, set[str]] = {}
    blocks = re.split(r"(?m)^\[\[package\]\][ \t]*$", contents)
    for block in blocks[1:]:
        name = re.search(r'(?m)^name = "([^"]+)"[ \t]*$', block)
        version = re.search(r'(?m)^version = "([^"]+)"[ \t]*$', block)
        if name is None or version is None:
            raise ContractError("Malformed lock package record")
        result.setdefault(name.group(1), set()).add(version.group(1))
    if not result:
        raise ContractError("uv.lock has no package records")
    return result


def require_lock_parity(
    locked: Mapping[str, set[str]], installed: Mapping[str, str]
) -> int:
    for name in REQUIRED:
        versions = locked.get(name)
        if not versions:
            raise ContractError(f"{name} missing from uv.lock")
        actual = installed.get(name)
        if actual is None:
            raise ContractError(f"{name} missing from production image")
        if actual not in versions:
            raise ContractError(f"{name} installed version does not match uv.lock")
    return len(REQUIRED)


def require_no_dev_packages(installed: set[str]) -> None:
    for name in DEV_ONLY:
        if name in installed:
            raise ContractError(f"{name} developer tool unexpectedly installed in release image")


def check_image() -> int:
    root = Path(__file__).resolve().parents[2]
    if Path(sys.prefix).resolve() != (root / ".venv").resolve():
        raise ContractError("Production image must run its locked app virtualenv")
    try:
        contents = (root / "uv.lock").read_text(encoding="utf-8")
    except OSError as exc:
        raise ContractError("Production uv.lock is not readable") from exc
    locked = _lock_versions(contents)
    installed: dict[str, str] = {}
    for distribution, module in REQUIRED.items():
        try:
            installed[distribution] = metadata.version(distribution)
            importlib.import_module(module)
        except (metadata.PackageNotFoundError, ImportError, OSError) as exc:
            raise ContractError(f"Cannot load production dependency {distribution}") from exc
    count = require_lock_parity(locked, installed)
    present_dev: set[str] = set()
    for distribution in DEV_ONLY:
        try:
            metadata.version(distribution)
        except metadata.PackageNotFoundError:
            continue
        present_dev.add(distribution)
    require_no_dev_packages(present_dev)
    psycopg = importlib.import_module("psycopg")
    if psycopg.pq.__impl__ != "binary":
        raise ContractError("psycopg is not using the shipped binary libpq")
    return count


def main() -> int:
    try:
        count = check_image()
    except ContractError as exc:
        print(f"A26 FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"A26 PASS: {count} locked runtime distributions; binary SQL driver; no dev tools")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
