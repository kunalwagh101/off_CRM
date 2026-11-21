"""The locked frontend Vitest release must include its patched transitive mocker."""
import json
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def test_vitest_family_is_patched_and_integrity_pinned():
    manifest = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((FRONTEND / "package-lock.json").read_text(encoding="utf-8"))
    version = manifest["devDependencies"]["vitest"]
    assert tuple(int(part) for part in version.split(".")) >= (4, 1, 12)
    assert lock["packages"][""]["devDependencies"]["vitest"] == version

    packages = lock["packages"]
    family = [
        key for key in packages
        if key == "node_modules/vitest" or key.startswith("node_modules/@vitest/")
    ]
    assert len(family) >= 8
    assert "node_modules/@vitest/mocker" in family
    for key in family:
        entry = packages[key]
        assert entry["version"] == version, key
        assert entry["resolved"].startswith("https://registry.npmjs.org/"), key
        assert entry["resolved"].endswith(f"-{version}.tgz"), key
        assert entry["integrity"].startswith("sha512-"), key
