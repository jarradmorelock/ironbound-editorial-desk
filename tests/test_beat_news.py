import json
from pathlib import Path

from editorial_desk.beat_news import build_beat_report, load_news_ledger


def _snapshot():
    return {
        "players": {
            "s1": {
                "full_name": "Rhamondre Stevenson",
                "gsis_id": "00-0036875",
            },
            "s2": {
                "full_name": "TreVeyon Henderson",
                "gsis_id": "00-0041100",
            },
        },
        "users": [
            {
                "user_id": "u1",
                "display_name": "Manager",
                "metadata": {"team_name": "The Buckaneers"},
            }
        ],
        "rosters": [
            {
                "roster_id": 1,
                "owner_id": "u1",
                "players": ["s1", "s2"],
                "reserve": [],
                "taxi": [],
            }
        ],
        "nfl_context": {
            "schedule": {
                "status": "available",
                "records": [
                    {"gameday": "2026-09-17"},
                    {"gameday": "2026-09-21"},
                ],
            }
        },
    }


def _event(
    event_id,
    published_at,
    *,
    player_id="00-0036875",
    player_name="Rhamondre Stevenson",
    tags=None,
):
    return {
        "schema_version": 1,
        "event_id": event_id,
        "accepted_at": published_at,
        "published_at": published_at,
        "source": {
            "name": "RotoWire",
            "url": f"https://example.com/{event_id}",
            "canonical_url": f"https://example.com/{event_id}",
            "categories": [],
        },
        "evidence": {
            "original_title": "Role update",
            "feed_summary": "The coaching staff expects a larger lead-back role.",
        },
        "editorial": {
            "headline": "Rhamondre Stevenson expected to lead backfield",
            "thread_title": "[NE] Rhamondre Stevenson expected to lead backfield",
            "tags": tags or ["Depth Chart", "Fantasy Analysis"],
        },
        "player": {
            "nflverse_id": player_id,
            "name": player_name,
            "nfl_team": "NE",
        },
        "related_players": [],
        "nfl_team": {"abbreviation": "NE", "name": "New England Patriots"},
        "discord": {"action": "create", "thread_id": "123"},
    }


def test_load_news_ledger_reads_jsonl_and_records_revision(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text(
        json.dumps(_event("news:1", "2026-09-16T12:00:00+00:00")) + "\n",
        encoding="utf-8",
    )

    source = load_news_ledger(path, revision="abc123")

    assert source["status"] == "available"
    assert source["source_revision"] == "abc123"
    assert len(source["records"]) == 1


def test_build_beat_report_maps_only_rostered_relevant_news_in_weekly_window():
    source = {
        "status": "available",
        "source_repository": "jarradmorelock/Ironbound-Forum-Feed-Poster",
        "source_branch": "news-data",
        "source_revision": "abc123",
        "records": [
            _event("news:in", "2026-09-16T12:00:00+00:00"),
            _event(
                "news:unrostered",
                "2026-09-17T12:00:00+00:00",
                player_id="00-0099999",
                player_name="Unrostered Player",
            ),
            _event("news:old", "2026-09-14T12:00:00+00:00"),
            _event("news:late", "2026-09-23T12:00:00+00:00"),
        ],
    }

    report = build_beat_report(_snapshot(), source)

    assert report["status"] == "READY"
    assert report["source_revision"] == "abc123"
    assert report["relevant_event_count"] == 1
    row = report["items"][0]
    assert row["event_id"] == "news:in"
    assert row["league_players"][0]["fantasy_team"] == "The Buckaneers"
    assert row["editorial_lanes"]["since_we_last_printed"] is True
    assert row["editorial_lanes"]["usage_context"] is True
    assert row["source"] == "RotoWire"
    assert row["source_url"] == "https://example.com/news:in"


def test_health_story_is_routed_to_health_and_preview_lanes():
    source = {
        "status": "available",
        "records": [
            _event(
                "news:health",
                "2026-09-20T12:00:00+00:00",
                tags=["Injury", "Game Status"],
            )
        ],
    }

    report = build_beat_report(_snapshot(), source)
    row = report["items"][0]

    assert row["editorial_lanes"]["health_context"] is True
    assert row["editorial_lanes"]["usage_context"] is True
    assert row["editorial_lanes"]["preview_context"] is True


def test_missing_schedule_date_requires_manual_verification():
    snapshot = _snapshot()
    snapshot["nfl_context"]["schedule"]["records"] = [{"game_id": "x"}]
    source = {"status": "available", "records": []}

    report = build_beat_report(snapshot, source)

    assert report["status"] == "MANUAL_VERIFY"
    assert "schedule" in report["error"].lower()
