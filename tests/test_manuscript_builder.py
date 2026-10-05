import json

import pytest

from editorial_desk.chronicle_queries import ChronicleQueries
from editorial_desk.manuscript_builder import (
    ManuscriptValidationError,
    build_issue_plan,
    build_manuscript_draft,
    write_offline_manuscript,
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
                    "verified_facts": {"winner": "Madtown"},
                    "evidence_ids": ["game:3:1"],
                }
            ],
            "story_candidates": [
                {"candidate_id": "story-trade", "evidence_ids": ["tx:3:1"]}
            ],
        },
        "game_dossiers": [{"matchup_id": 1, "evidence_ids": ["game:3:1"]}],
        "usage_desk": {"status": "READY", "evidence_ids": ["usage:3"]},
        "roster_health": {"status": "READY", "evidence_ids": ["health:3"]},
        "transaction_desk": {"coverage": {"status": "READY"}, "transactions": []},
        "manager_honors": {
            "manager_of_the_week": {"team": "Madtown", "evidence_ids": ["honor:3"]},
            "commissioner_selection_required": False,
        },
        "player_honors": {"overall_player_of_the_week": {"player": "Jahmyr Gibbs", "evidence_ids": ["honor:3"]}},
        "rookie_watch": {"rookie_watch_top_five": [{"player": "Rookie One", "evidence_ids": ["rookie:3"]}]},
        "power_rankings": {"status": "READY", "rows": []},
        "playoff_forecast": {"status": "READY", "rows": []},
        "power_board": {"writeup_inputs": []},
        "division_report": {"canonical": {"status": "READY"}, "outlook": {"division_status": "READY"}},
        "week_ahead": {"status": "READY", "rows": [{"matchup_id": 2, "evidence_ids": ["forecast:4:1"]}]},
        "sources_and_model_notes": {"information_cutoff": "2026-09-30T18:00:00+00:00"},
        "publication_assets": {},
    }


def test_builder_creates_editorial_plan_without_copying_facts_into_choices():
    plan = build_issue_plan(_packet())

    assert plan["packet_id"]
    assert plan["editorial_choices"]["cover_candidate_id"] == "cover-madtown"
    assert plan["editorial_choices"]["lead_feature_candidate_id"] == "cover-madtown"
    assert plan["sections"][0]["source_paths"] == ["feature_evidence.cover_candidates"]
    assert "winner" not in plan["editorial_choices"]


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
    assert secondary["facts"][0]["candidate_id"] == "story-trade"


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
    }
    assert json.loads((output_dir / "manuscript_draft.json").read_text())["status"] == "DRAFT"


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
