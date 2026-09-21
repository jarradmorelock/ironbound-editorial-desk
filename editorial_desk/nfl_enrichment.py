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

    stat_book = _build_flagship_stat_book(snapshot, stats, usage)

    return {
        "source_status": {
            "play_by_play": pbp.get("status", "unavailable"),
            "snap_counts": snaps.get("status", "unavailable"),
            "player_stats": stats.get("status", "unavailable"),
            "schedule": schedule.get("status", "unavailable"),
        },
        "team_offensive_touchdowns": dict(sorted(team_tds.items())),
        "players": usage,
        "stat_book": stat_book,
        "story_signals": signals,
    }


def _build_flagship_stat_book(
    snapshot: dict[str, Any],
    stats_source: dict[str, Any],
    usage: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build a writing-first starter stat book from official weekly NFL stats.

    Fantasy points are deliberately excluded. The magazine should describe
    football performance with real box-score and usage evidence, reserving
    fantasy points for matchup totals and decisions where the point swing
    changes the fantasy outcome.
    """
    status = str(stats_source.get("status") or "unavailable")
    if status != "available":
        return {
            "status": "unavailable",
            "records": [],
            "missing_starters": [],
            "error": str(
                stats_source.get("error")
                or "weekly nflverse player statistics were unavailable"
            ),
        }

    stats = stats_source.get("records") or []
    team_carries: dict[str, float] = defaultdict(float)
    team_targets: dict[str, float] = defaultdict(float)
    for row in stats:
        team = str(row.get("team") or "")
        if not team:
            continue
        team_carries[team] += _number(row.get("carries"))
        team_targets[team] += _number(row.get("targets"))

    players = snapshot.get("players") or {}
    users = {
        str(user.get("user_id")): user for user in snapshot.get("users") or []
    }
    rosters = {
        int(roster.get("roster_id") or 0): roster
        for roster in snapshot.get("rosters") or []
    }

    by_gsis: dict[str, dict[str, Any]] = {}
    by_signature: dict[tuple[str, str, str], dict[str, Any]] = {}
    expected: dict[str, dict[str, Any]] = {}

    for matchup in snapshot.get("matchups") or []:
        roster_id = int(matchup.get("roster_id") or 0)
        roster = rosters.get(roster_id) or {}
        owner = users.get(str(roster.get("owner_id"))) or {}
        metadata = owner.get("metadata") or {}
        fantasy_team = str(
            metadata.get("team_name")
            or owner.get("display_name")
            or f"Roster {roster_id}"
        )
        for raw_player_id in matchup.get("starters") or []:
            sleeper_id = str(raw_player_id)
            player = players.get(sleeper_id) or {}
            position = str(player.get("position") or "")
            # nflverse weekly player stats do not provide a team-defense row.
            if position.upper() in {"DEF", "DST", "D/ST"}:
                continue
            context = {
                "sleeper_player_id": sleeper_id,
                "fantasy_team": fantasy_team,
                "roster_id": roster_id,
                "player": _sleeper_player_name(player) or sleeper_id,
                "position": position or None,
                "nfl_team": player.get("team"),
            }
            expected[sleeper_id] = context
            gsis_id = str(player.get("gsis_id") or "").strip()
            if gsis_id:
                by_gsis[gsis_id] = context
            signature = _identity_signature(
                context["player"],
                player.get("team"),
                player.get("position"),
            )
            if signature:
                by_signature[signature] = context

    records: list[dict[str, Any]] = []
    matched_sleeper_ids: set[str] = set()

    for row in stats:
        nfl_id = str(row.get("player_id") or "").strip()
        name = str(
            row.get("player_display_name")
            or row.get("player_name")
            or nfl_id
        )
        signature = _identity_signature(
            name,
            row.get("team"),
            row.get("position"),
        )
        context = by_gsis.get(nfl_id) or (
            by_signature.get(signature) if signature else None
        )
        if not context:
            continue

        matched_sleeper_ids.add(str(context["sleeper_player_id"]))
        usage_row = usage.get(nfl_id) or {}
        team = str(row.get("team") or "")
        carries = _number(row.get("carries"))
        targets = _number(row.get("targets"))
        carry_share = (
            carries / team_carries[team] if team and team_carries.get(team) else None
        )
        target_share = (
            targets / team_targets[team] if team and team_targets.get(team) else None
        )

        record = {
            **context,
            "nfl_player_id": nfl_id or None,
            "opponent": row.get("opponent_team"),
            "completions": _number(row.get("completions")),
            "attempts": _number(row.get("attempts")),
            "passing_yards": _number(row.get("passing_yards")),
            "passing_tds": _number(row.get("passing_tds")),
            "passing_interceptions": _number(row.get("passing_interceptions")),
            "carries": carries,
            "rushing_yards": _number(row.get("rushing_yards")),
            "rushing_tds": _number(row.get("rushing_tds")),
            "receptions": _number(row.get("receptions")),
            "targets": targets,
            "receiving_yards": _number(row.get("receiving_yards")),
            "receiving_tds": _number(row.get("receiving_tds")),
            "carry_share": round(carry_share, 4) if carry_share is not None else None,
            "target_share": round(target_share, 4) if target_share is not None else None,
            "offense_snaps": usage_row.get("offense_snaps"),
            "snap_share": usage_row.get("snap_share"),
            "red_zone_opportunities": usage_row.get("red_zone_opportunities"),
            "inside_10_opportunities": usage_row.get("inside_10_opportunities"),
            "inside_5_opportunities": usage_row.get("inside_5_opportunities"),
        }
        record["nfl_stat_line"] = _format_nfl_stat_line(record)
        records.append(record)

    missing = [
        {
            **context,
            "reason": (
                "No weekly nflverse player-stat row matched this submitted starter. "
                "Verify bye, inactive/no-stat game, or player identity manually before publication."
            ),
        }
        for sleeper_id, context in expected.items()
        if sleeper_id not in matched_sleeper_ids
    ]

    records.sort(
        key=lambda row: (
            str(row.get("fantasy_team") or "").casefold(),
            str(row.get("position") or ""),
            str(row.get("player") or "").casefold(),
        )
    )
    missing.sort(
        key=lambda row: (
            str(row.get("fantasy_team") or "").casefold(),
            str(row.get("position") or ""),
            str(row.get("player") or "").casefold(),
        )
    )
    return {
        "status": "available",
        "records": records,
        "missing_starters": missing,
    }


def _format_nfl_stat_line(row: dict[str, Any]) -> str:
    """Format actual NFL production and usage for magazine research."""
    parts: list[str] = []

    attempts = int(_number(row.get("attempts")))
    completions = int(_number(row.get("completions")))
    passing_yards = _number(row.get("passing_yards"))
    passing_tds = int(_number(row.get("passing_tds")))
    interceptions = int(_number(row.get("passing_interceptions")))
    if attempts or completions or passing_yards or passing_tds or interceptions:
        passing = (
            f"{completions}/{attempts} passing for "
            f"{_display_number(passing_yards)} yards"
        )
        if passing_tds:
            passing += f", {passing_tds} TD"
        if interceptions:
            passing += f", {interceptions} INT"
        parts.append(passing)

    carries = int(_number(row.get("carries")))
    rushing_yards = _number(row.get("rushing_yards"))
    rushing_tds = int(_number(row.get("rushing_tds")))
    if carries or rushing_yards or rushing_tds:
        rushing = f"{carries} carries for {_display_number(rushing_yards)} yards"
        if rushing_tds:
            rushing += f", {rushing_tds} TD"
        if row.get("carry_share") is not None:
            rushing += f" ({_number(row['carry_share']):.1%} team carries)"
        parts.append(rushing)

    receptions = int(_number(row.get("receptions")))
    targets = int(_number(row.get("targets")))
    receiving_yards = _number(row.get("receiving_yards"))
    receiving_tds = int(_number(row.get("receiving_tds")))
    if receptions or targets or receiving_yards or receiving_tds:
        receiving = (
            f"{receptions} catches on {targets} targets for "
            f"{_display_number(receiving_yards)} yards"
        )
        if receiving_tds:
            receiving += f", {receiving_tds} TD"
        if row.get("target_share") is not None:
            receiving += f" ({_number(row['target_share']):.1%} team targets)"
        parts.append(receiving)

    if row.get("snap_share") is not None:
        snap_text = f"{_number(row['snap_share']):.1%} offensive snap share"
        if row.get("offense_snaps") is not None:
            snap_text += f" ({_display_number(row['offense_snaps'])} snaps)"
        parts.append(snap_text)

    high_value: list[str] = []
    for key, label in (
        ("red_zone_opportunities", "red-zone opps"),
        ("inside_10_opportunities", "inside-10"),
        ("inside_5_opportunities", "inside-5"),
    ):
        value = int(_number(row.get(key)))
        if value:
            high_value.append(f"{value} {label}")
    if high_value:
        parts.append(", ".join(high_value))

    return "; ".join(parts) if parts else "No recorded offensive box-score production"


def _display_number(value: Any) -> str:
    number = _number(value)
    return str(int(number)) if number.is_integer() else f"{number:.1f}".rstrip("0").rstrip(".")


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
