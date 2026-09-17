from editorial_desk.story_artifacts import _with_publication_readiness


def _candidate(candidate_type, *, depth="major_2_4_pages", visual="Use Player X in game action"):
    return {
        "candidate_id": f"candidate:{candidate_type}",
        "candidate_type": candidate_type,
        "depth_class": depth,
        "headline_packages": [
            {
                "headline": "Test headline",
                "image_suggestion": visual,
            }
        ],
        "evidence_refs": [
            {
                "evidence_id": f"evidence:{candidate_type}",
                "source": "chronicle" if candidate_type in {"rivalry_history", "playoff_rematch"} else "snapshot",
                "description": "test evidence",
            }
        ],
        "facts": [],
    }


def _packet(candidates, *, rankings=False, war=False):
    return {
        "publication_key": "ironbound_weekly",
        "status": "available",
        "candidates": candidates,
        "external_inputs": {
            "official_power_rankings": rankings,
            "war": war,
        },
    }


def _snapshot(*, player_stats="available", snap_counts="available", play_by_play="available"):
    return {
        "nfl_context": {
            "player_stats": {"status": player_stats, "records": [{}] if player_stats == "available" else []},
            "snap_counts": {"status": snap_counts, "records": [{}] if snap_counts == "available" else []},
            "play_by_play": {"status": play_by_play, "records": [{}] if play_by_play == "available" else []},
        }
    }


def test_readiness_requires_official_power_rankings_for_final_flagship_publication():
    result = _with_publication_readiness(
        _packet([_candidate("rivalry_history")]),
        _snapshot(),
    )

    readiness = result["publication_readiness"]
    assert readiness["ready_for_final_publication"] is False
    assert any(item["input"] == "official_power_rankings" for item in readiness["required_before_publication"])


def test_readiness_does_not_request_rankings_when_already_supplied():
    result = _with_publication_readiness(
        _packet([_candidate("rivalry_history")], rankings=True),
        _snapshot(),
    )

    readiness = result["publication_readiness"]
    assert not any(item["input"] == "official_power_rankings" for item in readiness["required_before_publication"])
    assert any(item["input"] == "official_power_rankings" for item in readiness["no_action_needed"])


def test_readiness_requests_war_only_when_relevant_story_family_would_benefit():
    relevant = _with_publication_readiness(
        _packet([_candidate("roster_architecture")], rankings=True),
        _snapshot(),
    )["publication_readiness"]
    irrelevant = _with_publication_readiness(
        _packet([_candidate("scoring_record")], rankings=True),
        _snapshot(),
    )["publication_readiness"]

    assert any(item["input"] == "war" for item in relevant["optional_enrichment"])
    assert not any(item["input"] == "war" for item in irrelevant["optional_enrichment"])


def test_readiness_acknowledges_nflverse_sources_already_available():
    readiness = _with_publication_readiness(
        _packet([_candidate("trade_afterlife")], rankings=True, war=True),
        _snapshot(),
    )["publication_readiness"]

    available = {item["input"] for item in readiness["no_action_needed"]}
    assert {"nflverse_player_stats", "nflverse_snap_counts", "nflverse_play_by_play"} <= available
    assert not any("usage" in item["request"].lower() for item in readiness["optional_enrichment"])


def test_readiness_requests_missing_usage_context_only_for_player_or_game_story_that_can_use_it():
    readiness = _with_publication_readiness(
        _packet([_candidate("trade_afterlife")], rankings=True, war=True),
        _snapshot(snap_counts="unavailable", play_by_play="unavailable"),
    )["publication_readiness"]

    requested = {item["input"] for item in readiness["optional_enrichment"]}
    assert "usage_context" in requested
    assert "game_context" in requested


def test_readiness_surfaces_commissioner_judgment_and_visual_sourcing_from_candidates():
    readiness = _with_publication_readiness(
        _packet(
            [
                _candidate("rivalry_history", visual="Source a rivalry matchup image"),
                _candidate("reaction_transaction", visual="Source the injured player and add"),
            ],
            rankings=True,
        ),
        _snapshot(),
    )["publication_readiness"]

    judgment_types = {item["candidate_type"] for item in readiness["commissioner_judgment"]}
    visual_types = {item["candidate_type"] for item in readiness["visuals_to_source_or_approve"]}
    assert {"rivalry_history", "reaction_transaction"} <= judgment_types
    assert {"rivalry_history", "reaction_transaction"} <= visual_types


def test_readiness_flags_incomplete_historical_coverage_without_claiming_history_is_missing():
    candidate = _candidate("rivalry_history")
    candidate["facts"] = [
        {
            "statement": "Series has four recorded meetings",
            "coverage_complete": False,
            "provenance": "chronicle_derived",
        }
    ]
    readiness = _with_publication_readiness(
        _packet([candidate], rankings=True),
        _snapshot(),
    )["publication_readiness"]

    assert any(item["input"] == "historical_context" for item in readiness["optional_enrichment"])
    assert any(item["input"] == "chronicle_history" for item in readiness["no_action_needed"])
