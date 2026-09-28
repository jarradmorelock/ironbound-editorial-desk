from editorial_desk.roster_market import (
    build_network_market_context,
    build_roster_market,
)


def _snapshot():
    players = {
        "p1": {"full_name": "Alpha QB", "position": "QB"},
        "p2": {"full_name": "Alpha RB", "position": "RB"},
        "p3": {"full_name": "Alpha WR", "position": "WR"},
        "p4": {"full_name": "Bench WR", "position": "WR"},
        "p5": {"full_name": "New Starter", "position": "WR"},
    }
    return {
        "week": 3,
        "editorial": {"league_key": "ironbound_sixteen"},
        "users": [
            {"user_id": "u1", "display_name": "Manager", "metadata": {"team_name": "Blue Moose"}}
        ],
        "rosters": [
            {
                "roster_id": 1,
                "owner_id": "u1",
                "players": ["p1", "p2", "p3", "p4", "p5"],
                "reserve": [],
                "taxi": [],
            }
        ],
        "players": players,
        "transactions": [
            {
                "transaction_id": "t3",
                "type": "waiver",
                "status": "complete",
                "adds": {"p5": 1},
                "drops": {"p4": 1},
                "settings": {"waiver_bid": 12},
            }
        ],
        "flagship_sleeper": {
            "schedule": {
                "status": "available",
                "weeks": {
                    "2": [
                        {
                            "roster_id": 1,
                            "starters": ["p1", "p2", "p3"],
                            "players": ["p1", "p2", "p3", "p4"],
                        }
                    ],
                    "3": [
                        {
                            "roster_id": 1,
                            "starters": ["p1", "p2", "p5"],
                            "players": ["p1", "p2", "p3", "p4", "p5"],
                        }
                    ],
                },
            },
            "transactions": {
                "status": "available",
                "weeks": {
                    "1": [
                        {"transaction_id": "t1", "type": "free_agent", "adds": {"p4": 1}, "drops": {}}
                    ],
                    "2": [
                        {"transaction_id": "t2", "type": "trade", "adds": {"p4": 1}, "drops": {"p2": 1}}
                    ],
                    "3": [
                        {
                            "transaction_id": "t3",
                            "type": "waiver",
                            "adds": {"p5": 1},
                            "drops": {"p4": 1},
                            "settings": {"waiver_bid": 12},
                        }
                    ],
                },
            },
        },
    }


def test_roster_market_detects_starter_churn_transactions_and_roster_shape():
    snapshot = _snapshot()
    dossier = {
        "roster_health": {
            "status": "available",
            "players": [
                {
                    "player_id": "p3",
                    "player": "Alpha WR",
                    "team": "Blue Moose",
                    "injury_status": "Questionable",
                }
            ],
        }
    }
    beat = {
        "status": "READY",
        "items": [
            {
                "event_id": "news:1",
                "published_at": "2026-09-20T15:00:00+00:00",
                "headline": "Alpha WR misses practice",
                "source": "RotoWire",
                "source_url": "https://example.com/alpha",
                "tags": ["Practice Report"],
                "league_players": [
                    {
                        "sleeper_player_id": "p3",
                        "player": "Alpha WR",
                        "fantasy_team": "Blue Moose",
                        "roster_id": 1,
                    }
                ],
                "editorial_lanes": {"health_context": True, "usage_context": True},
            }
        ],
    }

    market = build_roster_market(
        snapshot,
        dossier,
        beat_report=beat,
        network_market={
            "player_adds": {
                "p5": {
                    "player_id": "p5",
                    "player": "New Starter",
                    "league_count": 6,
                    "league_keys": ["a", "b", "c", "d", "e", "f"],
                }
            }
        },
    )

    assert market["status"] == "READY"
    churn = market["starter_churn"][0]
    assert churn["team"] == "Blue Moose"
    assert churn["moved_out"][0]["player"] == "Alpha WR"
    assert churn["moved_in"][0]["player"] == "New Starter"
    assert churn["moved_out"][0]["context_events"][0]["source"] == "RotoWire"
    assert market["current_transactions"][0]["faab"] == 12
    assert market["transaction_history"][0]["player"] == "Bench WR"
    assert market["transaction_history"][0]["event_count"] == 3
    shape = market["roster_architecture"][0]
    assert shape["position_counts"]["WR"] == 3
    assert market["network_add_signals"][0]["league_count"] == 6
    assert market["platform_market_rates"]["status"] == "UNAVAILABLE"
    assert market["platform_market_rates"]["required"] is False


def test_network_market_context_counts_distinct_leagues_not_duplicate_transactions():
    snapshots = [
        {
            "editorial": {"league_key": "one"},
            "week": 3,
            "transactions": [
                {"adds": {"p1": 1}},
                {"adds": {"p1": 2}},
            ],
            "players": {"p1": {"full_name": "Player One"}},
        },
        {
            "editorial": {"league_key": "two"},
            "week": 3,
            "transactions": [{"adds": {"p1": 1}}],
            "players": {"p1": {"full_name": "Player One"}},
        },
    ]

    context = build_network_market_context(snapshots, 3)

    assert context["player_adds"]["p1"]["league_count"] == 2
    assert context["player_adds"]["p1"]["transaction_count"] == 3
