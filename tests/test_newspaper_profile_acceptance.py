import json
from pathlib import Path

import pytest

from editorial_desk.external_inputs import ExternalEditorialInputs
from editorial_desk.newspaper_research import PROFILE_CONTRACTS
from editorial_desk.publication_complete import build_publication_complete_packet


FIXTURES = Path(__file__).parent / "fixtures" / "newspaper_acceptance"


def _manifest(publication_key):
    return json.loads((FIXTURES / f"{publication_key}.json").read_text(encoding="utf-8"))


def _canonical():
    return {
        "coverage": {"status": "READY", "weeks": [1]},
        "historical_matchups": [],
        "entering_records": {"1": {}},
        "team_season_totals": {},
        "player_season_totals": {},
        "player_season_totals_status": "READY",
        "division_summary": {"status": "NOT_APPLICABLE", "divisions": {}},
        "evidence_index": {},
        "conflicts": [],
    }


def _department(feature):
    if feature == "lineup_flip_candidates":
        return {
            "feature": feature,
            "display_name": feature,
            "required_in_phase": True,
            "status": "ready",
            "data": [
                {
                    "team": "Team One",
                    "started_player": "Starter",
                    "bench_player": "Bench",
                    "started_points": 5.0,
                    "bench_points": 20.0,
                    "hypothetical_team_points": 115.0,
                    "would_flip_result": True,
                }
            ],
        }
    if feature == "health_status":
        return {
            "feature": feature,
            "display_name": feature,
            "required_in_phase": True,
            "status": "ready_no_items",
            "data": [],
        }
    if feature == "league_wide_started_mvp":
        return {
            "feature": feature,
            "display_name": "King of the Hill",
            "required_in_phase": True,
            "status": "ready",
            "data": {
                "player_id": "p1",
                "player": "Player One",
                "team": "Team One",
                "points": 30.0,
                "status": "STARTED",
            },
        }
    if feature == "league_median":
        data = {"points": 100.0, "above": ["Team One"], "below": ["Team Two"]}
    elif feature == "idp_position_metrics":
        data = {"LB": {"player": "Linebacker", "points": 20.0}}
    elif feature == "workload_stat_lines":
        data = {"rushing_attempts": {"player": "Runner", "carries": 24}}
    else:
        data = {"verified": True}
    return {
        "feature": feature,
        "display_name": feature,
        "required_in_phase": True,
        "status": "ready",
        "data": data,
    }


def _packet(publication_key):
    manifest = _manifest(publication_key)
    snapshot = {
        "week": 1,
        "league": {"season": "2026"},
        "editorial": {
            "league_key": publication_key,
            "publication_profile": {"key": publication_key},
        },
    }
    research = {
        "publication_key": publication_key,
        "publication": publication_key,
        "week": 1,
        "sections": [_department(feature) for feature in manifest["required_departments"]],
    }
    transactions = {
        "coverage": {"status": "READY", "transaction_count": 0},
        "pick_provenance_status": "READY",
        "unresolved_pick_provenance": [],
        "transactions": [],
    }
    source_manifest = {
        "information_cutoff": "2026-09-16T12:00:00+00:00",
        "sleeper": {
            "matchups": {"status": "AVAILABLE", "weeks": [1]},
            "transactions": {"status": "AVAILABLE", "weeks": [1]},
            "projections": {"status": "AVAILABLE", "season": "2026", "week": 1},
        },
        "rankings": {"status": "READY"},
        "publication_assets": {"status": "NOT_REQUIRED"},
        "beat_news": {"status": "READY", "blocking": False},
    }
    return build_publication_complete_packet(
        snapshot,
        {},
        research,
        ExternalEditorialInputs(publication_key),
        canonical_evidence=_canonical(),
        transaction_evidence=transactions,
        source_manifest=source_manifest,
        health={"status": "READY_NO_ITEMS", "players": [], "news_events": []},
        publication_assets={},
    )


@pytest.mark.parametrize(
    "publication_key",
    [
        "ballad_crier",
        "the_stampede",
        "volunteer_voice",
        "saturday_standard",
        "hollywood_beat",
    ],
)
def test_newspaper_acceptance_manifest_matches_current_contract(publication_key):
    manifest = _manifest(publication_key)
    assert manifest["required_departments"] == PROFILE_CONTRACTS[publication_key]["required"]


@pytest.mark.parametrize(
    "publication_key",
    [
        "ballad_crier",
        "the_stampede",
        "volunteer_voice",
        "saturday_standard",
        "hollywood_beat",
    ],
)
def test_each_newspaper_profile_can_be_publication_ready_offline(publication_key):
    packet = _packet(publication_key)

    assert packet["readiness"]["publication_ready"] is True
    assert packet["readiness"]["blocking_gaps"] == []


def test_volunteer_acceptance_supersedes_old_division_and_mountain_labels():
    manifest = _manifest("volunteer_voice")
    packet = _packet("volunteer_voice")

    assert "Division Pulse" in manifest["superseded"]
    assert "Mountain MVP" in manifest["superseded"]
    assert "division_report" not in packet["required_departments"]
    assert (
        packet["departments"]["league_wide_started_mvp"]["data"]["display_name"]
        == "King of the Hill"
    )
