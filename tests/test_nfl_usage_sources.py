import gzip

from editorial_desk.nflverse import NFLVerseClient


class Response:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        return None


class RouteSession:
    def __init__(self, routes):
        self.routes = routes

    def get(self, url, headers, timeout):
        for marker, content in self.routes.items():
            if marker in url:
                return Response(content)
        raise AssertionError(f"Unexpected URL: {url}")


def test_snap_counts_parse_game_level_offensive_usage_for_requested_week():
    rows = "\n".join(
        [
            "game_id,pfr_game_id,season,game_type,week,player,pfr_player_id,position,team,opponent,offense_snaps,offense_pct,defense_snaps,defense_pct,st_snaps,st_pct",
            "2026_01_NO_ATL,g1,2026,REG,1,Travis Etienne,EttiTr00,RB,NO,ATL,34,0.52,0,0,0,0",
            "2026_02_NO_CAR,g2,2026,REG,2,Travis Etienne,EttiTr00,RB,NO,CAR,50,0.80,0,0,0,0",
        ]
    ).encode()
    client = NFLVerseClient(session=RouteSession({"snap_counts": rows}))

    result = client.snap_counts("2026", 1)

    assert result == [
        {
            "game_id": "2026_01_NO_ATL",
            "player": "Travis Etienne",
            "pfr_player_id": "EttiTr00",
            "position": "RB",
            "team": "NO",
            "opponent": "ATL",
            "offense_snaps": 34.0,
            "offense_pct": 0.52,
        }
    ]


def test_play_by_play_keeps_analysis_fields_for_requested_week():
    rows = "\n".join(
        [
            "season,season_type,week,game_id,qtr,time,game_seconds_remaining,posteam,defteam,down,ydstogo,yardline_100,play_type,pass_attempt,rush_attempt,complete_pass,pass_touchdown,rush_touchdown,touchdown,passer_player_id,receiver_player_id,rusher_player_id,td_player_id,yards_gained,first_down,first_down_rush,first_down_pass,qb_kneel,qb_spike,score_differential,posteam_score_post,defteam_score_post,desc",
            "2026,REG,1,2026_01_NO_ATL,4,05:00,300,NO,ATL,1,10,8,run,0,1,0,0,1,1,,,r1,r1,8,1,1,0,0,0,-4,24,21,Etienne rushes for a touchdown",
            "2026,REG,2,2026_02_NO_CAR,1,14:00,3540,NO,CAR,1,10,75,run,0,1,0,0,0,0,,,r1,,5,0,0,0,0,0,0,0,0,Week two play",
        ]
    )
    client = NFLVerseClient(
        session=RouteSession({"play_by_play": gzip.compress(rows.encode())})
    )

    result = client.play_by_play("2026", 1)

    assert len(result) == 1
    play = result[0]
    assert play["game_id"] == "2026_01_NO_ATL"
    assert play["quarter"] == 4
    assert play["posteam"] == "NO"
    assert play["rusher_player_id"] == "r1"
    assert play["rush_attempt"] is True
    assert play["rush_touchdown"] is True
    assert play["yardline_100"] == 8.0
    assert play["score_differential"] == -4.0
