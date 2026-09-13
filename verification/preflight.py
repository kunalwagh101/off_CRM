"""Fail before testing if the services are absent; save exact runtime identity."""
import json
import os
from pathlib import Path
import platform
import subprocess

import psycopg

from offsetx_apollo_builder.ai.sandbox import sandbox_available
from offsetx_apollo_builder.browser.session import find_browser


def output(*args):
    return subprocess.check_output(args, text=True, timeout=30).strip()


def main():
    evidence = Path(os.environ["OFF_CRM_LIVE_EVIDENCE"])
    evidence.mkdir(parents=True, exist_ok=True)
    assert os.geteuid() != 0, "Run browser tests as an ordinary user with Chromium sandbox enabled"
    available, reason = sandbox_available()
    assert available, reason
    image = json.loads(output("docker", "image", "inspect", "python:3.12-slim"))[0]
    digest = image["RepoDigests"][0]
    # The sandbox runs the resolved immutable digest, with --pull=never.
    with open(os.environ["GITHUB_ENV"], "a") as handle:
        handle.write(f"OFF_CRM_SANDBOX_TEST_IMAGE={digest}\n")
    with psycopg.connect(os.environ["OFF_CRM_TEST_POSTGRES_URL"]) as connection:
        postgres_version = connection.execute("SELECT version()").fetchone()[0]
    result = {
        "commit": output("git", "rev-parse", "HEAD"),
        "application_baseline": "9f71f3c07f32407857311a1c4ed756925a612e6d",
        "python": platform.python_version(),
        "browser": output(find_browser(), "--version"),
        "uid": os.geteuid(),
        "docker": output("docker", "version", "--format", "{{.Server.Version}}"),
        "sandbox_image": digest,
        "postgres": postgres_version,
    }
    (evidence / "runtime.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
