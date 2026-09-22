from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .external_inputs import ExternalEditorialInputs
from .chronicle_queries import ChronicleQueries


FLAGSHIP_PUBLICATIONS = {"ironbound_weekly", "unbound_weekly"}
CORE_POSITIONS = ("QB", "RB", "WR", "TE")


def build_flagship_research_packet(
    snapshot: dict[str, Any],
    dossier: dict[str, Any],
    story: dict[str, Any] | None,
    external: ExternalEditorialInputs,
    *,
    history_root: Path,
    chronicle: ChronicleQueries | None = None,
    publication_assets: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Build the deterministic factual contract that feeds flagship production.

    This object is intentionally pre-editorial. Code discovers facts, leaders,
    candidates, source gaps, and Tuesday handoff inputs. The AI/editor chooses
    story emphasis and writes prose later.
    """
    editorial = snapshot.get("editorial") or {}
    profile = editorial.get("publication_profile") or {}
    publication_key = str(profile.get("key") or "")
    if publication_key not in FLAGSHIP_PUBLICATIONS:
        return None

    season = str(
        (snapshot.get("nfl_state") or {}).get("season")
        or (snapshot.get("league") or {}).get("season")
        or dossier.get("season")
        or ""
    )
    week = int(snapshot.get("week") or dossier.get("week") or 0)
    league_key = str(editorial.get("league_key") or "")
    history = _season_dossiers(history_root, season, league_key, week)

    games = _game_research(snapshot, dossier)
    weekly = dossier.get("weekly_features") or {}
    awards = dossier.get("awards") or {}
    health = dossier.get("roster_health") or {}
    intelligence = dossier.get("nfl_game_intelligence") or {}

    packet: dict[str, Any] = {
        "schema_version": 1,
        "contract_version": "ironbound-production-v0.4",
        "publication_key": publication_key,
        "league_key": league_key,
        "season": season,
        "week": week,
        "information_current_through": dossier.get("information_current_through"),
        "contract_principles": {
            "deterministic_facts_first": True,
            "ai_role": "editorial selection and prose only",
            "fantasy_points_policy": (
                "Use fantasy points for matchup totals, awards, records, and "
                "result-changing lineup decisions. Use actual NFL statistics "
                "as the default description of player performance."
            ),
        },
        "game_coverage": {
            "required_matchups": 8,
            "feature_slots": 2,
            "remaining_game_writeups": 6,
            "editorial_selection_required": True,
            "games": games,
            "cover_candidates": _cover_candidates(games, dossier),
        },
        "usage_game_intelligence": {
            "source_status": intelligence.get("source_status") or {},
            "story_signals": intelligence.get("story_signals") or [],
            "actual_nfl_stat_book": intelligence.get("stat_book") or {},
        },
        "usage_desk": _usage_desk(intelligence),
        "injury_roster_health": health,
        "weekly_honors": {
            "started_position_leaders": _attach_stat_lines(
                weekly.get("started_position_leaders") or {}, intelligence
            ),
            "manager_of_the_week": awards.get("manager_of_the_week"),
            "weekly_efficiency_top_three": weekly.get("lineup_efficiency_top_three") or [],
            "season_efficiency_top_three": _season_efficiency_top_three(
                history,
                snapshot=snapshot,
                league_key=league_key,
                season=season,
                chronicle=chronicle,
            ),
            "season_team_score_top_three": _season_team_score_top_three(
                history,
                snapshot=snapshot,
                league_key=league_key,
                season=season,
                chronicle=chronicle,
            ),
            "benchwarmer_of_the_week": _attach_stat_lines(
                weekly.get("benchwarmer_of_the_week"), intelligence
            ),
            "rookie_watch_top_five": _attach_rookie_draft_context(
                _attach_stat_lines(
                    weekly.get("rookie_watch_top_five") or [], intelligence
                ),
                snapshot,
            ),
            "rotating_award_candidates": _rotating_award_candidates(dossier),
        },
        "power_board": {
            "writeup_inputs": _power_board_inputs(
                dossier,
                external,
                snapshot=snapshot,
                league_key=league_key,
                season=season,
                chronicle=chronicle,
            ),
            "writeups_are_editorial": True,
        },
        "power_rankings_chart": {
            "status": _external_status(external.power_rankings_supplied),
            "authority": "Ironbound_power_ranks",
            "movement_policy": "Use previous_rank and movement supplied by the Power Rankings engine. Do not recalculate movement in Editorial Desk.",
            "asset_key": "power_rankings",
            "rows": [
                {
                    "franchise_key": row.franchise_key,
                    "roster_id": row.roster_id,
                    "team": row.team,
                    "rank": row.rank,
                    "previous_rank": row.previous_rank,
                    "movement": row.movement,
                    "score": row.score,
                }
                for row in external.official_power_rankings
            ],
        },
        "playoff_odds_chart": {
            "status": _external_status(external.playoff_odds_supplied),
            "authority": "Ironbound_power_ranks",
            "asset_key": "playoff_forecast",
            "rows": [dict(row) for row in external.playoff_odds],
        },
        "ranking_publication_assets": {
            "authority": "Ironbound_power_ranks",
            "required": publication_assets is not None,
            "policy": "Use the supplied PNGs unchanged in the magazine. Do not redraw these charts.",
            "assets": dict(publication_assets or {}),
        },
        "tuesday_external_inputs": {
            "usage": {
                "status": _optional_external_status(external.usage_supplied),
                "rows": [dict(row) for row in external.usage],
                "note": "Optional legacy/external usage input. Weekly magazine usage is sourced from nflverse inside Editorial Desk.",
            },
            "war": {
                "status": _optional_external_status(external.war_supplied),
                "rows": [dict(row) for row in external.war],
            },
            "cwar": {
                "status": _optional_external_status(external.cwar_supplied),
                "rows": [dict(row) for row in external.cwar],
            },
            "source_metadata": dict(external.source_metadata),
            "notes": list(external.notes),
        },
        "story_desk": {
            "status": (story or {}).get("status", "unavailable"),
            "candidates": (story or {}).get("candidates") or [],
        },
    }
    packet["validation"] = validate_flagship_research_packet(packet)
    return packet


def validate_flagship_research_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Validate contract completeness without converting missing inputs into fiction."""
    checks: list[dict[str, Any]] = []
    manual: list[str] = []
    awaiting: list[str] = []
    editorial: list[str] = []

    games = ((packet.get("game_coverage") or {}).get("games") or [])
    required_games = int((packet.get("game_coverage") or {}).get("required_matchups") or 8)
    _check(checks, "eight_matchups", len(games) == required_games, f"{len(games)}/{required_games} matchups present")
    if len(games) != required_games:
        manual.append(
            f"Expected {required_games} completed matchups but found {len(games)}. Verify Sleeper matchup collection."
        )

    duplicate_ids = _duplicates(str(row.get("matchup_id")) for row in games)
    _check(checks, "unique_matchups", not duplicate_ids, "no duplicate matchup IDs" if not duplicate_ids else f"duplicates: {', '.join(duplicate_ids)}")
    if duplicate_ids:
        manual.append("Duplicate matchup coverage must be resolved before production.")

    for game in games:
        if not game.get("starter_stat_lines"):
            manual.append(
                f"Matchup {game.get('matchup_id')}: no submitted-starter NFL stat lines matched."
            )

    usage = packet.get("usage_desk") or {}
    usage_ok = usage.get("status") == "READY"
    _check(
        checks,
        "weekly_usage",
        usage_ok,
        str(usage.get("status") or "missing"),
    )
    if not usage_ok:
        manual.append(
            "Usage Desk evidence is incomplete. Weekly player usage from nflverse "
            "player stats must be available before flagship production."
        )

    health = packet.get("injury_roster_health") or {}
    health_ok = health.get("status") == "available"
    _check(checks, "injury_health", health_ok, str(health.get("status") or "missing"))
    if not health_ok:
        manual.append("Injury / roster-health source is unavailable.")

    honors = packet.get("weekly_honors") or {}
    for key in (
        "started_position_leaders",
        "manager_of_the_week",
        "season_efficiency_top_three",
        "season_team_score_top_three",
        "benchwarmer_of_the_week",
        "rookie_watch_top_five",
    ):
        value = honors.get(key)
        ok = value is not None and (not isinstance(value, (list, dict)) or bool(value))
        _check(checks, f"honors_{key}", ok, "present" if ok else "missing/empty")
        if not ok:
            manual.append(f"Weekly Honors: {key.replace('_', ' ')} is missing or empty.")

    season_week = int(packet.get("week") or 0)
    efficiency_rows = honors.get("season_efficiency_top_three") or []
    efficiency_coverage = (
        bool(efficiency_rows)
        and all(int(row.get("weeks") or 0) >= season_week for row in efficiency_rows)
    )
    _check(
        checks,
        "season_efficiency_history",
        efficiency_coverage,
        (
            f"complete through Week {season_week}"
            if efficiency_coverage
            else f"fewer than {season_week} finalized efficiency weeks are recorded"
        ),
    )
    if not efficiency_coverage:
        manual.append(
            "Running efficiency board is incomplete in Chronicle/history; backfill or manually verify missing completed weeks."
        )

    for key, label in (
        ("power_rankings_chart", "Power Rankings"),
        ("playoff_odds_chart", "Playoff Odds"),
    ):
        section = packet.get(key) or {}
        if section.get("status") != "READY":
            awaiting.append(f"{label} from Tuesday power-rankings delivery.")

    source_metadata = (packet.get("tuesday_external_inputs") or {}).get("source_metadata") or {}
    source_week = source_metadata.get("week")
    if source_week is not None:
        try:
            source_week_value = int(source_week)
        except (TypeError, ValueError):
            source_week_value = None
        if source_week_value != int(packet.get("week") or 0):
            awaiting.append(
                f"Current-week Power Rankings handoff. Received Week {source_week!r} "
                f"for Week {packet.get('week')} production."
            )

    asset_section = packet.get("ranking_publication_assets") or {}
    assets = asset_section.get("assets") or {}
    if asset_section.get("required"):
        for asset_key, label in (
            ("power_rankings", "Power Rankings graphic"),
            ("playoff_forecast", "Playoff Forecast graphic"),
        ):
            asset = assets.get(asset_key) or {}
            asset_ok = asset.get("status") == "READY" and bool(asset.get("package_path"))
            _check(
                checks,
                f"asset_{asset_key}",
                asset_ok,
                str(asset.get("status") or "missing"),
            )
            if not asset_ok:
                awaiting.append(f"{label} from the Power Rankings engine.")

    editorial.extend(
        [
            "Choose the two cover-feature game slots from deterministic cover candidates.",
            "Choose one rotating weekly award from the supplied candidate pool.",
            "Write game stories, context-box wording, headlines, Power Board writeups, and art direction from verified evidence.",
        ]
    )

    ready = not manual and not awaiting
    return {
        "contract_valid": not any(not row["passed"] for row in checks if row["name"] in {"eight_matchups", "unique_matchups"}),
        "research_complete": ready,
        "checks": checks,
        "manual_verify": manual,
        "awaiting_tuesday_input": awaiting,
        "editorial_judgment": editorial,
    }


def render_flagship_research_packet(packet: dict[str, Any]) -> str:
    lines = [
        f"# {packet.get('publication_key', 'flagship').replace('_', ' ').title()} — Week {packet.get('week')} Flagship Research",
        "",
        f"Contract: **{packet.get('contract_version')}**",
        "",
        "## RESEARCH READINESS",
        "",
    ]
    validation = packet.get("validation") or {}
    lines.append("Research complete: **" + ("YES" if validation.get("research_complete") else "NO") + "**")
    lines.append("Structural contract valid: **" + ("YES" if validation.get("contract_valid") else "NO") + "**")

    lines.extend(["", "### Manual Verification"])
    manual = validation.get("manual_verify") or []
    lines.extend(f"- {row}" for row in manual)
    if not manual:
        lines.append("- None.")

    lines.extend(["", "### Awaiting Tuesday Inputs"])
    waiting = validation.get("awaiting_tuesday_input") or []
    lines.extend(f"- {row}" for row in waiting)
    if not waiting:
        lines.append("- None.")

    lines.extend(["", "### Editorial Judgment"])
    lines.extend(f"- {row}" for row in validation.get("editorial_judgment") or [])

    coverage = packet.get("game_coverage") or {}
    lines.extend(["", "## GAME COVERAGE LEDGER", ""])
    lines.append(
        f"Cover feature slots: {coverage.get('feature_slots', 2)}; "
        f"remaining game writeups: {coverage.get('remaining_game_writeups', 6)}; "
        f"completed matchup dossiers: {len(coverage.get('games') or [])}."
    )
    lines.extend(["", "### Cover Candidates"])
    for row in coverage.get("cover_candidates") or []:
        lines.append(
            f"- {row.get('matchup')}: signal score {row.get('signal_score')}; "
            + "; ".join(row.get("reasons") or [])
        )

    for game in coverage.get("games") or []:
        lines.extend(["", f"### Matchup {game.get('matchup_id')} — {game.get('matchup')}", ""])
        lines.append(f"- Final: {game.get('scoreline')}; margin {float(game.get('margin') or 0):.2f}.")
        for stat in game.get("starter_stat_lines") or []:
            lines.append(
                f"- {stat.get('fantasy_team')}: {stat.get('player')} — {stat.get('nfl_stat_line')}"
            )
        for note in game.get("context_signals") or []:
            lines.append(f"- Context: {note}")

    usage = packet.get("usage_desk") or {}
    lines.extend(["", "## USAGE DESK INPUT", ""])
    lines.append(f"Status: {usage.get('status', 'UNKNOWN')}")
    enrichment = usage.get("enrichment_status") or {}
    lines.append(
        "- Source coverage: "
        + ", ".join(
            f"{key.replace('_', ' ')}={value}"
            for key, value in enrichment.items()
        )
    )
    leaders = usage.get("leaders") or {}
    for label, rows in leaders.items():
        lines.extend(["", f"### {label.replace('_', ' ').title()}"])
        for row in rows:
            parts = [
                f"{row.get('player')} — {row.get('fantasy_team') or 'unmapped'}",
            ]
            if row.get("carries") is not None:
                parts.append(f"{int(float(row.get('carries') or 0))} carries")
            if row.get("carry_share") is not None:
                parts.append(f"{float(row.get('carry_share')):.1%} team carries")
            if row.get("targets") is not None:
                parts.append(f"{int(float(row.get('targets') or 0))} targets")
            if row.get("target_share") is not None:
                parts.append(f"{float(row.get('target_share')):.1%} team targets")
            if row.get("snap_share") is not None:
                parts.append(f"{float(row.get('snap_share')):.1%} snaps")
            if row.get("red_zone_opportunities") is not None:
                parts.append(f"{int(float(row.get('red_zone_opportunities') or 0))} red-zone opps")
            lines.append("- " + "; ".join(parts))
    if usage.get("story_signals"):
        lines.extend(["", "### Usage Story Signals"])
        for row in usage.get("story_signals") or []:
            lines.append(
                f"- {row.get('signal_type') or row.get('type') or 'signal'}: "
                f"{row.get('explanation') or row.get('statement') or _compact(row)}"
            )

    lines.extend(["", "## INJURY & ROSTER HEALTH", ""])
    health = packet.get("injury_roster_health") or {}
    lines.append(f"Status: {health.get('status', 'unknown')}")
    for row in health.get("players") or []:
        details = [
            str(value)
            for value in (
                row.get("injury_status"),
                row.get("report_primary_injury"),
                row.get("practice_participation"),
                "IR/RESERVE" if row.get("on_ir") else None,
            )
            if value
        ]
        lines.append(f"- {row.get('team')}: {row.get('player')} — {', '.join(details) or 'flagged'}")

    honors = packet.get("weekly_honors") or {}
    lines.extend(["", "## WEEKLY HONORS & ROOKIE WATCH", "", "### Started Position Leaders"])
    for position in CORE_POSITIONS:
        row = (honors.get("started_position_leaders") or {}).get(position)
        if row:
            line = f"- {position}: {row.get('player')} — {row.get('team')} — {float(row.get('points') or 0):.2f} FP"
            if row.get("nfl_stat_line"):
                line += f" — {row.get('nfl_stat_line')}"
            lines.append(line)

    manager = honors.get("manager_of_the_week")
    lines.extend(["", "### Manager of the Week"])
    lines.append(
        f"- {manager.get('team')} — {float(manager.get('actual_points') or 0):.2f} points; {float(manager.get('efficiency') or 0):.1%} efficiency"
        if manager else "- No eligible manager."
    )

    lines.extend(
        [
            "",
            "### Season Efficiency Top 3",
            "",
            "| Rank | Team | Cumulative Efficiency | Weeks |",
            "|---:|---|---:|---:|",
        ]
    )
    for rank, row in enumerate(honors.get("season_efficiency_top_three") or [], 1):
        lines.append(
            f"| {rank} | {row.get('team')} | {float(row.get('efficiency') or 0):.1%} | {row.get('weeks')} |"
        )

    lines.extend(
        [
            "",
            "### Season Team Score Top 3",
            "",
            "| Rank | Team | Score | Week |",
            "|---:|---|---:|---:|",
        ]
    )
    for rank, row in enumerate(honors.get("season_team_score_top_three") or [], 1):
        lines.append(
            f"| {rank} | {row.get('team')} | {float(row.get('score') or 0):.2f} | {row.get('week')} |"
        )

    lines.extend(["", "### Benchwarmer of the Week"])
    bench = honors.get("benchwarmer_of_the_week")
    if bench:
        line = f"- {bench.get('player')} — {bench.get('team')} — {float(bench.get('points') or 0):.2f} FP"
        if bench.get("nfl_stat_line"):
            line += f" — {bench.get('nfl_stat_line')}"
        lines.append(line)
    else:
        lines.append("- No eligible benchwarmer.")

    lines.extend(
        [
            "",
            "### Rookie Watch — Top 5",
            "",
            "| Rank | Rookie | Week Line / FP | Current Team | Ironbound Draft |",
            "|---:|---|---|---|---|",
        ]
    )
    for rank, row in enumerate(honors.get("rookie_watch_top_five") or [], 1):
        draft = str(row.get("ironbound_draft") or "Not recorded")
        line = row.get("nfl_stat_line") or "NFL stat line unavailable"
        lines.append(
            f"| {rank} | {row.get('player')} | {line}; {float(row.get('points') or 0):.2f} FP | {row.get('team')} | {draft} |"
        )

    lines.extend(["", "### Rotating Award Candidates"])
    for row in honors.get("rotating_award_candidates") or []:
        lines.append(f"- {row.get('candidate_type')}: {row.get('team') or row.get('player') or row.get('started_player')} — {row.get('reason')}")

    lines.extend(["", "## POWER BOARD — INDIVIDUAL WRITEUP INPUTS", ""])
    for row in (packet.get("power_board") or {}).get("writeup_inputs") or []:
        lines.append(
            f"- {row.get('team')}: {row.get('wins', 0)}-{row.get('losses', 0)}; "
            f"{float(row.get('points_for') or 0):.2f} PF; official rank {row.get('official_rank', 'awaiting')}; "
            f"efficiency {float(row.get('efficiency') or 0):.1%}."
        )

    lines.extend(["", "## POWER RANKINGS CHART INPUT", ""])
    power = packet.get("power_rankings_chart") or {}
    lines.append(f"Status: {power.get('status')}")
    lines.append(
        "Authority: Ironbound_power_ranks. Movement below is imported from the "
        "ranking engine's shared Saturday/Tuesday publication history and must not be recalculated."
    )
    for row in sorted(power.get("rows") or [], key=lambda item: int(item.get("rank") or 999)):
        label = row.get("team") or row.get("franchise_key") or f"Roster {row.get('roster_id')}"
        previous = row.get("previous_rank")
        movement = row.get("movement")
        if previous is None or movement is None:
            movement_text = "movement unavailable"
        elif int(movement) > 0:
            movement_text = f"up {int(movement)} from #{int(previous)}"
        elif int(movement) < 0:
            movement_text = f"down {abs(int(movement))} from #{int(previous)}"
        else:
            movement_text = f"unchanged from #{int(previous)}"
        lines.append(
            f"- #{row.get('rank')} {label} — {movement_text}; "
            f"ranking score {float(row.get('score') or 0):.1f}"
        )

    lines.extend(["", "## RANKING PUBLICATION ASSETS", ""])
    assets = packet.get("ranking_publication_assets") or {}
    lines.append(str(assets.get("policy") or ""))
    for asset_key, label in (
        ("power_rankings", "Power Rankings"),
        ("playoff_forecast", "Playoff Forecast"),
    ):
        asset = (assets.get("assets") or {}).get(asset_key) or {}
        if asset.get("status") == "READY":
            lines.append(
                f"- {label}: {asset.get('package_path')} — "
                f"SHA-256 {asset.get('sha256') or asset.get('actual_sha256') or 'not supplied'} — "
                "PLACE THIS SUPPLIED GRAPHIC UNCHANGED."
            )
        else:
            lines.append(f"- {label}: {asset.get('status') or 'MISSING'}")

    lines.extend(["", "## PLAYOFF ODDS CHART INPUT", ""])
    odds = packet.get("playoff_odds_chart") or {}
    lines.append(f"Status: {odds.get('status')}")
    for row in odds.get("rows") or []:
        lines.append("- " + _compact(row))

    lines.extend(["", "## OPTIONAL SUPPLEMENTAL ANALYTICS", ""])
    ext = packet.get("tuesday_external_inputs") or {}
    lines.append(
        "Weekly usage is already supplied by the internal nflverse Usage Desk above. "
        "WAR and cWAR are optional feature-story enrichment and do not affect research completeness."
    )
    for key, label in (("war", "WAR"), ("cwar", "cWAR")):
        section = ext.get(key) or {}
        lines.extend(["", f"### {label} — {section.get('status')}"])
        for row in section.get("rows") or []:
            lines.append("- " + _compact(row))

    lines.extend(["", "## STORY DESK / COVER ANGLES", ""])
    for row in (packet.get("story_desk") or {}).get("candidates") or []:
        subjects = " / ".join(row.get("display_subjects") or [])
        lines.append(
            f"- {str(row.get('candidate_type') or 'story').replace('_', ' ').title()}"
            + (f" — {subjects}" if subjects else "")
        )
        for fact in (row.get("display_facts") or row.get("facts") or [])[:3]:
            if fact.get("statement"):
                lines.append(f"  - {fact['statement']}")

    lines.extend(
        [
            "",
            "## HANDOFF RULE",
            "",
            "This packet is factual research. The production manuscript may select angles and write prose, but it must not invent missing facts. A missing deterministic source must remain MANUAL_VERIFY; a missing Tuesday handoff must remain AWAITING_TUESDAY_INPUT.",
            "",
        ]
    )
    return "\n".join(lines)


def write_flagship_research_packet(directory: Path, packet: dict[str, Any]) -> tuple[Path, Path]:
    directory = Path(directory)
    json_path = directory / "flagship_research_packet.json"
    markdown_path = directory / "flagship_research_packet.md"
    json_path.write_text(json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown_path.write_text(render_flagship_research_packet(packet), encoding="utf-8")
    return json_path, markdown_path


def _game_research(snapshot: dict[str, Any], dossier: dict[str, Any]) -> list[dict[str, Any]]:
    scoreboard = dossier.get("scoreboard") or []
    stat_rows = (((dossier.get("nfl_game_intelligence") or {}).get("stat_book") or {}).get("records") or [])
    signals = (dossier.get("nfl_game_intelligence") or {}).get("story_signals") or []
    team_stat_rows: dict[str, list[dict[str, Any]]] = {}
    for row in stat_rows:
        team_stat_rows.setdefault(str(row.get("fantasy_team") or ""), []).append(row)

    games: list[dict[str, Any]] = []
    for game in scoreboard:
        teams = game.get("teams") or []
        team_names = [str(row.get("team") or "") for row in teams]
        starter_stats = [
            dict(row)
            for team in team_names
            for row in team_stat_rows.get(team, [])
        ]
        signal_lines = [
            str(signal.get("explanation"))
            for signal in signals
            if signal.get("explanation") and _signal_belongs_to_game(signal, starter_stats)
        ]
        ordered = sorted(teams, key=lambda row: float(row.get("points") or 0), reverse=True)
        matchup = " vs. ".join(row.get("team") or "Unknown" for row in teams)
        scoreline = " — ".join(
            f"{row.get('team')} {float(row.get('points') or 0):.2f}"
            for row in ordered
        )
        top_starter = _top_started_player_for_game(snapshot, team_names)
        games.append(
            {
                "matchup_id": game.get("matchup_id"),
                "matchup": matchup,
                "scoreline": scoreline,
                "teams": teams,
                "winner": game.get("winner"),
                "loser": game.get("loser"),
                "margin": game.get("margin"),
                "starter_stat_lines": starter_stats,
                "context_signals": signal_lines,
                "top_started_player": top_starter,
            }
        )
    return games


def _cover_candidates(games: list[dict[str, Any]], dossier: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    monday = (dossier.get("game_timing") or {}).get("monday") or {}
    changed = {
        (str(row.get("final_winner") or ""), str(row.get("final_loser") or ""))
        for row in monday.get("lead_changes") or []
    }
    for game in games:
        margin = float(game.get("margin") or 0)
        winner = game.get("winner") or {}
        loser = game.get("loser") or {}
        winner_points = float(winner.get("points") or 0)
        top = game.get("top_started_player") or {}
        reasons: list[str] = []
        score = 0.0
        if margin <= 10:
            score += 8
            reasons.append(f"close finish ({margin:.2f}-point margin)")
        elif margin <= 20:
            score += 4
            reasons.append(f"competitive finish ({margin:.2f}-point margin)")
        if winner_points >= 140:
            score += 7
            reasons.append(f"high team score ({winner_points:.2f})")
        elif winner_points >= 125:
            score += 3
            reasons.append(f"strong team score ({winner_points:.2f})")
        top_points = float(top.get("points") or 0)
        if top_points >= 35:
            score += min(top_points / 5, 10)
            reasons.append(f"singular started-player performance ({top.get('player')} {top_points:.2f})")
        if (str(winner.get("team") or ""), str(loser.get("team") or "")) in changed:
            score += 10
            reasons.append("Monday result-changing comeback")
        if game.get("context_signals"):
            score += min(len(game["context_signals"]) * 2, 6)
            reasons.append("usage/game-intelligence signal")
        candidates.append(
            {
                "matchup_id": game.get("matchup_id"),
                "matchup": game.get("matchup"),
                "signal_score": round(score, 2),
                "reasons": reasons or ["completed matchup available for editorial review"],
            }
        )
    return sorted(candidates, key=lambda row: (-float(row["signal_score"]), str(row["matchup_id"])))[:5]


def _top_started_player_for_game(snapshot: dict[str, Any], team_names: list[str]) -> dict[str, Any] | None:
    users = {str(row.get("user_id")): row for row in snapshot.get("users") or []}
    roster_team: dict[int, str] = {}
    for roster in snapshot.get("rosters") or []:
        owner = users.get(str(roster.get("owner_id"))) or {}
        meta = owner.get("metadata") or {}
        roster_team[int(roster.get("roster_id") or 0)] = str(
            meta.get("team_name") or owner.get("display_name") or f"Roster {roster.get('roster_id')}"
        )
    players = snapshot.get("players") or {}
    candidates: list[dict[str, Any]] = []
    for matchup in snapshot.get("matchups") or []:
        roster_id = int(matchup.get("roster_id") or 0)
        if roster_team.get(roster_id) not in team_names:
            continue
        points = matchup.get("players_points") or matchup.get("players_points_custom") or {}
        for player_id in matchup.get("starters") or []:
            player = players.get(str(player_id)) or {}
            candidates.append(
                {
                    "player_id": str(player_id),
                    "player": player.get("full_name") or str(player_id),
                    "team": roster_team.get(roster_id),
                    "points": float(points.get(str(player_id), points.get(player_id, 0)) or 0),
                }
            )
    return max(candidates, key=lambda row: (row["points"], row["player"]), default=None)


def _signal_belongs_to_game(signal: dict[str, Any], starter_stats: list[dict[str, Any]]) -> bool:
    player_ids = {str(row.get("nfl_player_id") or row.get("player_id") or "") for row in starter_stats}
    return str(signal.get("player_id") or "") in player_ids


def _season_dossiers(root: Path, season: str, league_key: str, through_week: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(Path(root).glob(f"{season}/week-*/{league_key}/dossier.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        week = int(value.get("week") or 0)
        if 0 < week <= through_week:
            rows.append(value)
    return rows


def _season_team_score_top_three(
    history: list[dict[str, Any]],
    *,
    snapshot: dict[str, Any],
    league_key: str,
    season: str,
    chronicle: ChronicleQueries | None,
) -> list[dict[str, Any]]:
    names = _roster_team_names(snapshot)
    by_week_roster: dict[tuple[int, int], dict[str, Any]] = {}

    if chronicle is not None:
        for row in chronicle.season_matchup_finals(league_key, season):
            roster_id = int(row.get("roster_id") or 0)
            week = int(row.get("week") or 0)
            if roster_id and week:
                by_week_roster[(week, roster_id)] = {
                    "team": names.get(roster_id, f"Roster {roster_id}"),
                    "roster_id": roster_id,
                    "score": float(row.get("points") or 0),
                    "week": week,
                }

    # Historical dossier artifacts are a compatibility fallback for weeks that
    # predate durable MATCHUP_FINAL events.
    for dossier in history:
        week = int(dossier.get("week") or 0)
        for game in dossier.get("scoreboard") or []:
            for team in game.get("teams") or []:
                roster_id = int(team.get("roster_id") or 0)
                if roster_id and week:
                    by_week_roster.setdefault(
                        (week, roster_id),
                        {
                            "team": team.get("team") or names.get(roster_id),
                            "roster_id": roster_id,
                            "score": float(team.get("points") or 0),
                            "week": week,
                        },
                    )

    # Always merge the reviewed week from the live dossier so a correctly
    # completed packet does not depend on materialized Chronicle freshness.
    current_week = int(snapshot.get("week") or 0)
    teams_by_name = {value: key for key, value in names.items()}
    for matchup in snapshot.get("matchups") or []:
        roster_id = int(matchup.get("roster_id") or 0)
        if roster_id and current_week:
            by_week_roster[(current_week, roster_id)] = {
                "team": names.get(roster_id, f"Roster {roster_id}"),
                "roster_id": roster_id,
                "score": float(matchup.get("points") or 0),
                "week": current_week,
            }

    rows = list(by_week_roster.values())
    rows.sort(
        key=lambda row: (
            -row["score"],
            row["week"],
            str(row.get("team") or "").casefold(),
        )
    )
    return rows[:3]


def _season_efficiency_top_three(
    history: list[dict[str, Any]],
    *,
    snapshot: dict[str, Any],
    league_key: str,
    season: str,
    chronicle: ChronicleQueries | None,
) -> list[dict[str, Any]]:
    by_team: dict[str, dict[str, float]] = {}
    max_week = 0
    if chronicle is not None:
        names = _roster_team_names(snapshot)
        for row in chronicle.season_efficiency(league_key, season):
            max_week = max(max_week, int(row.get("week") or 0))
            team = names.get(int(row.get("roster_id") or 0))
            if not team:
                continue
            aggregate = by_team.setdefault(
                team, {"actual": 0.0, "optimal": 0.0, "weeks": 0.0}
            )
            aggregate["actual"] += float(row.get("actual_points") or 0)
            aggregate["optimal"] += float(row.get("optimal_points") or 0)
            aggregate["weeks"] += 1
    if not by_team:
        for dossier in history:
            max_week = max(max_week, int(dossier.get("week") or 0))
            for row in dossier.get("lineup_efficiency") or []:
                team = str(row.get("team") or "")
                if not team:
                    continue
                aggregate = by_team.setdefault(
                    team, {"actual": 0.0, "optimal": 0.0, "weeks": 0.0}
                )
                aggregate["actual"] += float(row.get("actual_points") or 0)
                aggregate["optimal"] += float(row.get("optimal_points") or 0)
                aggregate["weeks"] += 1
    rows = [
        {
            "team": team,
            "efficiency": round(
                values["actual"] / values["optimal"], 4
            ) if values["optimal"] else 0.0,
            "actual_points": round(values["actual"], 2),
            "optimal_points": round(values["optimal"], 2),
            "weeks": int(values["weeks"]),
            "through_week": max_week,
        }
        for team, values in by_team.items()
        if values["weeks"]
    ]
    rows.sort(key=lambda row: (-row["efficiency"], -row["weeks"], row["team"].casefold()))
    return rows[:3]


def _rotating_award_candidates(dossier: dict[str, Any]) -> list[dict[str, Any]]:
    awards = dossier.get("awards") or {}
    rows: list[dict[str, Any]] = []
    for row in awards.get("waiver_star_candidates") or []:
        rows.append(
            {
                "candidate_type": "WAIVER_OR_TRADE_PICKUP_CHANGED_GAME",
                "team": row.get("team"),
                "player": row.get("player"),
                "reason": "Transaction addition contributed to a completed matchup result.",
                "evidence": row,
            }
        )
    for row in awards.get("result_flipping_decisions") or []:
        rows.append(
            {
                "candidate_type": "RESULT_CHANGING_START_SIT",
                "team": row.get("team"),
                "player": row.get("bench_player"),
                "reason": (
                    f"{row.get('bench_player')} over {row.get('started_player')} "
                    f"would have swung the result by {float(row.get('point_swing') or 0):.2f}."
                ),
                "evidence": row,
            }
        )
    records = dossier.get("weekly_records") or {}
    high = records.get("highest_score") if isinstance(records, dict) else None
    if high:
        rows.append(
            {
                "candidate_type": "WEEKLY_HIGH_SCORE_RECORD_CANDIDATE",
                "team": high.get("team"),
                "reason": f"Weekly high score: {float(high.get('points') or 0):.2f}.",
                "evidence": high,
            }
        )
    return rows


def _power_board_inputs(
    dossier: dict[str, Any],
    external: ExternalEditorialInputs,
    *,
    snapshot: dict[str, Any],
    league_key: str,
    season: str,
    chronicle: ChronicleQueries | None,
) -> list[dict[str, Any]]:
    standings = (
        (dossier.get("rankings") or {}).get("official_standings")
        or dossier.get("standings")
        or []
    )
    efficiency = {
        int(row.get("roster_id") or 0): row
        for row in dossier.get("lineup_efficiency") or []
    }
    rows = []
    for row in standings:
        rid = int(row.get("roster_id") or 0)
        team = str(row.get("team") or "")
        eff = efficiency.get(rid) or {}
        franchise_key = (
            chronicle.identity_for_roster(league_key, season, rid)
            if chronicle is not None
            else None
        )
        ranking = external.ranking_for_roster(
            rid,
            franchise_key=franchise_key,
            team=team,
        )
        rows.append(
            {
                **row,
                "franchise_key": franchise_key,
                "efficiency": eff.get("efficiency"),
                "points_left_on_bench": eff.get("points_left_on_bench"),
                "official_rank": ranking.rank if ranking else None,
                "previous_rank": ranking.previous_rank if ranking else None,
                "rank_movement": ranking.movement if ranking else None,
                "ranking_score": ranking.score if ranking else None,
                "playoff_odds": _row_for_team(
                    external.playoff_odds, rid, franchise_key, team
                ),
                "usage": _row_for_team(external.usage, rid, franchise_key, team),
                "war": _row_for_team(external.war, rid, franchise_key, team),
                "cwar": _row_for_team(external.cwar, rid, franchise_key, team),
            }
        )
    rows.sort(
        key=lambda row: (
            int(row.get("official_rank") or 999),
            str(row.get("team") or "").casefold(),
        )
    )
    return rows


def _row_for_team(
    rows: Any,
    roster_id: int,
    franchise_key: str | None,
    team: str,
) -> dict[str, Any] | None:
    wanted_team = str(team or "").strip().casefold()
    for row in rows or []:
        if row.get("roster_id") is not None:
            try:
                if int(row.get("roster_id")) == int(roster_id):
                    return dict(row)
            except (TypeError, ValueError):
                pass
    if franchise_key:
        for row in rows or []:
            if str(row.get("franchise_key") or "") == str(franchise_key):
                return dict(row)
    if wanted_team:
        for row in rows or []:
            if str(row.get("team") or "").strip().casefold() == wanted_team:
                return dict(row)
    return None


def _attach_stat_lines(value: Any, intelligence: dict[str, Any]) -> Any:
    stat_book = intelligence.get("stat_book") or {}
    source_rows = (
        stat_book.get("rostered_records")
        or stat_book.get("records")
        or []
    )
    by_sleeper = {
        str(row.get("sleeper_player_id")): row
        for row in source_rows
        if row.get("sleeper_player_id")
    }

    def enrich(row: dict[str, Any]) -> dict[str, Any]:
        stat = by_sleeper.get(str(row.get("player_id") or "")) or {}
        return {
            **row,
            "nfl_stat_line": stat.get("nfl_stat_line"),
            "snap_share": stat.get("snap_share"),
            "target_share": stat.get("target_share"),
            "carry_share": stat.get("carry_share"),
        }

    if value is None:
        return None
    if isinstance(value, list):
        return [enrich(dict(row)) for row in value]
    if isinstance(value, dict):
        if "player_id" in value:
            return enrich(dict(value))
        return {
            key: enrich(dict(row)) if isinstance(row, dict) else row
            for key, row in value.items()
        }
    return value


def _attach_rookie_draft_context(
    rows: list[dict[str, Any]],
    snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    draft_source = (
        ((snapshot.get("flagship_sleeper") or {}).get("drafts") or {})
        or (snapshot.get("draft_context") or {})
    )
    current_names = _roster_team_names(snapshot)
    team_count = max(1, len(current_names))
    by_player: dict[str, dict[str, Any]] = {}

    for record in draft_source.get("records") or []:
        draft = record.get("draft") or {}
        draft_season = str(draft.get("season") or "")
        league_season = str((snapshot.get("league") or {}).get("season") or "")
        if league_season and draft_season and draft_season != league_season:
            continue
        for pick in record.get("picks") or []:
            player_id = str(pick.get("player_id") or "")
            if not player_id:
                continue
            round_no = _safe_int(pick.get("round"))
            slot = _safe_int(pick.get("draft_slot"))
            pick_no = _safe_int(pick.get("pick_no"))
            if slot is None and round_no and pick_no:
                slot = pick_no - (round_no - 1) * team_count
            if round_no is None or slot is None or slot <= 0:
                continue
            by_player[player_id] = {
                "round": round_no,
                "slot": slot,
                "roster_id": _safe_int(pick.get("roster_id")),
            }

    enriched = []
    for row in rows:
        item = dict(row)
        pick = by_player.get(str(item.get("player_id") or ""))
        if pick:
            label = f"{pick['round']}.{pick['slot']:02d}"
            drafting_roster = pick.get("roster_id")
            drafting_team = current_names.get(int(drafting_roster or 0))
            current_team = str(item.get("team") or "")
            if drafting_team and drafting_team != current_team:
                label += f" — drafted by {drafting_team}"
            item["ironbound_draft"] = label
            item["ironbound_draft_round"] = pick["round"]
            item["ironbound_draft_slot"] = pick["slot"]
            item["ironbound_drafted_by"] = drafting_team
        else:
            item["ironbound_draft"] = None
        enriched.append(item)
    return enriched


def _safe_int(value: Any) -> int | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _usage_desk(intelligence: dict[str, Any]) -> dict[str, Any]:
    """Create a weekly magazine usage desk from internally collected NFL data."""
    source_status = intelligence.get("source_status") or {}
    stat_book = intelligence.get("stat_book") or {}
    rows = list(stat_book.get("rostered_records") or stat_book.get("records") or [])
    player_stats_ready = (
        str(source_status.get("player_stats") or "").casefold() == "available"
        and str(stat_book.get("status") or "").casefold() == "available"
        and bool(rows)
    )

    active = [
        dict(row)
        for row in rows
        if any(
            float(row.get(key) or 0) > 0
            for key in (
                "carries",
                "targets",
                "offense_snaps",
                "red_zone_opportunities",
                "inside_10_opportunities",
                "inside_5_opportunities",
            )
        )
    ]

    def top(field: str, limit: int = 8) -> list[dict[str, Any]]:
        candidates = [row for row in active if row.get(field) is not None]
        candidates.sort(
            key=lambda row: (
                -float(row.get(field) or 0),
                str(row.get("player") or "").casefold(),
            )
        )
        return candidates[:limit]

    return {
        "status": "READY" if player_stats_ready else "MANUAL_VERIFY",
        "required_source": "nflverse weekly player stats",
        "enrichment_status": {
            "player_stats": source_status.get("player_stats") or "unavailable",
            "snap_counts": source_status.get("snap_counts") or "unavailable",
            "play_by_play": source_status.get("play_by_play") or "unavailable",
        },
        "rostered_player_rows": rows,
        "leaders": {
            "targets": top("targets"),
            "carries": top("carries"),
            "snap_share": top("snap_share"),
            "red_zone_opportunities": top("red_zone_opportunities"),
        },
        "story_signals": list(intelligence.get("story_signals") or []),
    }


def _roster_team_names(snapshot: dict[str, Any]) -> dict[int, str]:
    users = {
        str(row.get("user_id")): row for row in snapshot.get("users") or []
    }
    names: dict[int, str] = {}
    for roster in snapshot.get("rosters") or []:
        roster_id = int(roster.get("roster_id") or 0)
        owner = users.get(str(roster.get("owner_id"))) or {}
        metadata = owner.get("metadata") or {}
        names[roster_id] = str(
            metadata.get("team_name")
            or owner.get("display_name")
            or f"Roster {roster_id}"
        )
    return names


def _optional_external_status(supplied: bool) -> str:
    return "READY" if supplied else "OPTIONAL_NOT_SUPPLIED"


def _external_status(supplied: bool) -> str:
    return "READY" if supplied else "AWAITING_TUESDAY_INPUT"


def _duplicates(values: Any) -> list[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for value in values:
        if value in seen:
            dupes.add(value)
        seen.add(value)
    return sorted(dupes)


def _check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def _compact(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(", ", ": "))
