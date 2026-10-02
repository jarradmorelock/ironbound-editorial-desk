import importlib
import importlib.util


def _module():
    spec = importlib.util.find_spec("editorial_desk.transaction_evidence")
    assert spec is not None, "transaction_evidence module is required"
    return importlib.import_module("editorial_desk.transaction_evidence")


def _base_snapshot():
    return {
        "week": 3,
        "league": {"season": "2026"},
        "editorial": {"league_key": "ironbound_sixteen", "publication_enabled": True},
        "users": [
            {"user_id": "u1", "display_name": "Jarrad", "metadata": {"team_name": "The Buckaneers"}},
            {"user_id": "u2", "display_name": "Austin", "metadata": {"team_name": "At least I have chicken"}},
            {"user_id": "u4", "display_name": "Four", "metadata": {"team_name": "Team Four"}},
            {"user_id": "u10", "display_name": "Ten", "metadata": {"team_name": "Team Ten"}},
        ],
        "rosters": [
            {"roster_id": 1, "owner_id": "u1"},
            {"roster_id": 2, "owner_id": "u2"},
            {"roster_id": 4, "owner_id": "u4"},
            {"roster_id": 10, "owner_id": "u10"},
        ],
        "players": {
            "london": {"full_name": "Drake London", "position": "WR"},
            "bernard": {"full_name": "Germie Bernard", "position": "WR"},
            "odunze": {"full_name": "Rome Odunze", "position": "WR"},
            "p2": {"full_name": "Player Two", "position": "RB"},
            "p4": {"full_name": "Player Four", "position": "RB"},
        },
        "matchups": [],
        "transactions": [],
    }


def test_trade_normalization_preserves_every_player_and_pick():
    snapshot = _base_snapshot()
    tx = {
        "transaction_id": "tx-buckaneers",
        "type": "trade",
        "status": "complete",
        "created": 1790860000000,
        "roster_ids": [1, 2],
        "adds": {"london": 1, "bernard": 1, "odunze": 2},
        "drops": {"london": 2, "bernard": 2, "odunze": 1},
        "draft_picks": [
            {
                "season": "2027",
                "round": 1,
                "roster_id": 1,
                "previous_owner_id": 1,
                "owner_id": 2,
            }
        ],
    }
    snapshot["flagship_sleeper"] = {
        "transactions": {"status": "available", "weeks": {"3": [tx]}, "errors": {}}
    }

    result = _module().build_transaction_evidence(snapshot, None)
    trade = result["transactions"][0]

    assert {
        row["player"]
        for row in trade["players"]["received_by"]["The Buckaneers"]
    } == {"Drake London", "Germie Bernard"}
    assert {
        row["player"]
        for row in trade["players"]["received_by"]["At least I have chicken"]
    } == {"Rome Odunze"}
    pick = trade["draft_picks"][0]
    assert pick["season"] == "2027"
    assert pick["round"] == 1
    assert pick["original_roster_id"] == 1
    assert pick["original_team"] == "The Buckaneers"
    assert pick["new_owner_roster_id"] == 2
    assert pick["new_owner_team"] == "At least I have chicken"


def test_pick_provenance_keeps_original_previous_and_new_owner():
    snapshot = _base_snapshot()
    tx = {
        "transaction_id": "tx-retraded-pick",
        "type": "trade",
        "status": "complete",
        "roster_ids": [2, 4],
        "adds": {"p4": 2, "p2": 4},
        "drops": {"p4": 4, "p2": 2},
        "draft_picks": [
            {
                "season": "2028",
                "round": 2,
                "roster_id": 10,
                "previous_owner_id": 2,
                "owner_id": 4,
            }
        ],
    }
    snapshot["publication_sleeper"] = {
        "transactions": {"status": "available", "weeks": {"3": [tx]}, "errors": {}}
    }

    pick = _module().build_transaction_evidence(snapshot, None)["transactions"][0]["draft_picks"][0]

    assert pick["original_roster_id"] == 10
    assert pick["original_team"] == "Team Ten"
    assert pick["previous_owner_roster_id"] == 2
    assert pick["previous_owner_team"] == "At least I have chicken"
    assert pick["new_owner_roster_id"] == 4
    assert pick["new_owner_team"] == "Team Four"


def test_transactions_across_sleeper_week_legs_are_not_dropped():
    snapshot = _base_snapshot()
    week2 = {
        "transaction_id": "tx-week2",
        "type": "trade",
        "status": "complete",
        "roster_ids": [1, 2],
        "adds": {"london": 1},
        "drops": {"london": 2},
        "draft_picks": [],
    }
    week3 = {
        "transaction_id": "tx-week3",
        "type": "waiver",
        "status": "complete",
        "roster_ids": [1],
        "adds": {"bernard": 1},
        "drops": {},
        "settings": {"waiver_bid": 11},
        "draft_picks": [],
    }
    snapshot["publication_sleeper"] = {
        "transactions": {
            "status": "available",
            "weeks": {"2": [week2], "3": [week3]},
            "errors": {},
        }
    }

    result = _module().build_transaction_evidence(snapshot, None)

    assert {row["transaction_id"] for row in result["transactions"]} == {
        "tx-week2",
        "tx-week3",
    }
    waiver = next(row for row in result["transactions"] if row["transaction_id"] == "tx-week3")
    assert waiver["faab"] == 11.0
    assert waiver["week"] == 3
