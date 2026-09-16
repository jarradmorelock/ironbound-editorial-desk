from dataclasses import dataclass
import json

import requests

from editorial_desk.chronicle_backfill import run_backfill
from editorial_desk.chronicle_identity import IdentityOverride, IdentityRegistry
from editorial_desk.chronicle_store import ChronicleStore


@dataclass(frozen=True)
class League:
    key: str = "demo"
    sleeper_league_id: str = "L26"
    league_format: str = "dynasty"


class MultiSeasonClient:
    def league(self, league_id):
        rows = {
            "L25": {
                "league_id": "L25",
                "season": "2025",
                "name": "Demo",
                "previous_league_id": None,
                "settings": {"playoff_week_start": 15},
            },
            "L26": {
                "league_id": "L26",
                "season": "2026",
                "name": "Demo",
                "previous_league_id": "L25",
                "settings": {"playoff_week_start": 15},
            },
        }
        return rows[league_id]

    def nfl_state(self):
        return {"season": "2026", "week": 3}

    def users(self, league_id):
        if league_id == "L25":
            return [
                {"user_id": "u1", "display_name": "Alice", "metadata": {"team_name": "Old Forge"}},
                {"user_id": "u2", "display_name": "Bob", "metadata": {"team_name": "Anvil"}},
            ]
        return [
            {"user_id": "u3", "display_name": "Carol", "metadata": {"team_name": "New Forge"}},
            {"user_id": "u2", "display_name": "Bob", "metadata": {"team_name": "Anvil"}},
        ]

    def rosters(self, league_id):
        if league_id == "L25":
            return [
                {"roster_id": 1, "owner_id": "u1"},
                {"roster_id": 2, "owner_id": "u2"},
            ]
        return [
            {"roster_id": 1, "owner_id": "u3"},
            {"roster_id": 2, "owner_id": "u2"},
        ]

    def matchups(self, league_id, week):
        if league_id == "L25" and week == 15:
            return [
                {"matchup_id": 9, "roster_id": 1, "points": 140.0},
                {"matchup_id": 9, "roster_id": 2, "points": 130.0},
            ]
        if league_id == "L26" and week == 1:
            return [
                {"matchup_id": 1, "roster_id": 1, "points": 125.0},
                {"matchup_id": 1, "roster_id": 2, "points": 115.0},
            ]
        return []

    def transactions(self, league_id, week):
        if league_id == "L25" and week == 2:
            return [{
                "transaction_id": "trade-25",
                "status": "complete",
                "type": "trade",
                "created": 1730000000000,
                "roster_ids": [1, 2],
                "adds": {},
                "drops": {},
                "settings": {},
            }]
        if league_id == "L26" and week == 1:
            return [{
                "transaction_id": "waiver-26",
                "status": "complete",
                "type": "waiver",
                "created": 1760000000000,
                "roster_ids": [1],
                "adds": {"player-x": 1},
                "drops": {},
                "settings": {"waiver_bid": 11},
            }]
        return []

    def drafts(self, league_id):
        return []

    def traded_picks(self, league_id):
        if league_id == "L25":
            return [{
                "season": "2027",
                "round": 1,
                "roster_id": 1,
                "owner_id": 2,
                "previous_owner_id": 1,
            }]
        return []

    def winners_bracket(self, league_id):
        if league_id == "L25":
            return [{"r": 1, "m": 9, "w": 1, "l": 2}]
        return []

    def losers_bracket(self, league_id):
        if league_id == "L25":
            raise requests.RequestException("old consolation bracket unavailable")
        return []


def _history_bytes(root):
    return {
        path.name: path.read_bytes()
        for path in sorted((root / "leagues" / "demo" / "history").glob("*.json"))
    }


def test_backfill_resolves_transfer_then_remains_idempotent(tmp_path):
    store = ChronicleStore(tmp_path)
    client = MultiSeasonClient()

    first = run_backfill([League()], client, store)
    assert first.failed_leagues == ("demo",)
    assert first.unresolved_ambiguities

    registry = store.read_identity_registry()
    old_franchise = registry.franchise_for("demo", "2025", 1)
    registry.apply_override(
        IdentityOverride(
            league_key="demo",
            season="2026",
            roster_id=1,
            franchise_key=old_franchise,
            reason="commissioner confirmed franchise transfer",
        )
    )
    store.write_identity_registry(registry)

    second = run_backfill([League()], client, store)
    assert second.failed_leagues == ()
    assert second.unresolved_ambiguities == ()

    registry = store.read_identity_registry()
    assert registry.franchise_for("demo", "2026", 1) == old_franchise
    assert [alias.name for alias in registry.aliases(old_franchise)] == [
        "Old Forge",
        "New Forge",
    ]
    assert [tenure.owner_id for tenure in registry.manager_tenures(old_franchise)] == [
        "u1",
        "u3",
    ]

    history_root = tmp_path / "leagues" / "demo" / "history"
    matchup_doc = json.loads((history_root / "matchups.json").read_text())
    assert any(row["competition"] == "playoffs" for row in matchup_doc["matchups"])
    assert {row["season"] for row in matchup_doc["matchups"]} == {"2025", "2026"}

    transactions = json.loads((history_root / "transactions.json").read_text())["transactions"]
    assert {row["event_type"] for row in transactions} >= {"TRADE", "WAIVER_ADD", "TRADED_PICK"}
    assert {row["season"] for row in transactions} >= {"2025", "2026"}

    assert not any(
        row["event_type"] == "PLAYER_STATUS_CHANGE"
        for row in store.read_all_league_events("demo")
    )
    coverage = store.read_backfill_coverage()["demo"]
    assert any("consolation bracket unavailable" in warning for warning in coverage["warnings"])

    before = _history_bytes(tmp_path)
    third = run_backfill([League()], client, store)
    after = _history_bytes(tmp_path)
    assert third.added_events == 0
    assert before == after


def test_redraft_manager_identity_survives_annual_team_name_change():
    registry = IdentityRegistry.empty()
    one = registry.register_redraft_season(
        league_key="family",
        season="2025",
        roster_id=1,
        owner_id="same-owner",
        team_name="Team One",
    )
    two = registry.register_redraft_season(
        league_key="family",
        season="2026",
        roster_id=7,
        owner_id="same-owner",
        team_name="Totally Different Name",
    )
    assert one.manager_key == two.manager_key
