from editorial_desk.external_inputs import ExternalEditorialInputs
from editorial_desk.publication_complete import build_publication_complete_packet


def _base_snapshot(publication_key):
    return {
        "week": 3,
        "league": {"season": "2026"},
        "editorial": {
            "league_key": publication_key,
            "publication_profile": {"key": publication_key},
        },
    }


def _canonical():
    return {
        "coverage": {"status": "READY", "weeks": [1, 2, 3]},
        "historical_matchups": [],
        "entering_records": {"3": {}},
        "team_season_totals": {},
        "player_season_totals": {},
        "player_season_totals_status": "READY",
        "division_summary": {"status": "NOT_APPLICABLE", "divisions": {}},
        "evidence_index": {},
        "conflicts": [],
    }


def _source_manifest():
    return {
        "information_cutoff": "2026-09-30T18:00:00+00:00",
        "sleeper": {
            "matchups": {"status": "AVAILABLE", "weeks": [1, 2, 3]},
            "transactions": {"status": "AVAILABLE", "weeks": [1, 2, 3]},
            "projections": {"status": "AVAILABLE", "season": "2026", "week": 3},
        },
        "rankings": {"status": "READY"},
        "publication_assets": {"status": "NOT_REQUIRED"},
        "beat_news": {"status": "READY", "blocking": False},
    }


def _transactions():
    return {
        "coverage": {"status": "READY", "transaction_count": 0},
        "pick_provenance_status": "READY",
        "unresolved_pick_provenance": [],
        "transactions": [],
    }


def _health(status="READY_NO_ITEMS"):
    return {"status": status, "players": [], "news_events": []}


def _department(feature, status="ready", data=None, required=True):
    return {
        "feature": feature,
        "display_name": feature,
        "required_in_phase": required,
        "status": status,
        "data": {} if data is None else data,
        "reason": None,
    }


def _build(publication_key, departments):
    research = {
        "publication_key": publication_key,
        "publication": publication_key,
        "week": 3,
        "sections": departments,
        "source_status": {},
    }
    return build_publication_complete_packet(
        _base_snapshot(publication_key),
        {},
        research,
        ExternalEditorialInputs(publication_key),
        canonical_evidence=_canonical(),
        transaction_evidence=_transactions(),
        source_manifest=_source_manifest(),
        health=_health(),
        publication_assets={},
    )


def test_ballad_lineup_flip_department_requires_evaluated_legal_substitutions():
    packet = _build(
        "ballad_crier",
        [
            _department(
                "lineup_flip_candidates",
                status="ready",
                data=[{"team": "Alpha", "started_player": "A", "bench_player": "B"}],
            )
        ],
    )

    assert packet["readiness"]["publication_ready"] is False
    assert any(
        gap["section"] == "lineup_flip_candidates"
        and gap["code"] == "INCOMPLETE_DEPARTMENT_EVIDENCE"
        for gap in packet["readiness"]["blocking_gaps"]
    )


def test_saturday_standard_blocks_when_required_idp_evidence_is_empty():
    packet = _build(
        "saturday_standard",
        [_department("idp_position_metrics", status="ready", data={})],
    )

    assert packet["readiness"]["publication_ready"] is False
    assert any(
        gap["section"] == "idp_position_metrics"
        for gap in packet["readiness"]["blocking_gaps"]
    )


def test_healthy_newspaper_health_department_is_ready_no_items_not_unavailable():
    packet = _build(
        "the_stampede",
        [_department("health_status", status="ready_no_items", data=[])],
    )

    assert not any(
        gap["section"] == "health_status"
        for gap in packet["readiness"]["blocking_gaps"]
    )


def test_volunteer_voice_packet_adds_king_of_the_hill_identity_and_forbids_division_requirement():
    packet = _build(
        "volunteer_voice",
        [
            _department(
                "league_wide_started_mvp",
                status="ready",
                data={
                    "player_id": "p1",
                    "player": "Player One",
                    "team": "Family Team",
                    "points": 31.5,
                    "status": "STARTED",
                },
            )
        ],
    )

    honor = packet["departments"]["league_wide_started_mvp"]["data"]
    assert honor["award_key"] == "KING_OF_THE_HILL"
    assert honor["display_name"] == "King of the Hill"
    assert "division_report" not in packet["required_departments"]


def test_structural_newspaper_department_cannot_use_ready_no_items():
    packet = _build(
        "ballad_crier",
        [_department("weekly_results", status="ready_no_items", data=[])],
    )

    assert packet["readiness"]["publication_ready"] is False
    assert any(
        gap["section"] == "weekly_results"
        and gap["code"] == "INCOMPLETE_DEPARTMENT_EVIDENCE"
        for gap in packet["readiness"]["blocking_gaps"]
    )
