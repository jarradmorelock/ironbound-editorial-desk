import json
from pathlib import Path
from types import SimpleNamespace

from editorial_desk.config import PublicationConfig
import editorial_desk.enriched_collector as enriched


def test_preview_uses_week_history_without_chronicle_writes(tmp_path, monkeypatch):
    chronicle_root = tmp_path / "chronicle"
    sentinel = chronicle_root / "sentinel.json"
    sentinel.parent.mkdir(parents=True)
    sentinel.write_text('{"preserve": true}\n', encoding="utf-8")
    before = {path: path.read_bytes() for path in chronicle_root.rglob("*") if path.is_file()}
    output_root = tmp_path / "output"
    league_dir = output_root / "week-02" / "a"
    league_dir.mkdir(parents=True)
    snapshot = {
        "week": 2,
        "nfl_state": {"season": "2026"},
        "league": {"season": "2026"},
        "editorial": {"publication_profile": {"key": "ironbound"}, "league_key": "a"},
        "rosters": [],
        "users": [],
        "players": {},
        "matchups": [],
    }
    snapshot_path = league_dir / "snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    monkeypatch.setattr(enriched, "collect_base", lambda *args, **kwargs: [snapshot_path])
    monkeypatch.setattr(enriched, "_collect_deep_nfl_context", lambda *args, **kwargs: {})
    monkeypatch.setattr(enriched, "_apply_player_context", lambda *args, **kwargs: None)
    monkeypatch.setattr(enriched, "_apply_context_scope", lambda *args, **kwargs: None)
    monkeypatch.setattr(enriched, "_ensure_draft_context", lambda *args, **kwargs: None)
    monkeypatch.setattr(enriched, "_ensure_next_matchups", lambda *args, **kwargs: None)
    monkeypatch.setattr(enriched, "build_editorial_review", lambda snapshot: {})
    monkeypatch.setattr(enriched, "render_editorial_review", lambda dossier: "review")
    monkeypatch.setattr(enriched, "_materialize_publication_assets", lambda *args, **kwargs: (None, []))
    monkeypatch.setattr(enriched, "build_beat_report", lambda *args, **kwargs: None)
    monkeypatch.setattr(enriched, "build_roster_market_report", lambda *args, **kwargs: {})
    monkeypatch.setattr(enriched, "reading_packet_from_artifacts", lambda *args, **kwargs: "packet")
    received = {}

    def build_packet(*args, **kwargs):
        received.update(kwargs)
        return None

    monkeypatch.setattr(enriched, "build_flagship_research_packet", build_packet)

    class Sleeper:
        def players(self):
            return {}

        def matchups(self, league_id, week):
            return [{
                "roster_id": 1,
                "players": ["p1"],
                "players_points": {"p1": week * 10},
            }]

    league = SimpleNamespace(
        key="a", name="League A", sleeper_league_id="sleeper-a",
        publication_enabled=True, publication_profile="ironbound", tier="flagship",
    )
    profile = PublicationConfig(
        key="ironbound", name="Ironbound", tier="flagship", source_files=(),
        recurring_sections=(), brand_departments=(), editorial_priorities=(),
    )

    enriched.collect_all(
        [league], 2, output_root, client=Sleeper(),
        publications={"ironbound": profile}, chronicle_root=chronicle_root,
    )

    rows = received["player_week_history"]
    assert {(row["week"], row["player_id"], row["points"]) for row in rows} == {
        (1, "p1", 10.0), (2, "p1", 20.0)
    }
    assert {path: path.read_bytes() for path in chronicle_root.rglob("*") if path.is_file()} == before
