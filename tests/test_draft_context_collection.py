from editorial_desk.enriched_collector import _collect_draft_context, _ensure_draft_context


class FakeSleeper:
    def drafts(self, league_id):
        assert league_id == "123"
        return [{"draft_id": "d1", "season": "2026", "type": "snake"}]

    def draft_picks(self, draft_id):
        assert draft_id == "d1"
        return [{"pick_no": 1, "roster_id": 1, "player_id": "p1"}]

    def draft_traded_picks(self, draft_id):
        assert draft_id == "d1"
        return [{"season": "2027", "round": 1, "roster_id": 2, "owner_id": 1}]


def test_newspaper_draft_context_collects_drafts_picks_and_traded_picks():
    context = _collect_draft_context(FakeSleeper(), "123")
    assert context["status"] == "available"
    assert context["records"][0]["draft"]["draft_id"] == "d1"
    assert context["records"][0]["picks"][0]["player_id"] == "p1"
    assert context["records"][0]["traded_picks"][0]["season"] == "2027"


def test_flagship_reuses_existing_draft_context_without_second_fetch():
    snapshot = {
        "flagship_sleeper": {
            "drafts": {
                "status": "available",
                "records": [{"draft": {"draft_id": "existing"}, "picks": [], "traded_picks": []}],
            }
        }
    }

    class MustNotFetch:
        def drafts(self, league_id):
            raise AssertionError("existing flagship draft context should be reused")

    _ensure_draft_context(snapshot, MustNotFetch(), "123")
    assert snapshot["draft_context"]["records"][0]["draft"]["draft_id"] == "existing"


def test_draft_collection_failure_is_explicitly_unavailable():
    class BrokenSleeper:
        def drafts(self, league_id):
            raise ValueError("draft endpoint unavailable")

    context = _collect_draft_context(BrokenSleeper(), "123")
    assert context["status"] == "unavailable"
    assert context["records"] == []
    assert "draft endpoint unavailable" in context["error"]
