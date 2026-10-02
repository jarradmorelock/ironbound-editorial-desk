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


def test_failed_claims_and_empty_week_are_not_completed_movement():
    snapshot = _snapshot()
    snapshot['flagship_sleeper']['transactions']['weeks']['3'] = []
    snapshot['transactions'][0]['status'] = 'failed'
    report = build_roster_market_report(snapshot, {}, None, None)
    assert report['transactions']['current_week_count'] == 0
    snapshot['flagship_sleeper']['transactions']['weeks']['3'] = snapshot['transactions']
    network = build_network_market_context({'main': snapshot})
    assert network['players']['p2']['added_leagues'] == 0


def test_empty_starter_slot_is_not_a_player():
    snapshot = _snapshot()
    snapshot['matchups'][0]['starters'] = ['p1', '0']
    report = build_roster_market_report(snapshot, {}, None, None)
    assert all(p['player_id'] != '0' for r in report['lineup_churn'] for p in r['moved_into_starting_lineup'])
    assert '0' not in build_network_market_context({'main': snapshot})['players']


def test_status_timeline_preserves_observation_interval_and_excludes_future(tmp_path):
    import json
    from editorial_desk.chronicle_queries import ChronicleQueries
    directory = tmp_path / 'cross_league' / 'nfl_player_events'
    directory.mkdir(parents=True)
    event = {'event_id': 'status1', 'event_type': 'PLAYER_STATUS_CHANGE',
             'entities': {'player_id': 'p3'}, 'source': 'sleeper_players',
             'observed_at': '2026-09-20T15:00:00+00:00',
             'observed_before': '2026-09-20T12:00:00+00:00',
             'observed_after': '2026-09-20T15:00:00+00:00',
             'before': {'injury_status': 'Doubtful'}, 'after': {'injury_status': 'Out'}}
    future = {**event, 'event_id': 'future', 'observed_at': '2026-10-01T15:00:00+00:00'}
    (directory / 'events.jsonl').write_text('\n'.join(map(json.dumps, [event, future])))
    beat = {'reporting_window': {'start': '2026-09-15T00:00:00+00:00', 'end': '2026-09-22T00:00:00+00:00'}}
    report = build_roster_market_report(_snapshot(), {}, beat, None, chronicle=ChronicleQueries(tmp_path))
    events = report['status_timeline']['events']
    assert [row['event_id'] for row in events] == ['status1']
    assert events[0]['observed_before'] == event['observed_before']
    assert events[0]['after']['injury_status'] == 'Out'


def test_trade_is_one_event_per_player_not_two_and_future_weeks_are_excluded():
    snapshot = _snapshot()
    tx = {'transaction_id': 'trade', 'status': 'complete', 'type': 'trade',
          'adds': {'p1': 1}, 'drops': {'p1': 2}}
    snapshot['flagship_sleeper']['transactions']['weeks'] = {'3': [tx], '4': [dict(tx, transaction_id='future')]}
    report = build_roster_market_report(snapshot, {}, None, None)
    assert report['transactions']['season_event_count'] == 1
    assert report['repeated_asset_movement'] == []


def test_unavailable_transaction_source_is_not_a_ready_quiet_week():
    snapshot = _snapshot()
    snapshot['flagship_sleeper']['transactions'] = {'status': 'unavailable', 'weeks': {}}
    assert build_roster_market_report(snapshot, {}, None, None)['status'] == 'MANUAL_VERIFY'


def test_status_history_survives_news_outage_and_player_drop(tmp_path):
    import json
    from editorial_desk.chronicle_queries import ChronicleQueries
    snapshot = _snapshot()
    snapshot['rosters'][0]['players'].remove('p3')
    snapshot['flagship_sleeper']['transactions']['weeks']['3'][0]['drops'] = {'p3': 1}
    snapshot['nfl_context'] = {'schedule': {'records': [{'gameday': '2026-09-17'}, {'gameday': '2026-09-21'}]}}
    directory = tmp_path / 'cross_league' / 'nfl_player_events'
    directory.mkdir(parents=True)
    (directory / 'events.jsonl').write_text(json.dumps({'event_id': 'dropped-injury',
        'event_type': 'PLAYER_STATUS_CHANGE', 'entities': {'player_id': 'p3'},
        'observed_at': '2026-09-20T15:00:00+00:00'}))
    report = build_roster_market_report(snapshot, {}, {'status': 'UNAVAILABLE'}, None,
                                       chronicle=ChronicleQueries(tmp_path))
    assert [e['event_id'] for e in report['status_timeline']['events']] == ['dropped-injury']


def test_roster_market_transaction_desk_preserves_complete_trade_compensation():
    snapshot = _snapshot()
    snapshot["users"].append(
        {"user_id": "u2", "display_name": "Other", "metadata": {"team_name": "Other Team"}}
    )
    snapshot["rosters"].append(
        {"roster_id": 2, "owner_id": "u2", "players": ["p4"]}
    )
    snapshot["players"]["p4"] = {"full_name": "Player Four", "position": "RB"}
    trade = {
        "transaction_id": "tx-trade",
        "type": "trade",
        "status": "complete",
        "roster_ids": [1, 2],
        "adds": {"p2": 1, "p4": 2},
        "drops": {"p2": 2, "p4": 1},
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
    snapshot["transactions"] = [trade]
    snapshot["flagship_sleeper"]["transactions"]["weeks"]["3"] = [trade]

    report = build_roster_market_report(snapshot, {}, None, None)
    row = report["transactions"]["current_week"][0]

    assert row["transaction_id"] == "tx-trade"
    assert row["draft_picks"][0]["original_team"] == "Blue Moose"
    assert row["draft_picks"][0]["new_owner_team"] == "Other Team"
    assert row["players"]["received_by"]["Blue Moose"][0]["player"] == "Quarterback Two"
