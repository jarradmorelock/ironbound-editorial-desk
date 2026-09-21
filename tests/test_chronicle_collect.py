from dataclasses import dataclass
from pathlib import Path

import requests

from editorial_desk.chronicle_collect import collect_pulse
from editorial_desk.chronicle_store import ChronicleStore


@dataclass
class League:
    key: str
    sleeper_league_id: str


class FakeClient:
    def __init__(self):
        self.calls = []
        self.player_payload = {
            "p1": {"status": "Active", "injury_status": None},
            "p2": {"status": "Active", "injury_status": "Questionable"},
            "unused": {"status": "Active", "injury_status": "Out"},
        }
        self.fail_rosters_for = set()

    def nfl_state(self):
        self.calls.append(("nfl_state",))
        return {"season": "2026", "week": 2}

    def players(self):
        self.calls.append(("players",))
        return self.player_payload

    def league(self, league_id):
        self.calls.append(("league", league_id))
        return {"league_id": league_id, "season": "2026"}

    def users(self, league_id):
        self.calls.append(("users", league_id))
        return []

    def rosters(self, league_id):
        self.calls.append(("rosters", league_id))
        if league_id in self.fail_rosters_for:
            raise requests.RequestException("boom")
        return [
            {
                "roster_id": 1,
                "owner_id": "u1",
                "players": ["p1", "p2"],
                "reserve": [],
                "taxi": [],
            },
            {
                "roster_id": 2,
                "owner_id": "u2",
                "players": ["p1"],
                "reserve": [],
                "taxi": [],
            },
        ]

    def matchups(self, league_id, week):
        self.calls.append(("matchups", league_id, week))
        return [
            {
                "roster_id": 1,
                "matchup_id": 1,
                "points": 110.0,
                "starters": ["p1"],
                "players": ["p1", "p2"],
            },
            {
                "roster_id": 2,
                "matchup_id": 1,
                "points": 100.0,
                "starters": ["p1"],
                "players": ["p1"],
            },
        ]

    def transactions(self, league_id, week):
        self.calls.append(("transactions", league_id, week))
        return [
            {
                "transaction_id": f"tx-{league_id}",
                "type": "trade",
                "status": "complete",
                "created": 1789500000000,
                "adds": {"p2": 1},
                "drops": {},
                "roster_ids": [1, 2],
                "settings": {},
            }
        ]

    def traded_picks(self, league_id):
        self.calls.append(("traded_picks", league_id))
        return []

    def drafts(self, *args):
        raise AssertionError("pulse collector must not call drafts")

    def winners_bracket(self, *args):
        raise AssertionError("pulse collector must not call winners bracket")

    def losers_bracket(self, *args):
        raise AssertionError("pulse collector must not call losers bracket")

    def projections(self, *args):
        raise AssertionError("pulse collector must not call projections")


def test_pulse_call_budget_and_cross_league_status_event_is_deduplicated(
    tmp_path: Path,
):
    store = ChronicleStore(tmp_path)
    client = FakeClient()
    leagues = [League("a", "1"), League("b", "2")]

    collect_pulse(leagues, client, store, 2, "2026-09-16T17:05:00+00:00")
    client.player_payload["p1"] = {
        "status": "Inactive",
        "injury_status": "Out",
    }
    result = collect_pulse(
        leagues, client, store, 2, "2026-09-16T21:04:00+00:00"
    )

    status_events = [
        row
        for row in store.read_events(None, "2026")
        if row["event_type"] == "PLAYER_STATUS_CHANGE"
        and row["entities"]["player_id"] == "p1"
    ]
    assert len(status_events) == 1
    assert status_events[0]["league_key"] is None
    assert status_events[0]["observed_before"] == "2026-09-16T17:05:00+00:00"
    assert status_events[0]["observed_after"] == "2026-09-16T21:04:00+00:00"
    assert not any(
        row["entities"].get("player_id") == "unused"
        for row in store.read_events(None, "2026")
    )
    assert result["source_freshness"]["player_health"] == "fresh"
    assert sum(1 for call in client.calls if call[0] == "players") == 2


def test_pulse_does_not_write_matchup_final_until_explicitly_finalized(
    tmp_path: Path,
):
    store = ChronicleStore(tmp_path)
    client = FakeClient()
    leagues = [League("a", "1")]
    collect_pulse(
        leagues,
        client,
        store,
        2,
        "2026-09-16T17:05:00+00:00",
        finalize_matchups=False,
    )
    assert not [
        row
        for row in store.read_events("a", "2026")
        if row["event_type"] == "MATCHUP_FINAL"
    ]

    collect_pulse(
        leagues,
        client,
        store,
        2,
        "2026-09-17T02:00:00+00:00",
        finalize_matchups=True,
    )
    finals = [
        row
        for row in store.read_events("a", "2026")
        if row["event_type"] == "MATCHUP_FINAL"
    ]
    assert len(finals) == 1
    assert finals[0]["evidence"]["winner_roster_id"] == 1


def test_failed_health_refresh_does_not_create_fake_healthy_transition(
    tmp_path: Path,
):
    store = ChronicleStore(tmp_path)
    client = FakeClient()
    leagues = [League("a", "1")]
    collect_pulse(leagues, client, store, 2, "2026-09-16T17:05:00+00:00")

    def fail_players():
        raise requests.RequestException("players unavailable")

    client.players = fail_players
    result = collect_pulse(
        leagues, client, store, 2, "2026-09-16T21:04:00+00:00"
    )
    assert result["source_freshness"]["player_health"] == "stale"
    assert not [
        row
        for row in store.read_events(None, "2026")
        if row["event_type"] == "PLAYER_STATUS_CHANGE"
    ]


def test_one_league_failure_does_not_discard_other_league_events(tmp_path: Path):
    store = ChronicleStore(tmp_path)
    client = FakeClient()
    client.fail_rosters_for.add("2")
    result = collect_pulse(
        [League("a", "1"), League("b", "2")],
        client,
        store,
        2,
        "2026-09-16T17:05:00+00:00",
    )
    assert result["leagues"]["a"]["status"] == "fresh"
    assert result["leagues"]["b"]["status"] == "unavailable"
    assert any(
        row["event_type"] == "TRADE"
        for row in store.read_events("a", "2026")
    )


def test_live_coverage_starts_on_first_success_and_never_moves_forward(
    tmp_path: Path,
):
    store = ChronicleStore(tmp_path)
    client = FakeClient()
    leagues = [League("a", "1")]

    original_players = client.players

    def fail_players():
        raise requests.RequestException("down")

    client.players = fail_players
    collect_pulse(leagues, client, store, 2, "2026-09-16T10:00:00+00:00")
    coverage = store.read_coverage()
    assert "player_health" not in (coverage.get("global") or {})

    client.players = original_players
    collect_pulse(leagues, client, store, 2, "2026-09-16T12:00:00+00:00")
    coverage = store.read_coverage()
    assert (
        coverage["global"]["player_health"]["first_success"]
        == "2026-09-16T12:00:00+00:00"
    )
    assert (
        coverage["leagues"]["a"]["lineups"]["first_success"]
        == "2026-09-16T10:00:00+00:00"
    )
    assert (
        coverage["leagues"]["a"]["reserve"]["first_success"]
        == "2026-09-16T10:00:00+00:00"
    )

    collect_pulse(leagues, client, store, 2, "2026-09-16T14:00:00+00:00")
    coverage = store.read_coverage()
    assert (
        coverage["global"]["player_health"]["first_success"]
        == "2026-09-16T12:00:00+00:00"
    )
    assert (
        coverage["leagues"]["a"]["lineups"]["first_success"]
        == "2026-09-16T10:00:00+00:00"
    )


def test_failed_league_refresh_preserves_previous_player_scope_for_global_status(
    tmp_path: Path,
):
    class ScopedClient(FakeClient):
        def rosters(self, league_id):
            self.calls.append(("rosters", league_id))
            if league_id in self.fail_rosters_for:
                raise requests.RequestException("boom")
            player = "p1" if league_id == "1" else "p2"
            return [
                {
                    "roster_id": 1,
                    "owner_id": f"u-{league_id}",
                    "players": [player],
                    "reserve": [],
                    "taxi": [],
                }
            ]

        def matchups(self, league_id, week):
            self.calls.append(("matchups", league_id, week))
            player = "p1" if league_id == "1" else "p2"
            return [
                {
                    "roster_id": 1,
                    "matchup_id": 1,
                    "points": 10.0,
                    "starters": [player],
                    "players": [player],
                }
            ]

        def transactions(self, league_id, week):
            self.calls.append(("transactions", league_id, week))
            return []

    store = ChronicleStore(tmp_path)
    client = ScopedClient()
    leagues = [League("a", "1"), League("b", "2")]
    collect_pulse(leagues, client, store, 2, "2026-09-16T17:05:00+00:00")

    client.player_payload["p2"] = {
        "status": "Inactive",
        "injury_status": "Out",
    }
    client.fail_rosters_for.add("2")
    collect_pulse(leagues, client, store, 2, "2026-09-16T21:04:00+00:00")

    assert any(
        row["event_type"] == "PLAYER_STATUS_CHANGE"
        and row["entities"]["player_id"] == "p2"
        for row in store.read_events(None, "2026")
    )


def test_unknown_transaction_type_is_not_mislabeled_as_free_agent_add(
    tmp_path: Path,
):
    class UnknownTxClient(FakeClient):
        def transactions(self, league_id, week):
            self.calls.append(("transactions", league_id, week))
            return [
                {
                    "transaction_id": "tx-unknown",
                    "type": "commissioner",
                    "status": "complete",
                    "created": 1789500000000,
                    "adds": {"p2": 1},
                    "drops": {},
                    "roster_ids": [1],
                    "settings": {},
                }
            ]

    store = ChronicleStore(tmp_path)
    collect_pulse(
        [League("a", "1")],
        UnknownTxClient(),
        store,
        2,
        "2026-09-16T17:05:00+00:00",
    )
    assert not [
        row
        for row in store.read_events("a", "2026")
        if row["event_type"] == "FREE_AGENT_ADD"
    ]


def test_lightweight_pulse_does_not_fetch_users_when_identity_is_not_needed(
    tmp_path: Path,
):
    store = ChronicleStore(tmp_path)
    client = FakeClient()
    collect_pulse(
        [League("a", "1")],
        client,
        store,
        2,
        "2026-09-16T17:05:00+00:00",
    )
    assert not any(call[0] == "users" for call in client.calls)


def test_finalize_matchups_persists_lineup_efficiency_event(tmp_path: Path):
    store = ChronicleStore(tmp_path)
    client = FakeClient()
    client.player_payload = {
        "p1": {"status": "Active", "injury_status": None, "position": "QB", "fantasy_positions": ["QB"]},
        "p2": {"status": "Active", "injury_status": None, "position": "QB", "fantasy_positions": ["QB"]},
    }

    original_league = client.league
    def league_with_slots(league_id):
        value = original_league(league_id)
        value["roster_positions"] = ["QB", "BN"]
        return value
    client.league = league_with_slots

    original_matchups = client.matchups
    def scored_matchups(league_id, week):
        rows = original_matchups(league_id, week)
        rows[0]["players_points"] = {"p1": 20, "p2": 10}
        rows[1]["players_points"] = {"p1": 15}
        return rows
    client.matchups = scored_matchups

    collect_pulse(
        [League("a", "1")],
        client,
        store,
        2,
        "2026-09-17T02:00:00+00:00",
        finalize_matchups=True,
    )

    rows = [
        row
        for row in store.read_events("a", "2026")
        if row["event_type"] == "LINEUP_EFFICIENCY_FINAL"
    ]
    assert len(rows) == 2
    first = next(row for row in rows if row["entities"]["roster_id"] == 1)
    assert first["evidence"]["actual_points"] == 20
    assert first["evidence"]["optimal_points"] == 20
    assert first["evidence"]["efficiency"] == 1.0
