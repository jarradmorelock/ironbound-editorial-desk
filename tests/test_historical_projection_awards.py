from editorial_desk import weekly_features
from editorial_desk.external_inputs import ExternalEditorialInputs, OfficialPowerRanking
from editorial_desk.honors import LABELS, research_honors
from editorial_desk.metrics import build_weekly_dossier


def _snapshot():
    return {
        "collected_at": "2026-09-30T14:00:00Z",
        "week": 3,
        "league": {
            "season": "2026",
            "roster_positions": ["QB", "BN"],
            "scoring_settings": {"pass_td": 6.0, "pass_yd": 0.04},
        },
        "editorial": {"league_key": "test"},
        "users": [],
        "players": {
            "a": {"position": "QB", "full_name": "Starter A"},
            "b": {"position": "QB", "full_name": "Bench B"},
            "o": {"position": "QB", "full_name": "Opponent O"},
        },
        "rosters": [
            {"roster_id": 1, "players": ["a", "b"]},
            {"roster_id": 2, "players": ["o"]},
        ],
        "matchups": [
            {
                "roster_id": 1,
                "matchup_id": 1,
                "points": 30.0,
                "players": ["a", "b"],
                "starters": ["a"],
                "players_points": {"a": 30.0, "b": 0.0},
            },
            {
                "roster_id": 2,
                "matchup_id": 1,
                "points": 20.0,
                "players": ["o"],
                "starters": ["o"],
                "players_points": {"o": 20.0},
            },
        ],
        "ranking_inputs": {
            "sleeper_projections": {
                "status": "available",
                "season": "2026",
                "week": 3,
                "players": {
                    # Exact league scoring should produce 12, 18, and 30.
                    "a": {"pass_td": 2.0, "pass_yd": 0.0},
                    "b": {"pass_td": 3.0, "pass_yd": 0.0},
                    "o": {"pass_td": 5.0, "pass_yd": 0.0},
                },
            }
        },
        "flagship_sleeper": {"schedule": {"weeks": {}}},
        "transactions": [],
    }


def _evaluate(snapshot):
    dossier = weekly_features.apply_weekly_features(snapshot, build_weekly_dossier(snapshot))
    external = ExternalEditorialInputs(
        "ironbound_weekly",
        official_power_rankings=(
            OfficialPowerRanking(None, 1, roster_id=1, previous_rank=5),
            OfficialPowerRanking(None, 2, roster_id=2, previous_rank=6),
        ),
        source_metadata={"results_through_week": 3, "ranking_week": 4},
    )
    return research_honors(snapshot, dossier, external)


def _types(result, roster_id=1):
    return {
        row["candidate_type"]
        for row in result["rotating_award_candidates"]
        if row["roster_id"] == roster_id
    }


def test_retained_same_week_sleeper_projections_are_valid_after_games_finish():
    result = _evaluate(_snapshot())

    assert "IRON_BALLS" in _types(result)
    assert "NO_FEAR" in _types(result)
    assert result["award_availability"]["IRON_BALLS"]["status"] == "AVAILABLE"
    assert result["award_availability"]["NO_FEAR"]["status"] == "AVAILABLE"

    iron_balls = next(
        row for row in result["rotating_award_candidates"]
        if row["candidate_type"] == "IRON_BALLS"
    )
    decision = iron_balls["evidence"]["decisions"][0]
    assert decision["started_projection"] == 12.0
    assert decision["alternative_projection"] == 18.0

    no_fear = next(
        row for row in result["rotating_award_candidates"]
        if row["candidate_type"] == "NO_FEAR"
    )
    assert no_fear["evidence"]["projected_deficit"] == 18.0


def test_retained_sleeper_projections_must_match_issue_season_and_week():
    snapshot = _snapshot()
    snapshot["ranking_inputs"]["sleeper_projections"]["week"] = 2

    result = _evaluate(snapshot)

    assert "IRON_BALLS" not in _types(result)
    assert result["award_availability"]["IRON_BALLS"]["status"] == "UNAVAILABLE"
    assert "same-season/week" in result["award_availability"]["IRON_BALLS"]["reason"]


def test_award_audit_explains_qualified_and_failed_rules():
    result = _evaluate(_snapshot())
    audit = result["award_audit"]

    assert set(LABELS) <= set(audit)
    assert audit["IRON_BALLS"]["qualified_candidate_ids"]

    rivet_rows = audit["BY_A_RIVET"]["evaluations"]
    assert any(
        row["roster_id"] == 1
        and row["result"] == "NOT_QUALIFIED"
        and row["metrics"]["margin"] == 10.0
        and row["metrics"]["threshold"] == 1.0
        for row in rivet_rows
    )

    hammer_rows = audit["HAMMER_DROP"]["evaluations"]
    assert any(
        row["roster_id"] == 1
        and row["result"] == "NOT_QUALIFIED"
        and row["metrics"]["margin"] == 10.0
        and row["metrics"]["threshold"] == 50.0
        for row in hammer_rows
    )


def test_unprojected_fringe_bench_player_does_not_disable_evaluable_awards():
    snapshot = _snapshot()
    snapshot["players"]["fringe"] = {"position": "WR", "full_name": "Fringe Bench"}
    snapshot["rosters"][0]["players"].append("fringe")
    snapshot["matchups"][0]["players"].append("fringe")
    snapshot["matchups"][0]["players_points"]["fringe"] = 1.0

    result = _evaluate(snapshot)

    assert result["award_availability"]["IRON_BALLS"]["status"] == "AVAILABLE"
    assert result["award_availability"]["NO_FEAR"]["status"] == "AVAILABLE"
    assert "IRON_BALLS" in _types(result)
    assert "NO_FEAR" in _types(result)


def test_full_forge_is_roster_specific_when_other_roster_projection_is_missing():
    snapshot = _snapshot()
    # Team 1 starter has a verified projection and beats it.
    snapshot["matchups"][0]["players_points"]["a"] = 20.0
    snapshot["matchups"][0]["points"] = 20.0
    # Remove only the opponent starter's projection. Team 1 can still be
    # evaluated for Full Forge even though the matchup cannot support No Fear.
    del snapshot["ranking_inputs"]["sleeper_projections"]["players"]["o"]

    result = _evaluate(snapshot)

    assert result["award_availability"]["FULL_FORGE"]["status"] in {"AVAILABLE", "PARTIAL"}
    assert "FULL_FORGE" in _types(result)
    assert result["award_availability"]["NO_FEAR"]["status"] in {"PARTIAL", "UNAVAILABLE"}
