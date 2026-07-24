from __future__ import annotations

import os
import shutil
import subprocess

import pytest

from offsetx_apollo_builder.off_ai.policy import SandboxPolicy


def test_networkless_container_cannot_reach_arbitrary_external_host(tmp_path):
    """Live wall test; enabled only when a pre-pulled Python image is supplied."""
    image = os.getenv("OFF_CRM_SANDBOX_TEST_IMAGE", "").strip()
    if not image:
        pytest.skip(
            "Set OFF_CRM_SANDBOX_TEST_IMAGE to a pre-pulled, version-pinned "
            "Python image for the live Docker egress test"
        )
    if not shutil.which("docker"):
        pytest.skip("Docker is not available")
    inspected = subprocess.run(
        ["docker", "image", "inspect", image],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    if inspected.returncode != 0:
        pytest.skip("The configured sandbox test image is not already present")

    command = SandboxPolicy.docker_command(
        image=image,
        source_dir=str(tmp_path),
        command=[
            "python",
            "-c",
            (
                "import socket; "
                "socket.create_connection(('example.com', 443), timeout=3); "
                "raise SystemExit('NETWORK_SHOULD_NOT_BE_REACHABLE')"
            ),
        ],
    )
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )

    assert completed.returncode != 0
    assert "NETWORK_SHOULD_NOT_BE_REACHABLE" not in completed.stderr
