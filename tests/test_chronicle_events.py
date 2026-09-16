from editorial_desk.chronicle_events import event_id_for, make_event


def test_event_id_is_stable_across_dict_order():
    left = {
        "event_type": "TRADE",
        "source_ref": "tx-1",
        "entities": {"b": 2, "a": 1},
    }
    right = {
        "entities": {"a": 1, "b": 2},
        "source_ref": "tx-1",
        "event_type": "TRADE",
    }
    assert event_id_for(left) == event_id_for(right)


def test_retry_observation_time_does_not_change_status_event_id():
    common = dict(
        event_type="PLAYER_STATUS_CHANGE",
        source="sleeper_players",
        source_ref="player:1234:status",
        league_key=None,
        season="2026",
        week=2,
        provenance="observed_live",
        entities={"player_id": "1234"},
        before={"status": "Questionable"},
        after={"status": "Out"},
        observed_before="2026-09-16T17:05:00+00:00",
    )
    first = make_event(
        **common,
        observed_at="2026-09-16T21:04:00+00:00",
        observed_after="2026-09-16T21:04:00+00:00",
    )
    retry = make_event(
        **common,
        observed_at="2026-09-16T21:06:00+00:00",
        observed_after="2026-09-16T21:06:00+00:00",
    )
    assert first.event_id == retry.event_id


def test_status_event_preserves_observation_window_without_fake_occurrence_time():
    event = make_event(
        event_type="PLAYER_STATUS_CHANGE",
        source="sleeper_players",
        source_ref="player:1234:status",
        league_key=None,
        season="2026",
        week=2,
        provenance="observed_live",
        entities={"player_id": "1234"},
        before={"status": "Questionable"},
        after={"status": "Out"},
        observed_at="2026-09-16T21:04:00+00:00",
        observed_before="2026-09-16T17:05:00+00:00",
        observed_after="2026-09-16T21:04:00+00:00",
    )
    row = event.to_dict()
    assert row["occurred_at"] is None
    assert row["observed_before"] == "2026-09-16T17:05:00+00:00"
    assert row["observed_after"] == "2026-09-16T21:04:00+00:00"


def test_correction_reference_survives_serialization():
    event = make_event(
        event_type="MATCHUP_FINAL",
        source="sleeper",
        source_ref="league:1:week:1:matchup:7:correction",
        league_key="demo",
        season="2026",
        week=1,
        provenance="source_exact",
        entities={"matchup_id": 7},
        observed_at="2026-09-16T21:04:00+00:00",
        evidence={"winner": 2, "loser": 1},
        correction_of="abc123",
    )
    assert event.to_dict()["correction_of"] == "abc123"
