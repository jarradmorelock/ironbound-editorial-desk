from editorial_desk.chronicle_identity import (
    IdentityOverride,
    IdentityRegistry,
)


def test_dynasty_owner_change_requires_override_and_preserves_franchise_after_override():
    registry = IdentityRegistry.empty()
    first = registry.register_dynasty_season(
        league_key="demo",
        season="2025",
        roster_id=3,
        owner_id="u1",
        team_name="Old Name",
        manager_name="Manager One",
    )

    attempted = registry.bootstrap_dynasty_season(
        league_key="demo",
        season="2026",
        rosters=[
            {
                "roster_id": 3,
                "owner_id": "u2",
                "team_name": "New Name",
                "manager_name": "Manager Two",
            }
        ],
    )
    assert attempted.mappings == ()
    assert len(attempted.ambiguities) == 1

    registry.apply_override(
        IdentityOverride(
            league_key="demo",
            season="2026",
            roster_id=3,
            franchise_key=first.franchise_key,
            reason="confirmed ownership transfer",
        )
    )
    resolved = registry.bootstrap_dynasty_season(
        league_key="demo",
        season="2026",
        rosters=[
            {
                "roster_id": 3,
                "owner_id": "u2",
                "team_name": "New Name",
                "manager_name": "Manager Two",
            }
        ],
    )
    assert resolved.ambiguities == ()
    assert resolved.mappings[0].franchise_key == first.franchise_key
    assert [row.name for row in registry.aliases(first.franchise_key)] == [
        "Old Name",
        "New Name",
    ]
    assert [row.owner_id for row in registry.manager_tenures(first.franchise_key)] == [
        "u1",
        "u2",
    ]


def test_redraft_returning_owner_keeps_manager_identity_across_team_names():
    registry = IdentityRegistry.empty()
    first = registry.register_redraft_season(
        league_key="family",
        season="2025",
        roster_id=1,
        owner_id="owner-7",
        team_name="First Team",
    )
    second = registry.register_redraft_season(
        league_key="family",
        season="2026",
        roster_id=4,
        owner_id="owner-7",
        team_name="Renamed Team",
    )
    assert first.manager_key == second.manager_key


def test_redraft_orphan_rosters_do_not_collapse_to_same_manager_identity():
    registry = IdentityRegistry.empty()
    first = registry.register_redraft_season(
        league_key="family",
        season="2026",
        roster_id=1,
        owner_id="",
        team_name="Orphan One",
    )
    second = registry.register_redraft_season(
        league_key="family",
        season="2026",
        roster_id=2,
        owner_id="",
        team_name="Orphan Two",
    )
    assert first.manager_key != second.manager_key


def test_registry_round_trip_preserves_override_aliases_tenures_and_ambiguity():
    registry = IdentityRegistry.empty()
    first = registry.register_dynasty_season(
        league_key="demo",
        season="2025",
        roster_id=1,
        owner_id="u1",
        team_name="Alpha",
        manager_name="A",
    )
    registry.bootstrap_dynasty_season(
        league_key="demo",
        season="2026",
        rosters=[
            {
                "roster_id": 1,
                "owner_id": "u2",
                "team_name": "Beta",
                "manager_name": "B",
            }
        ],
    )
    registry.apply_override(
        IdentityOverride(
            league_key="demo",
            season="2027",
            roster_id=1,
            franchise_key=first.franchise_key,
            reason="manual",
        )
    )

    restored = IdentityRegistry.from_dict(registry.to_dict())
    assert restored.to_dict() == registry.to_dict()
