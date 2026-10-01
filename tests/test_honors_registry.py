from copy import deepcopy
import pytest
from editorial_desk import weekly_features
from editorial_desk.external_inputs import ExternalEditorialInputs, OfficialPowerRanking
from editorial_desk.metrics import build_weekly_dossier


def fixture(scores=(30, 20), projections=(10, 20), opponent=25, slots=None):
    slots = slots or ["QB"]
    s = {
        "collected_at": "2026-09-29T22:00:00Z",
        "week": 3,
        "league": {"season": "2026", "roster_positions": slots + ["BN"]},
        "editorial": {"league_key": "test"},
        "users": [],
        "players": {
            "a": {"position": "QB", "full_name": "A"},
            "b": {"position": "QB", "full_name": "B"},
            "o": {"position": "QB", "full_name": "O"},
        },
        "rosters": [
            {"roster_id": 1, "players": ["a", "b"]},
            {"roster_id": 2, "players": ["o"]},
        ],
        "matchups": [
            {
                "roster_id": 1,
                "matchup_id": 1,
                "points": scores[0],
                "players": ["a", "b"],
                "starters": ["a"],
                "players_points": dict(zip(["a", "b"], scores)),
            },
            {
                "roster_id": 2,
                "matchup_id": 1,
                "points": opponent,
                "players": ["o"],
                "starters": ["o"],
                "players_points": {"o": opponent},
            },
        ],
        "frozen_pregame_projections": {
            "season": "2026",
            "week": 3,
            "source": "saved-pregame",
            "captured_at": "2026-09-24T10:00:00Z",
            "first_kickoff_at": "2026-09-24T20:00:00Z",
            "player_points": dict(zip(["a", "b", "o"], [*projections, 25])),
            "matchup_points": {"1": 10, "2": 25},
        },
        "flagship_sleeper": {
            "schedule": {
                "weeks": {
                    "1": [
                        {"roster_id": 1, "matchup_id": 1, "points": 10},
                        {"roster_id": 2, "matchup_id": 1, "points": 20},
                    ],
                    "2": [
                        {"roster_id": 1, "matchup_id": 1, "points": 20},
                        {"roster_id": 2, "matchup_id": 1, "points": 10},
                    ],
                }
            }
        },
        "transactions": [],
    }
    return s


def evaluate(s, ranks=(12, 2)):
    from editorial_desk.honors import research_honors

    d = weekly_features.apply_weekly_features(s, build_weekly_dossier(s))
    ext = ExternalEditorialInputs(
        "ironbound_weekly",
        official_power_rankings=tuple(
            OfficialPowerRanking(None, 3 - i, roster_id=i, previous_rank=r)
            for i, r in enumerate(ranks, 1)
        ),
        source_metadata={"results_through_week": 3, "ranking_week": 4},
    )
    return research_honors(s, d, ext)


def types(result, roster=1):
    return {
        r["candidate_type"]
        for r in result["rotating_award_candidates"]
        if r["roster_id"] == roster
    }


def test_registry_exists_and_never_selects_winner():
    h = evaluate(fixture())
    assert h["selected_rotating_award"] is None
    assert {"IRON_BALLS", "AGAINST_ALL_ODDS", "ONE_MAN_FOUNDRY"} <= types(h)
    assert not {
        "NO_FEAR",
        "GIANT_KILLER",
        "OLD_SCORE_SETTLED",
        "REVENGE_OF_THE_FORGE",
    } & types(h)


@pytest.mark.parametrize(
    "code,scores,opponent",
    [
        ("BONE_HEAD", (20, 30), 25),
        ("BY_A_RIVET", (30, 20), 29),
        ("HAMMER_DROP", (75, 20), 25),
    ],
)
def test_threshold_rules(code, scores, opponent):
    assert code in types(evaluate(fixture(scores=scores, opponent=opponent)))


def test_missing_or_postgame_projections_fail_closed():
    for change in ("missing", "late", "wrong_week", "partial"):
        s = fixture()
        if change == "missing":
            s.pop("frozen_pregame_projections")
        elif change == "late":
            s["frozen_pregame_projections"]["captured_at"] = "2026-09-29T10:00:00Z"
        elif change == "wrong_week":
            s["frozen_pregame_projections"]["week"] = 2
        else:
            s["frozen_pregame_projections"]["player_points"].pop("b")
        s["ranking_inputs"] = {
            "sleeper_projections": {
                "status": "available",
                "players": {"a": {"pass_yd": 200}},
            }
        }
        h = evaluate(s)
        assert "IRON_BALLS" not in types(h)
        assert h["award_availability"]["IRON_BALLS"]["status"] == "UNAVAILABLE"


def test_giant_killer_uses_previous_rank_not_published_rank():
    s = fixture()
    s.pop("frozen_pregame_projections")
    assert "GIANT_KILLER" in types(evaluate(s))
    assert "GIANT_KILLER" not in types(evaluate(s, ranks=(2, 12)))


def test_overall_removed_from_position_and_bench_zero_is_valid():
    s = fixture(scores=(40, 0))
    d = weekly_features.apply_weekly_features(s, build_weekly_dossier(s))
    assert d["weekly_features"]["overall_player_of_the_week"]["player_id"] == "a"
    assert d["weekly_features"]["started_position_leaders"]["QB"]["player_id"] == "o"
    assert d["weekly_features"]["benchwarmer_of_the_week"]["player_id"] == "b"


def test_manager_internal_five_weights_and_public_facts_only():
    from editorial_desk.honors import manager_scores

    s = fixture()
    d = weekly_features.apply_weekly_features(s, build_weekly_dossier(s))
    ext = ExternalEditorialInputs(
        "ironbound_weekly",
        official_power_rankings=(
            OfficialPowerRanking(None, 1, roster_id=1, previous_rank=12),
            OfficialPowerRanking(None, 2, roster_id=2, previous_rank=2),
        ),
    )
    rows = manager_scores(s, d, ext)
    assert len(rows) == 2
    for r in rows:
        c = r["components"]
        assert r["score"] == pytest.approx(
            0.25 * c["result"]
            + 0.25 * c["efficiency"]
            + 0.20 * c["scoring"]
            + 0.15 * c["record_consistency"]
            + 0.15 * c["opponent_quality"]
        )
    h = evaluate(s)
    assert h["manager_of_the_week"]["roster_id"] == 1
    assert h["manager_of_the_week"]["opponent_entering_power_rank"] == 2
    assert "components" not in h["manager_of_the_week"]


def lineup_fixture(
    start_points=(30, 20), bench_points=(10, 5), projected=(10, 10, 20, 20), opponent=45
):
    s = fixture(slots=["QB", "SUPER_FLEX"], opponent=opponent)
    ids = ["a", "c", "b", "d"]
    s["players"].update({p: {"position": "QB", "full_name": p.upper()} for p in ids})
    m = s["matchups"][0]
    m.update(
        starters=["a", "c"],
        players=ids,
        points=sum(start_points),
        players_points=dict(zip(ids, [*start_points, *bench_points])),
    )
    s["rosters"][0]["players"] = ids
    s["frozen_pregame_projections"]["player_points"].update(dict(zip(ids, projected)))
    return s


def test_mad_blacksmith_suppresses_base_and_requires_independent_decisions():
    assert "MAD_BLACKSMITH" in types(evaluate(lineup_fixture()))
    assert "IRON_BALLS" not in types(evaluate(lineup_fixture()))
    s = lineup_fixture()
    s["matchups"][0]["players"].remove("d")
    assert "MAD_BLACKSMITH" not in types(evaluate(s))
    assert "IRON_BALLS" in types(evaluate(s))


def test_legal_flex_rearrangement_and_illegal_alternative():
    s = lineup_fixture(start_points=(30, 20), bench_points=(0, 0), opponent=40)
    s["league"]["roster_positions"] = ["RB", "FLEX", "BN"]
    for p, pos in [("a", "RB"), ("c", "RB"), ("b", "WR"), ("d", "QB")]:
        s["players"][p]["position"] = pos
    rows = evaluate(s)["rotating_award_candidates"]
    decisions = next(
        r["evidence"]["decisions"] for r in rows if r["candidate_type"] == "IRON_BALLS"
    )
    assert any(
        d["started_player_id"] == "a" and d["alternative_player_id"] == "b"
        for d in decisions
    )
    assert all(d["alternative_player_id"] != "d" for d in decisions)


def test_left_on_anvil_collective_only_and_bone_head_suppression():
    s = lineup_fixture(start_points=(10, 10), bench_points=(16, 16), opponent=30)
    assert "LEFT_ON_THE_ANVIL" in types(evaluate(s))
    s["matchups"][0]["players_points"]["b"] = 21
    h = evaluate(s)
    assert "BONE_HEAD" in types(h) and "LEFT_ON_THE_ANVIL" not in types(h)
    s["matchups"][0]["players_points"].update(b=15, d=15)
    assert "LEFT_ON_THE_ANVIL" not in types(evaluate(s))  # optimal ties, does not win


@pytest.mark.parametrize(
    "won,projection,margin,expected",
    [
        (False, 10, 10, True),
        (False, 9.99, 5, False),
        (False, 10, 10.01, False),
        (True, 10, 1, True),
    ],
)
def test_zero_rules(won, projection, margin, expected):
    s = lineup_fixture(
        start_points=(0, 30),
        projected=(projection, 20, 25, 25),
        opponent=30 - margin if won else 30 + margin,
    )
    assert (("TEMPERED" if won else "GOOSED") in types(evaluate(s))) == expected


@pytest.mark.parametrize("code,change", [("BY_A_RIVET", 1.01), ("HAMMER_DROP", 49.99)])
def test_margin_outside_threshold(code, change):
    assert code not in types(evaluate(fixture(scores=(100, 0), opponent=100 - change)))


def test_upset_base_labels_and_boundaries():
    s = fixture()
    s["frozen_pregame_projections"]["matchup_points"]["2"] = 24.99
    assert "NO_FEAR" not in types(evaluate(s, ranks=(2, 3)))
    assert "GIANT_KILLER" in types(evaluate(s, ranks=(10, 2)))
    assert "GIANT_KILLER" not in types(evaluate(s, ranks=(9, 2)))
    s["frozen_pregame_projections"]["matchup_points"]["2"] = 25
    assert "NO_FEAR" in types(evaluate(s, ranks=(2, 3)))


def test_full_forge_all_starters_and_win_required():
    s = lineup_fixture(start_points=(10, 20), projected=(10, 20, 5, 5), opponent=25)
    assert "FULL_FORGE" in types(evaluate(s))
    s["frozen_pregame_projections"]["player_points"]["c"] = 20.01
    assert "FULL_FORGE" not in types(evaluate(s))
    s["matchups"][1]["points"] = 40
    assert "FULL_FORGE" not in types(evaluate(s))


@pytest.mark.parametrize(
    "kind,bid,code,modifier",
    [
        ("waiver", 0, "SCRAPHEAP_SAVIOR", True),
        ("free_agent", None, "SCRAPHEAP_SAVIOR", True),
        ("waiver", 12, "SCRAPHEAP_SAVIOR", False),
        ("trade", None, "HOT_OFF_THE_ANVIL", False),
    ],
)
def test_acquisitions_and_free_modifier(kind, bid, code, modifier):
    s = fixture()
    tx = {
        "transaction_id": "t",
        "status": "complete",
        "type": kind,
        "adds": {"a": 1},
        "drops": {},
        "settings": {"waiver_bid": bid},
    }
    s["transactions"] = [tx, deepcopy(tx)]
    rows = [
        r
        for r in evaluate(s)["rotating_award_candidates"]
        if r["candidate_type"] == code
    ]
    assert len(rows) == 1
    assert ("FOUND_STEEL" in rows[0]["modifiers"]) == modifier
    s["flagship_sleeper"]["transactions"] = {"weeks": {"2": [tx]}}
    s["transactions"] = []
    assert code not in types(evaluate(s))


@pytest.mark.parametrize("kind", ["trade", "free_agent"])
def test_former_player_dropped_or_traded(kind):
    s = fixture()
    s["flagship_sleeper"]["transactions"] = {
        "weeks": {
            "1": [
                {
                    "transaction_id": "old",
                    "status": "complete",
                    "type": kind,
                    "drops": {"a": 2},
                    "adds": {},
                }
            ]
        }
    }
    assert "CUT_BY_YOUR_OWN_BLADE" in types(evaluate(s))
    s["flagship_sleeper"]["transactions"]["weeks"]["1"][0]["drops"] = {"a": 1}
    assert "CUT_BY_YOUR_OWN_BLADE" not in types(evaluate(s))


def test_reforged_needs_prior_loss_and_40_point_improvement():
    s = fixture(scores=(60, 0), opponent=25)
    prior = s["flagship_sleeper"]["schedule"]["weeks"]["2"]
    prior[1]["points"] = 30
    assert "REFORGED" in types(evaluate(s))
    s["matchups"][0]["points"] = 59.99
    assert "REFORGED" not in types(evaluate(s))
    s["matchups"][0]["points"] = 60
    prior[1]["points"] = 10
    assert "REFORGED" not in types(evaluate(s))


def test_one_hand_tied_two_starters_and_faab_review_only():
    s = lineup_fixture(start_points=(2, 3), opponent=4)
    assert "ONE_HAND_TIED" in types(evaluate(s))
    s["matchups"][0]["players_points"]["c"] = 3.01
    assert "ONE_HAND_TIED" not in types(evaluate(s))
    s["transactions"] = [
        {
            "transaction_id": "faab",
            "type": "waiver",
            "status": "complete",
            "adds": {"b": 1},
            "settings": {"waiver_bid": 50},
        }
    ]
    s["matchups"][0]["players_points"]["b"] = 0
    h = evaluate(s)
    assert "FAAB_FURNACE" not in types(h)
    assert h["rotating_award_manual_review"][0]["status"] == "MANUAL_REVIEW"
    assert h["award_availability"]["THE_SPOILER"]["status"] == "UNSUPPORTED"


def test_anvil_to_anvil_top_four_and_winner_only():
    s = fixture()
    for rid in range(3, 7):
        s["rosters"].append({"roster_id": rid})
    for rid, score in [(3, 100), (4, 90), (5, 80), (6, 70)]:
        s["matchups"].append(
            {
                "roster_id": rid,
                "matchup_id": (rid + 1) // 2,
                "points": score,
                "starters": [],
                "players": [],
            }
        )
    assert "ANVIL_TO_ANVIL" not in types(evaluate(s))
    assert "ANVIL_TO_ANVIL" in types(evaluate(s), 3)
    assert "ANVIL_TO_ANVIL" not in types(evaluate(s), 4)


def test_five_distinct_player_winners_when_available():
    s = fixture()
    m = s["matchups"][0]
    for p, pos, pts in [("rb", "RB", 20), ("wr", "WR", 20), ("te", "TE", 20)]:
        s["players"][p] = {"position": pos, "full_name": p}
        m["players"].append(p)
        m["starters"].append(p)
        m["players_points"][p] = pts
    d = weekly_features.apply_weekly_features(s, build_weekly_dossier(s))[
        "weekly_features"
    ]
    ids = [d["overall_player_of_the_week"]["player_id"]] + [
        r["player_id"] for r in d["started_position_leaders"].values()
    ]
    assert len(ids) == len(set(ids)) == 5


def test_manager_ranking_changes_opponent_quality_only():
    from editorial_desk.honors import manager_scores

    s = fixture()
    d = weekly_features.apply_weekly_features(s, build_weekly_dossier(s))

    def scores(rank, previous):
        e = ExternalEditorialInputs(
            "ironbound_weekly",
            official_power_rankings=(
                OfficialPowerRanking(None, rank, roster_id=2, previous_rank=previous),
            ),
        )
        return {r["facts"]["roster_id"]: r for r in manager_scores(s, d, e)}

    assert scores(1, 2)[1]["score"] == scores(12, 2)[1]["score"]
    assert (
        scores(1, 1)[1]["components"]["opponent_quality"]
        > scores(1, 12)[1]["components"]["opponent_quality"]
    )


def test_no_loss_auto_award_and_no_postweek_record_leak():
    s = fixture()
    h = evaluate(s)
    for r in s["rosters"]:
        r["settings"] = {"wins": 999, "losses": 0}
    assert evaluate(s)["manager_of_the_week"] == h["manager_of_the_week"]
    assert h["manager_of_the_week"]["head_to_head_result"] == "win"


def test_stale_handoff_cannot_be_used_as_entering_ranks():
    from editorial_desk.honors import research_honors

    s = fixture()
    d = weekly_features.apply_weekly_features(s, build_weekly_dossier(s))
    ext = ExternalEditorialInputs(
        "ironbound_weekly",
        official_power_rankings=(
            OfficialPowerRanking(None, 1, roster_id=1, previous_rank=12),
            OfficialPowerRanking(None, 2, roster_id=2, previous_rank=2),
        ),
        source_metadata={"results_through_week": 2, "ranking_week": 3},
    )
    h = research_honors(s, d, ext)
    assert "AGAINST_ALL_ODDS" not in types(h)
    assert h["manager_of_the_week"]["opponent_entering_power_rank"] is None


def test_season_boards_merge_current_week_and_exclude_future(tmp_path):
    from editorial_desk.flagship_research import (
        _season_efficiency_top_three,
        _season_team_score_top_three,
    )

    s = fixture()
    s["week"] = 2

    class Chronicle:
        def season_efficiency(self, *args):
            return [
                {"week": 1, "roster_id": 1, "actual_points": 10, "optimal_points": 20},
                {
                    "week": 9,
                    "roster_id": 1,
                    "actual_points": 500,
                    "optimal_points": 500,
                },
            ]

        def season_matchup_finals(self, *args):
            return [
                {"week": 1, "roster_id": 1, "points": 10},
                {"week": 9, "roster_id": 1, "points": 999},
            ]

    history = [
        {
            "week": 1,
            "lineup_efficiency": [
                {
                    "roster_id": 1,
                    "team": "Roster 1",
                    "actual_points": 10,
                    "optimal_points": 20,
                },
                {
                    "roster_id": 2,
                    "team": "Roster 2",
                    "actual_points": 20,
                    "optimal_points": 20,
                },
            ],
        },
        {
            "week": 9,
            "scoreboard": [
                {"teams": [{"roster_id": 1, "team": "Roster 1", "points": 999}]}
            ],
        },
    ]
    args = {
        "snapshot": s,
        "league_key": "test",
        "season": "2026",
        "chronicle": Chronicle(),
    }
    rows = _season_efficiency_top_three(history, **args)
    one = next(r for r in rows if r["team"] == "Roster 1")
    assert (
        one["weeks"] == 2 and one["actual_points"] == 40 and one["optimal_points"] == 50
    )
    score_rows = _season_team_score_top_three(history, **args)
    score_one = next(r for r in score_rows if r["roster_id"] == 1)
    assert score_one["score"] == 40
    assert score_one["weeks"] == 2
    assert all(r["through_week"] == 2 for r in score_rows)


def test_exceptional_loss_is_review_only():
    from editorial_desk.honors import manager_honor

    s = fixture()
    values = [30, 31, 20, 10, 15, 5, 12, 2]
    s["rosters"] = [{"roster_id": i} for i in range(1, 9)]
    s["matchups"] = [
        {"roster_id": i, "matchup_id": (i + 1) // 2, "points": v}
        for i, v in enumerate(values, 1)
    ]
    d = {
        "lineup_efficiency": [
            {"roster_id": i, "actual_points": v, "efficiency": 1}
            for i, v in enumerate(values, 1)
        ]
    }
    e = ExternalEditorialInputs(
        "ironbound_weekly",
        official_power_rankings=(
            OfficialPowerRanking(None, 8, roster_id=2, previous_rank=1),
        ),
    )
    winner, review = manager_honor(s, d, e)
    assert winner["head_to_head_result"] == "win"
    assert [r["roster_id"] for r in review] == [1]
    assert review[0]["status"] == "MANUAL_REVIEW"
    s["matchups"][0]["points"] = 29.99
    assert manager_honor(s, d, e)[1] == []


def test_one_man_foundry_threshold_is_lineup_total():
    s = lineup_fixture(start_points=(40, 30), bench_points=(0, 30), opponent=25)
    s["league"]["roster_positions"] = ["QB", "SUPER_FLEX", "SUPER_FLEX", "BN"]
    s["matchups"][0]["starters"].append("d")
    s["matchups"][0]["points"] = 100
    assert "ONE_MAN_FOUNDRY" in types(evaluate(s))
    s["matchups"][0]["players_points"]["a"] = 39.99
    assert "ONE_MAN_FOUNDRY" not in types(evaluate(s))


def test_chronicle_former_player_history():
    from editorial_desk.honors import research_honors

    s = fixture()
    d = weekly_features.apply_weekly_features(s, build_weekly_dossier(s))

    class Chronicle:
        def season_matchup_finals(self, *args):
            return []

        def league_events(self, *args):
            return [
                {
                    "season": "2026",
                    "week": 1,
                    "event_id": "event1",
                    "evidence": {
                        "transaction_id": "t",
                        "type": "trade",
                        "drops": {"a": 2},
                        "adds": {"a": 1},
                    },
                }
            ]

    h = research_honors(
        s, d, ExternalEditorialInputs("ironbound_weekly"), chronicle=Chronicle()
    )
    assert "CUT_BY_YOUR_OWN_BLADE" in types(h)
    assert "HOT_OFF_THE_ANVIL" not in types(h)


def test_mad_blacksmith_requires_jointly_legal_independent_alternatives():
    s = lineup_fixture(start_points=(30, 20), bench_points=(0, 0), opponent=40)
    s["league"]["roster_positions"] = ["RB", "FLEX", "BN"]
    for p, pos in [("a", "RB"), ("c", "RB"), ("b", "WR"), ("d", "WR")]:
        s["players"][p]["position"] = pos
    assert "IRON_BALLS" in types(evaluate(s))
    assert "MAD_BLACKSMITH" not in types(evaluate(s))


def test_missing_transactions_and_rank_inputs_have_explicit_availability():
    from editorial_desk.honors import research_honors

    s = fixture()
    d = weekly_features.apply_weekly_features(s, build_weekly_dossier(s))
    h = research_honors(s, d, ExternalEditorialInputs("ironbound_weekly"))
    assert h["award_availability"]["AGAINST_ALL_ODDS"]["status"] != "AVAILABLE"
    assert h["award_availability"]["CUT_BY_YOUR_OWN_BLADE"]["status"] != "AVAILABLE"


def test_manager_can_resolve_team_named_authoritative_rank():
    from editorial_desk.honors import manager_honor

    s = fixture()
    d = weekly_features.apply_weekly_features(s, build_weekly_dossier(s))
    e = ExternalEditorialInputs(
        "ironbound_weekly",
        official_power_rankings=(
            OfficialPowerRanking(None, 4, team="Roster 2", previous_rank=1),
        ),
    )
    assert manager_honor(s, d, e)[0]["opponent_entering_power_rank"] == 1


def test_absent_vs_complete_empty_transaction_history():
    s = fixture()
    s.pop("transactions")
    h = evaluate(s)
    assert h["award_availability"]["SCRAPHEAP_SAVIOR"]["status"] == "UNAVAILABLE"
    assert h["award_availability"]["HOT_OFF_THE_ANVIL"]["status"] == "UNAVAILABLE"
    s["flagship_sleeper"]["transactions"] = {
        "status": "available",
        "weeks": {"1": [], "2": [], "3": []},
    }
    h = evaluate(s)
    assert h["award_availability"]["CUT_BY_YOUR_OWN_BLADE"]["status"] == "AVAILABLE"
    assert h["award_availability"]["SCRAPHEAP_SAVIOR"]["status"] == "AVAILABLE"
    assert "SCRAPHEAP_SAVIOR" not in types(h)
