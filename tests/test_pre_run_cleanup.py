import editorial_desk.review as review
from editorial_desk.collector import _collect_ranking_sources
from editorial_desk.metrics import build_weekly_dossier
from editorial_desk.weekly_features import apply_weekly_features


class TwoMarketRankingsClient:
    def dynasty_daddy_player_values(self):
        return [{"sleeper_id": "p1", "full_name": "Dynasty Player", "trade_value": 9000}]

    def redraft_daddy_player_values(self):
        return [{"sleeper_id": "p1", "full_name": "Redraft Player", "trade_value": 7000}]


class EmptySleeperClient:
    def projections(self, season, week):
        return {}


def test_collects_both_dynasty_and_redraft_daddy_markets():
    sources = _collect_ranking_sources(TwoMarketRankingsClient(), EmptySleeperClient(), "2026", 1)

    assert sources["dynasty_daddy"]["status"] == "available"
    assert sources["redraft_daddy"]["status"] == "available"
    assert sources["redraft_daddy"]["players"]["p1"]["trade_value"] == 7000


def test_market_context_uses_redraft_daddy_for_redraft_leagues():
    snapshot = {
        "editorial": {"league_format": "redraft"},
        "users": [{"user_id": "u1", "display_name": "Owner", "metadata": {"team_name": "Team One"}}],
        "rosters": [{"roster_id": 1, "owner_id": "u1", "players": ["p1"]}],
        "players": {"p1": {"full_name": "Player One", "position": "WR"}},
        "ranking_inputs": {
            "dynasty_daddy": {"status": "available", "players": {"p1": {"sleeper_id": "p1", "trade_value": 9000, "overall_rank": 5, "position_rank": 2}}},
            "redraft_daddy": {"status": "available", "players": {"p1": {"sleeper_id": "p1", "trade_value": 7000, "overall_rank": 20, "position_rank": 8}}},
        },
    }

    context = review._build_market_context(snapshot)

    assert context["source"] == "redraft_daddy"
    assert context["players"][0]["trade_value"] == 7000
    assert context["players"][0]["overall_rank"] == 20


def test_source_manifest_has_professional_clickable_data_citations():
    manifest = review._build_source_manifest()

    by_name = {row["name"]: row for row in manifest}
    assert by_name["Sleeper"]["url"].startswith("https://")
    assert "Sleeper API" in by_name["Sleeper"]["citation"]
    assert by_name["Dynasty Daddy"]["url"].startswith("https://")
    assert "Dynasty Daddy" in by_name["Dynasty Daddy"]["citation"]
    assert by_name["nflverse"]["url"].startswith("https://")
    assert "nflverse" in by_name["nflverse"]["citation"].lower()


def test_rendered_review_includes_data_and_sources_back_page_block():
    dossier = {
        "week": 1,
        "information_current_through": "2026-09-15T20:00:00Z",
        "league": {"publication": "Test Paper", "configured_name": "Test League", "tier": "newspaper"},
        "scoreboard": [],
        "lineup_efficiency": [],
        "rankings": {},
        "awards": {},
        "weekly_records": {},
        "weekly_features": {},
        "source_manifest": [
            {"name": "Sleeper", "citation": "Sleeper. (2026). Sleeper API.", "url": "https://docs.sleeper.com/", "role": "league data"}
        ],
    }

    text = review.render_editorial_review(dossier)

    assert "## Data & Sources" in text
    assert "Sleeper. (2026). Sleeper API." in text
    assert "https://docs.sleeper.com/" in text


def test_manager_of_week_is_highest_efficiency_even_if_that_team_lost():
    snapshot = {
        "collected_at": "2026-09-15T22:00:00+00:00",
        "week": 1,
        "editorial": {"league_key": "test", "configured_name": "Test League", "publication": "Test", "tier": "newspaper", "league_format": "redraft", "ranking_model": "redraft_projection_starters_record"},
        "league": {"name": "Test League", "season": "2026", "roster_positions": ["QB", "BN"], "settings": {}, "metadata": {}, "scoring_settings": {}},
        "users": [
            {"user_id": "u1", "display_name": "Perfect Loser", "metadata": {"team_name": "Perfect Loser"}},
            {"user_id": "u2", "display_name": "Imperfect Winner", "metadata": {"team_name": "Imperfect Winner"}},
        ],
        "rosters": [
            {"roster_id": 1, "owner_id": "u1", "players": ["q1"], "settings": {"wins": 0, "losses": 1, "fpts": 20}},
            {"roster_id": 2, "owner_id": "u2", "players": ["q2", "q3"], "settings": {"wins": 1, "losses": 0, "fpts": 25}},
        ],
        "players": {
            "q1": {"full_name": "Q One", "position": "QB", "fantasy_positions": ["QB"], "years_exp": 5},
            "q2": {"full_name": "Q Two", "position": "QB", "fantasy_positions": ["QB"], "years_exp": 5},
            "q3": {"full_name": "Q Three", "position": "QB", "fantasy_positions": ["QB"], "years_exp": 5},
        },
        "matchups": [
            {"matchup_id": 1, "roster_id": 1, "points": 20, "starters": ["q1"], "players": ["q1"], "players_points": {"q1": 20}},
            {"matchup_id": 1, "roster_id": 2, "points": 25, "starters": ["q2"], "players": ["q2", "q3"], "players_points": {"q2": 25, "q3": 30}},
        ],
        "transactions": [],
        "traded_picks": [],
        "ranking_inputs": {"sleeper_projections": {"status": "unavailable", "players": {}}, "dynasty_daddy": {"status": "unavailable", "players": {}}},
        "nfl_context": {"player_stats": {"status": "unavailable", "records": []}},
    }

    dossier = apply_weekly_features(snapshot, build_weekly_dossier(snapshot))

    assert dossier["awards"]["manager_of_the_week"]["roster_id"] == 1
    assert dossier["awards"]["manager_of_the_week"]["efficiency"] == 1.0
