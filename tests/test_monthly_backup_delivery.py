from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest

from editorial_desk.chronicle_backup import (
    create_chronicle_backup,
    is_first_tuesday,
    monthly_archive_due,
    monthly_receipt_path,
)
from editorial_desk.emailer import EmailDeliveryError, send_dossier_email


def _weekly_packet(root: Path, week: int = 1) -> None:
    publication = root / "2026" / f"week-{week:02d}" / "ironbound"
    publication.mkdir(parents=True)
    (publication / "dossier.md").write_text("# Weekly packet\n", encoding="utf-8")
    (publication / "dossier.json").write_text(
        json.dumps(
            {
                "season": "2026",
                "league": {
                    "league_key": "ironbound",
                    "configured_name": "Ironbound Sixteen",
                    "publication": "The Ironbound Weekly",
                },
            }
        ),
        encoding="utf-8",
    )


def _archive(tmp_path: Path, revision: str = "chronicle-sha-123") -> tuple[Path, Path]:
    chronicle = tmp_path / "chronicle"
    (chronicle / "registry").mkdir(parents=True)
    (chronicle / "registry" / "identity.json").write_text("{}\n", encoding="utf-8")
    archive = create_chronicle_backup(
        chronicle,
        tmp_path / "chronicle-2026-09.zip",
        chronicle_revision=revision,
        created_at="2026-09-01T15:55:00+00:00",
    )
    return chronicle, archive


def test_first_tuesday_is_evaluated_in_new_york_time():
    assert is_first_tuesday(datetime(2026, 9, 1, 12, tzinfo=timezone.utc)) is True
    assert is_first_tuesday(datetime(2026, 9, 8, 12, tzinfo=timezone.utc)) is False
    # 03:30 UTC on Sep 2 is still 23:30 EDT on Sep 1.
    assert is_first_tuesday(datetime(2026, 9, 2, 3, 30, tzinfo=timezone.utc)) is True
    # 04:30 UTC has crossed into Wednesday in New York.
    assert is_first_tuesday(datetime(2026, 9, 2, 4, 30, tzinfo=timezone.utc)) is False


def test_first_tuesday_rejects_naive_datetime():
    with pytest.raises(ValueError, match="timezone-aware"):
        is_first_tuesday(datetime(2026, 9, 1, 12))


def test_successful_monthly_delivery_writes_revision_checksum_and_acceptance_receipt(
    tmp_path, monkeypatch
):
    output = tmp_path / "output"
    _weekly_packet(output)
    chronicle, archive = _archive(tmp_path)
    accepted_at = datetime(2026, 9, 1, 16, 0, tzinfo=timezone.utc)
    deliveries = []

    monkeypatch.setattr(
        "editorial_desk.emailer._deliver",
        lambda message, sender, password: deliveries.append(message),
    )

    count = send_dossier_email(
        output,
        1,
        "desk@example.com",
        "app-password",
        "reader@example.com",
        extra_attachments=(archive,),
        monthly_receipt_root=chronicle,
        chronicle_revision="chronicle-sha-123",
        accepted_at=accepted_at,
    )

    assert count == 2
    assert len(deliveries) == 1
    receipt_path = monthly_receipt_path(chronicle, accepted_at)
    receipt = json.loads(receipt_path.read_text())
    assert receipt == {
        "archive_filename": "chronicle-2026-09.zip",
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "chronicle_revision": "chronicle-sha-123",
        "month": "2026-09",
        "smtp_accepted_at": "2026-09-01T16:00:00+00:00",
    }
    assert monthly_archive_due(chronicle, accepted_at) is False


def test_existing_monthly_receipt_makes_first_tuesday_archive_ineligible(tmp_path, monkeypatch):
    output = tmp_path / "output"
    _weekly_packet(output)
    chronicle, archive = _archive(tmp_path)
    accepted_at = datetime(2026, 9, 1, 16, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("editorial_desk.emailer._deliver", lambda *args: None)

    send_dossier_email(
        output,
        1,
        "desk@example.com",
        "app-password",
        "reader@example.com",
        extra_attachments=(archive,),
        monthly_receipt_root=chronicle,
        chronicle_revision="chronicle-sha-123",
        accepted_at=accepted_at,
    )

    assert monthly_archive_due(chronicle, accepted_at) is False


def test_smtp_failure_writes_no_receipt_and_retry_remains_due(tmp_path, monkeypatch):
    output = tmp_path / "output"
    _weekly_packet(output)
    chronicle, archive = _archive(tmp_path)
    accepted_at = datetime(2026, 9, 1, 16, 0, tzinfo=timezone.utc)

    def fail_delivery(*args):
        raise EmailDeliveryError("simulated SMTP failure")

    monkeypatch.setattr("editorial_desk.emailer._deliver", fail_delivery)

    with pytest.raises(EmailDeliveryError, match="simulated SMTP failure"):
        send_dossier_email(
            output,
            1,
            "desk@example.com",
            "app-password",
            "reader@example.com",
            extra_attachments=(archive,),
            monthly_receipt_root=chronicle,
            chronicle_revision="chronicle-sha-123",
            accepted_at=accepted_at,
        )

    assert not monthly_receipt_path(chronicle, accepted_at).exists()
    assert monthly_archive_due(chronicle, accepted_at) is True
