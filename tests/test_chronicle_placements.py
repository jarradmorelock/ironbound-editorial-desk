from editorial_desk.chronicle_events import make_event
from editorial_desk.chronicle_identity import IdentityRegistry
from editorial_desk.chronicle_materialize import materialize_league


def test_completed_winners_bracket_placement_materializes_champion_and_runner_up():
    registry = IdentityRegistry.empty()
    winner = registry.register_dynasty_season(
        league_key="demo", season="2025", roster_id=1, owner_id="a", team_name="A"
    )
    runner_up = registry.register_dynasty_season(
        league_key="demo", season="2025", roster_id=2, owner_id="b", team_name="B"
    )
    event = make_event(
        event_type="PLAYOFF_BRACKET_RESULT",
        source="sleeper_bracket",
        source_ref="league:L25:bracket:winners:round:3:match:6",
        league_key="demo",
        season="2025",
        week=None,
        provenance="reconstructed_from_sleeper",
        entities={"bracket": "winners", "round": 3, "match": 6},
        observed_at="backfill:2025",
        evidence={"r": 3, "m": 6, "w": 1, "l": 2, "p": 1},
    )

    history = materialize_league([event], registry)

    winner_row = history.seasons[f"2025:{winner.franchise_key}"]
    runner_row = history.seasons[f"2025:{runner_up.franchise_key}"]
    assert winner_row["finish"] == 1
    assert winner_row["champion"] is True
    assert runner_row["finish"] == 2
    assert runner_row["champion"] is False


def test_incomplete_or_non_winners_bracket_rows_do_not_invent_placements():
    registry = IdentityRegistry.empty()
    identity = registry.register_dynasty_season(
        league_key="demo", season="2025", roster_id=1, owner_id="a", team_name="A"
    )
    event = make_event(
        event_type="PLAYOFF_BRACKET_RESULT",
        source="sleeper_bracket",
        source_ref="league:L25:bracket:losers:round:3:match:6",
        league_key="demo",
        season="2025",
        week=None,
        provenance="reconstructed_from_sleeper",
        entities={"bracket": "losers", "round": 3, "match": 6},
        observed_at="backfill:2025",
        evidence={"r": 3, "m": 6, "w": 1, "l": 2, "p": 1},
    )

    history = materialize_league([event], registry)
    assert f"2025:{identity.franchise_key}" not in history.seasons
