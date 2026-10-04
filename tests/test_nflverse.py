import gzip

from editorial_desk.nflverse import NFLVerseClient


class Response:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        return None


class Session:
    def __init__(self, content):
        self.content = content

    def get(self, url, headers, timeout):
        return Response(self.content)


def test_late_play_feed_keeps_only_noteworthy_endgame_plays():
    rows = "\n".join(
        [
            "season,week,qtr,game_seconds_remaining,touchdown,field_goal_result,"
            "two_point_conv_result,safety,yards_gained,desc,play_id,game_id,time,"
            "play_type,total_home_score,total_away_score,receiver_player_id",
            "2026,1,4,8,1,,,0,70,Walk-off touchdown,1,g1,00:08,pass,30,24,p1",
            "2026,1,3,600,1,,,0,50,Too early,2,g1,10:00,pass,20,17,p2",
        ]
    )
    client = NFLVerseClient(session=Session(gzip.compress(rows.encode())))

    result = client.noteworthy_late_plays("2026", 1)

    assert len(result) == 1
    assert result[0]["walkoff_candidate"] is True
    assert result[0]["yards_gained"] == 70
    assert result[0]["player_ids"] == ["p1"]


def test_injury_feed_returns_weekly_official_report_fields():
    rows = "\n".join(
        [
            "season,season_type,team,week,gsis_id,position,full_name,first_name,last_name,"
            "report_primary_injury,report_secondary_injury,report_status,"
            "practice_primary_injury,practice_secondary_injury,practice_status,date_modified",
            "2026,REG,KC,2,00-0039999,WR,Player One,Player,One,Hamstring,,Questionable,"
            "Hamstring,,Limited Participation,2026-09-16T20:00:00Z",
            "2026,REG,KC,1,00-0039999,WR,Player One,Player,One,Hamstring,,Questionable,"
            "Hamstring,,Did Not Participate,2026-09-10T20:00:00Z",
        ]
    )
    client = NFLVerseClient(session=Session(rows.encode()))

    result = client.injuries("2026", 2)

    assert len(result) == 1
    assert result[0]["gsis_id"] == "00-0039999"
    assert result[0]["report_primary_injury"] == "Hamstring"
    assert result[0]["report_status"] == "Questionable"
    assert result[0]["practice_status"] == "Limited Participation"
