from editorial_desk.transaction_evidence import build_transaction_evidence


def _snapshot():
    return {
        "week": 3,
        "users": [
            {"user_id": "u1", "display_name": "One", "metadata": {"team_name": "The Buckaneers"}},
            {"user_id": "u2", "display_name": "Two", "metadata": {"team_name": "Chicken"}},
            {"user_id": "u3", "display_name": "Three", "metadata": {"team_name": "San Carlos FC"}},
        ],
        "rosters": [
            {"roster_id": 1, "owner_id": "u1"},
            {"roster_id": 2, "owner_id": "u2"},
            {"roster_id": 3, "owner_id": "u3"},
        ],
        "players": {
            "london": {"full_name": "Drake London"},
            "bernard": {"full_name": "Germie Bernard"},
            "odunze": {"full_name": "Rome Odunze"},
        },
        "publication_sleeper": {
            "transactions": {
                "status": "available",
                "weeks": {
                    "2": [
                        {
                            "transaction_id": "tx-week2",
                            "type": "trade",
                            "status": "complete",
                            "created": 1000,
                            "roster_ids": [1, 3],
                            "adds": {"bernard": 1},
                            "drops": {"bernard": 3},
                            "draft_picks": [],
                        }
                    ],
                    "3": [
                        {
                            "transaction_id": "tx-week3",
                            "type": "trade",
                            "status": "complete",
                            "created": 2000,
                            "roster_ids": [1, 2],
                            "adds": {"london": 1, "odunze": 2},
                            "drops": {"london": 2, "odunze": 1},
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
                    ],
                },
            }
        },
    }


def test_trade_normalization_preserves_every_player_and_pick():
    result = build_transaction_evidence(_snapshot(), None)

    trade = next(row for row in result["transactions"] if row["transaction_id"] == "tx-week3")
    received = trade["players"]["received_by"]
    assert {row["player"] for row in received["The Buckaneers"]} == {"Drake London"}
    assert {row["player"] for row in received["Chicken"]} == {"Rome Odunze"}

    pick = trade["draft_picks"][0]
    assert pick["season"] == "2027"
    assert pick["round"] == 1
    assert pick["original_team"] == "The Buckaneers"
    assert pick["previous_owner_team"] == "The Buckaneers"
    assert pick["new_owner_team"] == "Chicken"


def test_pick_provenance_keeps_original_previous_and_new_owner():
    pick = build_transaction_evidence(_snapshot(), None)["transactions"][1]["draft_picks"][0]

    assert pick["original_roster_id"] == 1
    assert pick["previous_owner_roster_id"] == 1
    assert pick["new_owner_roster_id"] == 2


def test_transactions_across_sleeper_week_legs_are_not_dropped():
    result = build_transaction_evidence(_snapshot(), None)

    assert {row["transaction_id"] for row in result["transactions"]} == {
        "tx-week2",
        "tx-week3",
    }
    assert result["coverage"]["status"] == "READY"


def test_transaction_evidence_attaches_reviewed_week_impact_for_acquired_players():
    snapshot = _snapshot()
    snapshot["matchups"] = [
        {
            "roster_id": 1,
            "matchup_id": 1,
            "players": ["london", "bernard"],
            "starters": ["london"],
            "players_points": {"london": 22.4, "bernard": 4.0},
            "points": 110.0,
        },
        {
            "roster_id": 2,
            "matchup_id": 1,
            "players": ["odunze"],
            "starters": ["odunze"],
            "players_points": {"odunze": 17.6},
            "points": 100.0,
        },
    ]

    trade = next(
        row
        for row in build_transaction_evidence(snapshot, None)["transactions"]
        if row["transaction_id"] == "tx-week3"
    )

    impact = {row["player"]: row for row in trade["reviewed_week_impact"]}
    assert impact["Drake London"]["to_team"] == "The Buckaneers"
    assert impact["Drake London"]["started"] is True
    assert impact["Drake London"]["fantasy_points"] == 22.4
    assert impact["Rome Odunze"]["to_team"] == "Chicken"
    assert impact["Rome Odunze"]["started"] is True
    assert impact["Rome Odunze"]["fantasy_points"] == 17.6
