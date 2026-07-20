from pathlib import Path

from offsetx_apollo_builder.cli import main


def test_cli_empty_inbox_is_clean_noop(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code = main([
        "--enrich-existing-pois",
        "--dry-run",
        "--outdir", "out",
        "--run-id", "empty_cli",
        "--enrich-input-dir", "queue/inbox",
        "--processing-dir", "queue/processing",
        "--processed-dir", "queue/processed",
        "--failed-dir", "queue/failed",
        "--exclusion-dir", "old_pois",
    ])
    captured = capsys.readouterr().out
    assert code == 0
    assert "No enrichment run started" in captured
    assert "No Apollo API call was made" in captured
    assert "Traceback" not in captured


def test_cli_queue_status_creates_and_reports_folders(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code = main([
        "--queue-status",
        "--enrich-input-dir", "queue/inbox",
        "--processing-dir", "queue/processing",
        "--processed-dir", "queue/processed",
        "--failed-dir", "queue/failed",
    ])
    captured = capsys.readouterr().out
    assert code == 0
    assert "Inbox:" in captured
    assert "Processed:" in captured
    assert (tmp_path / "queue" / "inbox").exists()
