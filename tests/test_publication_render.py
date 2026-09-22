import json

from editorial_desk.config import FeatureContractConfig, PublicationConfig
from editorial_desk.enriched_collector import _write_newspaper_packet
from editorial_desk.publication_render import render_publication_packet, write_publication_packet


def _packet():
    return {
        "schema_version": 1,
        "publication_key": "ballad_crier",
        "publication": "The Ballad Crier",
        "phase": "weekly",
        "week": 1,
        "status": "unavailable",
        "departments": [
            {
                "feature": "weekly_results",
                "display_name": "Week Cardiogram",
                "required_in_phase": True,
                "status": "ready",
                "data": [{"matchup": "A vs B", "score": "100-99"}],
                "reason": None,
                "freshness": None,
                "degraded": False,
                "dependency_warnings": [],
            },
            {
                "feature": "health_status",
                "display_name": "Ward Report",
                "required_in_phase": True,
                "status": "unavailable",
                "data": None,
                "reason": "Sleeper player metadata was not collected",
                "freshness": None,
                "degraded": False,
                "dependency_warnings": [],
            },
        ],
    }


def test_renderer_preserves_contract_order_and_visible_unavailable_reason():
    text = render_publication_packet(_packet())
    assert text.index("## Week Cardiogram") < text.index("## Ward Report")
    assert "Status: ready" in text
    assert "Status: unavailable" in text
    assert "Sleeper player metadata was not collected" in text
    assert 'A vs B: 100-99.' in text
    assert '```json' not in text


def test_writer_emits_json_and_markdown_without_mutating_packet(tmp_path):
    packet = _packet()
    before = json.loads(json.dumps(packet))
    paths = write_publication_packet(tmp_path, packet)

    assert {path.name for path in paths} == {
        "publication_packet.json",
        "publication_packet.md",
        "newspaper_research_packet.json",
        "newspaper_research_packet.md",
    }
    assert json.loads((tmp_path / "publication_packet.json").read_text()) == packet
    assert "## Ward Report" in (tmp_path / "publication_packet.md").read_text()
    assert packet == before


def test_newspaper_integration_builds_and_writes_weekly_packet(tmp_path):
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
                FeatureContractConfig("weekly_results", "Scoreboard", True),
            )
        },
    )
    snapshot = {"week": 1}
    dossier = {"scoreboard": [{"winner": {"team": "A"}, "loser": {"team": "B"}}]}

    paths = _write_newspaper_packet(
        tmp_path,
        snapshot,
        dossier,
        publication,
        phase="weekly",
    )

    assert {path.name for path in paths} == {"publication_packet.json", "publication_packet.md"}
    packet = json.loads((tmp_path / "publication_packet.json").read_text())
    assert packet["publication"] == "Paper"
    assert packet["departments"][0]["display_name"] == "Scoreboard"
