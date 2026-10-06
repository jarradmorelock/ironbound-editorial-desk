from editorial_desk.news_index import build_consumption_receipt, build_news_index


def _item(event_id="news:1", published_at="2026-09-20T12:00:00+00:00", tags=None):
    return {
        "event_id": event_id,
        "published_at": published_at,
        "editorial_lanes": {"health_context": bool(tags), "usage_context": True},
        "tags": tags or ["Depth Chart"],
        "league_players": [{"role": "primary", "sleeper_player_id": "s1"}],
    }


def test_news_index_maps_all_player_stories_and_status_context():
    report = {"status": "READY", "source_revision": "abc", "items": [_item(tags=["Injury"])]}
    status = [{
        "event_id": "status:1",
        "event_type": "PLAYER_STATUS_CHANGE",
        "observed_at": "2026-09-20T16:00:00+00:00",
        "entities": {"player_id": "s1", "status_before": "QUESTIONABLE", "status_after": "OUT"},
    }]

    index = build_news_index(report, {}, status_events=status)

    assert index["by_player"]["s1"] == ["news:1"]
    link = next(row for row in index["links"] if row["link_type"] == "sleeper_status_context")
    assert link["status_after"] == "OUT"
    assert link["causal_claim"] is False


def test_news_index_links_pregame_story_to_material_under_expected_result():
    report = {"status": "READY", "items": [_item(published_at="2026-09-20T12:00:00+00:00")]}
    dossier = {
        "game_timing": {
            "starter_game_days": [{
                "player_id": "s1",
                "gameday": "2026-09-20",
                "game_complete": True,
                "fantasy_points": 2.0,
                "projected_points": 12.0,
                "projection_difference": -10.0,
            }]
        }
    }

    index = build_news_index(report, dossier)

    link = next(row for row in index["links"] if row["link_type"] == "under_expected_context")
    assert link["actual_points"] == 2.0
    assert link["projected_points"] == 12.0
    assert link["causal_claim"] is False


def test_news_index_keeps_distant_status_story_unlinked():
    report = {"status": "READY", "items": [_item(published_at="2026-09-10T12:00:00+00:00")]}
    status = [{
        "event_id": "status:1",
        "event_type": "PLAYER_STATUS_CHANGE",
        "observed_at": "2026-09-20T16:00:00+00:00",
        "entities": {"player_id": "s1"},
    }]
    index = build_news_index(report, {}, status_events=status)
    assert not any(row["link_type"] == "sleeper_status_context" for row in index["links"])


def test_consumption_receipt_binds_packet_to_exact_ledger_revision(tmp_path):
    packet = tmp_path / "publication_complete_packet.json"
    packet.write_text('{"news_index": {"stories": ["news:1"]}}', encoding="utf-8")
    report = {
        "source_revision": "abc",
        "ledger_manifest": {
            "week_key": "2026-09-29",
            "event_count": 1,
            "events_sha256": "digest",
        },
    }
    receipt = build_consumption_receipt(report, packet, issue_key="ironbound-weekly-2026-W40")
    assert receipt["week_key"] == "2026-09-29"
    assert receipt["events_sha256"] == "digest"
    assert len(receipt["packet_sha256"]) == 64
