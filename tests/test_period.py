from editorial_desk.period import detect_completed_period


class FakeSleeper:
    def __init__(self, state):
        self.state = state

    def nfl_state(self):
        return self.state


class FakeNFLVerse:
    def __init__(self, schedule):
        self.schedule_rows = schedule

    def season_schedule(self, season):
        assert season == "2026"
        return self.schedule_rows


def test_detect_completed_period_selects_latest_fully_scored_week():
    schedule = [
        {"week": 1, "away_score": 20, "home_score": 24},
        {"week": 1, "away_score": 17, "home_score": 13},
        {"week": 2, "away_score": 10, "home_score": 14},
        {"week": 2, "away_score": None, "home_score": None},
    ]

    period = detect_completed_period(
        FakeSleeper({"season": "2026", "week": 2, "season_type": "regular"}),
        FakeNFLVerse(schedule),
    )

    assert period == {
        "active": True,
        "season": "2026",
        "week": 1,
        "reason": "NFL Week 1 is fully complete",
    }


def test_detect_completed_period_waits_when_no_week_is_complete():
    period = detect_completed_period(
        FakeSleeper({"season": "2026", "week": 1, "season_type": "regular"}),
        FakeNFLVerse(
            [{"week": 1, "away_score": None, "home_score": None}]
        ),
    )

    assert period["active"] is False
    assert period["week"] == 0


def test_detect_completed_period_does_not_schedule_outside_regular_season():
    period = detect_completed_period(
        FakeSleeper({"season": "2026", "week": 1, "season_type": "pre"}),
        FakeNFLVerse([]),
    )

    assert period["active"] is False
    assert period["season"] == "2026"
