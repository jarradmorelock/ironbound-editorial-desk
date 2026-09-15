from __future__ import annotations

import re
from collections import defaultdict
from typing import Any


def build_nfl_game_intelligence(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    """Build evidence-first NFL usage/game-script context for flagship leagues."""
    if (snapshot.get("editorial") or {}).get("tier") != "flagship":
        return None

    context = snapshot.get("nfl_context") or {}
    pbp = context.get("play_by_play") or {}
    snaps = context.get("snap_counts") or {}
    stats = context.get("player_stats") or {}
    schedule = context.get("schedule") or {}
    sleeper_players = snapshot.get("players") or {}

    current_sleeper_ids = _current_roster_player_ids(snapshot)
    rostered_gsis = {
        str((sleeper_players.get(pid) or {}).get("gsis_id"))
        for pid in current_sleeper_ids
        if (sleeper_players.get(pid) or {}).get("gsis_id")
    }
    rostered_signatures: set[tuple[str, str, str]] = set()
    for sid in current_sleeper_ids:
        player = sleeper_players.get(sid) or {}
        signature = _identity_signature(
            _sleeper_player_name(player),
            player.get("team"),
            player.get("position"),
        )
        if signature:
            rostered_signatures.add(signature)

    relevant_teams = {
        str((sleeper_players.get(pid) or {}).get("team"))
        for pid in current_sleeper_ids
        if (sleeper_players.get(pid) or {}).get("team")
    }

    names: dict[str, str] = {}
    positions: dict[str, str | None] = {}
    teams: dict[str, str | None] = {}
    for row in stats.get("records") or []:
        pid = str(row.get("player_id") or "")
        if not pid:
            continue
        name = str(row.get("player_display_name") or row.get("player_name") or pid)
        names[pid] = name
        positions[pid] = row.get("position")
        teams[pid] = row.get("team")
        signature = _identity_signature(name, row.get("team"), row.get("position"))
        if signature and signature in rostered_signatures:
            rostered_gsis.add(pid)

    for sid in current_sleeper_ids:
        player = sleeper_players.get(sid) or {}
        pid = str(player.get("gsis_id") or "")
        if not pid:
            continue
        names.setdefault(pid, str(player.get("full_name") or pid))
        positions.setdefault(pid, player.get("position"))
        teams.setdefault(pid, player.get("team"))

    usage: dict[str, dict[str, Any]] = {}

    def ensure(pid: str | None, team: str | None = None) -> dict[str, Any] | None:
        if not pid:
            return None
        pid = str(pid)
        if pid not in usage:
            usage[pid] = {
                "player_id": pid,
                "player": names.get(pid, pid),
                "team": teams.get(pid) or team,
                "position": positions.get(pid),
                "rostered": pid in rostered_gsis,
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
        elif team and not usage[pid].get("team"):
            usage[pid]["team"] = team
        return usage[pid]

    for pid in rostered_gsis:
        ensure(pid)
    # Initialize contextual teammates on relevant NFL teams so snap-count names
    # can join to GSIS IDs instead of creating duplicate PFR-only identities.
    for row in stats.get("records") or []:
        team = str(row.get("team") or "")
        if relevant_teams and team not in relevant_teams:
            continue
        ensure(_pid(row.get("player_id")), team)

    scoring = (snapshot.get("league") or {}).get("scoring_settings") or {}
    team_tds: dict[str, int] = defaultdict(int)
    trailing_q4: set[str] = set()

    for play in pbp.get("records") or []:
        team = str(play.get("posteam") or "")
        if relevant_teams and team not in relevant_teams:
            continue
        quarter = int(play.get("quarter") or 0)
        qkey = str(quarter)
        yardline = _number(play.get("yardline_100"))

        if play.get("pass_attempt"):
            passer = ensure(_pid(play.get("passer_player_id")), team)
            receiver = ensure(_pid(play.get("receiver_player_id")), team)
            if passer:
                points = 0.0
                if play.get("complete_pass"):
                    points += _weight(scoring, "pass_cmp")
                    points += _number(play.get("yards_gained")) * _weight(scoring, "pass_yd")
                if play.get("pass_touchdown"):
                    points += _weight(scoring, "pass_td")
                    passer["touchdowns"] += 1
                if play.get("interception"):
                    points += _weight(scoring, "pass_int")
                if play.get("first_down_pass"):
                    points += _weight(scoring, "pass_fd")
                _add_q_points(passer, qkey, points)
                _mark_comeback_context(passer, play, quarter, trailing_q4)
            if receiver:
                receiver["targets"] += 1
                receiver["opportunities"] += 1
                _add_high_value(receiver, yardline)
                points = 0.0
                if play.get("complete_pass"):
                    receiver["receptions"] += 1
                    points += _weight(scoring, "rec")
                    points += _number(play.get("yards_gained")) * _weight(scoring, "rec_yd")
                if play.get("pass_touchdown"):
                    points += _weight(scoring, "rec_td")
                    receiver["touchdowns"] += 1
                if play.get("first_down_pass"):
                    points += _weight(scoring, "rec_fd")
                _add_q_points(receiver, qkey, points)
                _mark_comeback_context(receiver, play, quarter, trailing_q4)
            if play.get("pass_touchdown"):
                team_tds[team] += 1

        if play.get("rush_attempt") and not play.get("qb_kneel") and not play.get("qb_spike"):
            rusher = ensure(_pid(play.get("rusher_player_id")), team)
            if rusher:
                rusher["carries"] += 1
                rusher["opportunities"] += 1
                _add_high_value(rusher, yardline)
                points = _weight(scoring, "rush_att")
                points += _number(play.get("yards_gained")) * _weight(scoring, "rush_yd")
                if play.get("rush_touchdown"):
                    points += _weight(scoring, "rush_td")
                    rusher["touchdowns"] += 1
                if play.get("first_down_rush"):
                    points += _weight(scoring, "rush_fd")
                _add_q_points(rusher, qkey, points)
                _mark_comeback_context(rusher, play, quarter, trailing_q4)
            if play.get("rush_touchdown"):
                team_tds[team] += 1

    name_to_id = {
        (_normalize_name(row["player"]), str(row.get("team") or "")): pid
        for pid, row in usage.items()
    }
    for snap in snaps.get("records") or []:
        team = str(snap.get("team") or "")
        if relevant_teams and team not in relevant_teams:
            continue
        key = (_normalize_name(str(snap.get("player") or "")), team)
        pid = name_to_id.get(key)
        if not pid:
            pid = f"pfr:{snap.get('pfr_player_id') or key[0]}"
            names[pid] = str(snap.get("player") or pid)
            positions[pid] = snap.get("position")
            teams[pid] = team
        row = ensure(pid, team)
        if not row:
            continue
        if not row.get("player") or row["player"] == pid:
            row["player"] = str(snap.get("player") or pid)
        if not row.get("position"):
            row["position"] = snap.get("position")
        row["offense_snaps"] = _number(snap.get("offense_snaps"))
        row["snap_share"] = round(_number(snap.get("offense_pct")), 4)

    for row in usage.values():
        qpoints = row["fantasy_points_by_quarter"]
        row["fantasy_points_by_quarter"] = {
            q: round(points, 2)
            for q, points in sorted(qpoints.items(), key=lambda item: int(item[0]))
            if abs(points) > 0.0001
        }
        row["reconstructed_fantasy_points"] = round(
            sum(row["fantasy_points_by_quarter"].values()), 2
        )

    winners = _winning_teams(schedule.get("records") or [])
    signals = []
    signals.extend(_backfield_split_signals(usage, relevant_teams))
    signals.extend(_high_value_touch_signals(usage, rostered_gsis, relevant_teams))
    signals.extend(_individual_signals(usage, rostered_gsis, team_tds, trailing_q4, winners))

    return {
        "source_status": {
            "play_by_play": pbp.get("status", "unavailable"),
            "snap_counts": snaps.get("status", "unavailable"),
            "player_stats": stats.get("status", "unavailable"),
            "schedule": schedule.get("status", "unavailable"),
        },
        "team_offensive_touchdowns": dict(sorted(team_tds.items())),
        "players": usage,
        "story_signals": signals,
    }


def _current_roster_player_ids(snapshot: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for roster in snapshot.get("rosters") or []:
        for field in ("players", "taxi", "reserve"):
            ids.update(str(pid) for pid in (roster.get(field) or []))
    return ids


def _sleeper_player_name(player: dict[str, Any]) -> str:
    return str(
        player.get("full_name")
        or " ".join(
            str(part)
            for part in (player.get("first_name"), player.get("last_name"))
            if part
        ).strip()
        or ""
    )


def _identity_signature(name: Any, team: Any, position: Any) -> tuple[str, str, str] | None:
    normalized = _normalize_name(str(name or ""))
    team_text = str(team or "").upper()
    position_text = str(position or "").upper()
    if not normalized or not team_text or not position_text:
        return None
    return normalized, team_text, position_text


def _mark_comeback_context(row: dict[str, Any], play: dict[str, Any], quarter: int, marked: set[str]) -> None:
    if quarter >= 4 and _number(play.get("score_differential")) <= -7:
        marked.add(row["player_id"])


def _backfield_split_signals(usage: dict[str, dict[str, Any]], relevant_teams: set[str]) -> list[dict[str, Any]]:
    by_team: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in usage.values():
        team = str(row.get("team") or "")
        if row.get("position") == "RB" and row.get("snap_share") is not None and (not relevant_teams or team in relevant_teams):
            by_team[team].append(row)
    results = []
    for team, backs in sorted(by_team.items()):
        backs.sort(key=lambda row: (-_number(row.get("snap_share")), row["player"]))
        if len(backs) < 2:
            continue
        first, second = backs[:2]
        if _number(second["snap_share"]) < 0.35 or abs(_number(first["snap_share"]) - _number(second["snap_share"])) > 0.15:
            continue
        if not (first.get("rostered") or second.get("rostered")):
            continue
        results.append({
            "type": "BACKFIELD_SPLIT",
            "team": team,
            "players": [
                {"player_id": row["player_id"], "player": row["player"], "snap_share": row["snap_share"], "offense_snaps": row["offense_snaps"]}
                for row in (first, second)
            ],
            "explanation": f"{first['player']} and {second['player']} played nearly even offensive snap shares.",
        })
    return results


def _high_value_touch_signals(usage: dict[str, dict[str, Any]], rostered: set[str], relevant_teams: set[str]) -> list[dict[str, Any]]:
    by_team: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in usage.values():
        team = str(row.get("team") or "")
        if row.get("position") == "RB" and (not relevant_teams or team in relevant_teams):
            by_team[team].append(row)
    results = []
    for pid in sorted(rostered):
        player = usage.get(pid)
        if not player or player.get("position") != "RB" or int(player.get("opportunities") or 0) < 4:
            continue
        team = str(player.get("team") or "")
        teammates = [row for row in by_team.get(team, []) if row["player_id"] != pid]
        if not teammates:
            continue
        rival = max(teammates, key=lambda row: (int(row.get("inside_10_opportunities") or 0), int(row.get("inside_5_opportunities") or 0), int(row.get("opportunities") or 0)))
        gap = int(rival.get("inside_10_opportunities") or 0) - int(player.get("inside_10_opportunities") or 0)
        if gap < 2 or int(rival.get("opportunities") or 0) < max(2, int(player["opportunities"]) * 0.4):
            continue
        results.append({
            "type": "HIGH_VALUE_TOUCH_SHIFT",
            "player_id": pid,
            "player": player["player"],
            "team": team,
            "inside_10_opportunities": player["inside_10_opportunities"],
            "teammate": rival["player"],
            "teammate_inside_10_opportunities": rival["inside_10_opportunities"],
            "explanation": f"{rival['player']} received {gap} more inside-the-10 opportunities than {player['player']}.",
        })
    return results


def _individual_signals(
    usage: dict[str, dict[str, Any]],
    rostered: set[str],
    team_tds: dict[str, int],
    trailing_q4: set[str],
    winners: set[str],
) -> list[dict[str, Any]]:
    results = []
    for pid in sorted(rostered):
        row = usage.get(pid)
        if not row:
            continue
        by_q = row.get("fantasy_points_by_quarter") or {}
        total = _number(row.get("reconstructed_fantasy_points"))
        late = sum(_number(points) for q, points in by_q.items() if int(q) >= 4)
        team = str(row.get("team") or "")
        opps = int(row.get("opportunities") or 0)
        if total >= 12 and late >= 8 and late / total >= 0.5:
            results.append({"type": "LATE_SURGE", "player_id": pid, "player": row["player"], "team": team, "reconstructed_points": round(total, 2), "q4_ot_points": round(late, 2), "late_share": round(late / total, 3), "explanation": f"{row['player']} produced {late / total:.0%} of reconstructed fantasy scoring in Q4/OT."})
        if pid in trailing_q4 and team in winners and late >= 8:
            results.append({"type": "COMEBACK_ENGINE", "player_id": pid, "player": row["player"], "team": team, "q4_ot_points": round(late, 2), "explanation": f"{row['player']} generated major Q4/OT production after his team had trailed by at least seven."})
        tds = int(team_tds.get(team, 0))
        if row.get("position") in {"RB", "WR", "TE"} and tds >= 4 and opps >= 6 and int(row.get("touchdowns") or 0) <= 1 and int(row.get("touchdowns") or 0) / tds <= 0.25:
            results.append({"type": "MISSED_WINDFALL", "player_id": pid, "player": row["player"], "team": team, "opportunities": opps, "player_touchdowns": row["touchdowns"], "team_offensive_touchdowns": tds, "explanation": f"{team} scored {tds} offensive touchdowns while {row['player']} handled {opps} opportunities but scored {row['touchdowns']}."})
        if opps >= 15 and total < 8:
            results.append({"type": "VOLUME_WITHOUT_RESULTS", "player_id": pid, "player": row["player"], "team": team, "opportunities": opps, "reconstructed_points": round(total, 2), "explanation": f"{row['player']} received {opps} opportunities without converting them into a strong fantasy result."})
        if row.get("position") in {"RB", "WR", "TE"} and total >= 20 and 0 < opps <= 8:
            results.append({"type": "EFFICIENCY_SPIKE", "player_id": pid, "player": row["player"], "team": team, "opportunities": opps, "reconstructed_points": round(total, 2), "explanation": f"{row['player']} generated a large fantasy result on only {opps} carries plus targets."})
    return results


def _add_high_value(row: dict[str, Any], yardline: float) -> None:
    if yardline <= 0:
        return
    if yardline <= 20:
        row["red_zone_opportunities"] += 1
    if yardline <= 10:
        row["inside_10_opportunities"] += 1
    if yardline <= 5:
        row["inside_5_opportunities"] += 1


def _add_q_points(row: dict[str, Any], quarter: str, points: float) -> None:
    if quarter and quarter != "0" and abs(points) > 0.0001:
        row["fantasy_points_by_quarter"][quarter] = _number(row["fantasy_points_by_quarter"].get(quarter)) + points


def _winning_teams(games: list[dict[str, Any]]) -> set[str]:
    winners = set()
    for game in games:
        home, away = game.get("home_score"), game.get("away_score")
        if home is None or away is None:
            continue
        if _number(home) > _number(away):
            winners.add(str(game.get("home_team") or ""))
        elif _number(away) > _number(home):
            winners.add(str(game.get("away_team") or ""))
    return winners


def _normalize_name(value: str) -> str:
    value = re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", value.casefold())
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
