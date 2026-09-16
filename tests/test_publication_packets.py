from editorial_desk.config import (
    FeatureContractConfig,
    FeatureDependencyConfig,
    PublicationConfig,
)
from editorial_desk.publication_packets import build_publication_packet


def _publication(key, name, contracts):
    return PublicationConfig(
        key=key,
        name=name,
        tier="newspaper",
        source_files=(),
        recurring_sections=(),
        brand_departments=(),
        editorial_priorities=(),
        feature_contracts={"weekly": tuple(contracts), "preseason": ()},
    )


def _snapshot(*, healthy=True):
    snapshot = {
        "week": 1,
        "league": {"roster_positions": ["QB", "BN"]},
        "users": [
            {"user_id": "u1", "display_name": "One", "metadata": {"team_name": "One"}},
            {"user_id": "u2", "display_name": "Two", "metadata": {"team_name": "Two"}},
        ],
        "rosters": [
            {"roster_id": 1, "owner_id": "u1", "players": ["q1", "b1"]},
            {"roster_id": 2, "owner_id": "u2", "players": ["q2", "b2"]},
        ],
        "matchups": [
            {"matchup_id": 1, "roster_id": 1, "points": 20, "starters": ["q1"], "players": ["q1", "b1"], "players_points": {"q1": 20, "b1": 5}},
            {"matchup_id": 1, "roster_id": 2, "points": 18, "starters": ["q2"], "players": ["q2", "b2"], "players_points": {"q2": 18, "b2": 25}},
        ],
        "ranking_inputs": {},
        "nfl_context": {},
        "transactions": [],
    }
    if healthy:
        snapshot["players"] = {
            "q1": {"full_name": "Q One", "position": "QB", "fantasy_positions": ["QB"], "status": "Active"},
            "b1": {"full_name": "B One", "position": "QB", "fantasy_positions": ["QB"], "status": "Active"},
            "q2": {"full_name": "Q Two", "position": "QB", "fantasy_positions": ["QB"], "status": "Active"},
            "b2": {"full_name": "B Two", "position": "QB", "fantasy_positions": ["QB"], "status": "Active"},
        }
    return snapshot


def _dossier():
    return {
        "scoreboard": [
            {"winner": {"roster_id": 1, "team": "One", "points": 20}, "loser": {"roster_id": 2, "team": "Two", "points": 18}, "margin": 2}
        ],
        "standings": [{"roster_id": 1, "team": "One", "wins": 1}],
        "awards": {"manager_of_the_week": {"roster_id": 1, "team": "One"}},
        "lineup_efficiency": [{"roster_id": 1, "efficiency": 1.0}],
        "weekly_features": {},
        "record_watch": [],
    }


def test_healthy_rosters_with_zero_flags_are_ready_no_items():
    publication = _publication(
        "ballad",
        "Ballad",
        [
            FeatureContractConfig(
                feature="health_status",
                display_name="Ward Report",
                required_in_phase=True,
                dependencies=(FeatureDependencyConfig("sleeper_health", "required"),),
            )
        ],
    )
    packet = build_publication_packet(_snapshot(), _dossier(), publication, "weekly")
    department = packet["departments"][0]
    assert department["status"] == "ready_no_items"
    assert department["data"] == []


def test_missing_health_source_makes_required_department_unavailable():
    publication = _publication(
        "ballad",
        "Ballad",
        [
            FeatureContractConfig(
                feature="health_status",
                display_name="Ward Report",
                required_in_phase=True,
                dependencies=(FeatureDependencyConfig("sleeper_health", "required"),),
            )
        ],
    )
    packet = build_publication_packet(_snapshot(healthy=False), _dossier(), publication, "weekly")
    department = packet["departments"][0]
    assert department["status"] == "unavailable"
    assert "Sleeper" in department["reason"]


def test_shared_lineup_flip_payload_is_unchanged_across_themed_department_names():
    contracts = [FeatureContractConfig("lineup_flip_candidates", "PLACEHOLDER", True)]
    names = {
        "ballad": "Weekly Rounds",
        "saturday": "Portal Film Room",
        "hollywood": "Cutting Room Floor",
    }
    payloads = []
    for key, display_name in names.items():
        publication = _publication(
            key,
            key.title(),
            [FeatureContractConfig("lineup_flip_candidates", display_name, True)],
        )
        packet = build_publication_packet(_snapshot(), _dossier(), publication, "weekly")
        department = packet["departments"][0]
        assert department["display_name"] == display_name
        assert department["status"] == "ready"
        payloads.append(department["data"])
    assert payloads[0] == payloads[1] == payloads[2]


def test_missing_preferred_dependency_marks_ready_feature_degraded_not_unavailable():
    publication = _publication(
        "paper",
        "Paper",
        [
            FeatureContractConfig(
                feature="weekly_results",
                display_name="Scoreboard",
                required_in_phase=True,
                dependencies=(FeatureDependencyConfig("optional_model", "preferred"),),
            )
        ],
    )
    packet = build_publication_packet(_snapshot(), _dossier(), publication, "weekly")
    department = packet["departments"][0]
    assert department["status"] == "ready"
    assert department["degraded"] is True
    assert "optional_model" in department["dependency_warnings"][0]


def test_missing_optional_dependency_does_not_penalize_readiness():
    publication = _publication(
        "paper",
        "Paper",
        [
            FeatureContractConfig(
                feature="weekly_results",
                display_name="Scoreboard",
                required_in_phase=True,
                dependencies=(FeatureDependencyConfig("nice_to_have", "optional"),),
            )
        ],
    )
    packet = build_publication_packet(_snapshot(), _dossier(), publication, "weekly")
    department = packet["departments"][0]
    assert department["status"] == "ready"
    assert department["degraded"] is False


def test_phase_filtering_does_not_pull_preseason_departments_into_weekly_packet():
    publication = PublicationConfig(
        key="paper",
        name="Paper",
        tier="newspaper",
        source_files=(),
        recurring_sections=(),
        brand_departments=(),
        editorial_priorities=(),
        feature_contracts={
            "weekly": (FeatureContractConfig("weekly_results", "Scoreboard", True),),
            "preseason": (FeatureContractConfig("draft_results", "Draft Desk", True),),
        },
    )
    packet = build_publication_packet(_snapshot(), _dossier(), publication, "weekly")
    assert [row["display_name"] for row in packet["departments"]] == ["Scoreboard"]
