import json
from pathlib import Path

import pytest

from editorial_desk.chronicle_events import make_event
from editorial_desk.chronicle_store import ChronicleStore


def _event(*, league_key="demo", event_type="MATCHUP_FINAL"):
    return make_event(
        event_type=event_type,
        source="sleeper",
        source_ref=f"source:{league_key}:{event_type}",
        league_key=league_key,
        season="2026",
        week=1,
        provenance="source_exact",
        entities={"matchup_id": 7},
        observed_at="2026-09-15T12:00:00+00:00",
        evidence={"winner": 1, "loser": 2},
    )


def test_append_events_is_idempotent(tmp_path: Path):
    store = ChronicleStore(tmp_path)
    first = store.append_events([_event()])
    second = store.append_events([_event()])
    assert first.added == 1
    assert first.skipped == 0
    assert second.added == 0
    assert second.skipped == 1
    assert len(store.read_events("demo", "2026")) == 1


def test_cross_league_events_use_cross_league_stream(tmp_path: Path):
    store = ChronicleStore(tmp_path)
    event = make_event(
        event_type="PLAYER_STATUS_CHANGE",
        source="sleeper_players",
        source_ref="player:123:status",
        league_key=None,
        season="2026",
        week=1,
        provenance="observed_live",
        entities={"player_id": "123"},
        before={"status": "Questionable"},
        after={"status": "Out"},
        observed_at="2026-09-15T12:00:00+00:00",
        observed_before="2026-09-15T10:00:00+00:00",
        observed_after="2026-09-15T12:00:00+00:00",
    )
    store.append_events([event])
    assert (
        tmp_path / "cross_league" / "nfl_player_events" / "2026.jsonl"
    ).exists()
    assert len(store.read_events(None, "2026")) == 1


def test_atomic_write_keeps_previous_ledger_when_replace_fails(
    tmp_path: Path, monkeypatch
):
    store = ChronicleStore(tmp_path)
    store.append_events([_event()])
    path = tmp_path / "leagues" / "demo" / "events" / "2026.jsonl"
    before = path.read_bytes()

    def boom(src, dst):
        raise OSError("replace failed")

    monkeypatch.setattr("editorial_desk.chronicle_store.os.replace", boom)
    with pytest.raises(OSError, match="replace failed"):
        store.append_events([_event(event_type="TRADE")])
    assert path.read_bytes() == before


def test_current_state_manifest_and_coverage_round_trip(tmp_path: Path):
    store = ChronicleStore(tmp_path)
    store.write_current_state(
        "global_players",
        {"observed_at": "t1", "players": {"1": {"status": "Out"}}},
    )
    assert (
        store.read_current_state("global_players")["players"]["1"]["status"]
        == "Out"
    )

    manifest = {"run_id": "r1", "event_counts": {"added": 1}}
    manifest_path = store.write_manifest("r1", manifest)
    assert json.loads(manifest_path.read_text())["run_id"] == "r1"

    store.write_coverage({"player_health": {"first_success": "t1"}})
    assert store.read_coverage()["player_health"]["first_success"] == "t1"
