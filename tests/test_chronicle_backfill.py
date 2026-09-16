from dataclasses import dataclass

from editorial_desk.chronicle_backfill import (
    BackfillError,
    SeasonRef,
    backfill_season,
    discover_seasons,
)
from editorial_desk.chronicle_identity import IdentityRegistry


@dataclass(frozen=True)
class League:
    key: str = "demo"
    league_format: str = "dynasty"


class ChainClient:
    def __init__(self):
        self.rows = {
            "l26": {"league_id": "l26", "season": "2026", "name": "Demo", "previous_league_id": "l25"},
            "l25": {"league_id": "l25", "season": "2025", "name": "Demo", "previous_league_id": "l24"},
            "l24": {"league_id": "l24", "season": "2024", "name": "Demo", "previous_league_id": None},
        }

    def league(self, league_id):
        return self.rows[league_id]


def test_discover_seasons_returns_oldest_to_newest():
    seasons = discover_seasons(ChainClient(), "l26")
    assert [(row.season, row.league_id) for row in seasons] == [
        ("2024", "l24"),
        ("2025", "l25"),
        ("2026", "l26"),
    ]


def test_discover_seasons_rejects_cycles():
    client = ChainClient()
    client.rows["l24"]["previous_league_id"] = "l26"
    try:
        discover_seasons(client, "l26")
    except BackfillError as exc:
        assert "cycle" in str(exc).lower()
        assert "l26" in str(exc)
    else:
        raise AssertionError("expected BackfillError")


class HistoryClient:
    def users(self, league_id):
        return [{"user_id": "u1", "display_name": "A"}, {"user_id": "u2", "display_name": "B"}]

    def rosters(self, league_id):
        return [{"roster_id": 1, "owner_id": "u1"}, {"roster_id": 2, "owner_id": "u2"}]

    def matchups(self, league_id, week):
        if week == 1:
            return [
                {"matchup_id": 1, "roster_id": 1, "points": 120.0},
                {"matchup_id": 1, "roster_id": 2, "points": 110.0},
            ]
        return []

    def transactions(self, league_id, week):
        if week == 1:
            return [{
                "transaction_id": "tx1",
                "status": "complete",
                "type": "waiver",
                "created": 1700000000000,
                "roster_ids": [1],
                "adds": {"p1": 1},
                "drops": {},
                "settings": {"waiver_bid": 7},
            }]
        return []

    def drafts(self, league_id):
        return [{"draft_id": "d1", "type": "rookie"}]

    def draft_picks(self, draft_id):
        return [{"pick_no": 1, "round": 1, "roster_id": 1, "player_id": "rookie1"}]

    def draft_traded_picks(self, draft_id):
        return []

    def traded_picks(self, league_id):
        return [{"season": "2027", "round": 1, "roster_id": 1, "owner_id": 2, "previous_owner_id": 1}]

    def winners_bracket(self, league_id):
        return [{"r": 1, "m": 1, "w": 1, "l": 2}]

    def losers_bracket(self, league_id):
        return []


def test_backfill_normalizes_durable_history_without_fabricating_health():
    season = SeasonRef(
        league_id="l25",
        season="2025",
        name="Demo",
        previous_league_id=None,
        league={"settings": {"playoff_week_start": 15}},
    )
    result = backfill_season(HistoryClient(), season, League(), IdentityRegistry.empty())
    event_types = {event.event_type for event in result.events}
    assert {"MATCHUP_FINAL", "WAIVER_ADD", "DRAFT_PICK", "TRADED_PICK", "PLAYOFF_BRACKET_RESULT"} <= event_types
    assert "PLAYER_STATUS_CHANGE" not in event_types
    waiver = next(event for event in result.events if event.event_type == "WAIVER_ADD")
    assert waiver.occurred_at is not None
    assert waiver.provenance == "source_exact"
