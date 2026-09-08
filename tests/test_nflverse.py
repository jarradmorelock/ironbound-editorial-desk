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
