import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from editorial_desk.chronicle_backup import (
    ChronicleBackupError,
    create_chronicle_backup,
    restore_chronicle_backup,
    validate_chronicle_backup,
)


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _chronicle(tmp_path: Path) -> Path:
    root = tmp_path / "chronicle"
    _write(root / "registry" / "identity.json", '{"registry": 1}\n')
    _write(root / "coverage" / "historical_backfill.json", '{"complete": true}\n')
    _write(
        root / "leagues" / "ironbound_sixteen" / "events" / "2026.jsonl",
        '{"event_id":"a","schema_version":1}\n',
    )
    _write(
        root / "leagues" / "ironbound_sixteen" / "history" / "records.json",
        '{"records": {}}\n',
    )
    _write(
        root / "cross_league" / "nfl_player_events" / "2026.jsonl",
        '{"event_id":"nfl-a","schema_version":1}\n',
    )
    _write(root / "manifests" / "run-1.json", '{"status":"fresh"}\n')
    _write(root / "diagnostics" / "current_state" / "pulse.json", '{"temporary": true}\n')
    _write(root / "cache" / "source.json", '{"temporary": true}\n')
    _write(root / "tmp" / "scratch.txt", "temporary\n")
    return root


def _permanent_files(root: Path) -> dict[str, bytes]:
    excluded = {"diagnostics", "cache", "tmp", "backups", ".cache"}
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.relative_to(root).parts[0] not in excluded
    }


def test_backup_contains_permanent_chronicle_and_revision_manifest(tmp_path):
    root = _chronicle(tmp_path)
    archive = tmp_path / "backup.zip"

    create_chronicle_backup(
        root,
        archive,
        chronicle_revision="chronicle-sha-123",
        created_at="2026-09-16T18:00:00+00:00",
    )

    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
        manifest = json.loads(zf.read("BACKUP_MANIFEST.json"))

    expected = _permanent_files(root)
    assert set(expected) <= names
    assert "diagnostics/current_state/pulse.json" not in names
    assert "cache/source.json" not in names
    assert "tmp/scratch.txt" not in names
    assert manifest["chronicle_revision"] == "chronicle-sha-123"
    assert manifest["created_at"] == "2026-09-16T18:00:00+00:00"
    assert manifest["schema_versions"] == {
        "backup": 1,
        "chronicle_events": [1],
    }
    assert manifest["leagues"] == ["ironbound_sixteen"]
    assert manifest["seasons"] == ["2026"]
    assert manifest["event_counts"] == {
        "cross_league": 1,
        "leagues": {"ironbound_sixteen": 1},
        "total": 2,
    }
    assert manifest["validation_status"] == "validated"
    assert set(manifest["files"]) == set(expected)
    for name, payload in expected.items():
        assert manifest["files"][name]["sha256"] == hashlib.sha256(payload).hexdigest()
        assert manifest["files"][name]["size"] == len(payload)


def test_backup_validation_rejects_revision_mismatch_and_tampering(tmp_path):
    root = _chronicle(tmp_path)
    archive = create_chronicle_backup(
        root,
        tmp_path / "backup.zip",
        chronicle_revision="chronicle-sha-123",
    )

    good = validate_chronicle_backup(archive, expected_revision="chronicle-sha-123")
    assert good.valid is True
    assert good.errors == ()

    wrong_revision = validate_chronicle_backup(
        archive, expected_revision="chronicle-sha-other"
    )
    assert wrong_revision.valid is False
    assert any("revision" in error.lower() for error in wrong_revision.errors)

    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(archive) as source, zipfile.ZipFile(tampered, "w") as target:
        for info in source.infolist():
            payload = source.read(info.filename)
            if info.filename == "registry/identity.json":
                payload = b'{"registry":"tampered"}\n'
            target.writestr(info, payload)

    bad = validate_chronicle_backup(tampered, expected_revision="chronicle-sha-123")
    assert bad.valid is False
    assert any("checksum" in error.lower() for error in bad.errors)


def test_restore_validated_backup_reproduces_permanent_tree(tmp_path):
    root = _chronicle(tmp_path)
    archive = create_chronicle_backup(
        root,
        tmp_path / "backup.zip",
        chronicle_revision="chronicle-sha-123",
    )
    restored = tmp_path / "restored"

    written = restore_chronicle_backup(
        archive,
        restored,
        expected_revision="chronicle-sha-123",
    )

    expected = _permanent_files(root)
    actual = {
        path.relative_to(restored).as_posix(): path.read_bytes()
        for path in sorted(restored.rglob("*"))
        if path.is_file()
    }
    assert actual == expected
    assert {path.relative_to(restored).as_posix() for path in written} == set(expected)


def test_restore_refuses_invalid_archive_before_writing(tmp_path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr(
            "BACKUP_MANIFEST.json",
            json.dumps(
                {
                    "schema_version": 1,
                    "chronicle_revision": "x",
                    "files": {},
                    "schema_versions": {"backup": 1, "chronicle_events": []},
                    "leagues": [],
                    "seasons": [],
                    "event_counts": {"cross_league": 0, "leagues": {}, "total": 0},
                    "validation_status": "validated",
                }
            ),
        )
        zf.writestr("unexpected.json", "{}")

    destination = tmp_path / "restore"
    with pytest.raises(ChronicleBackupError):
        restore_chronicle_backup(archive, destination, expected_revision="x")
    assert not destination.exists()
