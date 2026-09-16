import json

from editorial_desk.chronicle_queries import ChronicleQueries


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_story_queries_resolve_identity_and_read_materialized_detail(tmp_path):
    root = tmp_path / "chronicle"
    _write_json(
        root / "registry" / "identity.json",
        {
            "dynasty_mappings": [
                {
                    "league_key": "ironbound_sixteen",
                    "season": "2026",
                    "roster_id": 4,
                    "owner_id": "owner-4",
                    "franchise_key": "franchise:four",
                }
            ],
            "redraft_mappings": [],
            "aliases": {
                "franchise:four": [
                    {"season": "2025", "name": "Old Name"},
                    {"season": "2026", "name": "New Name"},
                ]
            },
            "manager_aliases": {},
            "manager_tenures": {
                "franchise:four": [
                    {"season": "2026", "owner_id": "owner-4", "manager_key": "manager:four"}
                ]
            },
        },
    )
    _write_json(
        root / "leagues" / "ironbound_sixteen" / "history" / "matchups.json",
        {"matchups": [{"event_id": "m1", "season": "2026", "week": 1}]},
    )
    _write_jsonl(
        root / "leagues" / "ironbound_sixteen" / "events" / "2026.jsonl",
        [
            {"event_id": "trade-1", "event_type": "TRADE", "observed_at": "2026-09-01T12:00:00+00:00"},
            {"event_id": "record-1", "event_type": "RECORD_SET", "observed_at": "2026-09-08T12:00:00+00:00"},
        ],
    )
    (root / "leagues" / "unbound_sixteen").mkdir(parents=True)

    query = ChronicleQueries(root)

    assert query.identity_for_roster("ironbound_sixteen", "2026", 4) == "franchise:four"
    assert query.league_matchups("ironbound_sixteen") == [
        {"event_id": "m1", "season": "2026", "week": 1}
    ]
    assert [row["event_id"] for row in query.league_events("ironbound_sixteen")] == [
        "trade-1",
        "record-1",
    ]
    assert [row["event_id"] for row in query.league_events("ironbound_sixteen", {"TRADE"})] == [
        "trade-1"
    ]
    assert query.tracked_league_keys() == ("ironbound_sixteen", "unbound_sixteen")
    assert query.identity_context("franchise:four") == {
        "aliases": [
            {"season": "2025", "name": "Old Name"},
            {"season": "2026", "name": "New Name"},
        ],
        "manager_tenures": [
            {"season": "2026", "owner_id": "owner-4", "manager_key": "manager:four"}
        ],
    }


def test_identity_for_roster_returns_none_when_mapping_is_absent(tmp_path):
    query = ChronicleQueries(tmp_path / "chronicle")
    assert query.identity_for_roster("ironbound_sixteen", "2026", 99) is None
