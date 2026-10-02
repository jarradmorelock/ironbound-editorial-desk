from editorial_desk.chronicle_queries import ChronicleQueries
from editorial_desk.nflverse import NFLVerseClient
from editorial_desk.publication_complete import validate_offline_consumability
from editorial_desk.sleeper import SleeperClient
from test_publication_complete import _packet


def _fail(*args, **kwargs):
    raise AssertionError("offline publication consumer attempted external research")


def test_publication_complete_consumer_requires_no_research_clients(monkeypatch):
    packet = _packet()

    monkeypatch.setattr(SleeperClient, "get_json", _fail)
    monkeypatch.setattr(NFLVerseClient, "player_stats", _fail)
    monkeypatch.setattr(ChronicleQueries, "league_events", _fail)

    summary = validate_offline_consumability(packet)

    assert summary["research_calls"] == 0
    assert summary["required_departments_ready"] is True
