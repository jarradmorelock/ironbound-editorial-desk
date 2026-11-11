from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from editorial_desk.future_pick_audit import build_future_pick_report, build_future_pick_audit_email

NOW = datetime(2026, 11, 10, 20, 17, tzinfo=timezone.utc)


def _fixture(root: Path, *, status: str = "available") -> None:
    base = root / "2026" / "week-10"
    def ms(dt: str) -> int:
        return int(datetime.fromisoformat(dt).timestamp() * 1000)
    transaction = {
        "transaction_id": "101", "type": "trade", "status": "complete",
        "status_updated": ms("2026-11-09T10:00:00+00:00"),
        "draft_picks": [
            {"season": "2027", "round": 2, "roster_id": 1, "previous_owner_id": 2, "owner_id": 1},
            {"season": "2028", "round": 1, "roster_id": 2, "owner_id": 1},
            {"season": "2026", "round": 3, "roster_id": 2, "previous_owner_id": 2, "owner_id": 1},
        ],
    }
    old = {**transaction, "transaction_id": "100", "status_updated": ms("2026-10-15T10:00:00+00:00")}
    for league in ("ironbound_sixteen", "free_ironbound_sixteen"):
        folder = base / league
        folder.mkdir(parents=True)
        snapshot = {
            "nfl_state": {"season": "2026"},
            "users": [{"user_id": "alice", "display_name": "Alice"}, {"user_id": "bob", "display_name": "Bob"}],
            "rosters": [{"roster_id": 1, "owner_id": "alice"}, {"roster_id": 2, "owner_id": "bob"}],
            "traded_picks": [
                {"season": "2027", "round": 2, "roster_id": 1, "owner_id": 1, "previous_owner_id": 2},
                {"season": "2026", "round": 1, "roster_id": 2, "owner_id": 1},
            ],
            "flagship_sleeper": {"transactions": {
                "status": status,
                "weeks": {"10": [transaction, old, transaction] if league == "ironbound_sixteen" else []},
            }},
        }
        (folder / "snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")


def test_weekly_delta_distinguishes_original_and_previous_holder(tmp_path: Path) -> None:
    _fixture(tmp_path)
    report = build_future_pick_report(tmp_path, "2026", 10, as_of=NOW)
    assert len(report["transfers"]) == 2
    assert len(report["holdings"]) == 2
    first, second = report["transfers"]
    assert (first["original_team"], first["traded_by"], first["received_by"]) == ("Alice", "Bob", "Alice")
    assert second["verification"] == "Check missing prior holder"
    assert "Unknown" in second["traded_by"]
    assert all(int(row["pick_year"]) > 2026 for row in report["transfers"])
    email = build_future_pick_audit_email(report, "sender@example.com", "to@example.com")
    assert "Commissioner Audit" in email["Subject"]
    assert "2027 Round 2" in email.get_body(preferencelist=("plain",)).get_content()
    attachments = list(email.iter_attachments())
    assert len(attachments) == 2
    assert {item.get_filename() for item in attachments} == {
        "future-pick-transfers.csv", "future-pick-holdings.csv",
    }


def test_partial_transaction_collection_never_sends_false_empty_report(tmp_path: Path) -> None:
    _fixture(tmp_path, status="partial")
    with pytest.raises(ValueError, match="Incomplete transaction collection"):
        build_future_pick_report(tmp_path, "2026", 10, as_of=NOW)


def test_missing_league_snapshot_is_not_silently_skipped(tmp_path: Path) -> None:
    _fixture(tmp_path)
    (tmp_path / "2026" / "week-10" / "free_ironbound_sixteen" / "snapshot.json").unlink()
    with pytest.raises(ValueError, match="Missing or invalid audit snapshot"):
        build_future_pick_report(tmp_path, "2026", 10, as_of=NOW)
