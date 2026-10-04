from dataclasses import dataclass

from editorial_desk.chronicle_backfill import SeasonRef, backfill_season
from editorial_desk.chronicle_identity import IdentityRegistry


@dataclass(frozen=True)
class League:
    key: str = "demo"
    league_format: str = "dynasty"


class CurrentSeasonClient:
    def users(self, league_id):
        return [{"user_id": "u1", "display_name": "A"}, {"user_id": "u2", "display_name": "B"}]

    def rosters(self, league_id):
        return [{"roster_id": 1, "owner_id": "u1"}, {"roster_id": 2, "owner_id": "u2"}]

    def matchups(self, league_id, week):
        if week in {1, 2}:
            return [
                {"matchup_id": 1, "roster_id": 1, "points": 120.0 + week},
                {"matchup_id": 1, "roster_id": 2, "points": 110.0},
            ]
        return []

    def transactions(self, league_id, week):
        return []

    def drafts(self, league_id):
        return []

    def traded_picks(self, league_id):
        return []

    def winners_bracket(self, league_id):
        return []

    def losers_bracket(self, league_id):
        return []


def test_current_season_backfill_only_finalizes_completed_matchup_weeks():
    season = SeasonRef(
        league_id="l26",
        season="2026",
        name="Demo",
        previous_league_id=None,
        league={"settings": {"playoff_week_start": 15}},
    )
    result = backfill_season(
        CurrentSeasonClient(),
        season,
        League(),
        IdentityRegistry.empty(),
        max_final_week=1,
    )
    assert [
        event.week for event in result.events if event.event_type == "MATCHUP_FINAL"
    ] == [1]
