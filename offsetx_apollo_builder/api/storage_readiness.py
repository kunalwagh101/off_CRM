"""Secret-safe, owner-only operator report of the app's real storage topology."""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import gettempdir
from typing import TYPE_CHECKING, Any

from ..db.connection import DATABASE_URL_ENV
from ..db.inventory import STORES

if TYPE_CHECKING:
    from .config import AppSettings


def _files_have_verified_mount(settings: AppSettings) -> bool:
    root = settings.persistent_mount
    if root is None or not root.is_mount():
        return False
    data = settings.data_dir.resolve()
    mount = root.resolve()
    # A container's OS root is a mount too, but it is not a separate durable
    # customer-data volume. Production also refuses temporary directories.
    if mount == Path("/"):
        return False
    temporary = (
        Path(gettempdir()).resolve(), Path("/tmp"), Path("/var/tmp"), Path("/dev/shm"),
    )
    if any(path == data or path in data.parents for path in temporary):
        return False
    return mount != data and mount in data.parents


def _hosted_database_store(description: str) -> bool:
    return "hosted database" in description or "follows `OFFSETX_DATABASE_URL`" in description


def describe_storage_readiness(settings: AppSettings) -> dict[str, Any]:
    """Inventory-derived classification, not proof of backup or production QA.

    No secret, hostname, database URL or filesystem path enters the result.
    Even a locally supplied SQLite test URL counts as a hosted *application
    topology*, not proof that a networked database survived a real restart.
    """
    hosted = bool(os.getenv(DATABASE_URL_ENV, "").strip())
    mounted = _files_have_verified_mount(settings)
    blockers: list[str] = []
    actions: list[str] = []

    if not mounted:
        blockers.append("ephemeral_customer_files")
        actions.append(
            "Attach a real mounted disk, set OFFSETX_PERSISTENT_MOUNT, "
            "and put OFFSETX_DATA_DIR in a subdirectory of that mount."
        )
    if hosted:
        # validate_storage intentionally refuses production with this mixed
        # topology until the external backups and remaining stores are solved.
        blockers.append("hosted_production_not_supported")
        actions.append(
            "Hosted database settings alone do not preserve all files. "
            "Resolve Q-29 / S-06.03.04 external backups and S-06.03.06 "
            "remaining store placement before enabling OFFSETX_PRODUCTION."
        )
        actions.append(
            "Keep OFFSETX_DATABASE_URL and OFFSETX_SECRETS_KEY together; "
            "do not put their values in reports or logs."
        )
    if settings.data_dir.resolve() not in settings.database_path.resolve().parents:
        blockers.append("local_crm_outside_data_root")
        actions.append("Place OFFSETX_OUTREACH_DB under OFFSETX_DATA_DIR.")

    stores = []
    for item in STORES:
        if hosted and _hosted_database_store(item.hosted) and not item.retains_hosted_files:
            durability = "hosted_database"
        elif item.name == "Operational logs":
            durability = "platform_retention_unverified"
        else:
            durability = "persistent_file" if mounted else "unverified_file"
        stores.append({"name": item.name, "durability": durability})

    if not blockers:
        actions.append(
            "The local disk layout meets startup constraints. "
            "Verify a complete backup and restore before production use."
        )

    return {
        "database": {"kind": "hosted" if hosted else "local"},
        "files": {"durability": "mounted" if mounted else "unverified"},
        "production": {
            "status": "blocked" if blockers else "storage_contract_met",
            "blockers": blockers,
        },
        "stores": stores,
        "actions": actions,
    }
