"""Exercise a safe recovery from an unsafe frontend dependency rollback.

Runs only in disposable CI with full Git history and npm registry access.
No customer/production workspace or checked-in package file is modified.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

# This immutable repository commit predates the audited @vitest/mocker fix.
LAST_UNSAFE_COMMIT = "0c28d7c9be64d24a67f846142c5ff1dd56f50af3"
MIN_SAFE_VITEST = (4, 1, 12)


def allowed_vitest_version(version: str) -> bool:
    """Never restore a package known to precede the mocker security fix."""
    if not isinstance(version, str):
        return False
    parts = version.split(".")
    if len(parts) != 3 or any(not x.isascii() or not x.isdecimal() for x in parts):
        return False
    return tuple(int(part) for part in parts) >= MIN_SAFE_VITEST


def _locked_vitest(manifest_bytes: bytes, lock_bytes: bytes) -> str:
    manifest = json.loads(manifest_bytes)
    lock = json.loads(lock_bytes)
    version = manifest["devDependencies"]["vitest"]
    if not allowed_vitest_version(version):
        raise ValueError("Refusing a known-unsafe or invalid Vitest release")
    if lock["packages"][""]["devDependencies"]["vitest"] != version:
        raise ValueError("Frontend manifest and lockfile are inconsistent")
    if lock["packages"]["node_modules/@vitest/mocker"]["version"] != version:
        raise ValueError("Frontend mocker is not pinned to the secure version")
    return version


def _git_original(repo: Path, path: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{LAST_UNSAFE_COMMIT}:{path}"],
        cwd=repo, check=True, capture_output=True, timeout=30,
    ).stdout


def _run(args: list[str], cwd: Path, *, timeout: int) -> str:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                            timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError(
            f"{' '.join(args[:2])} failed: "
            + (result.stderr or result.stdout).strip()[-700:]
        )
    return result.stdout


def main() -> int:
    repo = Path(__file__).resolve().parents[2]
    frontend = repo / "frontend"
    safe_manifest = (frontend / "package.json").read_bytes()
    safe_lock = (frontend / "package-lock.json").read_bytes()
    safe_version = _locked_vitest(safe_manifest, safe_lock)

    old_manifest = _git_original(repo, "frontend/package.json")
    old_lock = _git_original(repo, "frontend/package-lock.json")
    old_manifest_data = json.loads(old_manifest)
    old_lock_data = json.loads(old_lock)
    old_version = old_manifest_data["devDependencies"]["vitest"]
    if old_lock_data["packages"][""]["devDependencies"]["vitest"] != old_version:
        raise ValueError("Historical rollback pair is inconsistent")
    if allowed_vitest_version(old_version):
        raise ValueError("Historical fixture no longer represents an unsafe rollback")

    with TemporaryDirectory(prefix="offcrm-s16-recovery-") as directory:
        sandbox = Path(directory)
        (sandbox / "package.json").write_bytes(old_manifest)
        (sandbox / "package-lock.json").write_bytes(old_lock)
        # Refuse the old vulnerable graph before any package is installed.
        try:
            _locked_vitest(old_manifest, old_lock)
        except ValueError:
            pass
        else:
            raise AssertionError("Unsafe rollback was not rejected")

        # Restore the two safe files together, byte for byte.
        (sandbox / "package.json").write_bytes(safe_manifest)
        (sandbox / "package-lock.json").write_bytes(safe_lock)
        if ((sandbox / "package.json").read_bytes() != safe_manifest
                or (sandbox / "package-lock.json").read_bytes() != safe_lock):
            raise AssertionError("Safe locked pair did not restore byte-for-byte")
        assert _locked_vitest(safe_manifest, safe_lock) == safe_version
        _run(["npm", "ci", "--ignore-scripts", "--no-fund", "--no-audit"],
             sandbox, timeout=180)
        output = _run(["npm", "audit", "--json", "--audit-level=moderate"],
                      sandbox, timeout=90)
        results = json.loads(output)
        vulnerabilities = results.get("metadata", {}).get("vulnerabilities", {})
        if sum(int(v) for v in vulnerabilities.values()) != 0:
            raise AssertionError("Recovered dependency graph has vulnerabilities")

    print(f"S16 rollback drill PASS: refused {old_version}; restored {safe_version}; "
          "npm ci PASS; npm audit 0 vulnerabilities; disposable files removed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
