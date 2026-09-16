from editorial_desk import cli


def test_chronicle_collect_parser_defaults_to_non_finalizing_pulse():
    args = cli.parser().parse_args(
        [
            "chronicle-collect",
            "--config",
            "config/leagues.json",
            "--week",
            "2",
            "--chronicle-root",
            "../chronicle-data",
        ]
    )
    assert args.command == "chronicle-collect"
    assert args.week == 2
    assert args.finalize_matchups is False


def test_chronicle_collect_parser_accepts_explicit_finalization():
    args = cli.parser().parse_args(
        [
            "chronicle-collect",
            "--config",
            "config/leagues.json",
            "--week",
            "2",
            "--chronicle-root",
            "../chronicle-data",
            "--finalize-matchups",
        ]
    )
    assert args.finalize_matchups is True


def test_chronicle_collect_does_not_load_publication_config(monkeypatch, tmp_path):
    class League:
        key = "a"
        sleeper_league_id = "1"

    monkeypatch.setattr(cli, "load_leagues", lambda path: [League()])

    def should_not_run(path):
        raise AssertionError(
            "publication config should not be loaded for Chronicle collection"
        )

    monkeypatch.setattr(cli, "load_publications", should_not_run)
    monkeypatch.setattr(cli, "SleeperClient", lambda: object())
    monkeypatch.setattr(cli, "ChronicleStore", lambda path: object())
    monkeypatch.setattr(
        cli,
        "collect_pulse",
        lambda leagues, client, store, week, observed_at, finalize_matchups=False: {
            "leagues": {"a": {"status": "fresh"}},
            "event_counts": {"added": 0, "skipped": 0},
        },
    )

    assert (
        cli.main(
            [
                "chronicle-collect",
                "--config",
                str(tmp_path / "leagues.json"),
                "--week",
                "2",
                "--chronicle-root",
                str(tmp_path / "chronicle"),
            ]
        )
        == 0
    )
