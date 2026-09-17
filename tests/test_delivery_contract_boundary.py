import json

from editorial_desk.collector import collect_league
from editorial_desk.config import (
    FeatureContractConfig,
    LeagueConfig,
    PublicationConfig,
)
from editorial_desk.emailer import build_dossier_email
from editorial_desk.metrics import build_weekly_dossier
from editorial_desk.review import render_editorial_review
from editorial_desk.weekly_features import apply_weekly_features


class DivisionTaggedSleeperClient:
    def league(self, league_id):
        return {
            "league_id": league_id,
            "name": "Division Tagged League",
            "season": "2026",
            "settings": {},
            "metadata": {"division_1": "Holler", "division_2": "Mountain"},
            "roster_positions": ["QB"],
        }

    def users(self, league_id):
        return [
            {"user_id": "u1", "display_name": "Alpha", "metadata": {"team_name": "Alpha"}},
            {"user_id": "u2", "display_name": "Beta", "metadata": {"team_name": "Beta"}},
        ]

    def rosters(self, league_id):
        return [
            {
                "roster_id": 1,
                "owner_id": "u1",
                "players": ["p1"],
                "settings": {"division": 1, "wins": 1, "losses": 0, "ties": 0, "fpts": 20},
            },
            {
                "roster_id": 2,
                "owner_id": "u2",
                "players": ["p2"],
                "settings": {"division": 2, "wins": 0, "losses": 1, "ties": 0, "fpts": 10},
            },
        ]

    def matchups(self, league_id, week):
        return [
            {
                "matchup_id": 1,
                "roster_id": 1,
                "players": ["p1"],
                "starters": ["p1"],
                "players_points": {"p1": 20},
                "points": 20,
            },
            {
                "matchup_id": 1,
                "roster_id": 2,
                "players": ["p2"],
                "starters": ["p2"],
                "players_points": {"p2": 10},
                "points": 10,
            },
        ]

    def transactions(self, league_id, week):
        return []

    def traded_picks(self, league_id):
        return []


def _league(profile_key):
    return LeagueConfig(
        key="demo",
        name="Demo League",
        sleeper_league_id="123",
        publication="Demo Paper",
        publication_profile=profile_key,
        tier="newspaper",
        league_format="redraft",
        ranking_model="redraft_projection_starters_record",
        publication_enabled=True,
    )


def _publication(key, weekly_features):
    return PublicationConfig(
        key=key,
        name="Demo Paper",
        tier="newspaper",
        source_files=(),
        recurring_sections=(),
        brand_departments=(),
        editorial_priorities=(),
        feature_contracts={
            "weekly": tuple(
                FeatureContractConfig(
                    feature=feature,
                    display_name=feature,
                    required_in_phase=True,
                )
                for feature in weekly_features
            )
        },
    )


def _snapshot(profile):
    return collect_league(
        _league(profile.key),
        1,
        {"season": "2026"},
        {
            "p1": {"player_id": "p1", "full_name": "Player One", "position": "QB", "fantasy_positions": ["QB"]},
            "p2": {"player_id": "p2", "full_name": "Player Two", "position": "QB", "fantasy_positions": ["QB"]},
        },
        DivisionTaggedSleeperClient(),
        publication=profile,
        ranking_sources={},
        nfl_context={},
    )


def test_non_divisional_contract_suppresses_stale_sleeper_division_metadata():
    profile = _publication("volunteer_voice", ["league_wide_started_mvp"])
    snapshot = _snapshot(profile)

    assert snapshot["editorial"]["publication_profile"]["weekly_features"] == [
        "league_wide_started_mvp"
    ]

    dossier = apply_weekly_features(snapshot, build_weekly_dossier(snapshot))
    rendered = render_editorial_review(dossier)

    assert dossier["divisions"] == []
    assert "divisional_mvp_nominees" not in dossier["weekly_features"]
    assert "Division Pulse" not in rendered
    assert "Divisional MVP Nominations" not in rendered


def test_divisional_contract_preserves_division_features_for_saturday_standard():
    profile = _publication(
        "saturday_standard",
        ["division_metrics", "divisional_started_mvps"],
    )
    snapshot = _snapshot(profile)
    dossier = apply_weekly_features(snapshot, build_weekly_dossier(snapshot))
    rendered = render_editorial_review(dossier)

    assert {row["division_name"] for row in dossier["divisions"]} == {
        "Holler",
        "Mountain",
    }
    assert "divisional_mvp_nominees" in dossier["weekly_features"]
    assert "Division Pulse" in rendered
    assert "Divisional MVP Nominations" in rendered


def _write_dossier(directory, league_key, publication):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "dossier.md").write_text(
        "# Generic Research Dossier\n\n## Weekly Magazine Features\n",
        encoding="utf-8",
    )
    (directory / "dossier.json").write_text(
        json.dumps(
            {
                "season": "2026",
                "league": {
                    "league_key": league_key,
                    "configured_name": publication,
                    "publication": publication,
                },
            }
        ),
        encoding="utf-8",
    )


def test_newspaper_email_delivers_named_publication_packet_not_generic_dossier(tmp_path):
    directory = tmp_path / "2026" / "week-01" / "rocky_top_rumble"
    _write_dossier(directory, "rocky_top_rumble", "The Volunteer Voice")
    (directory / "publication_packet.md").write_text(
        "# The Volunteer Voice\n\n## Official Table\n\n## Decision Desk\n\n## Mountain MVP\n",
        encoding="utf-8",
    )

    (directory / "publication_packet.json").write_text(json.dumps({
        "publication_key": "volunteer_voice", "publication": "The Volunteer Voice", "week": 1,
        "departments": [{"display_name": name, "status": "ready", "data": []} for name in ("Official Table", "Decision Desk", "Mountain MVP")],
    }))
    message = build_dossier_email(
        tmp_path,
        1,
        "desk@example.com",
        "reader@example.com",
    )

    attachments = list(message.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_filename() == "rocky_top_rumble-week-01.md"
    content = attachments[0].get_content()
    assert "## Official Table" in content
    assert "## Decision Desk" in content
    assert "## Mountain MVP" in content
    assert "Weekly Magazine Features" not in content


def test_flagship_email_consolidates_dossier_and_story_desk(tmp_path):
    directory = tmp_path / "2026" / "week-01" / "ironbound_sixteen"
    _write_dossier(directory, "ironbound_sixteen", "The Ironbound Weekly")
    (directory / "story_desk.md").write_text(
        "# Story Desk\n\n## Rivalry/history candidate\n",
        encoding="utf-8",
    )

    (directory / "story_desk.json").write_text(json.dumps({
        "publication_key": "ironbound_weekly", "candidates": [{
            "candidate_type": "rivalry_history", "display_subjects": ["Alpha", "Beta"],
            "facts": [{"statement": "Three recorded meetings."}],
        }],
    }))
    message = build_dossier_email(
        tmp_path,
        1,
        "desk@example.com",
        "reader@example.com",
    )

    attachments = list(message.iter_attachments())
    assert [part.get_filename() for part in attachments] == [
        "ironbound_sixteen-week-01.md",
    ]
    content = attachments[0].get_content()
    assert "Generic Research Dossier" not in content
    assert "## EDITOR'S BRIEF" in content
    assert "Rivalry History — Alpha / Beta" in content
    assert (directory / "dossier.md").is_file()
    assert (directory / "story_desk.md").is_file()
