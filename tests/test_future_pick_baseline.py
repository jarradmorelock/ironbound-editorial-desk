from __future__ import annotations

from editorial_desk.future_pick_baseline import compare_paid_baseline


def test_payment_log_baseline_flags_outgoing_unrecorded_and_unpaid_future_picks():
    baseline = {
        "league_key": "ironbound_sixteen",
        "recorded_as_of": "2026-11-10",
        "seasons": {"2027": [
            {"team": f"Team {n}", "picks_traded": n in (1, 2),
             "paid": n == 2}
            for n in range(1, 17)
        ]},
    }
    snapshot = {
        "users": [
            {"user_id": f"u{n}", "display_name": f"Team {n}"}
            for n in range(1, 17)
        ],
        "rosters": [{"roster_id": n, "owner_id": f"u{n}"}
                    for n in range(1, 17)],
    }
    trades = {"x1": {
        "transaction_id": "x1",
        "draft_picks": [
            {"season": "2027", "round": 2, "roster_id": 4,
             "previous_owner_id": 3, "owner_id": 4},
            {"season": "2027", "round": 3, "roster_id": 2,
             "owner_id": 1},  # ambiguous sender: never guess
        ],
    }}
    result = compare_paid_baseline(baseline, snapshot, trades)
    assert len(result["rows"]) == 16
    assert result["matched_team_count"] == 16
    team1 = next(r for r in result["rows"] if r["team"] == "Team 1")
    team3 = next(r for r in result["rows"] if r["team"] == "Team 3")
    assert "recorded unpaid" in team1["finding"]
    assert "workbook says No" in team3["finding"]
    assert len(result["ambiguous_picks"]) == 1
    assert len(result["flagged"]) == 2


def test_ambiguous_names_are_not_guessed_from_row_position():
    baseline = {
        "league_key": "ironbound_sixteen",
        "seasons": {"2029": [
            {"team": f"Team {n}", "picks_traded": False, "paid": False}
            for n in range(1, 17)
        ]},
    }
    snapshot = {
        "users": [
            {"user_id": f"u{n}", "display_name": "Team 1" if n in (1, 2) else f"Team {n}"}
            for n in range(1, 17)
        ],
        "rosters": [{"roster_id": n, "owner_id": f"u{n}"}
                    for n in range(1, 17)],
    }
    report = compare_paid_baseline(baseline, snapshot, {})
    assert any("exact Sleeper team name" in x["finding"] for x in report["flagged"])


def test_reject_other_league_baseline():
    baseline = {"league_key": "free_ironbound_sixteen", "seasons": {"2027": []}}
    try:
        compare_paid_baseline(baseline, {}, {})
    except ValueError as exc:
        assert "Paid Ironbound" in str(exc)
    else:
        raise AssertionError("Expected refusal to mix paid and free league audit")
