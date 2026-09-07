import json
from pathlib import Path

import pytest

from editorial_desk.config import (
    ConfigurationError,
    load_leagues,
    load_publications,
    validate_publication_mappings,
)


def write_config(tmp_path: Path, league: dict) -> Path:
    path = tmp_path / "leagues.json"
    path.write_text(json.dumps({"leagues": [league]}), encoding="utf-8")
    return path


def test_enabled_league_requires_numeric_id(tmp_path):
    path = write_config(
        tmp_path,
        {
            "key": "ironbound",
            "name": "Ironbound",
            "sleeper_league_id": "REPLACE_ME",
            "publication": "Ironbound",
            "tier": "flagship",
            "league_format": "dynasty",
            "ranking_model": "ironbound_dynasty",
        },
    )
    with pytest.raises(ConfigurationError, match="must be numeric"):
        load_leagues(path)


def test_disabled_placeholder_does_not_block_ready_leagues(tmp_path):
    path = tmp_path / "leagues.json"
    path.write_text(
        json.dumps(
            {
                "leagues": [
                    {
                        "key": "ironbound",
                        "name": "Ironbound",
                        "sleeper_league_id": "REPLACE_ME",
                        "publication": "Ironbound",
                        "tier": "flagship",
                        "league_format": "dynasty",
                        "ranking_model": "ironbound_dynasty",
                        "enabled": False,
                    },
                    {
                        "key": "unbound",
                        "name": "Free Ironbound",
                        "sleeper_league_id": "123",
                        "publication": "Unbound Weekly",
                        "tier": "flagship",
                        "league_format": "dynasty",
                        "ranking_model": "ironbound_dynasty",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    leagues = load_leagues(path)
    assert [league.key for league in leagues] == ["unbound"]


def test_publication_profile_must_match_league_name_and_tier(tmp_path):
    league_path = write_config(
        tmp_path,
        {
            "key": "unbound",
            "name": "Free Ironbound",
            "sleeper_league_id": "123",
            "publication": "Unbound Weekly",
            "publication_profile": "unbound_weekly",
            "tier": "flagship",
            "league_format": "dynasty",
            "ranking_model": "ironbound_dynasty",
        },
    )
    publication_path = tmp_path / "publications.json"
    publication_path.write_text(
        json.dumps(
            {
                "publications": [
                    {
                        "key": "unbound_weekly",
                        "name": "Unbound Weekly",
                        "tier": "flagship",
                        "source_files": ["unbound.pdf"],
                        "recurring_sections": ["Week in review"],
                        "brand_departments": [],
                        "editorial_priorities": ["Flagship depth"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    leagues = load_leagues(league_path)
    publications = load_publications(publication_path)
    validate_publication_mappings(leagues, publications)

    wrong = dict(publications)
    wrong["unbound_weekly"] = publications["unbound_weekly"].__class__(
        **{**publications["unbound_weekly"].__dict__, "tier": "newspaper"}
    )
    with pytest.raises(ConfigurationError, match="tier does not match"):
        validate_publication_mappings(leagues, wrong)


def test_redraft_cannot_silently_use_dynasty_ranking_model(tmp_path):
    path = write_config(
        tmp_path,
        {
            "key": "redraft",
            "name": "Redraft League",
            "sleeper_league_id": "456",
            "publication": "Paper",
            "tier": "newspaper",
            "league_format": "redraft",
            "ranking_model": "ironbound_dynasty",
        },
    )
    with pytest.raises(ConfigurationError, match="redraft leagues must use"):
        load_leagues(path)


def test_data_only_league_does_not_require_publication_profile(tmp_path):
    path = write_config(
        tmp_path,
        {
            "key": "private_league",
            "name": "Private League",
            "sleeper_league_id": "789",
            "publication_enabled": False,
            "league_format": "dynasty",
            "ranking_model": "ironbound_dynasty",
        },
    )
    leagues = load_leagues(path)
    validate_publication_mappings(leagues, {})

    assert leagues[0].publication_enabled is False
    assert leagues[0].publication is None
    assert leagues[0].publication_profile is None
    assert leagues[0].tier == "data_only"
