import json
from pathlib import Path

from editorial_desk.external_inputs import ExternalEditorialInputs, OfficialPowerRanking
from editorial_desk.ranking_history import (
    resolve_power_ranking_input,
    seed_from_prior_issue,
)


def test_current_rankings_override_prior_snapshot():
    current = ExternalEditorialInputs(
        publication_key="ironbound_weekly",
        official_power_rankings=(OfficialPowerRanking("franchise:a", 2, score=88.0),),
        source_metadata={"label": "Saturday Power Rankings", "source_week": 4},
    )
    prior = {
        "week": 3,
        "source_metadata": {"label": "Saturday Power Rankings", "ranking_source_week": 3},
        "rows": [{"franchise_key": "franchise:a", "rank": 1, "score": 91.0}],
    }

    resolved = resolve_power_ranking_input(current, prior, season="2026", week=4)

    assert resolved.official_power_rankings[0].rank == 2
    assert resolved.official_power_rankings[0].score == 88.0
    assert resolved.source_metadata["ranking_status"] == "current"
    assert resolved.source_metadata["ranking_source_week"] == 4


def test_missing_current_rankings_carry_forward_without_movement():
    current = ExternalEditorialInputs(publication_key="ironbound_weekly")
    prior = {
        "week": 3,
        "source_metadata": {"label": "Saturday Power Rankings", "ranking_source_week": 3},
        "rows": [{
            "franchise_key": "franchise:a", "rank": 1, "roster_id": 2,
            "team": "Forge", "score": 91.0, "previous_rank": 2,
            "movement": 1, "components": {"season_results_points": 3},
        }],
    }

    resolved = resolve_power_ranking_input(current, prior, season="2026", week=4)

    row = resolved.official_power_rankings[0]
    assert row.rank == 1
    assert row.previous_rank is None
    assert row.movement is None
    assert row.score is None
    assert row.components == {}
    assert resolved.source_metadata["ranking_status"] == "carried_forward"
    assert resolved.source_metadata["ranking_source_week"] == 3
    assert resolved.source_metadata["carried_from_week"] == 3


def test_empty_chronicle_bootstraps_from_prior_issue_packet(tmp_path):
    packet_dir = tmp_path / "2026" / "week-03" / "ironbound_sixteen"
    packet_dir.mkdir(parents=True)
    (packet_dir / "publication_complete_packet.json").write_text(json.dumps({
        "publication_key": "ironbound_weekly",
        "season": "2026",
        "week": 3,
        "power_rankings_chart": {
            "rows": [
                {"franchise_key": "franchise:a", "rank": 1, "roster_id": 1, "team": "Forge"},
                {"franchise_key": "franchise:b", "rank": 2, "roster_id": 2, "team": "Anvil"},
            ],
            "source_metadata": {"label": "Saturday Power Rankings", "ranking_source_week": 3},
        },
    }), encoding="utf-8")
    older_contract = json.loads(
        (packet_dir / "publication_complete_packet.json").read_text(encoding="utf-8")
    )
    older_contract["publication_key"] = "unbound_weekly"
    unbound_dir = tmp_path / "2026" / "week-03" / "free_ironbound_sixteen"
    unbound_dir.mkdir()
    (unbound_dir / "flagship_research_packet.json").write_text(
        json.dumps(older_contract), encoding="utf-8"
    )

    seeded = seed_from_prior_issue(tmp_path, season="2026", week=4)

    assert [row.franchise_key for row in seeded["ironbound_weekly"]] == [
        "franchise:a", "franchise:b"
    ]
    assert [row.rank for row in seeded["ironbound_weekly"]] == [1, 2]
    assert [row.rank for row in seeded["unbound_weekly"]] == [1, 2]


def test_no_prior_ranking_keeps_missing_readiness():
    current = ExternalEditorialInputs(publication_key="ironbound_weekly")

    resolved = resolve_power_ranking_input(current, None, season="2026", week=4)

    assert resolved.power_rankings_supplied is False
    from test_flagship_research import _fixture
    from editorial_desk.flagship_research import build_flagship_research_packet

    snapshot, dossier = _fixture()
    packet = build_flagship_research_packet(
        snapshot, dossier, {}, resolved, history_root=Path("."),
    )
    assert packet["power_rankings_chart"]["status"] == "AWAITING_TUESDAY_INPUT"


def test_carried_ranking_provenance_is_plain_in_packet(tmp_path):
    from test_flagship_research import _fixture
    from editorial_desk.flagship_research import (
        build_flagship_research_packet,
        render_flagship_research_packet,
    )

    snapshot, dossier = _fixture()
    current = ExternalEditorialInputs(publication_key="ironbound_weekly")
    prior = {
        "week": 3,
        "source_metadata": {"label": "Saturday rankings", "ranking_source_week": 3},
        "rows": [{"franchise_key": "franchise:a", "rank": 1, "team": "Forge", "score": 90.0}],
    }
    resolved = resolve_power_ranking_input(current, prior, season="2026", week=4)

    packet = build_flagship_research_packet(
        snapshot, dossier, {}, resolved, history_root=tmp_path,
    )
    rendered = render_flagship_research_packet(packet)

    assert packet["power_rankings_chart"]["status"] == "READY"
    assert packet["power_rankings_chart"]["rows"][0]["score"] is None
    assert "carried forward from Week 3" in rendered
    assert "No current-week movement or score is supplied" in rendered
    assert "ranking score not supplied" in rendered
