import hashlib
import json

import pytest

from editorial_desk.external_inputs import ExternalInputError, load_external_inputs


def _write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_missing_external_input_path_returns_empty_valid_object(tmp_path):
    result = load_external_inputs(None, "ironbound_weekly")

    assert result.publication_key == "ironbound_weekly"
    assert result.official_power_rankings == ()
    assert result.war == ()
    assert result.cwar == ()
    assert result.usage == ()
    assert result.playoff_odds == ()
    assert result.notes == ()
    assert result.source_metadata == {}
    assert result.power_rankings_supplied is False
    assert result.war_supplied is False


def test_valid_external_input_packet_preserves_authoritative_rankings_and_metadata(tmp_path):
    path = _write(
        tmp_path / "ironbound.json",
        {
            "publication_key": "ironbound_weekly",
            "official_power_rankings": [
                {"franchise_key": "franchise:a", "rank": 1},
                {"franchise_key": "franchise:b", "rank": 15},
            ],
            "war": [
                {"franchise_key": "franchise:a", "value": 2.4},
            ],
            "cwar": [
                {"franchise_key": "franchise:a", "value": 1.8},
            ],
            "usage": [
                {"franchise_key": "franchise:a", "value": 0.61},
            ],
            "playoff_odds": [
                {"franchise_key": "franchise:a", "playoff": 72, "crown": 14},
            ],
            "notes": ["Commissioner-supplied context"],
            "source_metadata": {"label": "Ironbound Power Rankings", "week": 7},
        },
    )

    result = load_external_inputs(path, "ironbound_weekly")

    assert [(row.franchise_key, row.rank) for row in result.official_power_rankings] == [
        ("franchise:a", 1),
        ("franchise:b", 15),
    ]
    assert result.war == ({"franchise_key": "franchise:a", "value": 2.4},)
    assert result.cwar == ({"franchise_key": "franchise:a", "value": 1.8},)
    assert result.usage == ({"franchise_key": "franchise:a", "value": 0.61},)
    assert result.playoff_odds == ({"franchise_key": "franchise:a", "playoff": 72, "crown": 14},)
    assert result.source_metadata["week"] == 7
    assert result.power_rankings_supplied is True
    assert result.war_supplied is True
    assert result.cwar_supplied is True
    assert result.usage_supplied is True
    assert result.playoff_odds_supplied is True


@pytest.mark.parametrize(
    "rankings,match",
    [
        (
            [
                {"franchise_key": "franchise:a", "rank": 1},
                {"franchise_key": "franchise:b", "rank": 1},
            ],
            "Duplicate official rank",
        ),
        (
            [
                {"franchise_key": "franchise:a", "rank": 0},
            ],
            "positive integer",
        ),
        (
            [
                {"franchise_key": "franchise:a", "rank": 1},
                {"franchise_key": "franchise:a", "rank": 2},
            ],
            "Duplicate franchise_key",
        ),
    ],
)
def test_invalid_or_duplicate_rankings_raise(tmp_path, rankings, match):
    path = _write(
        tmp_path / "invalid.json",
        {
            "publication_key": "ironbound_weekly",
            "official_power_rankings": rankings,
        },
    )

    with pytest.raises(ExternalInputError, match=match):
        load_external_inputs(path, "ironbound_weekly")


def test_publication_key_mismatch_raises(tmp_path):
    path = _write(
        tmp_path / "wrong.json",
        {
            "publication_key": "unbound_weekly",
            "official_power_rankings": [],
        },
    )

    with pytest.raises(ExternalInputError, match="publication_key"):
        load_external_inputs(path, "ironbound_weekly")


def test_loader_rejects_non_object_json_instead_of_guessing(tmp_path):
    path = _write(tmp_path / "list.json", [1, 2, 3])

    with pytest.raises(ExternalInputError, match="JSON object"):
        load_external_inputs(path, "ironbound_weekly")


def test_ranking_handoff_accepts_roster_and_team_keys(tmp_path):
    path = _write(
        tmp_path / "handoff.json",
        {
            "publication_key": "ironbound_weekly",
            "official_power_rankings": [
                {
                    "roster_id": 7,
                    "team": "San Carlos FC",
                    "rank": 1,
                    "previous_rank": 3,
                    "movement": 2,
                    "score": 91.2,
                }
            ],
            "playoff_odds": [
                {
                    "roster_id": 7,
                    "team": "San Carlos FC",
                    "playoff": 91.0,
                    "championship": 15.0,
                }
            ],
        },
    )

    result = load_external_inputs(path, "ironbound_weekly")
    row = result.official_power_rankings[0]

    assert row.franchise_key is None
    assert row.roster_id == 7
    assert row.team == "San Carlos FC"
    assert row.previous_rank == 3
    assert row.movement == 2
    assert row.score == 91.2
    assert result.ranking_for_roster(7).rank == 1
    assert result.ranking_for_roster(99, team="San Carlos FC").rank == 1


def test_external_input_loads_and_verifies_publication_assets(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    rankings = assets / "ironbound_weekly-power-rankings.png"
    playoffs = assets / "ironbound_weekly-playoff-forecast.png"
    rankings.write_bytes(b"rankings-png")
    playoffs.write_bytes(b"playoffs-png")

    path = _write(
        tmp_path / "ironbound_weekly.json",
        {
            "publication_key": "ironbound_weekly",
            "publication_assets": {
                "power_rankings": {
                    "filename": rankings.name,
                    "media_type": "image/png",
                    "sha256": hashlib.sha256(rankings.read_bytes()).hexdigest(),
                },
                "playoff_forecast": {
                    "filename": playoffs.name,
                    "media_type": "image/png",
                    "sha256": hashlib.sha256(playoffs.read_bytes()).hexdigest(),
                },
            },
        },
    )

    result = load_external_inputs(path, "ironbound_weekly")

    assert result.publication_assets["power_rankings"]["available"] is True
    assert result.publication_assets["playoff_forecast"]["available"] is True
    assert result.publication_assets["power_rankings"]["actual_sha256"] == hashlib.sha256(
        rankings.read_bytes()
    ).hexdigest()


def test_external_input_rejects_publication_asset_checksum_mismatch(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    rankings = assets / "ironbound_weekly-power-rankings.png"
    rankings.write_bytes(b"rankings-png")

    path = _write(
        tmp_path / "ironbound_weekly.json",
        {
            "publication_key": "ironbound_weekly",
            "publication_assets": {
                "power_rankings": {
                    "filename": rankings.name,
                    "media_type": "image/png",
                    "sha256": "0" * 64,
                }
            },
        },
    )

    with pytest.raises(ExternalInputError, match="checksum mismatch"):
        load_external_inputs(path, "ironbound_weekly")


def test_v3_ranking_handoff_preserves_components_schedule_and_weekly_forecast(tmp_path):
    path = _write(
        tmp_path / "v3.json",
        {
            "schema_version": 3,
            "publication_key": "ironbound_weekly",
            "official_power_rankings": [
                {
                    "roster_id": 1,
                    "team": "Team 1",
                    "rank": 1,
                    "previous_rank": 3,
                    "movement": 2,
                    "score": 81.4,
                    "components": {
                        "market_percentile": 91.0,
                        "ros_starters_percentile": 88.0,
                        "season_results_percentile": 70.0,
                        "market_points": 31.9,
                        "ros_starters_points": 39.6,
                        "season_results_points": 14.0,
                        "weights": {
                            "market": 0.35,
                            "ros_starters": 0.45,
                            "season_results": 0.20,
                        },
                    },
                }
            ],
            "playoff_odds": [{"roster_id": 1, "playoff": 88.0}],
            "remaining_schedule_strength": [
                {
                    "roster_id": 1,
                    "team": "Team 1",
                    "remaining_opponents": [2, 3],
                    "average_opponent_index": 58.4,
                    "difficulty_rank": 1,
                    "grade": "F",
                }
            ],
            "weekly_matchup_forecast": [
                {
                    "week": 5,
                    "matchup_id": 1,
                    "roster_one": 1,
                    "team_one": "Team 1",
                    "roster_two": 2,
                    "team_two": "Team 2",
                    "projected_score_one": 128.4,
                    "projected_score_two": 124.1,
                    "spread": 4.5,
                    "over_under": 252.5,
                    "win_probability_one": 58.0,
                    "simulations": 10000,
                    "model": "Sleeper projected-optimal legal lineup Monte Carlo",
                }
            ],
            "source_metadata": {
                "ranking_week": 5,
                "results_through_week": 4,
            },
        },
    )

    result = load_external_inputs(path, "ironbound_weekly")

    ranking = result.official_power_rankings[0]
    assert ranking.components["market_percentile"] == 91.0
    assert ranking.components["weights"]["ros_starters"] == 0.45
    assert result.remaining_schedule_strength[0]["grade"] == "F"
    assert result.weekly_matchup_forecast[0]["spread"] == 4.5
    assert result.handoff_schema_version == 3
