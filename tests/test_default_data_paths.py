"""Every entry point opens the same CRM when nothing names one (D-127).

The web app's database follows OFFSETX_DATA_DIR, the one durable root a backup
covers. The two CLIs kept `local_data/offsetx_outreach.db`, so once the data
directory moved they opened a second, empty CRM beside the real one. The
container moved its data root too, and compose kept mounting the old one.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from dotenv import dotenv_values

from offsetx_apollo_builder import db_cli, notebook_cli, outreach_cli
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


def _moved_data_dir(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OFFSETX_DATA_DIR", str(tmp_path / "durable"))
    for name in ("OFFSETX_OUTREACH_DB", "OFFSETX_GMAIL_TOKEN", "OFFSETX_DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)
    return (tmp_path / "durable").resolve()


def test_gmail_authorize_writes_the_token_where_the_web_app_reads_it(tmp_path, monkeypatch):
    """The CLI kept `local_data/gmail_token.json`, so a token authorised from
    the command line was one the web app never found (D-138)."""
    durable = _moved_data_dir(tmp_path, monkeypatch)
    written: list[Path] = []
    monkeypatch.setattr(
        outreach_cli,
        "authorize_interactive",
        lambda *, token_path, **_: written.append(Path(token_path)),
    )

    assert outreach_cli.main(["gmail-authorize", "--no-browser"]) == 0
    assert written == [AppSettings.from_env(tmp_path).gmail_token]
    assert written[0].parent == durable


def test_a_gmail_send_reads_the_token_where_the_web_app_reads_it(tmp_path, monkeypatch):
    durable = _moved_data_dir(tmp_path, monkeypatch)
    monkeypatch.setenv("OFFSETX_GMAIL_CLIENT_SECRETS", str(tmp_path / "client.json"))
    monkeypatch.setenv("OFFSETX_OWN_EMAIL", "owner@example.test")
    opened: list[Path] = []

    class Stop(Exception):
        """Raised before anything could be sent."""

    def provider(*, client_secrets_path, token_path):
        opened.append(Path(token_path))
        raise Stop

    monkeypatch.setattr(outreach_cli, "GmailMailProvider", provider)
    with pytest.raises(Stop):
        outreach_cli.main(["send", "c1", "--mode", "gmail", "--confirm", "SEND LIVE EMAILS"])
    assert opened == [durable / "gmail_token.json"]


def test_offsetx_db_checks_the_egress_log_the_web_app_writes(tmp_path, monkeypatch, capsys):
    """Its default stayed `local_data/ai_egress.db` (D-138)."""
    durable = _moved_data_dir(tmp_path, monkeypatch)

    assert db_cli.main(["check"]) == 0
    assert f"sqlite at {durable / 'ai_egress.db'}" in capsys.readouterr().out
    assert not (tmp_path / "local_data").exists()


def test_the_notebook_reads_the_web_apps_context_when_the_crm_lives_elsewhere(tmp_path, monkeypatch):
    """It looked beside the CRM database; the web app keeps the context in the
    data directory, so a bundle quietly lost its "what worked" part (D-141)."""
    durable = _moved_data_dir(tmp_path, monkeypatch)
    monkeypatch.setenv("OFFSETX_OUTREACH_DB", "elsewhere/crm.db")

    assert Path(notebook_cli._parser().parse_args(["targets"]).context) == durable / "ai_context.db"


def test_the_env_template_leaves_every_durable_path_to_the_data_dir(tmp_path, monkeypatch):
    """Copied to `.env`, the template pinned the CRM and the Gmail token to
    `local_data/`, so moving OFFSETX_DATA_DIR left both behind: production
    refused to start, and a local install's token fell out of the backup (D-140)."""
    durable = _moved_data_dir(tmp_path, monkeypatch)
    for key, value in dotenv_values(ROOT / ".env.example").items():
        if key != "OFFSETX_DATA_DIR" and value is not None:
            monkeypatch.setenv(key, value)

    settings = AppSettings.from_env(tmp_path)
    assert settings.database_path.parent == durable
    assert settings.gmail_token.parent == durable


def test_an_empty_gmail_token_setting_means_gmail_is_off_everywhere(tmp_path, monkeypatch):
    """The web app has always read an empty value as "Gmail is off"; the CLI
    says so rather than authorising a token the web app would never use."""
    _moved_data_dir(tmp_path, monkeypatch)
    monkeypatch.setenv("OFFSETX_GMAIL_TOKEN", "")
    monkeypatch.setattr(
        outreach_cli,
        "authorize_interactive",
        lambda **_: pytest.fail("authorised a token the web app would not read"),
    )

    assert AppSettings.from_env(tmp_path).gmail_token is None
    with pytest.raises(SystemExit, match="turns Gmail off"):
        outreach_cli.main(["gmail-authorize", "--no-browser"])


@pytest.fixture(autouse=True)
def _no_dotenv(monkeypatch):
    """`offsetx-outreach` loads `.env` into the process; a developer's own file
    must not decide what these tests see, nor leak into the tests after them."""
    monkeypatch.setattr(outreach_cli, "load_dotenv", lambda *args, **kwargs: False)
