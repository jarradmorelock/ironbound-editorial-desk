from editorial_desk.chronicle_identity import IdentityOverride, IdentityRegistry
from editorial_desk.chronicle_materialize import materialize_league
from editorial_desk.chronicle_events import make_event
from editorial_desk.chronicle_store import ChronicleStore


def _registry():
    registry = IdentityRegistry.empty()
    first = registry.register_dynasty_season(
        league_key="demo",
        season="2025",
        roster_id=1,
        owner_id="u1",
        team_name="Old Name",
        manager_name="Manager One",
    )
    registry.apply_override(
        IdentityOverride("demo", "2026", 1, first.franchise_key, "confirmed")
    )
    registry.bootstrap_dynasty_season(
        league_key="demo",
        season="2026",
        rosters=[{"roster_id": 1, "owner_id": "u2", "team_name": "New Name", "manager_name": "Manager Two"}],
    )
    return registry


def test_store_round_trips_identity_registry_and_ambiguities(tmp_path):
    store = ChronicleStore(tmp_path)
    registry = _registry()
    store.write_identity_registry(registry)
    restored = store.read_identity_registry()
    assert restored.to_dict() == registry.to_dict()


def test_store_persists_backfill_coverage(tmp_path):
    store = ChronicleStore(tmp_path)
    coverage = {"demo": {"seasons": ["2024", "2025"], "warnings": ["2024 trades unavailable"]}}
    store.write_backfill_coverage(coverage)
    assert store.read_backfill_coverage() == coverage


def test_store_reads_all_league_events_across_seasons_and_writes_history(tmp_path):
    store = ChronicleStore(tmp_path)
    registry = IdentityRegistry.empty()
    a = registry.register_dynasty_season(
        league_key="demo", season="2025", roster_id=1, owner_id="u1", team_name="A"
    )
    b = registry.register_dynasty_season(
        league_key="demo", season="2025", roster_id=2, owner_id="u2", team_name="B"
    )
    event = make_event(
        event_type="MATCHUP_FINAL",
        source="sleeper_matchups",
        source_ref="demo-2025-1",
        league_key="demo",
        season="2025",
        week=1,
        provenance="reconstructed_from_sleeper",
        entities={"matchup_id": 1},
        observed_at="backfill:2025",
        evidence={
            "matchup_id": 1,
            "competition": "regular_season",
            "rosters": [
                {"roster_id": 1, "points": 120},
                {"roster_id": 2, "points": 100},
            ],
        },
    )
    store.append_events([event])
    assert [row["event_id"] for row in store.read_all_league_events("demo")] == [event.event_id]
    assert store.league_keys() == ("demo",)

    history = materialize_league(store.read_all_league_events("demo"), registry)
    store.write_materialized_history(history)
    assert (tmp_path / "leagues" / "demo" / "history" / "records.json").exists()
    assert (tmp_path / "leagues" / "demo" / "history" / "matchups.json").exists()
    assert a.franchise_key in (tmp_path / "leagues" / "demo" / "history" / "records.json").read_text()
    assert b.franchise_key in (tmp_path / "leagues" / "demo" / "history" / "records.json").read_text()
