from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.parse import urlparse

from ..outreach.models import to_utc_iso
from .policy import EgressPolicy, PolicyViolation, SandboxPolicy


GITHUB_REPOSITORY = re.compile(
    r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?$"
)
COMMIT_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
IMAGE_REFERENCE = re.compile(r"^[A-Za-z0-9./_-]+(?::[A-Za-z0-9._-]+|@sha256:[0-9a-f]{64})$")


class ToolError(RuntimeError):
    pass


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        temporary = Path(handle.name)
    os.replace(temporary, path)


class BringYourOwnToolRegistry:
    """Owner-controlled, public-input-only GitHub tools executed without network."""

    def __init__(self, root: Path | str, *, owner_domains: tuple[str, ...] = ()):
        self.root = Path(root)
        self.registry_path = self.root / "registry.json"
        self.run_log_path = self.root / "runs.jsonl"
        self.source_root = self.root / "sources"
        self._lock = threading.RLock()
        self.egress_policy = EgressPolicy(owner_domains=owner_domains)

    def _items(self) -> list[dict[str, Any]]:
        if not self.registry_path.exists():
            return []
        try:
            payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ToolError("Tool registry is invalid") from exc
        if not isinstance(payload, list):
            raise ToolError("Tool registry must contain a list")
        return [dict(item) for item in payload if isinstance(item, dict)]

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            items = self._items()
        items.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        return [self._public(item) for item in items]

    def get(self, tool_id: str, *, private: bool = False) -> dict[str, Any]:
        with self._lock:
            item = next(
                (entry for entry in self._items() if entry.get("id") == tool_id),
                None,
            )
        if not item:
            raise KeyError("Tool not found")
        return dict(item) if private else self._public(item)

    @staticmethod
    def _public(item: dict[str, Any]) -> dict[str, Any]:
        result = dict(item)
        result.pop("source_path", None)
        return result

    @staticmethod
    def _validated_repo_url(value: str) -> str:
        url = value.strip()
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "github.com"
            or not GITHUB_REPOSITORY.fullmatch(url)
        ):
            raise ValueError(
                "Use a public HTTPS GitHub repository URL with owner and repository"
            )
        return url

    @staticmethod
    def _validated_image(value: str) -> str:
        image = value.strip()
        if not IMAGE_REFERENCE.fullmatch(image):
            raise ValueError("Sandbox image must be an explicit tag or sha256 digest")
        if image.endswith(":latest") or ":" not in image and "@sha256:" not in image:
            raise ValueError("Sandbox image must be version-pinned; latest is not allowed")
        return image

    @staticmethod
    def _validated_command(command: list[str]) -> list[str]:
        result = [str(part) for part in command]
        if not result or len(result) > 40:
            raise ValueError("Tool command must contain 1 to 40 arguments")
        if any(not part or len(part) > 1000 or "\x00" in part for part in result):
            raise ValueError("Tool command contains an invalid argument")
        return result

    def register(
        self,
        *,
        name: str,
        repository_url: str,
        commit_sha: str,
        image: str,
        command: list[str],
        description: str = "",
    ) -> dict[str, Any]:
        repository_url = self._validated_repo_url(repository_url)
        commit_sha = commit_sha.strip().lower()
        if not COMMIT_SHA.fullmatch(commit_sha):
            raise ValueError("A full 40-character immutable Git commit SHA is required")
        image = self._validated_image(image)
        command = self._validated_command(command)
        name = name.strip()
        if not name:
            raise ValueError("Tool name is required")
        now = to_utc_iso()
        item = {
            "id": uuid.uuid4().hex,
            "name": name[:120],
            "description": description.strip()[:2000],
            "repository_url": repository_url,
            "commit_sha": commit_sha,
            "image": image,
            "command": command,
            "status": "registered",
            "network_policy": "none",
            "data_policy": "public_input_only",
            "source_path": "",
            "last_prepared_at": "",
            "last_run_at": "",
            "last_error": "",
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            items = self._items()
            items.append(item)
            _atomic_json(self.registry_path, items)
        return self._public(item)

    def _update(self, tool_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            items = self._items()
            index = next(
                (i for i, item in enumerate(items) if item.get("id") == tool_id),
                -1,
            )
            if index < 0:
                raise KeyError("Tool not found")
            items[index].update(changes)
            items[index]["updated_at"] = to_utc_iso()
            _atomic_json(self.registry_path, items)
            return dict(items[index])

    @staticmethod
    def _run_checked(
        command: list[str], *, cwd: Path | None = None, timeout: int = 120
    ) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                command,
                cwd=cwd,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={
                    **os.environ,
                    "GIT_TERMINAL_PROMPT": "0",
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_ASKPASS": os.devnull,
                    "GCM_INTERACTIVE": "Never",
                },
            )
        except FileNotFoundError as exc:
            raise ToolError(f"Required executable is unavailable: {command[0]}") from exc
        except subprocess.TimeoutExpired as exc:
            raise ToolError(f"Command timed out: {command[0]}") from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or str(exc))[-2000:]
            raise ToolError(detail) from exc

    def prepare(self, tool_id: str) -> dict[str, Any]:
        """Fetch one immutable public GitHub commit without credentials or submodules."""
        item = self.get(tool_id, private=True)
        destination = self.source_root / tool_id / item["commit_sha"]
        resolved_root = self.source_root.resolve()
        resolved_destination = destination.resolve()
        if resolved_root not in resolved_destination.parents:
            raise ToolError("Tool source path escaped its controlled root")
        if destination.exists():
            item = self._update(
                tool_id,
                {
                    "status": "prepared",
                    "source_path": str(destination),
                    "last_prepared_at": to_utc_iso(),
                    "last_error": "",
                },
            )
            return self._public(item)

        temporary = destination.parent / f".prepare-{uuid.uuid4().hex}"
        temporary.mkdir(parents=True, exist_ok=False)
        try:
            self._run_checked(["git", "init", "--quiet"], cwd=temporary)
            self._run_checked(
                [
                    "git",
                    "remote",
                    "add",
                    "origin",
                    str(item["repository_url"]),
                ],
                cwd=temporary,
            )
            self._run_checked(
                [
                    "git",
                    "-c",
                    "protocol.file.allow=never",
                    "fetch",
                    "--quiet",
                    "--depth=1",
                    "--no-tags",
                    "origin",
                    str(item["commit_sha"]),
                ],
                cwd=temporary,
                timeout=180,
            )
            self._run_checked(
                ["git", "checkout", "--quiet", "--detach", "FETCH_HEAD"],
                cwd=temporary,
            )
            resolved = self._run_checked(
                ["git", "rev-parse", "HEAD"], cwd=temporary
            ).stdout.strip().lower()
            if resolved != item["commit_sha"]:
                raise ToolError("Fetched commit does not match the pinned commit")
            shutil.rmtree(temporary / ".git")
            size = sum(
                path.stat().st_size
                for path in temporary.rglob("*")
                if path.is_file()
            )
            if size > 200 * 1024 * 1024:
                raise ToolError("Tool checkout exceeds the 200 MB safety limit")
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temporary, destination)
        except Exception as exc:
            if temporary.exists():
                shutil.rmtree(temporary)
            self._update(
                tool_id,
                {"status": "prepare_failed", "last_error": str(exc)[:2000]},
            )
            raise
        item = self._update(
            tool_id,
            {
                "status": "prepared",
                "source_path": str(destination),
                "last_prepared_at": to_utc_iso(),
                "last_error": "",
            },
        )
        return self._public(item)

    def execution_command(self, tool_id: str) -> list[str]:
        item = self.get(tool_id, private=True)
        if item.get("status") != "prepared" or not item.get("source_path"):
            raise ToolError("Prepare the pinned repository before running this tool")
        source = Path(str(item["source_path"])).resolve()
        if self.source_root.resolve() not in source.parents or not source.exists():
            raise ToolError("Prepared tool source is missing or outside its controlled root")
        return SandboxPolicy.docker_command(
            image=str(item["image"]),
            command=list(item["command"]),
            source_dir=str(source),
        )

    def execute(
        self, tool_id: str, *, public_input: str, timeout_seconds: int = 60
    ) -> dict[str, Any]:
        """Run a pinned checkout with no network, secrets, host writes, or CRM access."""
        scan = self.egress_policy.scan({"tool_public_input": public_input})
        if scan:
            raise PolicyViolation("Tool input blocked by pre-flight scan", reasons=scan)
        command = self.execution_command(tool_id)
        started = to_utc_iso()
        status = "succeeded"
        output = ""
        error = ""
        return_code = 0
        try:
            completed = subprocess.run(
                command,
                input=public_input,
                capture_output=True,
                text=True,
                timeout=max(1, min(int(timeout_seconds), 120)),
                check=False,
            )
            return_code = int(completed.returncode)
            output = (completed.stdout or "")[:1_000_000]
            error = (completed.stderr or "")[:100_000]
            if return_code != 0:
                status = "failed"
        except FileNotFoundError as exc:
            status = "failed"
            error = "Docker is not installed or not available to OFF_CRM"
            return_code = 127
            raise ToolError(error) from exc
        except subprocess.TimeoutExpired as exc:
            status = "failed"
            error = "Sandbox execution timed out"
            return_code = 124
            raise ToolError(error) from exc
        finally:
            record = {
                "id": uuid.uuid4().hex,
                "tool_id": tool_id,
                "status": status,
                "input_sha256": __import__("hashlib").sha256(
                    public_input.encode("utf-8")
                ).hexdigest(),
                "input_chars": len(public_input),
                "output_chars": len(output),
                "return_code": return_code,
                "error": error[-2000:],
                "started_at": started,
                "completed_at": to_utc_iso(),
            }
            self.run_log_path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock, self.run_log_path.open(
                "a", encoding="utf-8"
            ) as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            self._update(
                tool_id,
                {
                    "last_run_at": record["completed_at"],
                    "last_error": error[-2000:] if status == "failed" else "",
                },
            )
        return {
            "tool_id": tool_id,
            "status": status,
            "output": output,
            "error": error,
            "return_code": return_code,
            "network_policy": "none",
        }
