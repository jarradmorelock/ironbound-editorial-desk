import gzip

from editorial_desk.nflverse import NFLVerseClient


class Response:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        return None


class CountingSession:
    def __init__(self, content):
        self.content = content
        self.calls = 0

    def get(self, url, headers, timeout):
        self.calls += 1
        return Response(self.content)


def test_play_by_play_release_is_downloaded_once_when_used_by_two_readers():
    rows = "\n".join(
        [
            "season,season_type,week,game_id,qtr,time,game_seconds_remaining,posteam,defteam,down,ydstogo,yardline_100,play_type,pass_attempt,rush_attempt,complete_pass,pass_touchdown,rush_touchdown,touchdown,interception,passer_player_id,receiver_player_id,rusher_player_id,td_player_id,yards_gained,first_down,first_down_rush,first_down_pass,qb_kneel,qb_spike,score_differential,posteam_score_post,defteam_score_post,desc,field_goal_result,two_point_conv_result,safety,total_home_score,total_away_score,play_id",
            "2026,REG,1,g1,4,04:00,240,NO,ATL,1,10,20,pass,1,0,1,1,0,1,0,q1,w1,,w1,20,1,0,1,0,0,-7,24,21,TD pass,,,,24,21,1",
        ]
    ).encode()
    session = CountingSession(gzip.compress(rows))
    client = NFLVerseClient(session=session)

    client.noteworthy_late_plays("2026", 1)
    result = client.play_by_play("2026", 1)

    assert session.calls == 1
    assert result[0]["interception"] is False
