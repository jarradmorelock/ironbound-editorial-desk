from editorial_desk.metrics import build_weekly_dossier, optimal_lineup
from editorial_desk.render import render_markdown


PLAYERS = {
    "qb1": {"full_name": "Quarterback One", "fantasy_positions": ["QB"]},
    "qb2": {"full_name": "Quarterback Two", "fantasy_positions": ["QB"]},
    "rb1": {"full_name": "Runner One", "fantasy_positions": ["RB"]},
    "rb2": {"full_name": "Runner Two", "fantasy_positions": ["RB"]},
    "rb3": {"full_name": "Runner Three", "fantasy_positions": ["RB"]},
    "wr1": {"full_name": "Receiver One", "fantasy_positions": ["WR"]},
    "wr2": {"full_name": "Receiver Two", "fantasy_positions": ["WR"]},
    "wr3": {"full_name": "Receiver Three", "fantasy_positions": ["WR"]},
    "wr4": {"full_name": "Receiver Four", "fantasy_positions": ["WR"]},
}


def test_optimal_lineup_obeys_slot_eligibility():
    score, assignment = optimal_lineup(
        ["qb1", "qb2", "rb1", "rb2", "wr1"],
        {"qb1": 10, "qb2": 25, "rb1": 20, "rb2": 15, "wr1": 30},
        ["QB", "RB", "FLEX"],
        PLAYERS,
    )
    assert score == 75
    assert assignment[0] == "qb2"
    assert {assignment[1], assignment[2]} == {"rb1", "wr1"}


def snapshot():
    return {
        "collected_at": "2026-09-15T22:00:00+00:00",
        "week": 1,
        "editorial": {
            "league_key": "test",
            "configured_name": "Test League",
            "publication": "Test Paper",
            "tier": "newspaper",
            "league_format": "redraft",
            "ranking_model": "redraft_projection_starters_record",
        },
        "league": {
            "name": "Test League",
            "season": "2026",
            "roster_positions": ["QB", "RB", "WR", "FLEX", "BN"],
            "settings": {"league_average_match": 1, "divisions": 2},
            "metadata": {"division_1": "Forge", "division_2": "Anvil"},
            "scoring_settings": {"proj": 1},
        },
        "users": [
            {"user_id": "u1", "display_name": "Owner One", "metadata": {"team_name": "One"}},
            {"user_id": "u2", "display_name": "Owner Two", "metadata": {"team_name": "Two"}},
            {"user_id": "u3", "display_name": "Owner Three", "metadata": {"team_name": "Three"}},
            {"user_id": "u4", "display_name": "Owner Four", "metadata": {"team_name": "Four"}},
        ],
        "rosters": [
            {"roster_id": 1, "owner_id": "u1", "players": ["qb1", "rb1", "rb2", "wr1", "wr2"], "settings": {"division": 1, "wins": 0, "losses": 1, "fpts": 101}},
            {"roster_id": 2, "owner_id": "u2", "players": ["qb2", "rb2", "rb3", "wr3", "wr4"], "settings": {"division": 1, "wins": 1, "losses": 0, "fpts": 110}},
            {"roster_id": 3, "owner_id": "u3", "players": ["qb1", "rb1", "wr1", "wr2"], "settings": {"division": 2, "wins": 1, "losses": 0, "fpts": 70}},
            {"roster_id": 4, "owner_id": "u4", "players": ["qb2", "rb2", "wr3", "wr4"], "settings": {"division": 2, "wins": 0, "losses": 1, "fpts": 65}},
        ],
        "players": PLAYERS,
        "matchups": [
            {"matchup_id": 1, "roster_id": 1, "points": 101, "starters": ["qb1", "rb1", "wr1", "wr2"], "players": ["qb1", "rb1", "rb2", "wr1", "wr2"], "players_points": {"qb1": 20, "rb1": 20, "rb2": 35, "wr1": 31, "wr2": 30}},
            {"matchup_id": 1, "roster_id": 2, "points": 110, "starters": ["qb2", "rb2", "wr3", "wr4"], "players": ["qb2", "rb2", "rb3", "wr3", "wr4"], "players_points": {"qb2": 25, "rb2": 25, "rb3": 10, "wr3": 30, "wr4": 30}},
            {"matchup_id": 2, "roster_id": 3, "points": 70, "starters": ["qb1", "rb1", "wr1", "wr2"], "players": ["qb1", "rb1", "wr1", "wr2"], "players_points": {"qb1": 10, "rb1": 20, "wr1": 20, "wr2": 20}},
            {"matchup_id": 2, "roster_id": 4, "points": 65, "starters": ["qb2", "rb2", "wr3", "wr4"], "players": ["qb2", "rb2", "wr3", "wr4"], "players_points": {"qb2": 15, "rb2": 15, "wr3": 20, "wr4": 15}},
        ],
        "transactions": [
            {"transaction_id": "tx1", "status": "complete", "type": "waiver", "adds": {"wr3": 2}, "settings": {"waiver_bid": 7}}
        ],
        "traded_picks": [],
        "ranking_inputs": {
            "sleeper_projections": {
                "status": "available",
                "players": {
                    "qb1": {"proj": 20},
                    "qb2": {"proj": 25},
                    "rb1": {"proj": 10},
                    "rb2": {"proj": 30},
                    "rb3": {"proj": 8},
                    "wr1": {"proj": 15},
                    "wr2": {"proj": 12},
                    "wr3": {"proj": 30},
                    "wr4": {"proj": 25}
                }
            },
            "dynasty_daddy": {"status": "available", "players": {}}
        },
    }


def test_awards_and_lineup_metrics_are_derived_from_verified_scores():
    dossier = build_weekly_dossier(snapshot())
    assert dossier["awards"]["bad_beat"]["team"] == "One"
    assert dossier["awards"]["escape_artist"]["team"] == "Three"
    assert dossier["awards"]["bench_mvp"]["player"] == "Runner Two"
    assert dossier["awards"]["manager_of_the_week"]["team"] == "Two"
    assert dossier["awards"]["waiver_star_candidates"][0]["player"] == "Receiver Three"


def test_single_swap_that_changes_result_is_identified():
    dossier = build_weekly_dossier(snapshot())
    flip = dossier["awards"]["result_flipping_decisions"][0]
    assert flip["team"] == "One"
    assert flip["started_player"] == "Runner One"
    assert flip["bench_player"] == "Runner Two"
    assert flip["revised_team_score"] == 116


def test_median_and_named_division_context_are_preserved():
    dossier = build_weekly_dossier(snapshot())
    assert dossier["league_median"]["enabled"] is True
    assert dossier["league_median"]["points"] == 85.5
    assert dossier["awards"]["bad_beat"]["league_median"]["result"] == "win"
    assert [row["division_name"] for row in dossier["divisions"]] == [
        "Forge",
        "Anvil",
    ]
    assert dossier["divisions"][0]["weekly_scoring_rank"] == 1


def test_zero_point_preseason_matchups_do_not_create_false_awards_or_records():
    empty = snapshot()
    for matchup in empty["matchups"]:
        matchup["points"] = 0
        matchup["players_points"] = {
            player_id: 0 for player_id in matchup["players_points"]
        }
    dossier = build_weekly_dossier(empty)
    assert dossier["awards"]["mvp_card_result"] is None
    assert dossier["weekly_records"]["status"] == "awaiting_scores"
    assert dossier["weekly_records"]["highest_score"] is None


def test_redraft_power_ranking_uses_only_requested_three_inputs():
    dossier = build_weekly_dossier(snapshot())
    power = dossier["rankings"]["data_power_ranking"]
    assert power["status"] == "calculated"
    assert power["rows"][0]["team"] == "Two"
    assert set(power["rows"][0]["component_ranks"]) == {
        "projection",
        "starting_lineup",
        "win_loss_record",
    }
    assert power["methodology"]["excluded"] == [
        "dynasty roster value",
        "future draft capital",
        "all-play",
        "lineup efficiency",
    ]
    assert dossier["rankings"]["official_standings_status"] == "active"


def test_flagship_supplement_exposes_magazine_level_sleeper_evidence():
    flagship = snapshot()
    flagship["editorial"].update(
        {
            "tier": "flagship",
            "league_format": "dynasty",
            "ranking_model": "ironbound_dynasty",
        }
    )
    flagship["league"]["settings"]["playoff_week_start"] = 15
    flagship["transactions"][0].update(
        {
            "created": 1789500000000,
            "roster_ids": [2],
            "drops": {},
        }
    )
    week_two = [
        {"matchup_id": 1, "roster_id": 1, "points": 0},
        {"matchup_id": 1, "roster_id": 3, "points": 0},
        {"matchup_id": 2, "roster_id": 2, "points": 0},
        {"matchup_id": 2, "roster_id": 4, "points": 0},
    ]
    flagship["traded_picks"] = [
        {
            "season": "2027",
            "round": 1,
            "roster_id": 1,
            "previous_owner_id": 1,
            "owner_id": 2,
        }
    ]
    flagship["flagship_sleeper"] = {
        "schedule": {
            "status": "available",
            "weeks": {"1": flagship["matchups"], "2": week_two},
        },
        "transactions": {
            "status": "available",
            "weeks": {"1": flagship["transactions"], "2": []},
        },
        "drafts": {
            "status": "available",
            "records": [
                {
                    "draft": {
                        "draft_id": "d1",
                        "season": "2026",
                        "type": "rookie",
                        "status": "complete",
                        "settings": {"rounds": 4},
                    },
                    "picks": [
                        {
                            "pick_no": 1,
                            "round": 1,
                            "draft_slot": 1,
                            "roster_id": 1,
                            "player_id": "qb1",
                            "metadata": {"position": "QB"},
                        }
                    ],
                    "traded_picks": [],
                }
            ],
        },
        "playoff_brackets": {
            "status": "available",
            "winners": [{"r": 1, "m": 1, "t1": 1, "t2": 2, "w": 2}],
            "losers": [],
        },
        "next_week_projections": {
            "status": "available",
            "week": 2,
            "players": flagship["ranking_inputs"]["sleeper_projections"]["players"],
        },
    }

    dossier = build_weekly_dossier(flagship)
    supplement = dossier["flagship_supplement"]
    assert supplement["schedule"]["weeks_collected"] == 2
    assert supplement["schedule"]["division_context"][0]["division_strength_rank"]
    assert supplement["season_records"]["highest_team_score"]["team"] == "Two"
    assert supplement["transaction_ledger"]["season_summary"]["waivers"] == 1
    assert supplement["draft_archive"][0]["first_round"][0]["player"] == "Quarterback One"
    assert supplement["traded_pick_ledger"][0]["current_team"] == "Two"

    markdown = render_markdown(dossier)
    assert "## Flagship Sleeper Sourcebook" in markdown
    assert "### Schedule and Division Desk" in markdown
    assert "### Season Record Book" in markdown
    assert "### League Activity Ledger" in markdown
    assert "### Draft Archive" in markdown
