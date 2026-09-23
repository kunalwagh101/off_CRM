"""Every entry point opens the same CRM when nothing names one (D-127).

The web app's database follows OFFSETX_DATA_DIR, the one durable root a backup
covers. The two CLIs kept `local_data/offsetx_outreach.db`, so once the data
directory moved they opened a second, empty CRM beside the real one. The
container moved its data root too, and compose kept mounting the old one.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from offsetx_apollo_builder import notebook_cli, outreach_cli
from offsetx_apollo_builder.api.config import AppSettings

ROOT = Path(__file__).resolve().parents[1]


def _every_default(tmp_path: Path) -> set[Path]:
    return {
        AppSettings.from_env(tmp_path).database_path,
        Path(outreach_cli._parser().parse_args(["list-campaigns"]).db),
        Path(notebook_cli._parser().parse_args(["targets"]).db),
    }


def test_the_clis_open_the_web_apps_database_when_the_data_dir_moves(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OFFSETX_DATA_DIR", str(tmp_path / "durable"))
    monkeypatch.delenv("OFFSETX_OUTREACH_DB", raising=False)
    assert _every_default(tmp_path) == {(tmp_path / "durable" / "offsetx_outreach.db").resolve()}


def test_a_named_database_still_wins_everywhere(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OFFSETX_DATA_DIR", str(tmp_path / "durable"))
    monkeypatch.setenv("OFFSETX_OUTREACH_DB", "elsewhere/crm.db")
    assert _every_default(tmp_path) == {(tmp_path / "elsewhere" / "crm.db").resolve()}


def test_compose_mounts_the_host_folder_where_the_image_keeps_its_data():
    """Mounted at the old path, a restarted stack showed an empty CRM and kept
    new records in an unnamed volume that `down` then `up` does not reattach."""
    image_data = re.search(r"OFFSETX_DATA_DIR=(\S+)", (ROOT / "Dockerfile").read_text()).group(1)
    service = yaml.safe_load((ROOT / "docker-compose.yml").read_text())["services"]["offsetx"]
    mounts = dict(reversed(volume.split(":")[:2]) for volume in service["volumes"])
    assert mounts.get(image_data) == "./local_data"
    # The entrypoint takes ownership of the mount root only; here that must be
    # the bind-mounted folder, or a fresh one stays root-owned and unwritable.
    assert service["environment"]["OFFSETX_PERSISTENT_MOUNT"] == image_data
