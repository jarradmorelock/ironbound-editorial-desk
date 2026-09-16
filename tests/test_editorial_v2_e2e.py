from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from editorial_desk.chronicle_backfill import run_backfill, run_materialize
from editorial_desk.chronicle_backup import (
    create_chronicle_backup,
    monthly_receipt_path,
    validate_chronicle_backup,
)
from editorial_desk.chronicle_collect import collect_pulse
from editorial_desk.chronicle_identity import IdentityOverride, IdentityRegistry
from editorial_desk.chronicle_queries import ChronicleQueries
from editorial_desk.chronicle_store import ChronicleStore
from editorial_desk.config import LeagueConfig, load_publications
from editorial_desk.emailer import send_dossier_email
from editorial_desk.external_inputs import ExternalEditorialInputs, OfficialPowerRanking
from editorial_desk.publication_packets import build_publication_packet
from editorial_desk.story_desk import build_story_desk
from editorial_desk.supplement import generate_supplements


FIXTURE = Path("tests/fixtures/chronicle_history/editorial_v2.json")


class EditorialV2Client:
    def __init__(self, fixture):
        self.fixture = fixture
        self.health_out = False
        self.lineup_changed = False
        self.reaction_transaction = False

    def nfl_state(self):
        return dict(self.fixture["nfl_state"])

    def league(self, league_id):
        return deepcopy(self.fixture["leagues"][str(league_id)])

    def users(self, league_id):
        return deepcopy(self.fixture["users"][str(league_id)])

    def rosters(self, league_id):
        return deepcopy(self.fixture["rosters"][str(league_id)])

    def matchups(self, league_id, week):
        rows = deepcopy(
            (self.fixture["matchups"].get(str(league_id)) or {}).get(str(week), [])
        )
        if str(league_id) == self.fixture["current_league_id"] and int(week) == 7:
            for row in rows:
                if int(row.get("roster_id") or 0) == 1 and self.lineup_changed:
                    row["starters"] = ["p1", "p3"]
        return rows

    def transactions(self, league_id, week):
        rows = deepcopy(
            (self.fixture["transactions"].get(str(league_id)) or {}).get(str(week), [])
        )
        if (
            str(league_id) == self.fixture["current_league_id"]
            and int(week) == 7
            and self.reaction_transaction
        ):
            rows.append(
                {
                    "transaction_id": "reaction-add-26",
                    "status": "complete",
                    "type": "free_agent",
                    "created": 1790000000000,
                    "roster_ids": [1],
                    "adds": {"backup": 1},
                    "drops": {},
                    "settings": {},
                }
            )
        return rows

    def drafts(self, league_id):
        return []

    def draft_picks(self, draft_id):
        return []

    def draft_traded_picks(self, draft_id):
        return []

    def traded_picks(self, league_id):
        return deepcopy(self.fixture["traded_picks"].get(str(league_id), []))

    def winners_bracket(self, league_id):
        return deepcopy(self.fixture["winners_bracket"].get(str(league_id), []))

    def losers_bracket(self, league_id):
        return deepcopy(self.fixture["losers_bracket"].get(str(league_id), []))

    def players(self):
        players = deepcopy(self.fixture["players"])
        if self.health_out:
            players["p1"]["injury_status"] = "Out"
        return players


def _league():
    return LeagueConfig(
        key="ironbound_sixteen",
        name="Ironbound Sixteen",
        sleeper_league_id="2600",
        publication="The Ironbound Weekly",
        publication_profile="ironbound_weekly",
        tier="flagship",
        league_format="dynasty",
        ranking_model="ironbound_dynasty",
        publication_enabled=True,
    )


def _story_snapshot(fixture):
    league = deepcopy(fixture["leagues"]["2600"])
    rosters = deepcopy(fixture["rosters"]["2600"])
    users = deepcopy(fixture["users"]["2600"])
    matchups = deepcopy(fixture["matchups"]["2600"]["7"])
    matchups[0]["starters"] = ["p1", "p3"]
    players = deepcopy(fixture["players"])
    players["p1"]["injury_status"] = "Out"
    return {
        "week": 7,
        "nfl_state": {"season": "2026"},
        "editorial": {
            "league_key": "ironbound_sixteen",
            "league_format": "dynasty",
        },
        "league": league,
        "users": users,
        "rosters": rosters,
        "matchups": matchups,
        "players": players,
    }


def _story_dossier():
    return {
        "lineup_flip_candidates": [
            {
                "roster_id": 2,
                "team": "Anvil",
                "point_swing": 18.0,
                "would_flip_result": True,
                "started_player": "Low Starter",
                "bench_player": "Bench Boom",
            }
        ],
        "division_metrics": [
            {"division_id": "1", "division_name": "Hammer", "gap": 1},
            {"division_id": "2", "division_name": "Anvil", "gap": 1},
        ],
        "market_context": {
            "status": "available",
            "players": [
                {"player_id": "p1", "trade_value": 8000, "overall_rank": 12},
                {"player_id": "p3", "trade_value": 6500, "overall_rank": 25},
            ],
        },
    }


def _newspaper_snapshot(*, divisions=False):
    rosters = [
        {
            "roster_id": 1,
            "owner_id": "u1",
            "players": ["qb1", "lb1", "bench1"],
            "reserve": [],
            "taxi": [],
            "settings": {"division": 1} if divisions else {},
        },
        {
            "roster_id": 2,
            "owner_id": "u2",
            "players": ["qb2", "lb2", "bench2"],
            "reserve": [],
            "taxi": [],
            "settings": {"division": 2} if divisions else {},
        },
    ]
    league = {
        "roster_positions": ["QB", "LB", "BN"],
        "settings": {"divisions": 2 if divisions else 0},
        "metadata": {"division_1": "East", "division_2": "West"}
        if divisions
        else {},
    }
    return {
        "week": 7,
        "league": league,
        "users": [
            {"user_id": "u1", "display_name": "One", "metadata": {"team_name": "One"}},
            {"user_id": "u2", "display_name": "Two", "metadata": {"team_name": "Two"}},
        ],
        "rosters": rosters,
        "matchups": [
            {
                "matchup_id": 1,
                "roster_id": 1,
                "points": 120,
                "starters": ["qb1", "lb1"],
                "players": ["qb1", "lb1", "bench1"],
                "players_points": {"qb1": 24, "lb1": 22, "bench1": 4},
            },
            {
                "matchup_id": 1,
                "roster_id": 2,
                "points": 115,
                "starters": ["qb2", "lb2"],
                "players": ["qb2", "lb2", "bench2"],
                "players_points": {"qb2": 20, "lb2": 18, "bench2": 25},
            },
        ],
        "players": {
            "qb1": {"full_name": "QB One", "position": "QB", "fantasy_positions": ["QB"], "status": "Active"},
            "qb2": {"full_name": "QB Two", "position": "QB", "fantasy_positions": ["QB"], "status": "Active"},
            "lb1": {"full_name": "LB One", "position": "LB", "fantasy_positions": ["LB"], "status": "Active"},
            "lb2": {"full_name": "LB Two", "position": "LB", "fantasy_positions": ["LB"], "status": "Active"},
            "bench1": {"full_name": "Bench One", "position": "QB", "fantasy_positions": ["QB"], "status": "Active"},
            "bench2": {"full_name": "Bench Two", "position": "QB", "fantasy_positions": ["QB"], "status": "Active"},
        },
        "transactions": [
            {
                "transaction_id": "waiver-news",
                "status": "complete",
                "type": "waiver",
                "adds": {"bench1": 1},
                "settings": {"waiver_bid": 7},
            }
        ],
        "nfl_context": {
            "player_stats": {
                "status": "available",
                "records": [
                    {
                        "player_id": "qb1",
                        "attempts": 38,
                        "passing_yards": 325,
                        "passing_tds": 3,
                        "carries": 4,
                        "rushing_yards": 21,
                    },
                    {
                        "player_id": "qb2",
                        "attempts": 31,
                        "passing_yards": 270,
                        "passing_tds": 2,
                    },
                ],
            }
        },
        "next_matchups": {"status": "available", "week": 8, "records": []},
        "ranking_inputs": {},
    }


def _newspaper_dossier(*, divisions=False):
    value = {
        "scoreboard": [
            {
                "winner": {"roster_id": 1, "team": "One", "points": 120},
                "loser": {"roster_id": 2, "team": "Two", "points": 115},
                "margin": 5,
            }
        ],
        "standings": [
            {"roster_id": 1, "team": "One", "wins": 5},
            {"roster_id": 2, "team": "Two", "wins": 4},
        ],
        "ranking_movement": [],
        "lineup_efficiency": [
            {"roster_id": 1, "team": "One", "efficiency": 0.95, "actual_points": 120},
            {"roster_id": 2, "team": "Two", "efficiency": 0.85, "actual_points": 115},
        ],
        "awards": {
            "manager_of_the_week": {"roster_id": 1, "team": "One"},
            "bad_beat": {"roster_id": 2, "team": "Two"},
        },
        "weekly_features": {},
        "record_watch": [],
    }
    if divisions:
        value["division_metrics"] = [
            {"division_id": "1", "division_name": "East", "gap": 1},
            {"division_id": "2", "division_name": "West", "gap": 1},
        ]
    return value


def _write_issue_dossier(root, *, current_through):
    directory = root / "2026" / "week-07" / "ironbound_sixteen"
    directory.mkdir(parents=True, exist_ok=True)
    dossier = {
        "season": "2026",
        "week": 7,
        "information_current_through": current_through,
        "league": {
            "league_key": "ironbound_sixteen",
            "publication": "The Ironbound Weekly",
            "configured_name": "Ironbound Sixteen",
        },
    }
    (directory / "dossier.json").write_text(json.dumps(dossier), encoding="utf-8")
    (directory / "dossier.md").write_text("# Ironbound Week 7\n", encoding="utf-8")


def _series_wins(series, identity):
    if series["identity_a"] == identity:
        return int(series["wins_a"])
    return int(series["wins_b"])


def test_editorial_desk_v2_end_to_end(tmp_path, monkeypatch):
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    chronicle_root = tmp_path / "chronicle"
    store = ChronicleStore(chronicle_root)
    client = EditorialV2Client(fixture)
    league = _league()

    # Historical bootstrap deliberately exposes the dynasty ownership transition.
    first_backfill = run_backfill([league], client, store)
    assert first_backfill.unresolved_ambiguities
    registry = store.read_identity_registry()
    old_franchise = registry.franchise_for("ironbound_sixteen", "2025", 1)
    registry.apply_override(
        IdentityOverride(
            "ironbound_sixteen",
            "2026",
            1,
            old_franchise,
            "commissioner confirmed renamed franchise survived manager change",
        )
    )
    store.write_identity_registry(registry)

    second_backfill = run_backfill([league], client, store)
    assert second_backfill.failed_leagues == ()
    run_materialize(store)

    registry = store.read_identity_registry()
    opponent = registry.franchise_for("ironbound_sixteen", "2026", 2)
    aliases = [row.name for row in registry.aliases(old_franchise)]
    assert aliases == ["Old Forge", "New Forge"]
    assert [row.owner_id for row in registry.manager_tenures(old_franchise)] == ["u1", "u3"]

    redraft = IdentityRegistry.empty()
    old_manager = redraft.register_redraft_season(
        league_key="family",
        season="2025",
        roster_id=1,
        owner_id="same-manager",
        team_name="Old Family Name",
    )
    new_manager = redraft.register_redraft_season(
        league_key="family",
        season="2026",
        roster_id=7,
        owner_id="same-manager",
        team_name="New Family Name",
    )
    assert old_manager.manager_key == new_manager.manager_key

    queries = ChronicleQueries(chronicle_root)
    before = queries.head_to_head("ironbound_sixteen", old_franchise, opponent)
    assert before is not None
    before_games = int(before["series"]["games"])
    before_wins = _series_wins(before["series"], old_franchise)
    historical_types = {
        row["event_type"] for row in store.read_all_league_events("ironbound_sixteen")
    }
    assert {"TRADE", "WAIVER_ADD", "TRADED_PICK", "MATCHUP_FINAL"} <= historical_types
    assert before["playoff_meetings"]

    # Live era: seed observations, capture a status/lineup transition, then a later roster add.
    collect_pulse(
        [league], client, store, 7, "2026-09-16T12:00:00+00:00"
    )
    client.health_out = True
    client.lineup_changed = True
    health_pulse = collect_pulse(
        [league], client, store, 7, "2026-09-16T14:00:00+00:00"
    )
    assert health_pulse["event_counts"]["added"] >= 2
    client.reaction_transaction = True
    live = collect_pulse(
        [league],
        client,
        store,
        7,
        "2026-09-16T15:00:00+00:00",
        finalize_matchups=True,
    )
    assert live["event_counts"]["added"] >= 2
    run_materialize(store)

    after = queries.head_to_head("ironbound_sixteen", old_franchise, opponent)
    assert after is not None
    assert int(after["series"]["games"]) == before_games + 1
    assert _series_wins(after["series"], old_franchise) == before_wins + 1

    rerun = collect_pulse(
        [league],
        client,
        store,
        7,
        "2026-09-16T15:00:00+00:00",
        finalize_matchups=True,
    )
    assert rerun["event_counts"]["added"] == 0

    story_snapshot = _story_snapshot(fixture)
    story_dossier = _story_dossier()
    without_rankings = build_story_desk(
        "ironbound_weekly",
        story_snapshot,
        story_dossier,
        queries,
        observed_since="2026-09-16T13:00:00+00:00",
    )
    assert "david_vs_goliath" not in {
        row["candidate_type"] for row in without_rankings["candidates"]
    }

    official = ExternalEditorialInputs(
        publication_key="ironbound_weekly",
        official_power_rankings=(
            OfficialPowerRanking(old_franchise, 15),
            OfficialPowerRanking(opponent, 1),
        ),
        source_metadata={"label": "Ironbound Power Rankings", "week": 7},
    )
    with_rankings = build_story_desk(
        "ironbound_weekly",
        story_snapshot,
        story_dossier,
        queries,
        external_inputs=official,
        observed_since="2026-09-16T13:00:00+00:00",
    )
    families = {row["candidate_type"] for row in with_rankings["candidates"]}
    assert {"reaction_transaction", "playoff_rematch", "lineup_catastrophe", "david_vs_goliath"} <= families
    reaction = next(
        row for row in with_rankings["candidates"] if row["candidate_type"] == "reaction_transaction"
    )
    assert any("does not prove" in caution.lower() for caution in reaction["cautions"])
    assert all(row["evidence_refs"] for row in with_rankings["candidates"])

    assert build_story_desk(
        "unbound_weekly", story_snapshot, story_dossier, queries
    )["status"] == "available"
    for publication_key in (
        "ballad_crier",
        "the_stampede",
        "volunteer_voice",
        "saturday_standard",
        "hollywood_beat",
    ):
        assert build_story_desk(
            publication_key, story_snapshot, story_dossier, queries
        )["status"] == "disabled"

    publications = load_publications(Path("config/publications.json"))
    volunteer = build_publication_packet(
        _newspaper_snapshot(),
        _newspaper_dossier(),
        publications["volunteer_voice"],
        "weekly",
    )
    volunteer_names = {row["display_name"] for row in volunteer["departments"]}
    volunteer_features = {row["feature"] for row in volunteer["departments"]}
    assert "division_metrics" not in volunteer_features
    assert not any("Division" in name for name in volunteer_names)

    saturday = build_publication_packet(
        _newspaper_snapshot(divisions=True),
        _newspaper_dossier(divisions=True),
        publications["saturday_standard"],
        "weekly",
    )
    saturday_by_name = {row["display_name"]: row for row in saturday["departments"]}
    assert "East and West Division Pulse" in saturday_by_name
    assert "Position Board" in saturday_by_name
    assert "LB" in saturday_by_name["Position Board"]["data"]

    stampede = build_publication_packet(
        _newspaper_snapshot(),
        _newspaper_dossier(),
        publications["the_stampede"],
        "weekly",
    )
    stampede_names = {row["display_name"] for row in stampede["departments"]}
    assert "What a Way to Make a Living" in stampede_names
    assert not any("Heavy Lifting" in name for name in stampede_names)

    baseline_root = tmp_path / "baseline"
    current_root = tmp_path / "current"
    supplements = tmp_path / "supplements"
    _write_issue_dossier(
        baseline_root, current_through="2026-09-16T14:30:00+00:00"
    )
    _write_issue_dossier(
        current_root, current_through="2026-09-16T16:00:00+00:00"
    )
    generated = generate_supplements(
        baseline_root,
        current_root,
        supplements,
        7,
        chronicle_root=chronicle_root,
        baseline_time="2026-09-16T14:30:00+00:00",
    )
    assert generated
    supplement_text = (supplements / "2026" / "week-07" / "ironbound_sixteen" / "supplement.md").read_text()
    assert "Event Ledger Updates" in supplement_text
    assert "FREE AGENT ADD" in supplement_text

    archive = create_chronicle_backup(
        chronicle_root,
        tmp_path / "chronicle-fixture.zip",
        chronicle_revision="fixture-revision",
        created_at="2026-09-01T15:55:00+00:00",
    )
    validation = validate_chronicle_backup(
        archive, expected_revision="fixture-revision"
    )
    assert validation.valid is True

    delivered = []
    monkeypatch.setattr(
        "editorial_desk.emailer._deliver",
        lambda message, sender, password: delivered.append(message),
    )
    accepted_at = datetime(2026, 9, 1, 16, 0, tzinfo=timezone.utc)
    attachment_count = send_dossier_email(
        current_root,
        7,
        "desk@example.com",
        "app-password",
        "reader@example.com",
        extra_attachments=(archive,),
        monthly_receipt_root=chronicle_root,
        chronicle_revision="fixture-revision",
        accepted_at=accepted_at,
    )
    assert attachment_count == 2
    assert len(delivered) == 1
    filenames = {part.get_filename() for part in delivered[0].iter_attachments()}
    assert "ironbound_sixteen-week-07.md" in filenames
    assert "chronicle-fixture.zip" in filenames
    assert monthly_receipt_path(chronicle_root, accepted_at).exists()
