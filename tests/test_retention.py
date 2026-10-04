from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from editorial_desk.cli import parser
from editorial_desk.retention import prune_diagnostics


def _write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_prune_diagnostics_removes_only_files_older_than_30_days(tmp_path):
    root = tmp_path / "chronicle"
    now = datetime(2026, 9, 16, 18, 0, tzinfo=timezone.utc)
    old = root / "diagnostics" / "current_state" / "old.json"
    boundary = root / "diagnostics" / "current_state" / "boundary.json"
    recent = root / "diagnostics" / "current_state" / "recent.json"
    _write_json(old, {"observed_at": "2026-08-16T17:59:59+00:00"})
    _write_json(boundary, {"observed_at": "2026-08-17T18:00:00+00:00"})
    _write_json(recent, {"observed_at": "2026-09-15T18:00:00+00:00"})

    result = prune_diagnostics(root, now, retention_days=30)

    assert result.removed == (old,)
    assert not old.exists()
    assert boundary.exists()
    assert recent.exists()
    assert set(result.kept) == {boundary, recent}


def test_prune_diagnostics_never_touches_permanent_chronicle_or_backup_receipts(tmp_path):
    root = tmp_path / "chronicle"
    now = datetime(2026, 9, 16, 18, 0, tzinfo=timezone.utc)
    permanent = [
        root / "leagues" / "ironbound" / "events" / "2026.jsonl",
        root / "leagues" / "ironbound" / "history" / "records.json",
        root / "registry" / "identity.json",
        root / "coverage" / "live_observation.json",
        root / "manifests" / "old-run.json",
        root / "backup_receipts" / "monthly" / "2026-08.json",
        root / "backup_receipts" / "prechange" / "old.json",
    ]
    for path in permanent:
        _write_json(path, {"observed_at": "2020-01-01T00:00:00+00:00"})
    old_diagnostic = root / "diagnostics" / "snapshots" / "old.json"
    _write_json(old_diagnostic, {"created_at": "2020-01-01T00:00:00+00:00"})

    result = prune_diagnostics(root, now)

    assert result.removed == (old_diagnostic,)
    assert all(path.exists() for path in permanent)


def test_unparseable_diagnostic_is_kept_for_safety(tmp_path):
    root = tmp_path / "chronicle"
    path = root / "diagnostics" / "mystery" / "unknown.json"
    _write_json(path, {"no_timestamp": True})

    result = prune_diagnostics(
        root,
        datetime(2026, 9, 16, 18, 0, tzinfo=timezone.utc),
    )

    assert path.exists()
    assert result.skipped_unparseable == (path,)


def test_prune_rejects_naive_now_and_invalid_retention(tmp_path):
    with pytest.raises(ValueError, match="timezone-aware"):
        prune_diagnostics(tmp_path, datetime(2026, 9, 16, 18, 0))
    with pytest.raises(ValueError, match="retention_days"):
        prune_diagnostics(
            tmp_path,
            datetime(2026, 9, 16, 18, 0, tzinfo=timezone.utc),
            retention_days=0,
        )


def test_cli_exposes_diagnostic_prune_command():
    args = parser().parse_args(
        [
            "chronicle-prune-diagnostics",
            "--chronicle-root",
            "chronicle-data",
            "--retention-days",
            "30",
        ]
    )
    assert args.chronicle_root == Path("chronicle-data")
    assert args.retention_days == 30
