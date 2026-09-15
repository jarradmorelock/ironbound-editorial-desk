from __future__ import annotations

import re
from collections import defaultdict
from typing import Any


def build_nfl_game_intelligence(
    snapshot: dict[str, Any]
) -> dict[str, Any] | None:
    """Build evidence-first NFL usage/game-script context for flagship leagues."""
    if (snapshot.get("editorial") or {}).get("tier") != "flagship":
        return None

    context = snapshot.get("nfl_context") or {}
    pbp_source = context.get("play_by_play") or {}
    snap_source = context.get("snap_counts") or {}
    stat_source = context.get("player_stats") or {}
    schedule_source = context.get("schedule") or {}

    source_status = {
        "play_by_play": pbp_source.get("status", "unavailable"),
        "snap_counts": snap_source.get("status", "unavailable"),
        "player_stats": stat_source.get("status", "unavailable"),
        "schedule": schedule_source.get("status", "unavailable"),
    }

    sleeper_players = snapshot.get("players") or {}
    rostered_gsis = {
        str(player.get("gsis_id"))
        for player in sleeper_players.values()
        if player.get("gsis_id")
    }
    relevant_teams = {
        str(player.get("team"))
        for player in sleeper_players.values()
        if player.get("team")
    }

    names: dict[str, str] = {}
    positions: dict[str, str | None] = {}
    teams: dict[str, str | None] = {}
    for row in stat_source.get("records") or []:
        player_id = str(row.get("player_id") or "")
        if not player_id:
            continue
        names[player_id] = str(
            row.get("player_display_name") or row.get("player_name") or player_id
        )
        positions[player_id] = row.get("position")
        teams[player_id] = row.get("team")
    for player in sleeper_players.values():
        player_id = str(player.get("gsis_id") or "")
        if not player_id:
            continue
        names.setdefault(player_id, str(player.get("full_name") or player_id))
        positions.setdefault(player_id, player.get("position"))
        teams.setdefault(player_id, player.get("team"))

    usage: dict[str, dict[str, Any]] = {}

    def ensure(player_id: str | None, team: str | None = None) -> dict[str, Any] | None:
        if not player_id:
            return None
        player_id = str(player_id)
        if player_id not in usage:
            usage[player_id] = {
                "player_id": player_id,
                "player": names.get(player_id, player_id),
                "team": teams.get(player_id) or team,
                "position": positions.get(player_id),
                "rostered": player_id in rostered_gsis,
                "offense_snaps": None,
                "snap_share": None,
                "carries": 0,
                "targets": 0,
                "receptions": 0,
                "opportunities": 0,
                "red_zone_opportunities": 0,
                "inside_10_opportunities": 0,
                "inside_5_opportunities": 0,
                "touchdowns": 0,
                "fantasy_points_by_quarter": {},
                "reconstructed_fantasy_points": 0.0,
            }
        elif team and not usage[player_id].get("team"):
            usage[player_id]["team"] = team
        return usage[player_id]

    for player_id in rostered_gsis:
        ensure(player_id)

    scoring = (snapshot.get("league") or {}).get("scoring_settings") or {}
    team_offensive_tds: dict[str, int] = defaultdict(int)
    player_trailing_q4: set[str] = set()

    for play in pbp_source.get("records") or []:
        team = str(play.get("posteam") or "")
        if relevant_teams and team not in relevant_teams:
            continue
        quarter = int(play.get("quarter") or 0)
        qkey = str(quarter)
        yardline = _number(play.get("yardline_100"))

        if play.get("pass_attempt"):
            passer_id = _pid(play.get("passer_player_id"))
            receiver_id = _pid(play.get("receiver_player_id"))
            passer = ensure(passer_id, team)
            receiver = ensure(receiver_id, team)

            if passer:
                points = 0.0
                if play.get("complete_pass"):
                    points += _weight(scoring, "pass_cmp")
                    points += _number(play.get("yards_gained")) * _weight(
                        scoring, "pass_yd"
                    )
                if play.get("pass_touchdown"):
                    points += _weight(scoring, "pass_td")
                    passer["touchdowns"] += 1
                if play.get("interception"):
                    points += _weight(scoring, "pass_int")
                if play.get("first_down_pass"):
                    points += _weight(scoring, "pass_fd")
                _add_quarter_points(passer, qkey, points)
                if quarter >= 4 and _number(play.get("score_differential")) <= -7:
                    player_trailing_q4.add(passer["player_id"])

            if receiver:
                receiver["targets"] += 1
                receiver["opportunities"] += 1
                _add_high_value_opportunity(receiver, yardline)
                points = 0.0
                if play.get("complete_pass"):
                    receiver["receptions"] += 1
                    points += _weight(scoring, "rec")
                    points += _number(play.get("yards_gained")) * _weight(
                        scoring, "rec_yd"
                    )
                if play.get("pass_touchdown"):
                    points += _weight(scoring, "rec_td")
                    receiver["touchdowns"] += 1
                if play.get("first_down_pass"):
                    points += _weight(scoring, "rec_fd")
                _add_quarter_points(receiver, qkey, points)
                if quarter >= 4 and _number(play.get("score_differential")) <= -7:
                    player_trailing_q4.add(receiver["player_id"])

            if play.get("pass_touchdown"):
                team_offensive_tds[team] += 1

        if (
            play.get("rush_attempt")
            and not play.get("qb_kneel")
            and not play.get("qb_spike")
        ):
            rusher = ensure(_pid(play.get("rusher_player_id")), team)
            if rusher:
                rusher["carries"] += 1
                rusher["opportunities"] += 1
                _add_high_value_opportunity(rusher, yardline)
                points = _weight(scoring, "rush_att")
                points += _number(play.get("yards_gained")) * _weight(
                    scoring, "rush_yd"
                )
                if play.get("rush_touchdown"):
                    points += _weight(scoring, "rush_td")
                    rusher["touchdowns"] += 1
                if play.get("first_down_rush"):
                    points += _weight(scoring, "rush_fd")
                _add_quarter_points(rusher, qkey, points)
                if quarter >= 4 and _number(play.get("score_differential")) <= -7:
                    player_trailing_q4.add(rusher["player_id"])
            if play.get("rush_touchdown"):
                team_offensive_tds[team] += 1

    name_to_id = {
        (_normalize_name(row["player"]), str(row.get("team") or "")): player_id
        for player_id, row in usage.items()
    }
    for snap in snap_source.get("records") or []:
        team = str(snap.get("team") or "")
        if relevant_teams and team not in relevant_teams:
            continue
        key = (_normalize_name(str(snap.get("player") or "")), team)
        player_id = name_to_id.get(key)
        if not player_id:
            player_id = f"pfr:{snap.get('pfr_player_id') or key[0]}"
            names[player_id] = str(snap.get("player") or player_id)
            positions[player_id] = snap.get("position")
            teams[player_id] = team
        row = ensure(player_id, team)
        if not row:
            continue
        if not row.get("player") or row["player"] == player_id:
            row["player"] = str(snap.get("player") or player_id)
        if not row.get("position"):
            row["position"] = snap.get("position")
        row["offense_snaps"] = _number(snap.get("offense_snaps"))
        row["snap_share"] = round(_number(snap.get("offense_pct")), 4)

    for row in usage.values():
        row["fantasy_points_by_quarter"] = {
            quarter: round(points, 2)
            for quarter, points in sorted(
                row["fantasy_points_by_quarter"].items(),
                key=lambda item: int(item[0]),
            )
            if abs(points) > 0.0001
        }
        row["reconstructed_fantasy_points"] = round(
            sum(row["fantasy_points_by_quarter"].values()), 2
        )

    winners = _winning_teams(schedule_source.get("records") or [])
    signals: list[dict[str, Any]] = []
    signals.extend(_backfield_split_signals(usage, relevant_teams))
    signals.extend(
        _high_value_touch_signals(usage, rostered_gsis, relevant_teams)
    )
    signals.extend(
        _individual_story_signals(
            usage,
            rostered_gsis,
            team_offensive_tds,
            player_trailing_q4,
            winners,
        )
    )

    return {
        "source_status": source_status,
        "team_offensive_touchdowns": dict(sorted(team_offensive_tds.items())),
        "players": usage,
        "story_signals": signals,
    }


def _backfield_split_signals(
    usage: dict[str, dict[str, Any]], relevant_teams: set[str]
) -> list[dict[str, Any]]:
    by_team: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in usage.values():
        if row.get("position") != "RB" or row.get("snap_share") is None:
            continue
        team = str(row.get("team") or "")
        if relevant_teams and team not in relevant_teams:
            continue
        by_team[team].append(row)

    results = []
    for team, backs in sorted(by_team.items()):
        backs.sort(key=lambda row: (-_number(row.get("snap_share")), row["player"]))
        if len(backs) < 2:
            continue
        first, second = backs[:2]
        first_share = _number(first.get("snap_share"))
        second_share = _number(second.get("snap_share"))
        if second_share < 0.35 or abs(first_share - second_share) > 0.15:
            continue
        if not (first.get("rostered") or second.get("rostered")):
            continue
        results.append(
            {
                "type": "BACKFIELD_SPLIT",
                "team": team,
                "players": [
                    {
                        "player_id": row["player_id"],
                        "player": row["player"],
                        "snap_share": row["snap_share"],
                        "offense_snaps": row["offense_snaps"],
                    }
                    for row in (first, second)
                ],
                "explanation": (
                    f"{first['player']} and {second['player']} played nearly even "
                    "offensive snap shares."
                ),
            }
        )
    return results


def _high_value_touch_signals(
    usage: dict[str, dict[str, Any]],
    rostered_gsis: set[str],
    relevant_teams: set[str],
) -> list[dict[str, Any]]:
    by_team: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in usage.values():
        if row.get("position") != "RB":
            continue
        team = str(row.get("team") or "")
        if relevant_teams and team not in relevant_teams:
            continue
        by_team[team].append(row)

    results = []
    for player_id in sorted(rostered_gsis):
        player = usage.get(player_id)
        if not player or player.get("position") != "RB":
            continue
        opportunities = int(player.get("opportunities") or 0)
        if opportunities < 4:
            continue
        team = str(player.get("team") or "")
        teammates = [row for row in by_team.get(team, []) if row["player_id"] != player_id]
        if not teammates:
            continue
        rival = max(
            teammates,
            key=lambda row: (
                int(row.get("inside_10_opportunities") or 0),
                int(row.get("inside_5_opportunities") or 0),
                int(row.get("opportunities") or 0),
            ),
        )
        gap = int(rival.get("inside_10_opportunities") or 0) - int(
            player.get("inside_10_opportunities") or 0
        )
        if gap < 2:
            continue
        if int(rival.get("opportunities") or 0) < max(2, opportunities * 0.4):
            continue
        results.append(
            {
                "type": "HIGH_VALUE_TOUCH_SHIFT",
                "player_id": player_id,
                "player": player["player"],
                "team": team,
                "inside_10_opportunities": player["inside_10_opportunities"],
                "teammate": rival["player"],
                "teammate_inside_10_opportunities": rival[
                    "inside_10_opportunities"
                ],
                "explanation": (
                    f"{rival['player']} received {gap} more inside-the-10 "
                    f"opportunities than {player['player']}."
                ),
            }
        )
    return results


def _individual_story_signals(
    usage: dict[str, dict[str, Any]],
    rostered_gsis: set[str],
    team_offensive_tds: dict[str, int],
    player_trailing_q4: set[str],
    winning_teams: set[str],
) -> list[dict[str, Any]]:
    results = []
    for player_id in sorted(rostered_gsis):
        row = usage.get(player_id)
        if not row:
            continue
        points_by_q = row.get("fantasy_points_by_quarter") or {}
        total_points = _number(row.get("reconstructed_fantasy_points"))
        late_points = sum(
            _number(points)
            for quarter, points in points_by_q.items()
            if int(quarter) >= 4
        )
        team = str(row.get("team") or "")
        opportunities = int(row.get("opportunities") or 0)

        if total_points >= 12 and late_points >= 8 and late_points / total_points >= 0.5:
            results.append(
                {
                    "type": "LATE_SURGE",
                    "player_id": player_id,
                    "player": row["player"],
                    "team": team,
                    "reconstructed_points": round(total_points, 2),
                    "q4_ot_points": round(late_points, 2),
                    "late_share": round(late_points / total_points, 3),
                    "explanation": (
                        f"{row['player']} produced {late_points / total_points:.0%} "
                        "of reconstructed fantasy scoring in Q4/OT."
                    ),
                }
            )

        if (
            player_id in player_trailing_q4
            and team in winning_teams
            and late_points >= 8
        ):
            results.append(
                {
                    "type": "COMEBACK_ENGINE",
                    "player_id": player_id,
                    "player": row["player"],
                    "team": team,
                    "q4_ot_points": round(late_points, 2),
                    "explanation": (
                        f"{row['player']} generated major Q4/OT production after "
                        "his team had trailed by at least seven."
                    ),
                }
            )

        team_tds = int(team_offensive_tds.get(team, 0))
        if (
            row.get("position") in {"RB", "WR", "TE"}
            and team_tds >= 4
            and opportunities >= 6
            and int(row.get("touchdowns") or 0) <= 1
            and int(row.get("touchdowns") or 0) / team_tds <= 0.25
        ):
            results.append(
                {
                    "type": "MISSED_WINDFALL",
                    "player_id": player_id,
                    "player": row["player"],
                    "team": team,
                    "opportunities": opportunities,
                    "player_touchdowns": row["touchdowns"],
                    "team_offensive_touchdowns": team_tds,
                    "explanation": (
                        f"{team} scored {team_tds} offensive touchdowns while "
                        f"{row['player']} handled {opportunities} opportunities but "
                        f"scored {row['touchdowns']}."
                    ),
                }
            )

        if opportunities >= 15 and total_points < 8:
            results.append(
                {
                    "type": "VOLUME_WITHOUT_RESULTS",
                    "player_id": player_id,
                    "player": row["player"],
                    "team": team,
                    "opportunities": opportunities,
                    "reconstructed_points": round(total_points, 2),
                    "explanation": (
                        f"{row['player']} received {opportunities} opportunities "
                        "without converting them into a strong fantasy result."
                    ),
                }
            )

        if total_points >= 20 and 0 < opportunities <= 8:
            results.append(
                {
                    "type": "EFFICIENCY_SPIKE",
                    "player_id": player_id,
                    "player": row["player"],
                    "team": team,
                    "opportunities": opportunities,
                    "reconstructed_points": round(total_points, 2),
                    "explanation": (
                        f"{row['player']} generated a large fantasy result on only "
                        f"{opportunities} carries plus targets."
                    ),
                }
            )
    return results


def _add_high_value_opportunity(row: dict[str, Any], yardline: float) -> None:
    if yardline <= 0:
        return
    if yardline <= 20:
        row["red_zone_opportunities"] += 1
    if yardline <= 10:
        row["inside_10_opportunities"] += 1
    if yardline <= 5:
        row["inside_5_opportunities"] += 1


def _add_quarter_points(row: dict[str, Any], quarter: str, points: float) -> None:
    if not quarter or quarter == "0" or abs(points) < 0.0001:
        return
    bucket = row["fantasy_points_by_quarter"]
    bucket[quarter] = _number(bucket.get(quarter)) + points


def _winning_teams(schedule: list[dict[str, Any]]) -> set[str]:
    winners = set()
    for game in schedule:
        home_score = game.get("home_score")
        away_score = game.get("away_score")
        if home_score is None or away_score is None:
            continue
        if _number(home_score) > _number(away_score):
            winners.add(str(game.get("home_team") or ""))
        elif _number(away_score) > _number(home_score):
            winners.add(str(game.get("away_team") or ""))
    return winners


def _normalize_name(value: str) -> str:
    value = value.casefold()
    value = re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", value)
    return re.sub(r"[^a-z0-9]", "", value)


def _pid(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _weight(settings: dict[str, Any], key: str) -> float:
    return _number(settings.get(key))


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
