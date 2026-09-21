import json
from pathlib import Path

import pytest

from editorial_desk.chronicle_queries import ChronicleQueries


def _write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


@pytest.fixture
def chronicle_root(tmp_path):
    root = tmp_path / "chronicle"
    history = root / "leagues" / "ironbound_sixteen" / "history"
    events = root / "leagues" / "ironbound_sixteen" / "events" / "2026.jsonl"
    player_events = root / "cross_league" / "nfl_player_events" / "2026.jsonl"

    _write_json(
        history / "head_to_head.json",
        {
            "head_to_head": [
                {
                    "identity_a": "franchise:a",
                    "identity_b": "franchise:b",
                    "wins_a": 2,
                    "wins_b": 1,
                    "ties": 0,
                    "games": 3,
                    "playoff_games": 1,
                    "current_streak_identity": "franchise:a",
                    "current_streak_length": 1,
                }
            ]
        },
    )
    _write_json(
        history / "matchups.json",
        {
            "matchups": [
                {
                    "event_id": "game-2025-playoff",
                    "season": "2025",
                    "week": 16,
                    "competition": "playoffs",
                    "left_identity": "franchise:a",
                    "right_identity": "franchise:b",
                    "winner_identity": "franchise:b",
                    "margin": 4.5,
                },
                {
                    "event_id": "game-2026-week1",
                    "season": "2026",
                    "week": 1,
                    "competition": "regular_season",
                    "left_identity": "franchise:a",
                    "right_identity": "franchise:b",
                    "winner_identity": "franchise:a",
                    "margin": 7.0,
                },
            ]
        },
    )
    _write_json(
        history / "records.json",
        {
            "records": {
                "franchise:a": {"games": 5, "wins": 4, "losses": 1},
                "franchise:b": {"games": 5, "wins": 2, "losses": 3},
            },
            "coverage": {
                "start_season": "2024",
                "complete": False,
                "warnings": ["2023 renewal link unavailable"],
            },
        },
    )
    _write_json(
        history / "seasons.json",
        {
            "seasons": {
                "2025:franchise:a": {
                    "season": "2025",
                    "identity": "franchise:a",
                    "wins": 8,
                    "losses": 6,
                },
                "2026:franchise:a": {
                    "season": "2026",
                    "identity": "franchise:a",
                    "wins": 1,
                    "losses": 0,
                },
                "2026:franchise:b": {
                    "season": "2026",
                    "identity": "franchise:b",
                    "wins": 0,
                    "losses": 1,
                },
            }
        },
    )
    _write_jsonl(
        events,
        [
            {
                "event_id": "old-trade",
                "event_type": "TRADE",
                "league_key": "ironbound_sixteen",
                "season": "2026",
                "week": 1,
                "observed_at": "2026-09-15T16:00:00+00:00",
                "occurred_at": "2026-09-15T15:55:00+00:00",
                "source": "sleeper_transactions",
                "source_ref": "transaction:old",
                "entities": {"player_id": "p1", "roster_ids": [1, 2]},
                "evidence": {"adds": {"p1": 1}},
            },
            {
                "event_id": "new-waiver",
                "event_type": "WAIVER_ADD",
                "league_key": "ironbound_sixteen",
                "season": "2026",
                "week": 2,
                "observed_at": "2026-09-16T13:00:00+00:00",
                "occurred_at": "2026-09-16T12:58:00+00:00",
                "source": "sleeper_transactions",
                "source_ref": "transaction:new:add:p1",
                "entities": {"player_id": "p1", "roster_id": 1},
                "evidence": {"adds": {"p1": 1}},
            },
            {
                "event_id": "new-drop",
                "event_type": "DROP",
                "league_key": "ironbound_sixteen",
                "season": "2026",
                "week": 2,
                "observed_at": "2026-09-16T13:00:00+00:00",
                "occurred_at": "2026-09-16T12:58:00+00:00",
                "source": "sleeper_transactions",
                "source_ref": "transaction:new:drop:p2",
                "entities": {"player_id": "p2", "roster_id": 1},
                "evidence": {"drops": {"p2": 1}},
            },
        ],
    )
    _write_jsonl(
        player_events,
        [
            {
                "event_id": "status-p1",
                "event_type": "PLAYER_STATUS_CHANGE",
                "league_key": None,
                "season": "2026",
                "week": 2,
                "observed_at": "2026-09-16T12:30:00+00:00",
                "source": "sleeper_players",
                "source_ref": "player:p1:status",
                "entities": {"player_id": "p1"},
                "before": {"injury_status": "Questionable"},
                "after": {"injury_status": "Out"},
                "evidence": {},
            },
            {
                "event_id": "status-p2",
                "event_type": "PLAYER_STATUS_CHANGE",
                "league_key": None,
                "season": "2026",
                "week": 2,
                "observed_at": "2026-09-16T12:45:00+00:00",
                "source": "sleeper_players",
                "source_ref": "player:p2:status",
                "entities": {"player_id": "p2"},
                "evidence": {},
            },
        ],
    )
    return root


def test_head_to_head_preserves_materialized_series_playoff_meetings_and_coverage(chronicle_root):
    query = ChronicleQueries(chronicle_root)

    result = query.head_to_head("ironbound_sixteen", "franchise:b", "franchise:a")

    assert result["series"] == {
        "identity_a": "franchise:a",
        "identity_b": "franchise:b",
        "wins_a": 2,
        "wins_b": 1,
        "ties": 0,
        "games": 3,
        "playoff_games": 1,
        "current_streak_identity": "franchise:a",
        "current_streak_length": 1,
    }
    assert [row["event_id"] for row in result["playoff_meetings"]] == ["game-2025-playoff"]
    assert result["coverage_complete"] is False
    assert result["coverage_warnings"] == ["2023 renewal link unavailable"]


def test_current_streak_is_exact_materialized_streak_with_coverage(chronicle_root):
    result = ChronicleQueries(chronicle_root).current_streak(
        "ironbound_sixteen", "franchise:a", "franchise:b"
    )

    assert result == {
        "identity": "franchise:a",
        "length": 1,
        "coverage_complete": False,
        "coverage_warnings": ["2023 renewal link unavailable"],
    }


def test_season_records_filters_materialized_season_rows_without_recomputing(chronicle_root):
    result = ChronicleQueries(chronicle_root).season_records("ironbound_sixteen", "2026")

    assert result["records"] == {
        "franchise:a": {"season": "2026", "identity": "franchise:a", "wins": 1, "losses": 0},
        "franchise:b": {"season": "2026", "identity": "franchise:b", "wins": 0, "losses": 1},
    }
    assert result["coverage_complete"] is False


def test_recent_events_uses_observation_time_and_optional_type_filter(chronicle_root):
    query = ChronicleQueries(chronicle_root)

    all_new = query.recent_events("ironbound_sixteen", "2026-09-16T12:00:00+00:00")
    waivers = query.recent_events(
        "ironbound_sixteen",
        "2026-09-16T12:00:00+00:00",
        event_types={"WAIVER_ADD"},
    )

    assert [row["event_id"] for row in all_new] == ["new-waiver", "new-drop"]
    assert [row["event_id"] for row in waivers] == ["new-waiver"]


def test_player_events_reads_global_player_ledger_and_filters_player(chronicle_root):
    rows = ChronicleQueries(chronicle_root).player_events(
        "p1", since="2026-09-16T12:00:00+00:00"
    )

    assert [row["event_id"] for row in rows] == ["status-p1"]


def test_transactions_for_entity_returns_only_transaction_events_containing_entity(chronicle_root):
    rows = ChronicleQueries(chronicle_root).transactions_for_entity(
        "ironbound_sixteen", "p1", since="2026-09-15T00:00:00+00:00"
    )

    assert [row["event_id"] for row in rows] == ["old-trade", "new-waiver"]


def test_missing_head_to_head_returns_none(chronicle_root):
    assert (
        ChronicleQueries(chronicle_root).head_to_head(
            "ironbound_sixteen", "franchise:a", "franchise:missing"
        )
        is None
    )


def test_season_efficiency_reads_finalized_metric_events(tmp_path):
    from editorial_desk.chronicle_events import make_event
    from editorial_desk.chronicle_store import ChronicleStore

    store = ChronicleStore(tmp_path)
    store.append_events(
        [
            make_event(
                event_type="LINEUP_EFFICIENCY_FINAL",
                source="sleeper_matchups",
                source_ref="eff:1",
                league_key="demo",
                season="2026",
                week=1,
                provenance="reconstructed_from_sleeper",
                entities={"roster_id": 1},
                evidence={
                    "roster_id": 1,
                    "actual_points": 100,
                    "optimal_points": 110,
                    "points_left_on_bench": 10,
                    "efficiency": 0.9091,
                },
            )
        ]
    )

    rows = ChronicleQueries(tmp_path).season_efficiency("demo", "2026")

    assert rows == [
        {
            "season": "2026",
            "week": 1,
            "roster_id": 1,
            "actual_points": 100.0,
            "optimal_points": 110.0,
            "points_left_on_bench": 10.0,
            "efficiency": 0.9091,
            "event_id": rows[0]["event_id"],
        }
    ]
