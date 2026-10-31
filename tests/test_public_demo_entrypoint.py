"""The public service must boot the guarded web app, regardless of custom CMD."""
import importlib.util
import os
import sys
from pathlib import Path

import pytest


def load_entrypoint():
    spec = importlib.util.spec_from_file_location("container_entrypoint", Path("scripts/container_entrypoint.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_public_container_boots_guarded_web_app_and_keeps_signing_secret_private(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OFFSETX_PERSISTENT_MOUNT", str(tmp_path))
    monkeypatch.setenv("OFFSETX_PUBLIC_DEMO", "1")
    monkeypatch.delenv("OFFSETX_SESSION_SECRET", raising=False)
    monkeypatch.setattr(os, "getuid", lambda: 10001)
    monkeypatch.setattr(os, "chmod", lambda *args: None)
    monkeypatch.setattr(os, "umask", lambda *args: None)
    monkeypatch.setattr(sys, "argv", ["container_entrypoint.py", "python", "-c", '"custom command"'])
    captured = []
    monkeypatch.setattr(os, "execvp", lambda command, args: captured.append((command, args)))
    load_entrypoint().main()
    assert captured == [(sys.executable, [sys.executable, "run_offsetx_web.py"])]
    secret = os.environ["OFFSETX_SESSION_SECRET"]
    assert len(secret) >= 32
    assert secret not in capsys.readouterr().out


@pytest.mark.parametrize("public_mode", ["", "0", "false"])
def test_private_container_keeps_its_existing_command(tmp_path, monkeypatch, public_mode):
    monkeypatch.setenv("OFFSETX_PERSISTENT_MOUNT", str(tmp_path))
    monkeypatch.setenv("OFFSETX_PUBLIC_DEMO", public_mode)
    monkeypatch.setattr(os, "getuid", lambda: 10001)
    monkeypatch.setattr(os, "chmod", lambda *args: None)
    monkeypatch.setattr(os, "umask", lambda *args: None)
    monkeypatch.setattr(sys, "argv", ["container_entrypoint.py", "python", "custom_worker.py"])
    captured = []
    monkeypatch.setattr(os, "execvp", lambda command, args: captured.append((command, args)))
    load_entrypoint().main()
    assert captured == [("python", ["python", "custom_worker.py"])]
