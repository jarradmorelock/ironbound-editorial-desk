import json
from pathlib import Path

import pytest

from editorial_desk.config import ConfigurationError, load_publications


ROOT = Path(__file__).resolve().parents[1]


def _features(profile, phase):
    return {contract.feature: contract for contract in profile.contracts_for(phase)}


def test_story_desk_is_explicitly_enabled_only_for_ironbound_and_unbound():
    publications = load_publications(ROOT / "config" / "publications.json")
    assert publications["ironbound_weekly"].story_desk is True
    assert publications["unbound_weekly"].story_desk is True
    for key in (
        "ballad_crier",
        "the_stampede",
        "volunteer_voice",
        "saturday_standard",
        "hollywood_beat",
    ):
        assert publications[key].story_desk is False


def test_volunteer_voice_contract_has_no_division_features_or_labels():
    publications = load_publications(ROOT / "config" / "publications.json")
    weekly = publications["volunteer_voice"].contracts_for("weekly")
    features = {row.feature for row in weekly}
    assert "division_metrics" not in features
    assert "divisional_started_mvps" not in features
    assert all("division" not in row.display_name.casefold() for row in weekly)
    assert _features(publications["volunteer_voice"], "weekly")[
        "league_wide_started_mvp"
    ].display_name == "Mountain MVP"


def test_saturday_standard_keeps_divisions_and_idp_first_class():
    publications = load_publications(ROOT / "config" / "publications.json")
    weekly = _features(publications["saturday_standard"], "weekly")
    assert weekly["division_metrics"].display_name == "East and West Division Pulse"
    assert "divisional_started_mvps" in weekly
    assert "idp_position_metrics" in weekly


def test_stampede_workload_department_uses_locked_name_and_no_retired_label():
    publications = load_publications(ROOT / "config" / "publications.json")
    weekly = _features(publications["the_stampede"], "weekly")
    assert weekly["workload_stat_lines"].display_name == "What a Way to Make a Living"
    document = (ROOT / "config" / "publications.json").read_text(encoding="utf-8")
    assert "Heavy Lifting" not in document


def test_hollywood_beat_has_complete_weekly_contract():
    publications = load_publications(ROOT / "config" / "publications.json")
    weekly = {row.display_name for row in publications["hollywood_beat"].contracts_for("weekly")}
    assert {
        "Box Office",
        "Marquee / Official Standings",
        "Top Billing / First Cut",
        "Hollywood Board",
        "Monday Night / Late Show",
        "For Your Consideration",
        "Cutting Room Floor",
        "Studio Efficiency",
        "Casting Call",
        "Production Delays",
        "Dailies / Backlot Reports",
        "This Week's Bill",
    } <= weekly


def test_contracts_are_phase_aware_and_preseason_does_not_leak_into_weekly():
    publications = load_publications(ROOT / "config" / "publications.json")
    ballad = publications["ballad_crier"]
    weekly = {row.display_name for row in ballad.contracts_for("weekly")}
    preseason = {row.display_name for row in ballad.contracts_for("preseason")}
    assert "Weekly Rounds" in weekly
    assert "Draft Desk" not in weekly
    assert "Draft Desk" in preseason
    assert "Streamers' Pact" in preseason


def test_dependency_strengths_are_parsed():
    publications = load_publications(ROOT / "config" / "publications.json")
    health = _features(publications["ballad_crier"], "weekly")["health_status"]
    assert health.dependencies
    assert {row.strength for row in health.dependencies} <= {
        "required",
        "preferred",
        "optional",
    }


def test_duplicate_feature_ids_in_same_phase_are_rejected(tmp_path):
    path = tmp_path / "publications.json"
    path.write_text(
        json.dumps(
            {
                "publications": [
                    {
                        "key": "paper",
                        "name": "Paper",
                        "tier": "newspaper",
                        "feature_contracts": {
                            "weekly": [
                                {"feature": "scores", "display_name": "Scores", "required_in_phase": True},
                                {"feature": "scores", "display_name": "Again", "required_in_phase": True},
                            ]
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="Duplicate feature"):
        load_publications(path)


def test_invalid_dependency_strength_is_rejected(tmp_path):
    path = tmp_path / "publications.json"
    path.write_text(
        json.dumps(
            {
                "publications": [
                    {
                        "key": "paper",
                        "name": "Paper",
                        "tier": "newspaper",
                        "feature_contracts": {
                            "weekly": [
                                {
                                    "feature": "scores",
                                    "display_name": "Scores",
                                    "required_in_phase": True,
                                    "dependencies": [
                                        {"source": "weekly_results", "strength": "sometimes"}
                                    ],
                                }
                            ]
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="strength"):
        load_publications(path)


def test_missing_contract_display_name_is_rejected(tmp_path):
    path = tmp_path / "publications.json"
    path.write_text(
        json.dumps(
            {
                "publications": [
                    {
                        "key": "paper",
                        "name": "Paper",
                        "tier": "newspaper",
                        "feature_contracts": {
                            "weekly": [
                                {"feature": "scores", "required_in_phase": True}
                            ]
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="display_name"):
        load_publications(path)
