import copy

from editorial_desk.player_scoring_history import collect_player_scoring_history, season_leaders
from editorial_desk.sleeper import SleeperClient


def snapshot():
    return {
        'week': 2, 'league': {'season': '2026', 'league_id': 'league', 'scoring_settings': {'rec': 0.5, 'rec_yd': 0.1}},
        'rosters': [{'roster_id': 1, 'players': ['old', 'added', 'inactive']}],
        'players': {p: {'full_name': p, 'position': 'WR', 'years_exp': 0 if p == 'added' else 2}
                    for p in ['old', 'added', 'inactive']},
        'users': [],
        'matchups': [{'roster_id': 1, 'players': ['old', 'added'], 'players_points': {'old': 3, 'added': 7}}],
    }


class Client:
    def matchups(self, league_id, week):
        return [{'roster_id': 1, 'players': ['old'], 'players_points': {'old': 4}}]

    def weekly_stats(self, season, week):
        return {'old': {'rec': 2, 'rec_yd': 30}, 'added': {'rec': 4, 'rec_yd': 50}}


def test_scores_include_weeks_before_acquisition_without_inventing_ownership():
    s = snapshot()
    h = collect_player_scoring_history(Client(), s)
    assert h['coverage']['complete']
    rows = {(r['week'], r['player_id']): r for r in h['rows']}
    assert rows[1, 'added']['points'] == 7
    assert rows[1, 'added']['roster_id'] is None
    assert rows[1, 'added']['source'] == 'sleeper_weekly_stats'
    assert rows[2, 'old']['points'] == 3  # exact matchup overrides later stat corrections
    assert rows[1, 'inactive']['points'] == 0
    assert rows[1, 'inactive']['source'] == 'sleeper_weekly_stats_no_stat_line'
    s['player_scoring_history'] = h
    leaders = season_leaders(s)
    assert leaders['player_season_top_three']['status'] == 'READY'
    assert leaders['player_season_top_three']['by_position']['WR'][0]['points'] == 14
    assert leaders['rookie_season_leaders']['by_position']['WR']['player_id'] == 'added'


def test_empty_or_truncated_feed_cannot_turn_missing_players_into_zero():
    for payload in [{}, {'added': {'rec': 2}}]:
        client = Client()
        client.weekly_stats = lambda *args: payload
        h = collect_player_scoring_history(client, snapshot())
        assert not h['coverage']['complete']
        assert not any(r['player_id'] == 'inactive' for r in h['rows'])


def test_unknown_scoring_or_source_failure_remains_incomplete():
    s = snapshot()
    s['league']['scoring_settings'] = {}
    assert not collect_player_scoring_history(Client(), s)['coverage']['complete']


def test_weekly_stats_cached_once_per_season_week():
    client = SleeperClient()
    calls = []
    client.get_json = lambda path: calls.append(path) or {'p': {'rec': 1}}
    client.weekly_stats('2026', 1)
    client.weekly_stats('2026', 1)
    client.weekly_stats('2026', 2)
    assert calls == ['stats/nfl/regular/2026/1', 'stats/nfl/regular/2026/2']
