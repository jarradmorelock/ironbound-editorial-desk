import json
from pathlib import Path

import pytest

from editorial_desk.config import ConfigurationError, load_leagues


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
                        "enabled": False,
                    },
                    {
                        "key": "unbound",
                        "name": "Free Ironbound",
                        "sleeper_league_id": "123",
                        "publication": "Unbound Weekly",
                        "tier": "flagship",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    leagues = load_leagues(path)
    assert [league.key for league in leagues] == ["unbound"]
