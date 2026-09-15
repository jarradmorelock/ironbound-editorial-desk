from editorial_desk.collector import _collect_nfl_week_context, _trim_nfl_context


class FakeNFLVerse:
    def schedule(self, season, week):
        return [{"game_id": "g1"}]

    def player_stats(self, season, week):
        return [
            {"player_id": "rostered", "player_display_name": "Rostered"},
            {"player_id": "free", "player_display_name": "Free Agent"},
        ]

    def noteworthy_late_plays(self, season, week):
        return [{"game_id": "g1", "player_ids": ["rostered"]}]

    def snap_counts(self, season, week):
        return [{"game_id": "g1", "player": "Rostered", "team": "TEN"}]

    def play_by_play(self, season, week):
        return [{"game_id": "g1", "posteam": "TEN", "pass_attempt": True}]


def test_collect_nfl_context_collects_deep_sources_once():
    result = _collect_nfl_week_context(FakeNFLVerse(), "2026", 1)

    assert result["snap_counts"]["status"] == "available"
    assert result["play_by_play"]["status"] == "available"
    assert len(result["player_stats"]["records"]) == 2


def test_trim_context_keeps_complete_player_stats_for_free_agent_feature():
    context = _collect_nfl_week_context(FakeNFLVerse(), "2026", 1)
    players = {"1": {"gsis_id": "rostered"}}

    result = _trim_nfl_context(context, players, include_deep=False)

    assert {row["player_id"] for row in result["player_stats"]["records"]} == {"rostered", "free"}
    assert result["snap_counts"]["status"] == "not_collected"
    assert result["play_by_play"]["status"] == "not_collected"


def test_trim_context_keeps_deep_sources_for_flagship_only():
    context = _collect_nfl_week_context(FakeNFLVerse(), "2026", 1)
    players = {"1": {"gsis_id": "rostered"}}

    result = _trim_nfl_context(context, players, include_deep=True)

    assert result["snap_counts"]["records"][0]["team"] == "TEN"
    assert result["play_by_play"]["records"][0]["posteam"] == "TEN"
