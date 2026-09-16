from editorial_desk.chronicle_events import make_event
from editorial_desk.chronicle_identity import IdentityOverride, IdentityRegistry
from editorial_desk.chronicle_materialize import effective_events, materialize_league


def _match(event_id_suffix, season, week, left_points, right_points):
    return make_event(
        event_type="MATCHUP_FINAL",
        source="sleeper_matchups",
        source_ref=f"match:{event_id_suffix}",
        league_key="demo",
        season=str(season),
        week=week,
        provenance="reconstructed_from_sleeper",
        entities={"matchup_id": event_id_suffix},
        observed_at=f"backfill:{season}",
        evidence={
            "matchup_id": event_id_suffix,
            "competition": "regular_season",
            "rosters": [
                {"roster_id": 1, "points": left_points},
                {"roster_id": 2, "points": right_points},
            ],
        },
    )


def _registry():
    registry = IdentityRegistry.empty()
    a = registry.register_dynasty_season(
        league_key="demo", season="2025", roster_id=1, owner_id="a", team_name="A"
    )
    b = registry.register_dynasty_season(
        league_key="demo", season="2025", roster_id=2, owner_id="b", team_name="B"
    )
    registry.apply_override(IdentityOverride("demo", "2026", 1, a.franchise_key, "same franchise"))
    registry.apply_override(IdentityOverride("demo", "2026", 2, b.franchise_key, "same franchise"))
    registry.register_dynasty_season(
        league_key="demo", season="2026", roster_id=1, owner_id="a", team_name="A"
    )
    registry.register_dynasty_season(
        league_key="demo", season="2026", roster_id=2, owner_id="b", team_name="B"
    )
    return registry, a.franchise_key, b.franchise_key


def test_new_live_result_updates_backfilled_all_time_series():
    registry, a, b = _registry()
    historical = [_match(f"old-{n}", 2025, n + 1, 120, 100) for n in range(13)]
    historical += [_match("loss", 2025, 14, 90, 100), _match("tie", 2025, 15, 100, 100)]
    new_live = _match("new", 2026, 1, 130, 100)

    history = materialize_league(historical + [new_live], registry)
    series = history.head_to_head[tuple(sorted((a, b)))]
    if series.identity_a == a:
        assert (series.wins_a, series.wins_b, series.ties) == (14, 1, 1)
    else:
        assert (series.wins_a, series.wins_b, series.ties) == (1, 14, 1)


def test_correction_supersedes_original_without_deleting_audit_event():
    registry, _, _ = _registry()
    original = _match("bad", 2025, 1, 120, 100)
    correction = make_event(
        event_type="MATCHUP_FINAL",
        source="manual_correction",
        source_ref="match:bad:corrected",
        league_key="demo",
        season="2025",
        week=1,
        provenance="source_exact",
        entities={"matchup_id": "bad"},
        observed_at="2026-09-16T12:00:00+00:00",
        evidence={
            "matchup_id": "bad",
            "competition": "regular_season",
            "rosters": [
                {"roster_id": 1, "points": 99},
                {"roster_id": 2, "points": 101},
            ],
        },
        correction_of=original.event_id,
    )
    rows = effective_events([original, correction])
    assert original not in rows
    assert correction in rows

    history = materialize_league([original, correction], registry)
    assert len(history.matchups) == 1
    assert history.matchups[0]["left_points"] in {99.0, 101.0}


def test_coverage_warning_marks_history_incomplete():
    registry, _, _ = _registry()
    history = materialize_league(
        [_match("one", 2025, 1, 120, 100)],
        registry,
        coverage_warnings=["2024 transactions unavailable"],
    )
    assert history.coverage_complete is False
    assert history.coverage_warnings == ("2024 transactions unavailable",)


def test_record_events_are_derived_from_matchups_not_prior_materialized_totals():
    registry, _, _ = _registry()
    history = materialize_league(
        [_match("one", 2025, 1, 120, 100), _match("two", 2025, 2, 140, 90)],
        registry,
    )
    types = [event.evidence["record_type"] for event in history.record_events]
    assert "all_time_team_high_score" in types
    assert "all_time_largest_margin" in types
