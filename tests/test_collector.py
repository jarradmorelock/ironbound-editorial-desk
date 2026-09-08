import requests

from editorial_desk.collector import (
    _collect_ranking_sources,
    _trim_ranking_sources,
    collect_all,
    collect_league,
)
from editorial_desk.config import LeagueConfig


class FailingRankingsClient:
    def dynasty_daddy_player_values(self):
        raise requests.ConnectionError("ranking source offline")


class FailingSleeperClient:
    def projections(self, season, week):
        raise requests.ConnectionError("projection source offline")


class EmptyRankingsClient:
    def dynasty_daddy_player_values(self):
        return []


class EmptySleeperClient:
    def nfl_state(self):
        return {"season": "2026"}

    def players(self):
        return {}

    def projections(self, season, week):
        return {}

    def league(self, league_id):
        return {
            "league_id": league_id,
            "name": "Private League",
            "season": "2026",
            "settings": {},
            "roster_positions": [],
        }

    def users(self, league_id):
        return []

    def rosters(self, league_id):
        return []

    def matchups(self, league_id, week):
        return []

    def transactions(self, league_id, week):
        return []

    def traded_picks(self, league_id):
        return []


class FlagshipSleeperClient(EmptySleeperClient):
    def league(self, league_id):
        return {
            "league_id": league_id,
            "name": "Flagship League",
            "season": "2026",
            "settings": {"playoff_week_start": 15},
            "roster_positions": ["QB", "BN"],
        }

    def rosters(self, league_id):
        return [{"roster_id": 1, "owner_id": "u1", "players": ["p1"]}]

    def matchups(self, league_id, week):
        player_id = "p1" if week == 1 else "p2"
        return [
            {
                "matchup_id": 1,
                "roster_id": 1,
                "players": [player_id],
                "starters": [player_id],
                "players_points": {player_id: 10},
                "points": 10,
            }
        ]

    def transactions(self, league_id, week):
        if week != 1:
            return []
        return [
            {
                "transaction_id": "tx1",
                "status": "complete",
                "type": "waiver",
                "adds": {"p3": 1},
                "drops": {},
            }
        ]

    def drafts(self, league_id):
        return [{"draft_id": "d1", "season": "2026"}]

    def draft_picks(self, draft_id):
        return [{"player_id": "p4", "round": 1, "pick_no": 1}]

    def draft_traded_picks(self, draft_id):
        return [{"season": "2026", "round": 1}]

    def winners_bracket(self, league_id):
        return [{"r": 1, "m": 1, "t1": 1}]

    def losers_bracket(self, league_id):
        return [{"r": 1, "m": 1, "t1": 1}]

    def projections(self, season, week):
        return {"p1": {"pts": 10}, "p2": {"pts": 12}}


def test_optional_ranking_source_failure_does_not_abort_collection():
    sources = _collect_ranking_sources(
        FailingRankingsClient(),
        FailingSleeperClient(),
        "2026",
        4,
    )
    assert sources["dynasty_daddy"]["status"] == "unavailable"
    assert sources["sleeper_projections"]["status"] == "unavailable"


def test_ranking_inputs_are_trimmed_to_players_in_the_league():
    sources = {
        "dynasty_daddy": {
            "status": "available",
            "players": {
                "p1": {
                    "sleeper_id": "p1",
                    "full_name": "Player One",
                    "trade_value": 100,
                    "unneeded": "discard",
                },
                "p2": {"sleeper_id": "p2", "full_name": "Player Two"},
            },
        },
        "sleeper_projections": {
            "status": "available",
            "players": {"p1": {"rush_yd": 80}, "p2": {"rush_yd": 40}},
        },
    }
    trimmed = _trim_ranking_sources(sources, {"p1"})
    assert set(trimmed["dynasty_daddy"]["players"]) == {"p1"}
    assert "unneeded" not in trimmed["dynasty_daddy"]["players"]["p1"]
    assert set(trimmed["sleeper_projections"]["players"]) == {"p1"}


def test_data_only_league_generates_analysis_but_no_publication_dossier(tmp_path):
    league = LeagueConfig(
        key="private_league",
        name="Private League",
        sleeper_league_id="789",
        publication=None,
        publication_profile=None,
        tier="data_only",
        league_format="dynasty",
        ranking_model="ironbound_dynasty",
        publication_enabled=False,
    )

    generated = collect_all(
        [league],
        1,
        tmp_path,
        client=EmptySleeperClient(),
        rankings_client=EmptyRankingsClient(),
    )

    assert {path.name for path in generated} == {"snapshot.json", "analysis.json"}
    assert not list(tmp_path.rglob("dossier.*"))


def test_flagship_collection_adds_full_sleeper_editorial_context():
    league = LeagueConfig(
        key="flagship",
        name="Flagship League",
        sleeper_league_id="123",
        publication="Flagship Weekly",
        publication_profile=None,
        tier="flagship",
        league_format="dynasty",
        ranking_model="ironbound_dynasty",
        publication_enabled=True,
    )
    players = {
        player_id: {
            "player_id": player_id,
            "full_name": f"Player {player_id}",
            "position": "QB",
            "fantasy_positions": ["QB"],
            "age": 25,
            "college": "Test University",
        }
        for player_id in ("p1", "p2", "p3", "p4")
    }

    result = collect_league(
        league,
        1,
        {"season": "2026"},
        players,
        FlagshipSleeperClient(),
        ranking_sources={},
    )

    context = result["flagship_sleeper"]
    assert context["schedule"]["status"] == "available"
    assert len(context["schedule"]["weeks"]) == 18
    assert len(context["transactions"]["weeks"]) == 18
    assert context["drafts"]["records"][0]["picks"][0]["player_id"] == "p4"
    assert context["playoff_brackets"]["status"] == "available"
    assert context["next_week_projections"]["week"] == 2
    assert set(result["players"]) == {"p1", "p2", "p3", "p4"}
    assert result["players"]["p1"]["age"] == 25
    assert result["players"]["p1"]["college"] == "Test University"
