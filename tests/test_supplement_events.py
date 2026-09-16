import json
from pathlib import Path

from editorial_desk.supplement import generate_supplements


def _write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _dossier(current_through="2026-09-15T22:00:00+00:00"):
    return {
        "season": "2026",
        "week": 7,
        "information_current_through": current_through,
        "league": {
            "publication": "The Ironbound Weekly",
            "configured_name": "Ironbound Sixteen",
        },
    }


def _issue_paths(tmp_path):
    baseline_root = tmp_path / "baseline"
    current_root = tmp_path / "current"
    output_root = tmp_path / "output"
    relative = Path("2026/week-07/ironbound_sixteen/dossier.json")
    _write_json(baseline_root / relative, _dossier())
    _write_json(current_root / relative, _dossier("2026-09-16T14:00:00+00:00"))
    return baseline_root, current_root, output_root


def _event(**overrides):
    row = {
        "event_id": "event-1",
        "schema_version": 1,
        "event_type": "WAIVER_ADD",
        "league_key": "ironbound_sixteen",
        "season": "2026",
        "week": 7,
        "occurred_at": "2026-09-16T12:30:00+00:00",
        "observed_at": "2026-09-16T12:35:00+00:00",
        "observed_before": None,
        "observed_after": None,
        "source": "sleeper",
        "source_ref": "transaction:tx-1",
        "provenance": "source_exact",
        "entities": {"player_id": "p1", "roster_id": 4},
        "before": None,
        "after": {"status": "added"},
        "evidence": {"transaction_id": "tx-1"},
    }
    row.update(overrides)
    return row


def test_post_tuesday_ledger_event_creates_supplement_even_without_dossier_diff(tmp_path):
    baseline_root, current_root, output_root = _issue_paths(tmp_path)
    chronicle_root = tmp_path / "chronicle"
    _write_jsonl(
        chronicle_root / "leagues" / "ironbound_sixteen" / "events" / "2026.jsonl",
        [_event()],
    )

    generated = generate_supplements(
        baseline_root,
        current_root,
        output_root,
        7,
        chronicle_root=chronicle_root,
        baseline_time="2026-09-15T22:00:00+00:00",
    )

    assert len(generated) == 2
    markdown = generated[0].read_text()
    assert "Event Ledger Updates" in markdown
    assert "WAIVER ADD" in markdown
    assert "transaction:tx-1" in markdown
    assert "player_id=p1" in markdown
    assert "roster_id=4" in markdown


def test_event_at_or_before_tuesday_baseline_is_not_repeated(tmp_path):
    baseline_root, current_root, output_root = _issue_paths(tmp_path)
    chronicle_root = tmp_path / "chronicle"
    _write_jsonl(
        chronicle_root / "leagues" / "ironbound_sixteen" / "events" / "2026.jsonl",
        [
            _event(
                event_id="old-event",
                observed_at="2026-09-15T21:59:59+00:00",
                occurred_at="2026-09-15T21:55:00+00:00",
            )
        ],
    )

    generated = generate_supplements(
        baseline_root,
        current_root,
        output_root,
        7,
        chronicle_root=chronicle_root,
        baseline_time="2026-09-15T22:00:00+00:00",
    )

    assert generated == []


def test_health_event_uses_observation_interval_not_invented_exact_change_time(tmp_path):
    baseline_root, current_root, output_root = _issue_paths(tmp_path)
    chronicle_root = tmp_path / "chronicle"
    _write_jsonl(
        chronicle_root / "leagues" / "ironbound_sixteen" / "events" / "2026.jsonl",
        [
            _event(
                event_id="health-1",
                event_type="PLAYER_STATUS_CHANGE",
                occurred_at=None,
                observed_at="2026-09-16T13:05:00+00:00",
                observed_before="2026-09-16T11:00:00+00:00",
                observed_after="2026-09-16T13:05:00+00:00",
                provenance="observed_live",
                source_ref="sleeper-player:p1",
                before={"injury_status": "Questionable"},
                after={"injury_status": "Out"},
                entities={"player_id": "p1", "roster_id": 4},
            )
        ],
    )

    generated = generate_supplements(
        baseline_root,
        current_root,
        output_root,
        7,
        chronicle_root=chronicle_root,
        baseline_time="2026-09-15T22:00:00+00:00",
    )

    markdown = generated[0].read_text()
    assert "2026-09-16T11:00:00+00:00" in markdown
    assert "2026-09-16T13:05:00+00:00" in markdown
    assert "observed between" in markdown
    assert "occurred at" not in markdown.lower()
    assert "Questionable" in markdown
    assert "Out" in markdown
    assert "sleeper-player:p1" in markdown


def test_ledger_event_for_different_week_is_ignored(tmp_path):
    baseline_root, current_root, output_root = _issue_paths(tmp_path)
    chronicle_root = tmp_path / "chronicle"
    _write_jsonl(
        chronicle_root / "leagues" / "ironbound_sixteen" / "events" / "2026.jsonl",
        [_event(event_id="week-8", week=8)],
    )

    generated = generate_supplements(
        baseline_root,
        current_root,
        output_root,
        7,
        chronicle_root=chronicle_root,
        baseline_time="2026-09-15T22:00:00+00:00",
    )

    assert generated == []
