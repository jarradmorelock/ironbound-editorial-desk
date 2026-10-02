from editorial_desk.external_inputs import ExternalEditorialInputs
from editorial_desk.publication_sources import (
    build_source_manifest,
    health_evidence,
)


def _snapshot():
    return {
        "collected_at": "2026-09-30T18:00:00+00:00",
        "week": 3,
        "league": {"season": "2026"},
        "nfl_context": {
            "schedule": {"status": "available", "records": []},
            "player_stats": {"status": "available", "records": []},
            "injuries": {"status": "available", "records": []},
            "noteworthy_late_plays": {"status": "available", "records": []},
            "snap_counts": {"status": "available", "records": []},
            "play_by_play": {"status": "available", "records": []},
        },
        "ranking_inputs": {
            "sleeper_projections": {
                "status": "available",
                "season": "2026",
                "week": 3,
                "players": {"p1": {"pts_half_ppr": 10.0}},
            }
        },
        "flagship_sleeper": {
            "schedule": {
                "status": "available",
                "weeks": {"1": [], "2": [], "3": []},
                "errors": {},
            },
            "transactions": {
                "status": "available",
                "weeks": {"1": [], "2": [], "3": []},
                "errors": {},
            },
        },
    }


def _dossier():
    return {
        "information_current_through": "2026-09-30T18:00:00+00:00",
        "roster_health": {
            "status": "available",
            "players": [
                {
                    "player_id": "p1",
                    "player": "Player One",
                    "team": "The Buckaneers",
                    "injury_status": "Questionable",
                    "reserve_status": None,
                    "observed_at": "2026-09-30T17:30:00+00:00",
                },
                {
                    "player_id": "p2",
                    "player": "Player Two",
                    "team": "Other Team",
                    "injury_status": "Out",
                    "reserve_status": "IR",
                    "observed_at": "2026-09-30T19:30:00+00:00",
                },
            ],
        },
    }


def _external():
    return ExternalEditorialInputs(
        publication_key="ironbound_weekly",
        schema_version=3,
        source_metadata={
            "ranking_week": 4,
            "results_through_week": 3,
            "source_revision": "rank-sha",
        },
        official_power_rankings=(),
    )


def _beat():
    return {
        "status": "PARTIAL_HISTORY",
        "coverage": {
            "durable_since": "2026-09-28T04:07:46+00:00",
            "complete_for_reporting_window": False,
            "note": "Earlier Discord history is not represented durably.",
        },
        "items": [
            {
                "event_id": "before-cutoff",
                "published_at": "2026-09-30T17:00:00+00:00",
                "headline": "Player One limited",
                "league_players": [
                    {
                        "sleeper_player_id": "p1",
                        "player": "Player One",
                        "fantasy_team": "The Buckaneers",
                    }
                ],
                "editorial_lanes": {"health_context": True},
            },
            {
                "event_id": "after-cutoff",
                "published_at": "2026-09-30T19:00:00+00:00",
                "headline": "Player One ruled out",
                "league_players": [
                    {
                        "sleeper_player_id": "p1",
                        "player": "Player One",
                        "fantasy_team": "The Buckaneers",
                    }
                ],
                "editorial_lanes": {"health_context": True},
            },
        ],
    }


def test_source_manifest_reports_sleeper_nflverse_ranking_and_asset_status():
    manifest = build_source_manifest(
        _snapshot(),
        _dossier(),
        _external(),
        beat_report=_beat(),
        publication_assets={
            "power_rankings": {"status": "READY", "package_path": "publication-assets/rankings.png"},
            "playoff_forecast": {"status": "READY", "package_path": "publication-assets/playoffs.png"},
        },
    )

    assert manifest["information_cutoff"] == "2026-09-30T18:00:00+00:00"
    assert manifest["sleeper"]["matchups"]["weeks"] == [1, 2, 3]
    assert manifest["sleeper"]["transactions"]["weeks"] == [1, 2, 3]
    assert manifest["sleeper"]["projections"]["season"] == "2026"
    assert manifest["sleeper"]["projections"]["week"] == 3
    assert manifest["nflverse"]["player_stats"]["status"] == "READY"
    assert manifest["rankings"]["schema_version"] == 3
    assert manifest["rankings"]["ranking_week"] == 4
    assert manifest["publication_assets"]["power_rankings"]["status"] == "READY"


def test_health_evidence_excludes_observations_after_information_cutoff():
    result = health_evidence(
        _snapshot(),
        _dossier(),
        _beat(),
        "2026-09-30T18:00:00+00:00",
    )

    assert [row["player_id"] for row in result["players"]] == ["p1"]
    assert [row["event_id"] for row in result["news_events"]] == ["before-cutoff"]
    assert result["information_cutoff"] == "2026-09-30T18:00:00+00:00"


def test_partial_beat_history_is_a_nonblocking_source_warning():
    manifest = build_source_manifest(
        _snapshot(),
        _dossier(),
        _external(),
        beat_report=_beat(),
        publication_assets=None,
    )

    assert manifest["beat_news"]["status"] == "PARTIAL"
    assert manifest["beat_news"]["blocking"] is False
    assert manifest["beat_news"]["durable_since"] == "2026-09-28T04:07:46+00:00"
    assert any("beat" in row["source"] for row in manifest["warnings"])
