import json

import pytest
import requests

from editorial_desk.roster_market import (
    normalize_sleeper_platform_research,
    build_network_market_context,
)
from editorial_desk.sleeper import SleeperClient


class _Response:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")

    def json(self):
        return self._payload


class _Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def get(self, url, **kwargs):
        self.urls.append(url)
        return self.responses.pop(0)


def test_sleeper_player_research_uses_undocumented_read_only_research_endpoint():
    session = _Session([_Response({"p1": {"owned": 0.91, "started": 0.25}})])
    client = SleeperClient(session=session)

    payload = client.player_research("2026", 3)

    assert payload["p1"]["owned"] == 0.91
    assert session.urls == [
        "https://api.sleeper.app/players/nfl/research/regular/2026/3"
    ]


def test_sleeper_trending_uses_documented_v1_endpoint():
    session = _Session([_Response([{"player_id": "p1", "count": 123}])])
    client = SleeperClient(session=session)

    payload = client.trending_players("add", lookback_hours=24, limit=50)

    assert payload == [{"player_id": "p1", "count": 123}]
    assert session.urls == [
        "https://api.sleeper.app/v1/players/nfl/trending/add?lookback_hours=24&limit=50"
    ]


@pytest.mark.parametrize(
    "raw,expected",
    [
        (0.25, 25.0),
        (1.0, 100.0),
        (25.0, 25.0),
        (100.0, 100.0),
    ],
)
def test_platform_rate_normalization_supports_fraction_or_percent_shape(raw, expected):
    result = normalize_sleeper_platform_research(
        {"p1": {"owned": raw, "started": raw}}
    )

    assert result["status"] == "EXPERIMENTAL_READY"
    assert result["players"]["p1"]["owned_raw"] == raw
    assert result["players"]["p1"]["started_raw"] == raw
    assert result["players"]["p1"]["rostered_pct"] == expected
    assert result["players"]["p1"]["started_pct"] == expected


def test_invalid_platform_rate_is_preserved_but_not_claimed_as_percentage():
    result = normalize_sleeper_platform_research(
        {"p1": {"owned": 250, "started": "unknown"}}
    )

    assert result["players"]["p1"]["owned_raw"] == 250
    assert result["players"]["p1"]["rostered_pct"] is None
    assert result["players"]["p1"]["started_pct"] is None


def test_network_context_merges_sleeper_wide_rates_and_trending_without_relabeling_tracked_rates():
    snapshot = {
        "players": {"p1": {"full_name": "Jordan Love"}},
        "rosters": [{"roster_id": 1, "players": ["p1"]}],
        "matchups": [{"roster_id": 1, "starters": ["p1"]}],
        "transactions": [],
    }
    platform = normalize_sleeper_platform_research(
        {"p1": {"owned": 0.80, "started": 0.25}}
    )

    context = build_network_market_context(
        {"ironbound": snapshot},
        sleeper_platform_research=platform,
        sleeper_trending={
            "status": "READY",
            "lookback_hours": 24,
            "adds": [{"player_id": "p1", "count": 120}],
            "drops": [{"player_id": "p1", "count": 9}],
        },
    )

    assert context["scope"] == "Ironbound Network"
    assert context["players"]["p1"]["tracked_start_rate"] == 1.0
    assert context["sleeper_platform_rates"]["status"] == "EXPERIMENTAL_READY"
    assert context["sleeper_platform_rates"]["players"]["p1"]["started_pct"] == 25.0
    assert context["sleeper_trending"]["adds"][0]["count"] == 120
