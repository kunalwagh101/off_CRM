"""Reliable file queue helpers for inbox -> processing -> processed/failed flows.

The queue intentionally archives source files rather than deleting them. Inbox files
are atomically moved into ``processing`` when claimed. Explicit/reused files are
copied into ``processing`` so the original archive remains intact.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SUPPORTED_INPUT_SUFFIXES = {".csv", ".xlsx", ".xls"}


@dataclass(frozen=True)
class QueuedInputFile:
    original_path: Path
    processing_path: Path
    processed_path: Path
    failed_path: Path
    source_preserved: bool = False


@dataclass(frozen=True)
class QueueStatus:
    inbox_files: tuple[Path, ...]
    processing_files: tuple[Path, ...]
    processed_files: tuple[Path, ...]
    failed_files: tuple[Path, ...]

    @property
    def latest_processed(self) -> Path | None:
        if not self.processed_files:
            return None
        return max(self.processed_files, key=lambda path: path.stat().st_mtime)


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ensure_queue_dirs(inbox_dir: Path, processing_dir: Path, processed_dir: Path, failed_dir: Path) -> None:
    for path in (inbox_dir, processing_dir, processed_dir, failed_dir):
        path.mkdir(parents=True, exist_ok=True)


def is_supported_input_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_INPUT_SUFFIXES and not path.name.startswith("~$")


def discover_input_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted((path for path in directory.iterdir() if is_supported_input_file(path)), key=lambda path: path.name.lower())


def inspect_queue(inbox_dir: Path, processing_dir: Path, processed_dir: Path, failed_dir: Path) -> QueueStatus:
    ensure_queue_dirs(inbox_dir, processing_dir, processed_dir, failed_dir)
    return QueueStatus(
        inbox_files=tuple(discover_input_files(inbox_dir)),
        processing_files=tuple(discover_input_files(processing_dir)),
        processed_files=tuple(discover_input_files(processed_dir)),
        failed_files=tuple(discover_input_files(failed_dir)),
    )


def latest_supported_file(directory: Path) -> Path | None:
    files = discover_input_files(directory)
    if not files:
        return None
    return max(files, key=lambda path: path.stat().st_mtime)


def _unique_destination(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    for i in range(1, 10_000):
        alt = directory / f"{stem}_{i}{suffix}"
        if not alt.exists():
            return alt
    raise RuntimeError(f"Could not allocate unique destination for {filename} in {directory}")


def claim_input_file(
    path: Path,
    *,
    processing_dir: Path,
    processed_dir: Path,
    failed_dir: Path,
    run_id: str,
    preserve_source: bool = False,
) -> QueuedInputFile:
    """Claim one input file for a run.

    ``preserve_source=False`` is used for normal inbox files and moves them out of
    the inbox, preventing a second worker from claiming the same file.

    ``preserve_source=True`` is used for explicit files or the
    ``--reuse-latest-processed`` workflow. It copies the source into processing so
    the archived original remains untouched.
    """
    path = path.expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Input file does not exist: {path}")
    if not is_supported_input_file(path):
        raise ValueError(f"Unsupported input file: {path}. Use CSV, XLSX, or XLS.")

    stamp = utc_stamp()
    safe_run_id = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in run_id)[:80]
    queued_name = f"{stamp}_{safe_run_id}_{path.name}"

    processing_path = _unique_destination(processing_dir, queued_name)
    processed_path = _unique_destination(processed_dir, queued_name)
    failed_path = _unique_destination(failed_dir, queued_name)

    processing_path.parent.mkdir(parents=True, exist_ok=True)
    if preserve_source:
        shutil.copy2(path, processing_path)
    else:
        shutil.move(str(path), str(processing_path))

    return QueuedInputFile(
        original_path=path,
        processing_path=processing_path,
        processed_path=processed_path,
        failed_path=failed_path,
        source_preserved=preserve_source,
    )


def archive_processed(queued: QueuedInputFile) -> Path:
    queued.processed_path.parent.mkdir(parents=True, exist_ok=True)
    if not queued.processing_path.exists():
        raise FileNotFoundError(f"Claimed processing file disappeared: {queued.processing_path}")
    shutil.move(str(queued.processing_path), str(queued.processed_path))
    return queued.processed_path


def archive_failed(queued: QueuedInputFile) -> Path:
    queued.failed_path.parent.mkdir(parents=True, exist_ok=True)
    if queued.processing_path.exists():
        shutil.move(str(queued.processing_path), str(queued.failed_path))
    return queued.failed_path
