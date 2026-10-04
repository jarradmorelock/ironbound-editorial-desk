import json

from editorial_desk.story_desk import build_story_desk


class _ChronicleStub:
    def __init__(self, *, status_event=None, league_events=None):
        self.status_event = status_event
        self._league_events = list(league_events or [])

    def identity_for_roster(self, league_key, season, roster_id):
        return f"franchise:{roster_id}"

    def league_events(self, league_key, event_types=None):
        if event_types is None:
            return list(self._league_events)
        return [row for row in self._league_events if row.get("event_type") in set(event_types)]

    def tracked_league_keys(self):
        return ("league",)

    def player_events(self, player_id, since=None):
        if self.status_event and player_id == "p1":
            return [self.status_event]
        return []

    def head_to_head(self, *args, **kwargs):
        return None

    def current_streak(self, *args, **kwargs):
        return None

    def season_records(self, *args, **kwargs):
        return {"records": {}, "coverage_complete": True, "coverage_warnings": []}

    def transactions_for_entity(self, league_key, entity_key, since=None):
        return [row for row in self._league_events if entity_key in json.dumps(row.get("entities") or {})]

    def identity_context(self, identity_key):
        return {"aliases": [], "manager_tenures": []}

    def league_matchups(self, league_key):
        return []


def _snapshot(publication_league="league"):
    return {
        "week": 7,
        "nfl_state": {"season": "2026"},
        "editorial": {"league_key": publication_league, "league_format": "dynasty"},
        "league": {"settings": {}},
        "rosters": [{"roster_id": 1, "players": ["p1"]}],
        "matchups": [],
        "players": {"p1": {"full_name": "Player One", "position": "WR"}},
    }


def _record_event():
    return {
        "event_id": "record-1",
        "event_type": "RECORD_SET",
        "observed_at": "2026-09-15T12:00:00+00:00",
        "source": "chronicle",
        "entities": {"identity": "franchise:1"},
        "evidence": {"value": 175.5},
    }


def test_ironbound_and_unbound_use_distinct_voice_without_changing_evidence_identity():
    chronicle = _ChronicleStub(league_events=[_record_event()])

    ironbound = build_story_desk("ironbound_weekly", _snapshot(), {}, chronicle)
    unbound = build_story_desk("unbound_weekly", _snapshot(), {}, chronicle)

    iron = ironbound["candidates"][0]
    unbound_row = unbound["candidates"][0]
    assert iron["candidate_id"] == unbound_row["candidate_id"]
    assert iron["evidence_refs"] == unbound_row["evidence_refs"]
    assert any(token in " ".join(iron["title_concepts"]) for token in ("Forge", "Steel", "Fire", "Crown", "Pressure"))
    assert any(token in " ".join(unbound_row["title_concepts"]) for token in ("Chain", "Link", "Tension", "Break"))
    assert iron["title_concepts"] != unbound_row["title_concepts"]


def test_story_depth_and_graphic_ideas_are_backed_by_available_candidate_evidence():
    desk = build_story_desk(
        "ironbound_weekly",
        _snapshot(),
        {},
        _ChronicleStub(league_events=[_record_event()]),
    )
    candidate = desk["candidates"][0]

    assert candidate["depth_class"] in {
        "cover_4_6_pages",
        "major_2_4_pages",
        "analysis_1_2_pages",
        "sidebar_graphic",
        "brief",
    }
    assert candidate["graphic_ideas"]
    assert candidate["evidence_refs"]


def test_status_and_reaction_candidates_warn_against_unsupported_causation_or_motive():
    status = {
        "event_id": "status-1",
        "event_type": "PLAYER_STATUS_CHANGE",
        "observed_at": "2026-09-15T12:00:00+00:00",
        "source": "sleeper_players",
        "entities": {"player_id": "p1"},
        "before": {"injury_status": "Questionable"},
        "after": {"injury_status": "Out"},
        "evidence": {},
    }
    add = {
        "event_id": "add-1",
        "event_type": "FREE_AGENT_ADD",
        "observed_at": "2026-09-15T13:00:00+00:00",
        "source": "sleeper_transactions",
        "entities": {"player_id": "replacement", "roster_id": 1},
        "evidence": {},
    }
    desk = build_story_desk(
        "ironbound_weekly",
        _snapshot(),
        {},
        _ChronicleStub(status_event=status, league_events=[add]),
        observed_since="2026-09-15T00:00:00+00:00",
    )
    by_type = {row["candidate_type"]: row for row in desk["candidates"]}

    for candidate_type in ("injury_shock", "reaction_transaction"):
        caution = " ".join(by_type[candidate_type]["cautions"]).casefold()
        assert "does not" in caution or "not prove" in caution
