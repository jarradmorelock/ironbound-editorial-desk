import json

import pytest

from editorial_desk.chronicle_queries import ChronicleQueries
from editorial_desk.manuscript_builder import (
    ManuscriptValidationError,
    build_issue_plan,
    build_manuscript_draft,
    write_offline_manuscript,
)
from editorial_desk.editorial_handoff import (
    render_editorial_review,
    render_offline_writer_brief,
)
from editorial_desk.nflverse import NFLVerseClient
from editorial_desk.sleeper import SleeperClient


def _packet():
    return {
        "schema_version": 1,
        "contract_version": "publication-complete-v1",
        "publication": "Ironbound Weekly",
        "publication_key": "ironbound_weekly",
        "issue_identity": {
            "publication_key": "ironbound_weekly",
            "league_key": "ironbound_sixteen",
            "season": "2026",
            "week": 3,
            "information_cutoff": "2026-09-30T18:00:00+00:00",
        },
        "readiness": {"publication_ready": True, "status": "READY"},
        "feature_evidence": {
            "cover_candidates": [
                {
                    "candidate_id": "cover-madtown",
                    "candidate_type": "matchup",
                    "verified_facts": {
                        "matchup": "At least I have chicken vs. Madtown Coyotes",
                        "winner": {"team": "Madtown Coyotes", "points": 122.03},
                        "top_started_player": {"player": "Jahmyr Gibbs", "points": 41.9},
                    },
                    "evidence_ids": ["game:3:1"],
                },
                {
                    "candidate_id": "cover-blue",
                    "candidate_type": "matchup",
                    "verified_facts": {
                        "matchup": "Blue Moose vs. Scenic City Beavers",
                        "winner": {"team": "Blue Moose", "points": 110.0},
                        "top_started_player": {"player": "Josh Allen", "points": 30.0},
                    },
                    "evidence_ids": ["game:3:2"],
                },
            ],
            "story_candidates": [
                {
                    "candidate_id": "story-trade",
                    "candidate_type": "trade_market_shift",
                    "display_facts": [{"statement": "The league recorded many trades."}],
                    "evidence_ids": ["tx:3:1"],
                }
            ],
        },
        "game_dossiers": [
            {
                "matchup_id": 1,
                "matchup": "At least I have chicken vs. Madtown Coyotes",
                "scoreline": "Madtown Coyotes 122.03 — At least I have chicken 100.00",
                "margin": 22.03,
                "winner": {"team": "Madtown Coyotes", "roster_id": 2},
                "loser": {"team": "At least I have chicken", "roster_id": 1},
                "top_started_player": {"player": "Jahmyr Gibbs", "player_id": "1", "points": 41.9},
                "teams": [
                    {
                        "team": "Madtown Coyotes",
                        "submitted_starters": [
                            {"player": "Jahmyr Gibbs", "player_id": "1", "nfl_stat_line": "18 carries for 112 yards and 2 touchdowns", "fantasy_points": 41.9}
                        ],
                        "bench": [],
                    },
                    {
                        "team": "At least I have chicken",
                        "submitted_starters": [
                            {"player": "Josh Allen", "player_id": "2", "nfl_stat_line": "24/31 passing for 280 yards and 3 touchdowns", "fantasy_points": 30.0}
                        ],
                        "bench": [],
                    },
                ],
                "evidence_ids": ["game:3:1"],
            }
        ],
        "usage_desk": {"status": "READY", "evidence_ids": ["usage:3"]},
        "roster_health": {"status": "READY", "players": [], "evidence_ids": ["health:3"]},
        "news_index": {"status": "READY", "by_player": {}, "stories": []},
        "transaction_desk": {"coverage": {"status": "READY"}, "transactions": []},
        "manager_honors": {
            "manager_of_the_week": {"team": "Madtown", "evidence_ids": ["honor:3"]},
            "commissioner_selection_required": False,
        },
        "player_honors": {"overall_player_of_the_week": {"player": "Jahmyr Gibbs", "evidence_ids": ["honor:3"]}},
        "rookie_watch": {"rookie_watch_top_five": [{"player": "Rookie One", "evidence_ids": ["rookie:3"]}]},
        "power_rankings": {
            "status": "READY",
            "rows": [{"team": "At least I have chicken", "rank": 1, "score": 90.0, "movement": 2}],
        },
        "playoff_forecast": {"status": "READY", "rows": []},
        "power_board": {"writeup_inputs": []},
        "division_report": {
            "canonical": {
                "status": "READY",
                "team_records": {
                    "1": {
                        "team": "The Buckaneers",
                        "division_record": {"wins": 2, "losses": 0, "ties": 0},
                        "overall_record": {"wins": 3, "losses": 0, "ties": 0},
                        "cross_division_record": {"wins": 1, "losses": 0, "ties": 0},
                        "evidence_ids": ["division:1"],
                    }
                },
            },
            "outlook": {"division_status": "READY"},
        },
        "week_ahead": {"status": "READY", "rows": [{"matchup_id": 2, "evidence_ids": ["forecast:4:1"]}]},
        "sources_and_model_notes": {"information_cutoff": "2026-09-30T18:00:00+00:00"},
        "publication_assets": {},
    }


def test_builder_creates_editorial_plan_without_copying_facts_into_choices():
    plan = build_issue_plan(_packet())

    assert plan["packet_id"]
    assert plan["editorial_choices"]["cover_candidate_id"] == "cover-madtown"
    assert plan["editorial_choices"]["lead_feature_candidate_id"] == "cover-madtown"
    assert plan["editorial_choices"]["secondary_feature_candidate_id"] == "cover-blue"
    assert plan["sections"][0]["source_paths"] == ["feature_evidence.cover_candidates"]
    assert "winner" not in plan["editorial_choices"]


def test_secondary_matchup_is_selected_away_from_the_editor_chosen_lead():
    plan = build_issue_plan(
        _packet(),
        overrides={"cover_candidate_id": "cover-blue", "lead_feature_candidate_id": "cover-blue"},
    )

    assert plan["editorial_choices"]["lead_feature_candidate_id"] == "cover-blue"
    assert plan["editorial_choices"]["secondary_feature_candidate_id"] == "cover-madtown"


def test_builder_emits_evidence_bound_manuscript_sections():
    packet = _packet()
    plan = build_issue_plan(packet)
    draft = build_manuscript_draft(packet, plan)

    assert draft["packet_id"] == plan["packet_id"]
    assert draft["status"] == "DRAFT"
    cover = next(row for row in draft["sections"] if row["section_id"] == "cover")
    assert cover["evidence_ids"] == ["game:3:1"]
    assert cover["copy"]["headline"] == ""
    assert cover["facts"][0]["candidate_id"] == "cover-madtown"
    secondary = next(row for row in draft["sections"] if row["section_id"] == "secondary_feature")
    assert secondary["facts"][0]["candidate_id"] == "cover-blue"


def test_builder_rejects_unknown_evidence_ids():
    packet = _packet()
    plan = build_issue_plan(packet)
    plan["sections"][0]["evidence_ids"] = ["missing:evidence"]

    with pytest.raises(ManuscriptValidationError, match="unknown evidence"):
        build_manuscript_draft(packet, plan)


def test_writer_only_reads_packet_and_writes_local_artifacts(tmp_path):
    packet_path = tmp_path / "publication_complete_packet.json"
    output_dir = tmp_path / "manuscript"
    packet_path.write_text(json.dumps(_packet()), encoding="utf-8")

    paths = write_offline_manuscript(packet_path, output_dir)

    assert {path.name for path in paths} == {
        "issue_plan.json",
        "manuscript_draft.json",
        "manuscript_draft.md",
        "EDITORIAL_REVIEW.md",
        "OFFLINE_WRITER_BRIEF.md",
    }
    assert json.loads((output_dir / "supporting_files" / "manuscript_draft.json").read_text())["status"] == "DRAFT"


def test_week3_style_manuscript_generation_is_network_independent(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("offline manuscript builder attempted research")

    monkeypatch.setattr(SleeperClient, "get_json", fail)
    monkeypatch.setattr(NFLVerseClient, "player_stats", fail)
    monkeypatch.setattr(ChronicleQueries, "league_events", fail)

    packet = _packet()
    plan = build_issue_plan(packet)
    draft = build_manuscript_draft(packet, plan)

    assert draft["status"] == "DRAFT"


def test_editorial_choices_keep_secondary_team_story_separate_from_recurring_coverlines():
    packet = _packet()
    plan = build_issue_plan(packet)

    text = render_offline_writer_brief(packet, plan)

    assert "CURRENT SECONDARY PICK**: Matchup story — Blue Moose vs. Scenic City Beavers" in text
    assert "League trade activity" not in text
    assert "Power Rankings — At least I have chicken stays at No. 1" in text
    assert "Divisional Heat — The Buckaneers remain perfect against division opponents (2-0)" in text


def test_writer_brief_leads_matchup_performances_with_nfl_stats_and_keeps_fantasy_points():
    packet = _packet()
    plan = build_issue_plan(packet)

    text = render_offline_writer_brief(packet, plan)

    assert "18 carries for 112 yards and 2 touchdowns" in text
    assert "41.90 fantasy points" in text
    assert "NFL stat line unavailable" not in text


def test_writer_brief_leaves_editable_page_headline_before_each_game_breakdown():
    packet = _packet()
    plan = build_issue_plan(packet)

    text = render_offline_writer_brief(packet, plan)
    headline = "- Game-page headline: `FINAL: [write a page headline, or leave blank for a writer suggestion]`"
    facts = "At least I have chicken vs. Madtown Coyotes: **Madtown Coyotes 122.03 — At least I have chicken 100.00**"

    assert text.count(headline) == len(packet["game_dossiers"])
    assert text.index(headline) < text.index(facts)
    assert "Use any completed Game-page headline verbatim" in text


def test_power_board_writer_inputs_show_score_components_weights_and_distinct_standings():
    packet = _packet()
    packet["power_board"]["writeup_inputs"] = [
        {
            "team": "At least I have chicken",
            "rank": 5,
            "official_rank": 1,
            "previous_rank": 3,
            "rank_movement": 2,
            "ranking_score": 77.5,
            "wins": 2,
            "losses": 1,
            "ties": 0,
            "ranking_components": {
                "season_results_points": 13.6,
                "season_results_percentile": 68.0,
                "ros_starters_points": 43.5,
                "ros_starters_percentile": 96.7,
                "market_points": 20.42,
                "market_percentile": 58.3,
                "weights": {"season_results": 0.2, "ros_starters": 0.45, "market": 0.35},
            },
            "evidence_ids": ["power:1"],
        }
    ]
    plan = build_issue_plan(packet)

    text = render_offline_writer_brief(packet, plan)

    assert "Power Board rank 5" in text
    assert "official standings rank 1" in text
    assert "77.50" in text
    assert "season results: 13.60 points (68th percentile; 20% weight)" in text
    assert "rest-of-season starters: 43.50 points (96.7 percentile rank; 45% weight)" in text
    assert "market: 20.42 points (58.3 percentile rank; 35% weight)" in text


def test_transaction_context_has_eastern_timestamp_and_only_meaningful_week_impact():
    packet = _packet()
    packet["news_index"]["reporting_window"] = {
        "start": "2026-09-22T00:00:00-04:00",
        "end": "2026-09-29T23:59:59-04:00",
    }
    packet["transaction_desk"]["transactions"] = [
        {
            "type": "waiver",
            "completed_at": "2026-09-24T13:30:00+00:00",
            "teams": ["Madtown Coyotes"],
            "players": {"received_by": {"Madtown Coyotes": [{"player": "Relevant Starter"}]}},
            "reviewed_week_impact": [
                {"reviewed_week": 3, "player": "Relevant Starter", "fantasy_points": 15.4, "started": True, "to_team": "Madtown Coyotes"}
            ],
            "evidence_ids": ["tx:relevant"],
        },
        {
            "type": "trade",
            "completed_at": "2026-02-01T13:30:00+00:00",
            "teams": ["The Cheek Seekers"],
            "reviewed_week_impact": [
                {"reviewed_week": 3, "player": "Unused Reserve", "fantasy_points": 1.2, "started": False, "to_team": "The Cheek Seekers"}
            ],
            "evidence_ids": ["tx:irrelevant"],
        },
        {
            "type": "trade",
            "completed_at": "2026-09-25T21:46:00-04:00",
            "teams": ["Madtown Coyotes", "The Mad Hatters FC"],
            "reviewed_week_impact": [
                {"reviewed_week": 3, "player": "Newest Starter", "fantasy_points": 1.65, "started": True, "to_team": "Madtown Coyotes"}
            ],
            "evidence_ids": ["tx:newest"],
        },
    ]
    plan = build_issue_plan(packet)

    text = render_offline_writer_brief(packet, plan)

    assert "Sep 24, 2026 at 9:30 AM ET" in text
    assert "Relevant Starter" in text
    assert "Unused Reserve" not in text
    assert "Sep 25, 2026 at 9:46 PM ET" in text
    assert text.index("Sep 25, 2026 at 9:46 PM ET") < text.index("Sep 24, 2026 at 9:30 AM ET")
    assert "Feb 1, 2026" not in text


def test_coverline_menu_draws_from_multiple_magazine_departments():
    packet = _packet()
    packet["manager_honors"]["manager_of_the_week"] = {
        "team": "Madtown Coyotes", "points": 122.03, "evidence_ids": ["honor:mow"]
    }
    packet["player_honors"]["overall_player_of_the_week"] = {
        "player": "Jahmyr Gibbs", "points": 41.9, "evidence_ids": ["honor:player"]
    }
    packet["rookie_watch"]["rookie_watch_top_five"] = [
        {"player": "Rookie One", "team": "Blue Moose", "points": 14.2, "evidence_ids": ["rookie:one"]}
    ]
    packet["usage_desk"]["leaders"] = {
        "carries": [{"player": "Bijan Robinson", "team": "Atlanta", "nfl_stat_line": "29 carries for 194 yards and 2 touchdowns", "evidence_ids": ["usage:bijan"]}]
    }
    packet["playoff_forecast"]["rows"] = [
        {"team": "Madtown Coyotes", "playoff": 91.1, "projected_record": "10-4", "evidence_ids": ["forecast:madtown"]}
    ]
    packet["week_ahead"]["rows"] = [
        {
            "teams": [{"team": "A", "projected_score": 100.0}, {"team": "B", "projected_score": 101.0}],
            "projected_score_one": 100.0,
            "projected_score_two": 101.0,
            "projected_total": 201.0,
            "evidence_ids": ["forecast:close"],
        }
    ]
    plan = build_issue_plan(packet)

    text = render_offline_writer_brief(packet, plan)

    assert "Manager of the Week — Madtown Coyotes" in text
    assert "Player of the Week — Jahmyr Gibbs" in text
    assert "Rookie Watch — Rookie One" in text
    assert "Usage Desk — Bijan Robinson" in text
    assert "Playoff Picture — Madtown Coyotes" in text
    assert "Week Ahead — A vs. B" in text
    assert text.count("FINAL:") >= 8


def test_writer_brief_is_canonical_decision_document_and_review_is_optional_summary():
    packet = _packet()
    plan = build_issue_plan(packet)

    brief = render_offline_writer_brief(packet, plan)
    review = render_editorial_review(packet, plan)

    assert "Make all editorial choices in this Writer Brief" in brief
    assert "Replace the bracketed prompts beside each decision" in brief
    assert "This short sheet is optional" in review
    assert "Use the Offline Writer Brief as the single decision and fact document" in review
    assert len(review) < len(brief) / 3


def test_writer_generation_repairs_legacy_secondary_that_is_not_a_team_writeup(tmp_path):
    packet = _packet()
    plan = build_issue_plan(packet)
    plan["editorial_choices"]["secondary_feature_candidate_id"] = "story-trade"
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    paths = write_offline_manuscript(packet_path, tmp_path / "out", issue_plan=plan)
    saved_plan = json.loads(paths[0].read_text(encoding="utf-8"))
    brief = paths[-1].read_text(encoding="utf-8")

    assert saved_plan["editorial_choices"]["secondary_feature_candidate_id"] == "cover-blue"
    assert "Current second article: Matchup story — Blue Moose vs. Scenic City Beavers" in brief
    assert "Current second article: League trade activity" not in brief


def test_health_spotlight_uses_new_designations_and_full_season_projection_rank():
    packet = _packet()
    packet["news_index"]["reporting_window"] = {
        "start": "2026-09-22T00:00:00-04:00",
        "end": "2026-09-29T23:59:59-04:00",
    }
    packet["roster_health"]["players"] = [
        {
            "player": "High Projection Veteran", "team": "Madtown Coyotes", "player_id": "11",
            "injury_status": "IR", "season_total_projected_fp": 250,
            "evidence_ids": ["health:11"],
        },
        {
            "player": "Newly Out Starter", "team": "Blue Moose", "player_id": "12",
            "injury_status": "Out", "designation_changed_at": "2026-09-28T12:00:00-04:00",
            "season_total_projected_fp": 120, "evidence_ids": ["health:12"],
        },
        {
            "player": "Low Projection Old IR", "team": "The Cheek Seekers", "player_id": "13",
            "injury_status": "IR", "season_total_projected_fp": 0,
            "evidence_ids": ["health:13"],
        },
    ]
    packet["roster_health"]["players"].extend(
        {
            "player": f"Lower Projection {index}", "team": "The Cheek Seekers", "player_id": str(20 + index),
            "injury_status": "IR", "season_total_projected_fp": index,
            "evidence_ids": [f"health:{20 + index}"],
        }
        for index in range(1, 13)
    )
    packet["news_index"]["stories"] = []
    plan = build_issue_plan(packet)

    text = render_offline_writer_brief(packet, plan)

    assert "High Projection Veteran" in text
    assert "Newly Out Starter" in text
    assert "Low Projection Old IR" not in text
    assert "total-year projection" in text


def test_week3_health_spotlight_marks_missing_projection_and_change_dates():
    packet = _packet()
    packet["roster_health"]["players"] = [
        {"player": "Baker Mayfield", "team": "Blue Moose", "player_id": "4", "injury_status": "Out", "on_ir": None, "evidence_ids": ["health:baker"]},
        {"player": "Healthy Reserve", "team": "Blue Moose", "player_id": "5", "injury_status": "", "on_ir": None},
    ]
    plan = build_issue_plan(packet)

    text = render_offline_writer_brief(packet, plan)

    assert "Full-season player projections were not supplied" in text
    assert "Injury-designation change dates were not supplied" in text


def test_health_spotlight_keeps_player_linked_news_even_when_story_tag_is_not_injury():
    packet = _packet()
    packet["news_index"].update(
        {
            "reporting_window": {"start": "2026-09-22T00:00:00-04:00", "end": "2026-09-29T23:59:59-04:00"},
            "by_player": {"4": ["story:baker"]},
            "stories": [
                {
                    "event_id": "story:baker",
                    "headline": "Baker Mayfield Likely To Miss At Least 2-4 Weeks",
                    "source": "Draft Sharks",
                    "published_at": "2026-09-28T14:58:17+00:00",
                    "tags": ["Rookie / Prospect"],
                }
            ],
        }
    )
    packet["roster_health"]["players"] = [
        {"player": "Baker Mayfield", "team": "Blue Moose", "player_id": "4", "injury_status": "Out", "evidence_ids": ["health:baker"]}
    ]
    plan = build_issue_plan(packet)

    text = render_offline_writer_brief(packet, plan)

    assert "Baker Mayfield — Blue Moose: Out" in text
    assert "Baker Mayfield Likely To Miss At Least 2-4 Weeks (Draft Sharks" in text
