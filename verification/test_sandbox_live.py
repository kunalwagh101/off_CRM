"""Four original live Docker boundary cases from integration/main-consolidation.

Run explicitly on a disposable Docker-capable runner; missing infrastructure
is a failure, never a skip. Only a pre-pulled immutable test image is used.
"""
import json
from ipaddress import IPv4Address
import os
from pathlib import Path
import secrets
import subprocess
import tempfile

import pytest

from offsetx_apollo_builder.ai.sandbox import SandboxPolicy, SandboxWorkspace


def run(command, timeout=30):
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout)


def container(policy, workspace, source):
    image = os.environ["OFF_CRM_SANDBOX_TEST_IMAGE"]
    assert "@sha256:" in image, "The tested image must be immutable"
    # Code lives in a read-only input file, preserving the argument-size limit.
    (workspace.inbox / "probe.py").write_text(source)
    return run(policy.docker_command(
        image=image, workspace=workspace, command=["python", "/inbox/probe.py"],
    ))


@pytest.fixture
def workspace():
    # Match the real application's mkdir/umask behaviour, including ownership.
    with tempfile.TemporaryDirectory(prefix="offcrm-sandbox-") as folder:
        item = SandboxWorkspace(Path(folder) / "job").prepare()
        yield item


def test_sandbox_code_starts_as_unprivileged_user_with_caps_removed(workspace):
    result = container(SandboxPolicy(), workspace,
        "import os,json\nfrom pathlib import Path\n"
        "status=Path('/proc/self/status').read_text()\n"
        "fields=dict(line.split(':',1) for line in status.splitlines() if ':' in line)\n"
        "assert os.geteuid()==65534\nassert int(fields['CapEff'].strip(),16)==0\n"
        "assert fields['NoNewPrivs'].strip()=='1'\n"
        "print(json.dumps({'started':True,'uid':os.geteuid(),'caps':0,'no_new_privileges':True}))\n")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["started"] is True


def test_sandbox_work_directory_really_accepts_output(workspace):
    result = container(SandboxPolicy(), workspace,
        "from pathlib import Path\nPath('/work/result.txt').write_text('completed')\nprint('WROTE_OUTPUT')\n")
    assert result.returncode == 0, result.stderr
    assert (workspace.work / "result.txt").read_text() == "completed"


def test_sandbox_root_and_inbox_are_readonly_and_store_is_absent(workspace):
    workspace.store.mkdir()
    (workspace.store / "private-canary").write_text("synthetic-private-canary")
    result = container(SandboxPolicy(), workspace,
        "from pathlib import Path\n"
        "for path in ('/inbox/forbidden.txt','/forbidden.txt'):\n"
        " try:\n  Path(path).write_text('forbidden')\n"
        " except OSError:\n  pass\n"
        " else:\n  raise AssertionError('write unexpectedly allowed: '+path)\n"
        "assert not Path('/store').exists()\n"
        "assert not Path('/var/run/docker.sock').exists()\nprint('BOUNDARIES_VERIFIED')\n")
    assert result.returncode == 0, result.stderr
    assert "BOUNDARIES_VERIFIED" in result.stdout


def _bridge_ipv4(inspected):
    """Resolve the actual named bridge, not Docker's removed legacy field."""
    try:
        address = inspected['NetworkSettings']['Networks']['bridge']['IPAddress']
        return str(IPv4Address(address))
    except (KeyError, TypeError, ValueError) as exc:
        raise AssertionError('Docker positive control has no valid bridge IPv4 address') from exc


def test_sandbox_network_is_denied_with_a_working_positive_control(workspace):
    image = os.environ["OFF_CRM_SANDBOX_TEST_IMAGE"]
    name = "offcrm-network-probe-" + secrets.token_hex(5)
    started = run(["docker", "run", "--detach", "--rm", "--pull=never",
        "--name", name, "--network=bridge", "--read-only", "--cap-drop=ALL",
        "--security-opt=no-new-privileges", "--user=65534:65534", image,
        "python", "-m", "http.server", "9000"])
    assert started.returncode == 0, started.stderr
    try:
        inspected = run(["docker", "inspect", name])
        assert inspected.returncode == 0, inspected.stderr
        address = _bridge_ipv4(json.loads(inspected.stdout)[0])
        probe = (
            "import socket,time\n"
            "for attempt in range(20):\n"
            f" try:\n  s=socket.create_connection(({address!r},9000),timeout=1); s.close(); break\n"
            " except OSError:\n  time.sleep(.1)\n"
            "else:\n raise AssertionError('positive control cannot connect')\n"
            "print('CONNECTED')\n"
        )
        control = container(SandboxPolicy(network="bridge"), workspace, probe)
        assert control.returncode == 0, control.stderr
        assert "CONNECTED" in control.stdout
        denied = container(SandboxPolicy(), workspace,
            "import socket\nprint('PROBE_STARTED',flush=True)\n"
            f"try:\n socket.create_connection(({address!r},9000),timeout=3)\n"
            "except OSError as error:\n print('NETWORK_DENIED',type(error).__name__)\n"
            "else:\n raise AssertionError('network escaped')\n")
        assert denied.returncode == 0, denied.stderr
        assert "PROBE_STARTED" in denied.stdout and "NETWORK_DENIED" in denied.stdout
    finally:
        run(["docker", "rm", "--force", name])


