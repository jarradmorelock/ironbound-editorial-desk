import hashlib
from pathlib import Path

from editorial_desk.enriched_collector import _materialize_publication_assets
from editorial_desk.external_inputs import ExternalEditorialInputs
from editorial_desk.flagship_research import validate_flagship_research_packet


def test_materialize_publication_assets_copies_exact_images_into_publication_package(tmp_path):
    source_dir = tmp_path / "inputs" / "assets"
    source_dir.mkdir(parents=True)
    rankings = source_dir / "ironbound_weekly-power-rankings.png"
    playoffs = source_dir / "ironbound_weekly-playoff-forecast.png"
    rankings.write_bytes(b"rankings-image")
    playoffs.write_bytes(b"playoff-image")

    external = ExternalEditorialInputs(
        publication_key="ironbound_weekly",
        publication_assets={
            "power_rankings": {
                "filename": rankings.name,
                "media_type": "image/png",
                "sha256": hashlib.sha256(rankings.read_bytes()).hexdigest(),
                "local_path": str(rankings),
                "available": True,
                "owner": "Ironbound_power_ranks",
                "placement_policy": "use supplied graphic unchanged",
            },
            "playoff_forecast": {
                "filename": playoffs.name,
                "media_type": "image/png",
                "sha256": hashlib.sha256(playoffs.read_bytes()).hexdigest(),
                "local_path": str(playoffs),
                "available": True,
                "owner": "Ironbound_power_ranks",
                "placement_policy": "use supplied graphic unchanged",
            },
        },
    )

    manifest, copied = _materialize_publication_assets(
        external,
        tmp_path / "publication",
    )

    assert len(copied) == 2
    assert (tmp_path / "publication" / manifest["power_rankings"]["package_path"]).read_bytes() == b"rankings-image"
    assert (tmp_path / "publication" / manifest["playoff_forecast"]["package_path"]).read_bytes() == b"playoff-image"
    assert manifest["power_rankings"]["status"] == "READY"
    assert manifest["power_rankings"]["placement_policy"] == "use supplied graphic unchanged"
    assert "local_path" not in manifest["power_rankings"]


def test_missing_publication_graphics_block_production_completeness():
    packet = {
        "week": 2,
        "game_coverage": {
            "required_matchups": 8,
            "games": [
                {"matchup_id": i, "starter_stat_lines": [{"player": "P"}]}
                for i in range(1, 9)
            ],
        },
        "usage_desk": {"status": "READY"},
        "injury_roster_health": {"status": "available"},
        "weekly_honors": {
            "started_position_leaders": {"QB": {"player": "QB"}},
            "manager_of_the_week": {"team": "Team"},
            "season_efficiency_top_three": [{"team": "Team", "weeks": 2}],
            "season_team_score_top_three": [{"team": "Team", "score": 100}],
            "benchwarmer_of_the_week": {"player": "Bench"},
            "rookie_watch_top_five": [{"player": "Rookie"}],
        },
        "power_rankings_chart": {"status": "READY"},
        "playoff_odds_chart": {"status": "READY"},
        "ranking_publication_assets": {
            "required": True,
            "assets": {
                "power_rankings": {
                    "status": "AWAITING_TUESDAY_INPUT",
                },
                "playoff_forecast": {
                    "status": "READY",
                    "package_path": "publication-assets/playoffs.png",
                },
            },
        },
        "tuesday_external_inputs": {
            "source_metadata": {"week": 2},
        },
    }

    validation = validate_flagship_research_packet(packet)

    assert validation["research_complete"] is False
    waiting = " ".join(validation["awaiting_tuesday_input"])
    assert "Power Rankings graphic" in waiting


def test_stale_power_rankings_handoff_blocks_current_week():
    packet = {
        "week": 2,
        "game_coverage": {
            "required_matchups": 8,
            "games": [
                {"matchup_id": i, "starter_stat_lines": [{"player": "P"}]}
                for i in range(1, 9)
            ],
        },
        "usage_desk": {"status": "READY"},
        "injury_roster_health": {"status": "available"},
        "weekly_honors": {
            "started_position_leaders": {"QB": {"player": "QB"}},
            "manager_of_the_week": {"team": "Team"},
            "season_efficiency_top_three": [{"team": "Team", "weeks": 2}],
            "season_team_score_top_three": [{"team": "Team", "score": 100}],
            "benchwarmer_of_the_week": {"player": "Bench"},
            "rookie_watch_top_five": [{"player": "Rookie"}],
        },
        "power_rankings_chart": {"status": "READY"},
        "playoff_odds_chart": {"status": "READY"},
        "ranking_publication_assets": {
            "required": True,
            "assets": {
                "power_rankings": {
                    "status": "READY",
                    "package_path": "publication-assets/rankings.png",
                },
                "playoff_forecast": {
                    "status": "READY",
                    "package_path": "publication-assets/playoffs.png",
                },
            },
        },
        "tuesday_external_inputs": {
            "source_metadata": {"week": 1},
        },
    }

    validation = validate_flagship_research_packet(packet)

    assert validation["research_complete"] is False
    assert any("Received Week 1" in row for row in validation["awaiting_tuesday_input"])
