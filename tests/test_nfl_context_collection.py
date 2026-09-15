from editorial_desk.enriched_collector import _apply_context_scope, _collect_deep_nfl_context


class FakeNFLVerse:
    def player_stats(self, season, week):
        return [
            {"player_id": "rostered", "player_display_name": "Rostered"},
            {"player_id": "free", "player_display_name": "Free Agent"},
        ]

    def snap_counts(self, season, week):
        return [{"game_id": "g1", "player": "Rostered", "team": "TEN"}]

    def play_by_play(self, season, week):
        return [{"game_id": "g1", "posteam": "TEN", "pass_attempt": True}]


def test_collect_nfl_context_collects_deep_sources_once():
    result = _collect_deep_nfl_context(FakeNFLVerse(), "2026", 1)

    assert result["snap_counts"]["status"] == "available"
    assert result["play_by_play"]["status"] == "available"
    assert len(result["player_stats"]["records"]) == 2


def test_context_scope_keeps_complete_player_stats_for_free_agent_feature():
    shared = _collect_deep_nfl_context(FakeNFLVerse(), "2026", 1)
    snapshot = {"nfl_context": {"schedule": {"status": "available", "records": []}}}

    _apply_context_scope(snapshot, shared, include_deep=False)
    result = snapshot["nfl_context"]

    assert {row["player_id"] for row in result["player_stats"]["records"]} == {"rostered", "free"}
    assert result["snap_counts"]["status"] == "not_collected"
    assert result["play_by_play"]["status"] == "not_collected"


def test_context_scope_keeps_deep_sources_for_flagship_only():
    shared = _collect_deep_nfl_context(FakeNFLVerse(), "2026", 1)
    snapshot = {"nfl_context": {}}

    _apply_context_scope(snapshot, shared, include_deep=True)
    result = snapshot["nfl_context"]

    assert result["snap_counts"]["records"][0]["team"] == "TEN"
    assert result["play_by_play"]["records"][0]["posteam"] == "TEN"
