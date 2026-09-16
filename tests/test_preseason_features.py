from editorial_desk.feature_producers import (
    draft_adp_value,
    draft_bargains,
    draft_market,
    draft_reach,
    draft_results,
    draft_value_board,
    dynasty_market,
    future_pick_ledger,
    keeper_value,
    offense_defense_splits,
    positional_strength,
    recruiting_class,
    rookie_draft,
    roster_age,
    streaming_roster_state,
)


def _snapshot():
    return {
        "league": {"roster_positions": ["QB", "RB", "WR", "TE", "FLEX", "DL", "LB", "DB", "BN"]},
        "users": [
            {"user_id": "u1", "display_name": "One", "metadata": {"team_name": "One"}},
            {"user_id": "u2", "display_name": "Two", "metadata": {"team_name": "Two"}},
        ],
        "rosters": [
            {"roster_id": 1, "owner_id": "u1", "players": ["qb", "rb", "wr", "lb", "dst"]},
            {"roster_id": 2, "owner_id": "u2", "players": ["te", "dl", "db"]},
        ],
        "players": {
            "qb": {"full_name": "Quarter Back", "position": "QB", "years_exp": 5},
            "rb": {"full_name": "Running Back", "position": "RB", "years_exp": 1},
            "wr": {"full_name": "Wide Rookie", "position": "WR", "years_exp": 0},
            "te": {"full_name": "Tight End", "position": "TE", "years_exp": 4},
            "lb": {"full_name": "Line Backer", "position": "LB", "years_exp": 2},
            "dl": {"full_name": "D Line", "position": "DL", "years_exp": 3},
            "db": {"full_name": "D Back", "position": "DB", "years_exp": 0},
            "dst": {"full_name": "Bills D/ST", "position": "DEF", "years_exp": None},
        },
        "draft_context": {
            "status": "available",
            "records": [
                {
                    "draft": {"draft_id": "d1", "type": "snake", "season": "2026", "metadata": {"name": "2026 Draft"}},
                    "picks": [
                        {"pick_no": 1, "round": 1, "roster_id": 1, "player_id": "wr", "metadata": {"first_name": "Wide", "last_name": "Rookie", "position": "WR", "adp": 3.5}},
                        {"pick_no": 2, "round": 1, "roster_id": 2, "player_id": "db", "metadata": {"first_name": "D", "last_name": "Back", "position": "DB", "adp": 8.0}},
                        {"pick_no": 10, "round": 2, "roster_id": 1, "player_id": "rb", "metadata": {"position": "RB", "adp": 7.0}},
                    ],
                    "traded_picks": [],
                }
            ],
        },
        "keeper_costs": [
            {"roster_id": 1, "player_id": "rb", "cost_round": 5, "prior_round": 6}
        ],
        "traded_picks": [
            {"season": "2027", "round": 1, "roster_id": 2, "owner_id": 1, "previous_owner_id": 2}
        ],
        "ranking_inputs": {
            "draft_adp": {"status": "available", "players": {"wr": {"adp": 3.5}, "db": {"adp": 8.0}, "rb": {"adp": 7.0}}},
            "dynasty_daddy": {"status": "unavailable", "players": {}, "error": "not configured"},
        },
    }


def test_sleeper_native_draft_results_are_ready_when_context_is_present():
    result = draft_results(_snapshot())
    assert result.status == "ready"
    assert [row["player_id"] for row in result.data] == ["wr", "db", "rb"]
    assert result.data[0]["pick_no"] == 1


def test_draft_adp_value_uses_authoritative_adp_when_present():
    result = draft_adp_value(_snapshot())
    assert result.status == "ready"
    first = result.data[0]
    assert first["player_id"] == "wr"
    assert first["pick_no"] == 1
    assert first["adp"] == 3.5
    assert first["value_delta"] == 2.5


def test_adp_derived_boards_share_one_authoritative_value_calculation():
    value_board = draft_value_board(_snapshot())
    bargains = draft_bargains(_snapshot())
    reaches = draft_reach(_snapshot())
    market = draft_market(_snapshot())

    assert value_board.status == "ready"
    assert [row["player_id"] for row in value_board.data] == ["db", "wr", "rb"]
    assert [row["value_delta"] for row in value_board.data] == [6.0, 2.5, -3.0]

    assert bargains.status == "ready"
    assert [row["player_id"] for row in bargains.data] == ["db", "wr"]
    assert all(row["value_delta"] > 0 for row in bargains.data)

    assert reaches.status == "ready"
    assert [row["player_id"] for row in reaches.data] == ["rb"]
    assert reaches.data[0]["value_delta"] == -3.0

    assert market.status == "ready"
    assert market.data["players"]["wr"]["adp"] == 3.5
    assert market.data["status"] == "available"


def test_adp_derived_boards_do_not_fabricate_when_authoritative_adp_is_missing():
    snapshot = _snapshot()
    snapshot["ranking_inputs"].pop("draft_adp")
    for pick in snapshot["draft_context"]["records"][0]["picks"]:
        pick["metadata"].pop("adp", None)

    for producer in (draft_value_board, draft_bargains, draft_reach, draft_market):
        result = producer(snapshot)
        assert result.status == "unavailable"
        assert "ADP" in (result.reason or "")


def test_keeper_value_preserves_cost_and_prior_round():
    result = keeper_value(_snapshot())
    assert result.status == "ready"
    assert result.data[0]["player"] == "Running Back"
    assert result.data[0]["cost_round"] == 5
    assert result.data[0]["prior_round"] == 6


def test_roster_age_uses_years_experience_without_fabricating_age():
    result = roster_age(_snapshot())
    assert result.status == "ready"
    one = next(row for row in result.data if row["roster_id"] == 1)
    assert one["average_years_experience"] == 1.75
    assert one["rookies"] == 1
    assert "average_age" not in one


def test_positional_strength_and_offense_defense_split_treat_idp_as_first_class():
    strength = positional_strength(_snapshot())
    splits = offense_defense_splits(_snapshot())
    assert strength.status == "ready"
    assert strength.data[1]["LB"] == 1
    assert strength.data[2]["DL"] == 1
    assert splits.status == "ready"
    one = next(row for row in splits.data if row["roster_id"] == 1)
    assert one["offense_players"] == 3
    assert one["idp_players"] == 1


def test_future_pick_ledger_preserves_original_and_current_owner_slots():
    result = future_pick_ledger(_snapshot())
    assert result.status == "ready"
    assert result.data[0]["season"] == "2027"
    assert result.data[0]["round"] == 1
    assert result.data[0]["original_roster_id"] == 2
    assert result.data[0]["current_roster_id"] == 1


def test_rookie_draft_and_recruiting_class_preserve_idp_positions():
    draft = rookie_draft(_snapshot())
    classes = recruiting_class(_snapshot())
    assert draft.status == "ready"
    assert any(row["position"] == "DB" for row in draft.data)
    assert classes.status == "ready"
    two = next(row for row in classes.data if row["roster_id"] == 2)
    assert two["idp_rookies"] == 1


def test_missing_external_dynasty_market_is_unavailable_not_fabricated():
    result = dynasty_market(_snapshot())
    assert result.status == "unavailable"
    assert "not configured" in result.reason


def test_streaming_roster_state_reports_rostered_defenses():
    result = streaming_roster_state(_snapshot())
    assert result.status == "ready"
    assert result.data[0]["player"] == "Bills D/ST"
    assert result.data[0]["roster_id"] == 1
