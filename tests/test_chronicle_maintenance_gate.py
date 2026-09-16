from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest

import editorial_desk.chronicle_backup as backup_module
from editorial_desk.chronicle_backup import (
    MAJOR_MAINTENANCE_OPERATIONS,
    BackupReceipt,
    ChronicleBackupError,
    require_prechange_backup,
    validate_chronicle_backup,
)


def _chronicle(tmp_path: Path) -> Path:
    root = tmp_path / "chronicle"
    (root / "registry").mkdir(parents=True)
    (root / "registry" / "identity.json").write_text("{}\n", encoding="utf-8")
    return root


def test_major_maintenance_operation_labels_are_protected():
    assert MAJOR_MAINTENANCE_OPERATIONS == frozenset(
        {
            "re-backfill",
            "registry-restructure",
            "bulk-correction",
            "storage-migration",
            "materializer-rewrite",
        }
    )
    assert "append-collection" not in MAJOR_MAINTENANCE_OPERATIONS


def test_successful_gate_emails_valid_backup_writes_receipt_then_runs_maintenance(tmp_path):
    root = _chronicle(tmp_path)
    archive = tmp_path / "prechange.zip"
    order = []
    sent_at = datetime(2026, 9, 16, 18, 30, tzinfo=timezone.utc)

    def send_backup(path: Path) -> None:
        order.append("send")
        assert path == archive
        assert validate_chronicle_backup(
            path, expected_revision="chronicle-sha-456"
        ).valid

    def maintenance() -> None:
        order.append("maintenance")

    receipt = require_prechange_backup(
        "bulk-correction",
        chronicle_root=root,
        backup_path=archive,
        chronicle_revision="chronicle-sha-456",
        send_backup=send_backup,
        maintenance_callback=maintenance,
        sent_at=sent_at,
    )

    assert isinstance(receipt, BackupReceipt)
    assert order == ["send", "maintenance"]
    assert receipt.operation == "bulk-correction"
    assert receipt.chronicle_revision == "chronicle-sha-456"
    assert receipt.archive_sha256 == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert receipt.sent_at == "2026-09-16T18:30:00+00:00"
    stored = json.loads(receipt.receipt_path.read_text())
    assert stored["operation"] == "bulk-correction"
    assert stored["chronicle_revision"] == "chronicle-sha-456"
    assert stored["archive_sha256"] == receipt.archive_sha256
    assert stored["sent_at"] == receipt.sent_at


def test_backup_creation_failure_prevents_send_receipt_and_maintenance(tmp_path, monkeypatch):
    root = _chronicle(tmp_path)
    calls = []

    def fail_build(*args, **kwargs):
        raise ChronicleBackupError("simulated build failure")

    monkeypatch.setattr(backup_module, "create_chronicle_backup", fail_build)

    with pytest.raises(ChronicleBackupError, match="simulated build failure"):
        require_prechange_backup(
            "re-backfill",
            chronicle_root=root,
            backup_path=tmp_path / "backup.zip",
            chronicle_revision="sha",
            send_backup=lambda path: calls.append("send"),
            maintenance_callback=lambda: calls.append("maintenance"),
        )

    assert calls == []
    assert not (root / "backup_receipts" / "prechange").exists()


def test_backup_validation_failure_prevents_email_receipt_and_maintenance(tmp_path, monkeypatch):
    root = _chronicle(tmp_path)
    archive = tmp_path / "backup.zip"
    calls = []

    def fake_build(*args, **kwargs):
        archive.write_bytes(b"not a valid zip")
        return archive

    monkeypatch.setattr(backup_module, "create_chronicle_backup", fake_build)

    with pytest.raises(ChronicleBackupError, match="validation failed"):
        require_prechange_backup(
            "storage-migration",
            chronicle_root=root,
            backup_path=archive,
            chronicle_revision="sha",
            send_backup=lambda path: calls.append("send"),
            maintenance_callback=lambda: calls.append("maintenance"),
        )

    assert calls == []
    assert not (root / "backup_receipts" / "prechange").exists()


def test_email_failure_prevents_receipt_and_maintenance(tmp_path):
    root = _chronicle(tmp_path)
    archive = tmp_path / "backup.zip"
    calls = []

    def fail_send(path: Path) -> None:
        calls.append("send")
        raise RuntimeError("simulated SMTP failure")

    with pytest.raises(RuntimeError, match="simulated SMTP failure"):
        require_prechange_backup(
            "materializer-rewrite",
            chronicle_root=root,
            backup_path=archive,
            chronicle_revision="sha",
            send_backup=fail_send,
            maintenance_callback=lambda: calls.append("maintenance"),
        )

    assert calls == ["send"]
    assert not (root / "backup_receipts" / "prechange").exists()


def test_unprotected_operation_is_rejected_before_any_backup_or_maintenance(tmp_path):
    root = _chronicle(tmp_path)
    calls = []

    with pytest.raises(ValueError, match="not a protected Chronicle maintenance operation"):
        require_prechange_backup(
            "append-collection",
            chronicle_root=root,
            backup_path=tmp_path / "backup.zip",
            chronicle_revision="sha",
            send_backup=lambda path: calls.append("send"),
            maintenance_callback=lambda: calls.append("maintenance"),
        )

    assert calls == []
