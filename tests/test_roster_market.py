from editorial_desk.roster_market import (
    build_network_market_context,
    build_roster_market_report,
)


def _snapshot(team_name="Blue Moose"):
    return {
        "week": 3,
        "users": [
            {
                "user_id": "u1",
                "display_name": "Manager",
                "metadata": {"team_name": team_name},
            }
        ],
        "rosters": [
            {
                "roster_id": 1,
                "owner_id": "u1",
                "players": ["p1", "p2", "p3"],
            }
        ],
        "players": {
            "p1": {"full_name": "Jordan Love", "position": "QB"},
            "p2": {"full_name": "Quarterback Two", "position": "QB"},
            "p3": {"full_name": "Puka Nacua", "position": "WR"},
        },
        "matchups": [
            {
                "roster_id": 1,
                "matchup_id": 1,
                "starters": ["p1", "p3"],
                "players": ["p1", "p2", "p3"],
            }
        ],
        "transactions": [
            {
                "transaction_id": "tx-current",
                "type": "waiver",
                "status": "complete",
                "adds": {"p2": 1},
                "drops": {},
                "settings": {"waiver_bid": 7},
            }
        ],
        "flagship_sleeper": {
            "schedule": {
                "status": "available",
                "weeks": {
                    "2": [
                        {
                            "roster_id": 1,
                            "matchup_id": 1,
                            "starters": ["p2", "p3"],
                            "players": ["p1", "p2", "p3"],
                        }
                    ]
                },
            },
            "transactions": {
                "status": "available",
                "weeks": {
                    "1": [
                        {
                            "transaction_id": "tx-old",
                            "type": "waiver",
                            "status": "complete",
                            "adds": {"p1": 1},
                            "drops": {},
                        }
                    ],
                    "2": [
                        {
                            "transaction_id": "tx-repeat",
                            "type": "free_agent",
                            "status": "complete",
                            "adds": {"p1": 1},
                            "drops": {},
                        }
                    ],
                    "3": [
                        {
                            "transaction_id": "tx-current",
                            "type": "waiver",
                            "status": "complete",
                            "adds": {"p2": 1},
                            "drops": {},
                            "settings": {"waiver_bid": 7},
                        }
                    ],
                },
            },
        },
    }


def test_network_context_reports_tracked_roster_and_start_rates_without_calling_them_sleeper_wide():
    snapshots = {
        "main": _snapshot(),
        "free": {
            **_snapshot("Other Team"),
            "matchups": [
                {
                    "roster_id": 1,
                    "matchup_id": 1,
                    "starters": ["p3"],
                    "players": ["p1", "p3"],
                }
            ],
            "transactions": [],
        },
    }

    context = build_network_market_context(snapshots)

    assert context["scope"] == "Ironbound Network"
    assert context["players"]["p1"]["rostered_leagues"] == 2
    assert context["players"]["p1"]["started_leagues"] == 1
    assert context["players"]["p1"]["tracked_start_rate"] == 0.5
    assert context["sleeper_platform_rates"]["status"] == "UNAVAILABLE"


def test_roster_market_combines_starter_churn_transactions_health_and_beat_timeline():
    snapshot = _snapshot()
    beat = {
        "status": "READY",
        "items": [
            {
                "event_id": "news:puka-doubtful",
                "published_at": "2026-09-19T15:00:00+00:00",
                "headline": "Puka Nacua remains doubtful",
                "source": "RotoWire",
                "source_url": "https://example.com/doubtful",
                "tags": ["Injury", "Game Status"],
                "league_players": [
                    {
                        "sleeper_player_id": "p3",
                        "player": "Puka Nacua",
                        "fantasy_team": "Blue Moose",
                    }
                ],
                "editorial_lanes": {"health_context": True},
            },
            {
                "event_id": "news:puka-out",
                "published_at": "2026-09-20T15:00:00+00:00",
                "headline": "Puka Nacua ruled out",
                "source": "Draft Sharks",
                "source_url": "https://example.com/out",
                "tags": ["Injury", "Game Status"],
                "league_players": [
                    {
                        "sleeper_player_id": "p3",
                        "player": "Puka Nacua",
                        "fantasy_team": "Blue Moose",
                    }
                ],
                "editorial_lanes": {"health_context": True},
            },
        ],
    }
    dossier = {
        "roster_health": {
            "status": "available",
            "players": [
                {
                    "player_id": "p3",
                    "player": "Puka Nacua",
                    "team": "Blue Moose",
                    "injury_status": "Out",
                }
            ],
        }
    }
    network = build_network_market_context({"main": snapshot})

    report = build_roster_market_report(snapshot, dossier, beat, network)

    assert report["status"] == "READY"
    churn = report["lineup_churn"][0]
    assert churn["team"] == "Blue Moose"
    assert churn["moved_into_starting_lineup"][0]["player"] == "Jordan Love"
    assert churn["moved_out_of_starting_lineup"][0]["player"] == "Quarterback Two"
    assert report["transactions"]["current_week"][0]["faab"] == 7
    assert report["repeated_asset_movement"][0]["player"] == "Jordan Love"
    timeline = next(row for row in report["news_timelines"] if row["player"] == "Puka Nacua")
    assert [event["source"] for event in timeline["events"]] == ["RotoWire", "Draft Sharks"]
    assert report["sleeper_platform_rates"]["status"] == "UNAVAILABLE"
