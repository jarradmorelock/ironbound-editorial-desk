import json

import editorial_desk.cli as cli
from editorial_desk.chronicle_backfill import BackfillRunResult, MaterializeRunResult
from editorial_desk.chronicle_identity import IdentityAmbiguity


def _config(tmp_path):
    path = tmp_path / "leagues.json"
    path.write_text(
        json.dumps(
            {
                "leagues": [
                    {
                        "key": "demo",
                        "name": "Demo Dynasty",
                        "sleeper_league_id": "12345",
                        "publication_enabled": False,
                        "league_format": "dynasty",
                        "ranking_model": "ironbound_dynasty",
                        "enabled": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def test_parser_accepts_historical_chronicle_commands():
    parser = cli.parser()
    args = parser.parse_args(["chronicle-backfill", "--config", "x.json", "--chronicle-root", "data"])
    assert args.command == "chronicle-backfill"
    args = parser.parse_args(["chronicle-materialize", "--chronicle-root", "data"])
    assert args.command == "chronicle-materialize"
    args = parser.parse_args(["chronicle-identity-report", "--chronicle-root", "data"])
    assert args.command == "chronicle-identity-report"


def test_backfill_returns_nonzero_when_identity_is_unresolved(tmp_path, monkeypatch, capsys):
    ambiguity = IdentityAmbiguity(
        league_key="demo",
        season="2026",
        roster_id=1,
        owner_id="new-owner",
        candidate_franchise_keys=("franchise_abc",),
        reason="ownership changed",
    )
    monkeypatch.setattr(
        cli,
        "run_backfill",
        lambda leagues, client, store: BackfillRunResult(
            added_events=10,
            skipped_events=0,
            failed_leagues=("demo",),
            unresolved_ambiguities=(ambiguity,),
            warnings=(),
        ),
    )
    monkeypatch.setattr(cli, "SleeperClient", lambda: object())
    result = cli.main(
        [
            "chronicle-backfill",
            "--config",
            str(_config(tmp_path)),
            "--chronicle-root",
            str(tmp_path / "chronicle"),
        ]
    )
    assert result == 1
    assert "unresolved" in capsys.readouterr().out.lower()


def test_materialize_returns_nonzero_when_identity_is_unresolved(tmp_path, monkeypatch):
    ambiguity = IdentityAmbiguity(
        league_key="demo",
        season="2026",
        roster_id=1,
        owner_id="new-owner",
        candidate_franchise_keys=("franchise_abc",),
        reason="ownership changed",
    )
    monkeypatch.setattr(
        cli,
        "run_materialize",
        lambda store: MaterializeRunResult(
            failed_leagues=("demo",),
            unresolved_ambiguities=(ambiguity,),
            record_events_added=0,
        ),
    )
    result = cli.main(
        ["chronicle-materialize", "--chronicle-root", str(tmp_path / "chronicle")]
    )
    assert result == 1
