import json
from pathlib import Path

from editorial_desk.cli import parser
from editorial_desk.config import PublicationConfig
from editorial_desk.story_artifacts import write_story_desk_artifacts


def _publication(key="ironbound_weekly", *, story_desk=True):
    return PublicationConfig(
        key=key,
        name="Test Magazine",
        tier="flagship" if story_desk else "newspaper",
        source_files=(),
        recurring_sections=(),
        brand_departments=(),
        editorial_priorities=(),
        story_desk=story_desk,
        feature_contracts={},
    )


def _write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _chronicle(tmp_path):
    root = tmp_path / "chronicle"
    _write_json(
        root / "registry" / "identity.json",
        {"dynasty_mappings": [], "redraft_mappings": [], "aliases": {}, "manager_aliases": {}, "manager_tenures": {}},
    )
    _write_jsonl(
        root / "leagues" / "ironbound_sixteen" / "events" / "2026.jsonl",
        [
            {
                "event_id": "record-1",
                "event_type": "RECORD_SET",
                "season": "2026",
                "week": 7,
                "observed_at": "2026-09-15T12:00:00+00:00",
                "source": "chronicle",
                "entities": {"identity": "franchise:a"},
                "evidence": {"value": 170.1},
            }
        ],
    )
    return root


def _snapshot():
    return {
        "week": 7,
        "nfl_state": {"season": "2026"},
        "editorial": {"league_key": "ironbound_sixteen", "league_format": "dynasty"},
        "league": {"settings": {}},
        "rosters": [],
        "matchups": [],
        "players": {},
    }


def test_story_desk_enabled_publication_writes_json_and_markdown(tmp_path):
    output = tmp_path / "issue"
    output.mkdir()

    generated = write_story_desk_artifacts(
        output,
        _snapshot(),
        {},
        _publication(),
        chronicle_root=_chronicle(tmp_path),
    )

    assert generated == (output / "story_desk.json", output / "story_desk.md")
    packet = json.loads((output / "story_desk.json").read_text())
    markdown = (output / "story_desk.md").read_text()
    assert packet["publication_key"] == "ironbound_weekly"
    assert packet["status"] == "available"
    assert packet["candidates"][0]["candidate_type"] == "scoring_record"
    assert "Scoring Record" in markdown
    assert "Evidence" in markdown


def test_newspaper_publication_does_not_write_story_desk_artifacts(tmp_path):
    output = tmp_path / "issue"
    output.mkdir()

    generated = write_story_desk_artifacts(
        output,
        _snapshot(),
        {},
        _publication("hollywood_beat", story_desk=False),
        chronicle_root=_chronicle(tmp_path),
    )

    assert generated == ()
    assert not (output / "story_desk.json").exists()
    assert not (output / "story_desk.md").exists()


def test_story_desk_loads_optional_external_inputs_from_publication_named_file(tmp_path):
    output = tmp_path / "issue"
    output.mkdir()
    external_dir = tmp_path / "external"
    _write_json(
        external_dir / "ironbound_weekly.json",
        {
            "publication_key": "ironbound_weekly",
            "official_power_rankings": [{"franchise_key": "franchise:a", "rank": 1}],
            "war": [{"franchise_key": "franchise:a", "value": 1.2}],
            "source_metadata": {"week": 7},
        },
    )

    write_story_desk_artifacts(
        output,
        _snapshot(),
        {},
        _publication(),
        chronicle_root=_chronicle(tmp_path),
        external_inputs_dir=external_dir,
    )

    packet = json.loads((output / "story_desk.json").read_text())
    assert packet["external_inputs"] == {"official_power_rankings": True, "war": True}


def test_collect_cli_accepts_chronicle_and_external_inputs_paths():
    args = parser().parse_args(
        [
            "collect",
            "--config",
            "config/leagues.json",
            "--week",
            "7",
            "--chronicle-root",
            "chronicle-data",
            "--external-inputs-dir",
            "editorial-inputs",
        ]
    )

    assert args.chronicle_root == Path("chronicle-data")
    assert args.external_inputs_dir == Path("editorial-inputs")
