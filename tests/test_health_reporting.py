from editorial_desk.review import build_editorial_review, render_editorial_review


def _snapshot(tier="newspaper"):
    return {
        "collected_at": "2026-09-16T10:00:00+00:00",
        "week": 1,
        "editorial": {
            "league_key": "test",
            "configured_name": "Test League",
            "publication": "Test Paper",
            "tier": tier,
            "league_format": "redraft" if tier == "newspaper" else "dynasty",
            "ranking_model": (
                "redraft_projection_starters_record"
                if tier == "newspaper"
                else "ironbound_dynasty"
            ),
        },
        "league": {
            "name": "Test League",
            "season": "2026",
            "roster_positions": ["QB", "RB", "BN", "IR"],
            "settings": {},
            "metadata": {},
        },
        "users": [
            {
                "user_id": "u1",
                "display_name": "Owner One",
                "metadata": {"team_name": "Alpha"},
            }
        ],
        "rosters": [
            {
                "roster_id": 1,
                "owner_id": "u1",
                "players": ["healthy", "questionable", "reserve"],
                "reserve": ["reserve"],
                "settings": {},
            }
        ],
        "players": {
            "healthy": {
                "full_name": "Healthy Player",
                "position": "RB",
                "team": "BUF",
                "status": "Active",
            },
            "questionable": {
                "full_name": "Questionable Player",
                "position": "WR",
                "team": "KC",
                "status": "Active",
                "injury_status": "Questionable",
                "practice_participation": "Limited Participation",
                "injury_start_date": "2026-09-14",
                "depth_chart_order": 1,
            },
            "reserve": {
                "full_name": "Reserve Player",
                "position": "RB",
                "team": "TEN",
                "status": "Active",
            },
        },
        "matchups": [],
        "transactions": [],
        "traded_picks": [],
        "ranking_inputs": {
            "sleeper_projections": {"status": "available", "players": {}},
            "dynasty_daddy": {"status": "available", "players": {}},
            "redraft_daddy": {"status": "available", "players": {}},
        },
        "nfl_context": {},
    }


def test_newspaper_health_report_includes_general_status_and_ir_only():
    dossier = build_editorial_review(_snapshot("newspaper"))

    health = dossier["roster_health"]
    assert health["status"] == "available"
    assert {row["player"] for row in health["players"]} == {
        "Questionable Player",
        "Reserve Player",
    }

    questionable = next(
        row for row in health["players"] if row["player"] == "Questionable Player"
    )
    reserve = next(
        row for row in health["players"] if row["player"] == "Reserve Player"
    )
    assert questionable["injury_status"] == "Questionable"
    assert questionable["on_ir"] is False
    assert reserve["on_ir"] is True
    assert "practice_participation" not in questionable
    assert "injury_start_date" not in questionable
    assert "depth_chart_order" not in questionable

    markdown = render_editorial_review(dossier)
    assert "## Roster Health" in markdown
    assert "Questionable Player" in markdown
    assert "Reserve Player" in markdown
    assert "IR/RESERVE" in markdown
    assert "Limited Participation" not in markdown
    assert "2026-09-14" not in markdown


def test_flagship_health_report_retains_expanded_health_context():
    snapshot = _snapshot("flagship")
    snapshot["flagship_sleeper"] = {
        "schedule": {"status": "available", "weeks": {}},
        "transactions": {"status": "available", "weeks": {}},
        "drafts": {"status": "available", "records": []},
        "playoff_brackets": {"status": "available", "winners": [], "losers": []},
        "next_week_projections": {"status": "not_applicable", "players": {}},
    }

    dossier = build_editorial_review(snapshot)
    health = dossier["roster_health"]
    questionable = next(
        row for row in health["players"] if row["player"] == "Questionable Player"
    )

    assert questionable["practice_participation"] == "Limited Participation"
    assert questionable["injury_start_date"] == "2026-09-14"
    assert questionable["depth_chart_order"] == 1

    markdown = render_editorial_review(dossier)
    assert "Limited Participation" in markdown
    assert "injury start 2026-09-14" in markdown


def test_healthy_roster_is_reported_as_clear_not_unavailable():
    snapshot = _snapshot("newspaper")
    snapshot["rosters"][0]["players"] = ["healthy"]
    snapshot["rosters"][0]["reserve"] = []

    dossier = build_editorial_review(snapshot)

    assert dossier["roster_health"] == {"status": "available", "players": []}
    markdown = render_editorial_review(dossier)
    assert "No roster health flags returned" in markdown
    assert "injury data unavailable" not in markdown.lower()
