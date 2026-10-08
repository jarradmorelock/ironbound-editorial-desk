"""Player season scoring, with ownership history kept separate from NFL scoring."""
from __future__ import annotations

import math
from typing import Any

import requests


def _number(value: Any) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def collect_player_scoring_history(client: Any, snapshot: dict[str, Any]) -> dict[str, Any]:
    league = snapshot.get("league") or {}
    season = str(league.get("season") or (snapshot.get("nfl_state") or {}).get("season") or "")
    through_week = int(snapshot.get("week") or 0)
    settings = league.get("scoring_settings") or {}
    players = snapshot.get("players") or {}
    required = {str(pid) for roster in snapshot.get("rosters") or []
                for field in ("players", "taxi", "reserve") for pid in roster.get(field) or []}
    schedule = ((snapshot.get("flagship_sleeper") or {}).get("schedule") or {}).get("weeks") or {}
    rows, weeks = [], {}
    for week in range(1, through_week + 1):
        warnings = []
        try:
            matchups = (snapshot.get("matchups") or []) if week == through_week else schedule.get(str(week))
            if matchups is None:
                matchups = client.matchups(str(league.get("league_id") or ""), week)
            if not isinstance(matchups, list) or not matchups:
                raise ValueError("No historical matchup rows")
        except (requests.RequestException, OSError, ValueError, AttributeError) as exc:
            matchups = []
            warnings.append(str(exc))
        exact, owners = {}, {}
        conflicts = set()
        for matchup in matchups:
            rid = int(matchup.get("roster_id") or 0)
            for pid in matchup.get("players") or []:
                owners[str(pid)] = rid
            points = dict(matchup.get("players_points") or {})
            points.update(matchup.get("players_points_custom") or {})
            for pid, value in points.items():
                pid, value = str(pid), _number(value)
                if value is None:
                    continue
                if pid in exact and exact[pid] != value:
                    conflicts.add(pid)
                exact[pid] = value
                owners[pid] = rid
        raw, verified = {}, False
        try:
            raw = client.weekly_stats(season, week)
            if not isinstance(raw, dict) or not raw or not settings:
                raise ValueError("Full weekly statistics or league scoring settings unavailable")
            # A sparse full-week feed omits inactive players. Never infer a zero
            # from an empty/failed/truncated response: corroborate its coverage
            # with the independent completed league matchup scores first.
            nonzero = {pid for pid, value in exact.items() if value != 0}
            if not nonzero or any(not isinstance(raw.get(pid), dict) or not raw[pid] for pid in nonzero):
                raise ValueError("Weekly statistics do not cover the league's recorded scorers")
            verified = True
        except (requests.RequestException, OSError, ValueError, AttributeError) as exc:
            warnings.append(str(exc))
        missing = []
        for pid in sorted(required | exact.keys()):
            source, stats = "sleeper_matchup", None
            value = exact.get(pid)
            if pid in conflicts:
                value = None
            elif value is None and verified:
                stats = raw.get(pid)
                if stats is None:
                    value, source = 0.0, "sleeper_weekly_stats_no_stat_line"
                elif isinstance(stats, dict) and all(_number(v) is not None for v in settings.values()):
                    values = [_number(stats.get(key, 0)) for key in settings]
                    if all(v is not None for v in values):
                        value = sum(v * float(weight) for v, weight in zip(values, settings.values()))
                        source = "sleeper_weekly_stats"
            if value is None:
                if pid in required:
                    missing.append(pid)
                continue
            rows.append({
                "season": season, "week": week, "player_id": pid,
                "player": (players.get(pid) or {}).get("full_name") or pid,
                "position": (players.get(pid) or {}).get("position"),
                "roster_id": owners.get(pid), "points": round(value, 2),
                "source": source,
                "source_url": (f"https://api.sleeper.app/v1/league/{league.get('league_id')}/matchups/{week}"
                               if source == "sleeper_matchup" else f"https://api.sleeper.app/v1/stats/nfl/regular/{season}/{week}"),
                **({"stats": stats} if stats is not None else {}),
            })
        weeks[str(week)] = {"complete": not missing and bool(required), "missing_player_ids": missing,
                            "weekly_stats_verified": verified, "warnings": warnings,
                            "conflicting_player_ids": sorted(conflicts)}
    return {"schema_version": 1, "season": season, "through_week": through_week,
            "scoring_settings": settings, "rows": rows,
            "zero_policy": "No stat line in a successfully verified completed full-week feed means no recorded scoring statistics; failed or unverified feeds remain missing.",
            "coverage": {"complete": bool(weeks) and all(v["complete"] for v in weeks.values()), "weeks": weeks}}


def season_leaders(snapshot: dict[str, Any]) -> dict[str, Any]:
    history = snapshot.get("player_scoring_history") or {}
    through_week = int(snapshot.get("week") or 0)
    players = snapshot.get("players") or {}
    users = {str(u.get("user_id")): u for u in snapshot.get("users") or []}
    owners, names = {}, {}
    for roster in snapshot.get("rosters") or []:
        rid = int(roster["roster_id"])
        user = users.get(str(roster.get("owner_id")), {})
        names[rid] = (user.get("metadata") or {}).get("team_name") or user.get("display_name") or f"Roster {rid}"
        for field in ("players", "taxi", "reserve"):
            for pid in roster.get(field) or []:
                owners[str(pid)] = rid
    scores = {(int(r["week"]), str(r["player_id"])): r for r in history.get("rows") or []
              if 0 < int(r["week"]) <= through_week}
    incomplete = {pid for pid in owners if any((w, pid) not in scores for w in range(1, through_week + 1))}
    rookie_ids = {pid for pid in owners if (players.get(pid) or {}).get("years_exp") == 0}
    result = {}
    for key, ids in [("player_season_top_three", set(owners)), ("rookie_season_leaders", rookie_ids)]:
        missing = incomplete & ids
        ready = not missing and through_week > 0 and bool(history) and bool(owners)
        by_position = {}
        if ready:
            for pid in ids:
                player = players.get(pid) or {}
                position = player.get("position") or "UNKNOWN"
                by_position.setdefault(position, []).append({
                    "player_id": pid, "player": player.get("full_name") or pid, "position": position,
                    "points": round(sum(scores[w, pid]["points"] for w in range(1, through_week + 1)), 2),
                    "fantasy_team": names[owners[pid]],
                })
            for pos, rows in by_position.items():
                rows.sort(key=lambda r: (-r["points"], r["player"]))
                by_position[pos] = rows[0] if key == "rookie_season_leaders" else rows[:3]
        result[key] = {"status": "READY" if ready else "UNAVAILABLE", "through_week": through_week,
                       "reason": ("Missing verified weekly scores for " + ", ".join(sorted(missing))) if missing else None,
                       "by_position": by_position,
                       "policy": "Full NFL season points under this league's scoring; team labels identify current ownership."}
    return result
