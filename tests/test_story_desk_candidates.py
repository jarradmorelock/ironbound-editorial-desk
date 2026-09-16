import json

import pytest

from editorial_desk.chronicle_queries import ChronicleQueries
from editorial_desk.external_inputs import ExternalEditorialInputs, OfficialPowerRanking
from editorial_desk.story_desk import build_story_desk


EXPECTED_FAMILIES = {
    "rivalry_history",
    "injury_shock",
    "reaction_transaction",
    "waiver_run",
    "trade_afterlife",
    "trade_market_shift",
    "asset_journey",
    "roster_architecture",
    "dynasty_identity",
    "historic_upset",
    "scoring_record",
    "streak",
    "repeated_close_losses",
    "former_player_matchup",
    "playoff_rematch",
    "lineup_catastrophe",
    "division_pressure",
    "cross_league_shock",
    "david_vs_goliath",
}


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _event(event_id, event_type, observed_at, **kwargs):
    return {
        "event_id": event_id,
        "event_type": event_type,
        "season": "2026",
        "week": 7,
        "observed_at": observed_at,
        "occurred_at": observed_at,
        "source": kwargs.pop("source", "sleeper"),
        "source_ref": kwargs.pop("source_ref", event_id),
        "entities": kwargs.pop("entities", {}),
        "evidence": kwargs.pop("evidence", {}),
        **kwargs,
    }


def _rich_chronicle(tmp_path):
    root = tmp_path / "chronicle"
    mappings = []
    for roster_id, key in ((1, "franchise:a"), (2, "franchise:b"), (3, "franchise:c"), (4, "franchise:d")):
        mappings.append(
            {
                "league_key": "ironbound_sixteen",
                "season": "2026",
                "roster_id": roster_id,
                "owner_id": f"owner-{roster_id}",
                "franchise_key": key,
            }
        )
    _write_json(
        root / "registry" / "identity.json",
        {
            "dynasty_mappings": mappings,
            "redraft_mappings": [],
            "aliases": {
                "franchise:a": [
                    {"season": "2025", "name": "Old A"},
                    {"season": "2026", "name": "New A"},
                ]
            },
            "manager_aliases": {},
            "manager_tenures": {
                "franchise:a": [
                    {"season": "2025", "owner_id": "old-owner", "manager_key": "manager:old"},
                    {"season": "2026", "owner_id": "owner-1", "manager_key": "manager:new"},
                ]
            },
        },
    )
    _write_json(
        root / "leagues" / "ironbound_sixteen" / "history" / "head_to_head.json",
        {
            "head_to_head": [
                {
                    "identity_a": "franchise:a",
                    "identity_b": "franchise:b",
                    "wins_a": 5,
                    "wins_b": 3,
                    "ties": 0,
                    "games": 8,
                    "playoff_games": 2,
                    "current_streak_identity": "franchise:a",
                    "current_streak_length": 3,
                }
            ]
        },
    )
    close_losses = [
        {
            "event_id": f"close-{week}",
            "season": "2026",
            "week": week,
            "competition": "regular_season",
            "left_identity": "franchise:c",
            "right_identity": "franchise:d",
            "winner_identity": "franchise:d",
            "loser_identity": "franchise:c",
            "margin": margin,
        }
        for week, margin in ((2, 2.0), (4, 3.5), (6, 1.0))
    ]
    _write_json(
        root / "leagues" / "ironbound_sixteen" / "history" / "matchups.json",
        {
            "matchups": [
                {
                    "event_id": "playoff-a-b",
                    "season": "2025",
                    "week": 16,
                    "competition": "playoffs",
                    "left_identity": "franchise:a",
                    "right_identity": "franchise:b",
                    "winner_identity": "franchise:a",
                    "loser_identity": "franchise:b",
                    "margin": 5.0,
                },
                *close_losses,
            ]
        },
    )
    _write_json(
        root / "leagues" / "ironbound_sixteen" / "history" / "records.json",
        {
            "records": {},
            "coverage": {"start_season": "2024", "complete": True, "warnings": []},
        },
    )
    _write_json(
        root / "leagues" / "ironbound_sixteen" / "history" / "seasons.json",
        {
            "seasons": {
                "2026:franchise:a": {"season": "2026", "identity": "franchise:a", "wins": 1, "losses": 4},
                "2026:franchise:b": {"season": "2026", "identity": "franchise:b", "wins": 4, "losses": 1},
                "2026:franchise:c": {"season": "2026", "identity": "franchise:c", "wins": 2, "losses": 3},
                "2026:franchise:d": {"season": "2026", "identity": "franchise:d", "wins": 3, "losses": 2},
            }
        },
    )

    ironbound_events = [
        _event(
            "trade-p3-1",
            "TRADE",
            "2026-08-20T12:00:00+00:00",
            entities={"player_id": "p3", "from_roster_id": 2, "to_roster_id": 1},
        ),
        _event(
            "trade-p3-2",
            "TRADE",
            "2026-09-01T12:00:00+00:00",
            entities={"player_id": "p3", "from_roster_id": 4, "to_roster_id": 2},
        ),
        _event(
            "trade-p3-3",
            "TRADE",
            "2026-09-10T12:00:00+00:00",
            entities={"player_id": "p3", "from_roster_id": 2, "to_roster_id": 1},
        ),
        _event("trade-volume-2", "TRADE", "2026-09-11T12:00:00+00:00", entities={"player_id": "x2"}),
        _event("trade-volume-3", "TRADE", "2026-09-12T12:00:00+00:00", entities={"player_id": "x3"}),
        _event("trade-volume-4", "TRADE", "2026-09-13T12:00:00+00:00", entities={"player_id": "x4"}),
        _event(
            "reaction-add",
            "FREE_AGENT_ADD",
            "2026-09-15T14:00:00+00:00",
            entities={"player_id": "backup", "roster_id": 1},
        ),
        _event(
            "waiver-p2-iron",
            "WAIVER_ADD",
            "2026-09-15T15:00:00+00:00",
            entities={"player_id": "p2", "roster_id": 3},
        ),
        _event(
            "drop-p1-iron",
            "DROP",
            "2026-09-15T16:00:00+00:00",
            entities={"player_id": "p1", "roster_id": 1},
        ),
        _event(
            "record-week7",
            "RECORD_SET",
            "2026-09-15T23:00:00+00:00",
            entities={"identity": "franchise:a"},
            evidence={"record_type": "all_time_team_high_score", "value": 168.4},
        ),
    ]
    _write_jsonl(
        root / "leagues" / "ironbound_sixteen" / "events" / "2026.jsonl",
        ironbound_events,
    )
    _write_jsonl(
        root / "leagues" / "unbound_sixteen" / "events" / "2026.jsonl",
        [
            _event(
                "waiver-p2-unbound",
                "WAIVER_ADD",
                "2026-09-15T15:20:00+00:00",
                entities={"player_id": "p2", "roster_id": 8},
            ),
            _event(
                "drop-p1-unbound",
                "DROP",
                "2026-09-15T16:30:00+00:00",
                entities={"player_id": "p1", "roster_id": 9},
            ),
        ],
    )
    _write_jsonl(
        root / "cross_league" / "nfl_player_events" / "2026.jsonl",
        [
            _event(
                "status-p1-out",
                "PLAYER_STATUS_CHANGE",
                "2026-09-15T12:00:00+00:00",
                source="sleeper_players",
                entities={"player_id": "p1"},
                before={"injury_status": "Questionable"},
                after={"injury_status": "Out"},
                evidence={"observed_before": "2026-09-15T06:00:00+00:00", "observed_after": "2026-09-15T12:00:00+00:00"},
            )
        ],
    )
    return ChronicleQueries(root)


def _snapshot():
    rb_ids = [f"rb{i}" for i in range(1, 8)]
    players = {
        "p1": {"full_name": "Injured Star", "position": "WR", "injury_status": "Out"},
        "p2": {"full_name": "Waiver Rocket", "position": "RB"},
        "p3": {"full_name": "Former Star", "position": "WR"},
        "backup": {"full_name": "Replacement", "position": "WR"},
        **{player_id: {"full_name": player_id.upper(), "position": "RB"} for player_id in rb_ids},
    }
    return {
        "week": 7,
        "nfl_state": {"season": "2026"},
        "editorial": {"league_key": "ironbound_sixteen", "league_format": "dynasty"},
        "league": {"settings": {"divisions": 2}, "metadata": {"division_1": "Hammer", "division_2": "Anvil"}},
        "rosters": [
            {"roster_id": 1, "owner_id": "owner-1", "players": ["p1", "p3", *rb_ids], "settings": {"division": 1}},
            {"roster_id": 2, "owner_id": "owner-2", "players": ["backup"], "settings": {"division": 1}},
            {"roster_id": 3, "owner_id": "owner-3", "players": ["p2"], "settings": {"division": 2}},
            {"roster_id": 4, "owner_id": "owner-4", "players": [], "settings": {"division": 2}},
        ],
        "matchups": [
            {
                "matchup_id": 1,
                "roster_id": 1,
                "points": 168.4,
                "starters": ["p1", "p3"],
                "players_points": {"p1": 5.0, "p3": 31.0, **{player_id: 0 for player_id in rb_ids}},
            },
            {
                "matchup_id": 1,
                "roster_id": 2,
                "points": 120.0,
                "starters": ["backup"],
                "players_points": {"backup": 9.0},
            },
            {"matchup_id": 2, "roster_id": 3, "points": 101.0, "starters": ["p2"], "players_points": {"p2": 20.0}},
            {"matchup_id": 2, "roster_id": 4, "points": 106.0, "starters": [], "players_points": {}},
        ],
        "players": players,
    }


def _dossier():
    return {
        "lineup_flip_candidates": [
            {
                "roster_id": 3,
                "team": "Three",
                "point_swing": 18.0,
                "would_flip_result": True,
                "started_player": "Low Starter",
                "bench_player": "Bench Boom",
            }
        ],
        "division_metrics": [
            {"division_id": "1", "division_name": "Hammer", "leader": "franchise:b", "gap": 1},
            {"division_id": "2", "division_name": "Anvil", "leader": "franchise:d", "gap": 1},
        ],
        "market_context": {
            "status": "available",
            "players": [
                {"player_id": "p1", "fantasy_team": "One", "trade_value": 8000, "overall_rank": 12},
                {"player_id": "p3", "fantasy_team": "One", "trade_value": 6500, "overall_rank": 25},
            ],
        },
    }


def _official_inputs():
    return ExternalEditorialInputs(
        publication_key="ironbound_weekly",
        official_power_rankings=(
            OfficialPowerRanking("franchise:a", 15),
            OfficialPowerRanking("franchise:b", 1),
        ),
    )


def test_rich_evidence_week_can_emit_every_approved_candidate_family(tmp_path):
    desk = build_story_desk(
        "ironbound_weekly",
        _snapshot(),
        _dossier(),
        _rich_chronicle(tmp_path),
        external_inputs=_official_inputs(),
        observed_since="2026-09-09T00:00:00+00:00",
    )

    families = {row["candidate_type"] for row in desk["candidates"]}
    assert EXPECTED_FAMILIES <= families
    assert len(desk["candidates"]) <= 20
    assert all(row["evidence_refs"] for row in desk["candidates"])
    assert all(row["signal_components"] for row in desk["candidates"])


@pytest.mark.parametrize(
    "publication_key",
    ["ballad_crier", "the_stampede", "volunteer_voice", "saturday_standard", "hollywood_beat"],
)
def test_story_desk_is_disabled_for_newspaper_publications(tmp_path, publication_key):
    desk = build_story_desk(
        publication_key,
        _snapshot(),
        _dossier(),
        _rich_chronicle(tmp_path),
    )

    assert desk["status"] == "disabled"
    assert desk["candidates"] == []


def test_david_vs_goliath_is_not_emitted_without_official_rankings(tmp_path):
    desk = build_story_desk(
        "ironbound_weekly",
        _snapshot(),
        _dossier(),
        _rich_chronicle(tmp_path),
        external_inputs=None,
        observed_since="2026-09-09T00:00:00+00:00",
    )

    assert "david_vs_goliath" not in {row["candidate_type"] for row in desk["candidates"]}


def test_weak_week_is_not_padded_to_arbitrary_candidate_minimum(tmp_path):
    chronicle = ChronicleQueries(tmp_path / "empty")
    snapshot = {
        "week": 7,
        "nfl_state": {"season": "2026"},
        "editorial": {"league_key": "ironbound_sixteen", "league_format": "dynasty"},
        "league": {"settings": {}},
        "rosters": [],
        "matchups": [],
        "players": {},
    }

    desk = build_story_desk("ironbound_weekly", snapshot, {}, chronicle)

    assert desk["status"] == "available"
    assert desk["candidates"] == []
