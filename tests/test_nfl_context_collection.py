from editorial_desk.enriched_collector import (
    _apply_context_scope,
    _build_rookie_player_directory,
    _collect_deep_nfl_context,
)


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


def test_rookie_directory_maps_only_rookies_with_supported_positions_and_gsis_ids():
    directory, unmapped = _build_rookie_player_directory(
        {
            "100": {
                "years_exp": 0,
                "position": "QB",
                "gsis_id": "gsis-100",
                "full_name": "Jack Strand",
                "team": "NYJ",
            },
            "101": {"years_exp": 0, "position": "WR", "full_name": "Unmapped Rookie"},
            "102": {"years_exp": 1, "position": "RB", "gsis_id": "gsis-102"},
            "103": {"years_exp": 0, "position": "K", "gsis_id": "gsis-103"},
        },
        season_stats_rows=[
            {
                "player_id": "gsis-unmapped-a",
                "player_display_name": "Unmapped Rookie",
                "position": "WR",
                "team": "NYJ",
                "week": 1,
            },
            {
                "player_id": "gsis-unmapped-b",
                "player_display_name": "Unmapped Rookie",
                "position": "WR",
                "team": "BUF",
                "week": 2,
            },
        ],
    )

    assert directory == {
        "gsis-100": {
            "player_id": "100",
            "player": "Jack Strand",
            "position": "QB",
            "nfl_team": "NYJ",
            "years_exp": 0,
        }
    }
    assert unmapped == 1


def test_rookie_directory_recovers_only_unique_stat_bearing_no_gsis_rookies():
    directory, unmapped = _build_rookie_player_directory(
        {
            "100": {
                "years_exp": 0,
                "position": "QB",
                "full_name": "Jack Strand",
                "team": "NYJ",
            },
            "101": {
                "years_exp": 0,
                "position": "WR",
                "full_name": "Inactive Prospect",
                "team": "NYJ",
            },
            "102": {
                "years_exp": 0,
                "position": "RB",
                "full_name": "Ambiguous Rookie",
                "team": "BUF",
            },
        },
        season_stats_rows=[
            {
                "player_id": "gsis-100",
                "player_display_name": "Jack Strand",
                "position": "QB",
                "team": "NYJ",
                "week": 1,
            },
            {
                "player_id": "gsis-102a",
                "player_display_name": "Ambiguous Rookie",
                "position": "RB",
                "team": "BUF",
                "week": 1,
            },
            {
                "player_id": "gsis-102b",
                "player_display_name": "Ambiguous Rookie",
                "position": "RB",
                "team": "BUF",
                "week": 2,
            },
        ],
    )

    assert directory["gsis-100"]["player_id"] == "100"
    assert "gsis-102a" not in directory
    assert "gsis-102b" not in directory
    assert unmapped == 1
