import json

from editorial_desk.supplement import generate_supplements


def _write_dossier(root, data):
    directory = root / "2026" / "week-01" / "ironbound"
    directory.mkdir(parents=True)
    (directory / "dossier.json").write_text(
        json.dumps(data), encoding="utf-8"
    )


def _base_dossier():
    return {
        "season": "2026",
        "week": 1,
        "information_current_through": "2026-09-15T21:17:00Z",
        "league": {
            "league_key": "ironbound",
            "configured_name": "Ironbound Sixteen",
            "publication": "The Ironbound Weekly",
            "tier": "flagship",
        },
        "scoreboard": [
            {
                "matchup_id": 1,
                "teams": [
                    {"roster_id": 1, "team": "Alpha", "points": 100.0},
                    {"roster_id": 2, "team": "Beta", "points": 99.0},
                ],
            }
        ],
        "awards": {},
        "game_timing": {
            "source_status": {
                "schedule": "available",
                "player_stats": "unavailable",
                "play_by_play": "unavailable",
            },
            "starter_game_days": [],
            "early_week": {},
            "monday": {},
        },
    }


def test_generate_supplement_contains_only_newly_available_evidence(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    output = tmp_path / "supplements"
    before = _base_dossier()
    after = _base_dossier()
    after["information_current_through"] = "2026-09-16T05:17:00Z"
    after["game_timing"] = {
        "source_status": {
            "schedule": "available",
            "player_stats": "available",
            "play_by_play": "available",
        },
        "starter_game_days": [
            {
                "roster_id": 1,
                "player_id": "p1",
                "weekday": "Monday",
                "player": "Quarter Back",
                "team": "Alpha",
                "fantasy_points": 31.2,
                "projection_difference": 10.2,
                "nfl_stat_line": "300 pass yds, 3 pass TD",
            }
        ],
        "early_week": {},
        "monday": {
            "late_play_candidates": [
                {
                    "game_id": "2026_01_X_Y",
                    "play_id": "88",
                    "quarter": 4,
                    "clock": "00:08",
                    "description": "70-yard touchdown",
                    "linked_fantasy_starters": [
                        {"player": "Quarter Back", "team": "Alpha"}
                    ],
                    "smallest_linked_final_margin": 0.8,
                }
            ]
        },
    }
    _write_dossier(baseline, before)
    _write_dossier(current, after)

    generated = generate_supplements(baseline, current, output, 1)

    assert len(generated) == 2
    markdown = generated[0].read_text(encoding="utf-8")
    assert "only material that was not present" in markdown
    assert "NFL player stats: unavailable → available" in markdown
    assert "70-yard touchdown" in markdown
    assert "300 pass yds, 3 pass TD" in markdown
    assert "## Lineup Efficiency" not in markdown


def test_generate_supplement_writes_nothing_when_packets_match(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    output = tmp_path / "supplements"
    dossier = _base_dossier()
    _write_dossier(baseline, dossier)
    _write_dossier(current, dossier)

    assert generate_supplements(baseline, current, output, 1) == []
    assert not output.exists()


def test_generate_supplement_does_not_report_a_source_regression(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    output = tmp_path / "supplements"
    before = _base_dossier()
    after = _base_dossier()
    before["game_timing"]["source_status"]["player_stats"] = "available"
    after["game_timing"]["source_status"]["player_stats"] = "unavailable"
    _write_dossier(baseline, before)
    _write_dossier(current, after)

    assert generate_supplements(baseline, current, output, 1) == []
