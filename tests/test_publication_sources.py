from editorial_desk.external_inputs import ExternalEditorialInputs
from editorial_desk.publication_sources import build_source_manifest, health_evidence


def _snapshot():
    return {
        "week": 3,
        "collected_at": "2026-09-30T17:00:00+00:00",
        "league": {"season": "2026"},
        "publication_sleeper": {
            "schedule": {"status": "available", "weeks": {"1": [], "2": [], "3": []}},
            "transactions": {"status": "available", "weeks": {"1": [], "2": [], "3": []}},
        },
        "ranking_inputs": {
            "sleeper_projections": {
                "status": "available",
                "season": "2026",
                "week": 3,
                "players": {"p1": {"pts_half_ppr": 10}},
            }
        },
        "nfl_context": {
            "player_stats": {"status": "available", "records": []},
            "season_player_stats": {
                "status": "available",
                "through_week": 3,
                "weeks": [1, 2, 3],
                "records": [{"player_id": "gsis-rookie", "week": 1}],
            },
            "snap_counts": {"status": "available", "records": []},
            "play_by_play": {"status": "available", "records": []},
            "injuries": {"status": "available", "records": []},
        },
    }


def _external():
    return ExternalEditorialInputs(
        "ironbound_weekly",
        schema_version=3,
        source_metadata={"results_through_week": 3, "ranking_week": 4},
        publication_assets={
            "power_rankings": {"status": "READY", "package_path": "publication-assets/ranks.png"},
            "playoff_forecast": {"status": "READY", "package_path": "publication-assets/playoffs.png"},
        },
    )


def test_source_manifest_reports_history_projection_and_ranking_status():
    manifest = build_source_manifest(
        _snapshot(),
        {"information_current_through": "2026-09-30T17:00:00+00:00"},
        _external(),
        beat_report={"status": "READY", "coverage": {"durable_since": "2026-09-01T00:00:00+00:00"}},
        publication_assets=_external().publication_assets,
    )

    assert manifest["sleeper"]["matchups"]["weeks"] == [1, 2, 3]
    assert manifest["sleeper"]["projections"]["week"] == 3
    assert manifest["rankings"]["status"] == "READY"
    assert manifest["rankings"]["results_through_week"] == 3
    assert manifest["publication_assets"]["status"] == "READY"
    assert manifest["nflverse"]["season_player_stats"] == {
        "status": "AVAILABLE",
        "record_count": 1,
    }


def test_health_evidence_excludes_observation_after_cutoff():
    dossier = {
        "information_current_through": "2026-09-30T17:00:00+00:00",
        "roster_health": {
            "status": "available",
            "players": [
                {
                    "player_id": "p1",
                    "player": "Player One",
                    "team": "Alpha",
                    "injury_status": "Questionable",
                    "observed_at": "2026-09-30T16:00:00+00:00",
                },
                {
                    "player_id": "p2",
                    "player": "Player Two",
                    "team": "Beta",
                    "injury_status": "Out",
                    "observed_at": "2026-09-30T20:00:00+00:00",
                },
            ],
        },
    }
    beat = {
        "status": "READY",
        "items": [
            {
                "event_id": "before-cutoff",
                "published_at": "2026-09-30T16:30:00+00:00",
                "editorial_lanes": {"health_context": True},
            },
            {
                "event_id": "after-cutoff",
                "published_at": "2026-09-30T20:30:00+00:00",
                "editorial_lanes": {"health_context": True},
            },
        ],
    }

    result = health_evidence(
        _snapshot(),
        dossier,
        beat,
        "2026-09-30T18:00:00+00:00",
    )

    assert [row["player_id"] for row in result["players"]] == ["p1"]
    assert [row["event_id"] for row in result["news_events"]] == ["before-cutoff"]
    assert result["information_cutoff"] == "2026-09-30T18:00:00+00:00"


def test_partial_beat_history_is_warning_not_blocker():
    manifest = build_source_manifest(
        _snapshot(),
        {},
        _external(),
        beat_report={
            "status": "PARTIAL_HISTORY",
            "coverage": {"durable_since": "2026-09-28T04:07:46+00:00"},
        },
        publication_assets=_external().publication_assets,
    )

    assert manifest["beat_news"]["status"] == "PARTIAL"
    assert manifest["beat_news"]["blocking"] is False
