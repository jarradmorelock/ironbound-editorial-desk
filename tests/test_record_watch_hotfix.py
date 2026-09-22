from editorial_desk.newspaper_research import render_newspaper_research_packet
from editorial_desk.publication_packets import build_publication_packet
from editorial_desk.config import FeatureContractConfig, PublicationConfig


def test_weekly_records_mapping_is_normalized_before_newspaper_rendering():
    publication = PublicationConfig(
        key="paper",
        name="Paper",
        tier="newspaper",
        source_files=(),
        recurring_sections=(),
        brand_departments=(),
        editorial_priorities=(),
        feature_contracts={
            "weekly": (
                FeatureContractConfig("record_watch", "Record Watch", True),
            )
        },
    )
    dossier = {
        "weekly_records": {
            "status": "scoring_available",
            "highest_score": {"team": "Alpha", "points": 147.08},
            "lowest_score": {"team": "Beta", "points": 71.22},
            "largest_margin": {
                "margin": 44.1,
                "winner": {"team": "Alpha"},
                "loser": {"team": "Beta"},
            },
            "smallest_margin": {
                "margin": 1.3,
                "winner": {"team": "Gamma"},
                "loser": {"team": "Delta"},
            },
        }
    }
    packet = build_publication_packet(
        {"week": 2},
        dossier,
        publication,
        "weekly",
        chronicle_history={"coverage": {"complete": True, "warnings": []}},
    )
    section = packet["departments"][0]
    assert section["status"] == "ready"
    assert all(isinstance(row, dict) for row in section["data"]["records"])
    assert {row["record_type"] for row in section["data"]["records"]} == {
        "highest_score",
        "lowest_score",
        "largest_margin",
        "smallest_margin",
    }


def test_record_watch_renderer_tolerates_legacy_scalar_rows():
    packet = {
        "publication_key": "paper",
        "publication": "Paper",
        "week": 2,
        "contract_label": "test",
        "editorial_notes": [],
        "source_status": {},
        "validation": {
            "contract_valid": True,
            "research_complete": True,
            "manual_verify": [],
        },
        "sections": [
            {
                "feature": "record_watch",
                "display_name": "Record Watch",
                "status": "ready",
                "data": {
                    "records": ["highest_score"],
                    "coverage_complete": True,
                    "coverage_warnings": [],
                },
                "reason": None,
            }
        ],
    }
    text = render_newspaper_research_packet(packet)
    assert "highest_score" in text
