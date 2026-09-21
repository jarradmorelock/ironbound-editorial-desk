"""Human reading packets, with full evidence retained in adjacent artifacts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .publication_policy import publication_view


def _number(value: Any) -> float:
    return float(value or 0)


def fact_lines(value: Any, limit: int = 8) -> list[str]:
    """Select supported narrative facts, never serialize arbitrary evidence fields."""
    result: list[str] = []

    def visit(row: Any) -> None:
        if len(result) >= limit:
            return
        if isinstance(row, list):
            for item in row:
                visit(item)
        elif isinstance(row, dict):
            teams = row.get('teams') or []
            if row.get('division_name') and 'average_points' in row:
                record = row.get('head_to_head_record') or {}
                result.append(f"{row['division_name']}: {_number(row['average_points']):.2f} average points; {record.get('wins', 0)}–{record.get('losses', 0)}–{record.get('ties', 0)} head-to-head record.")
            elif row.get('started_player') and row.get('bench_player'):
                outcome = 'would have changed the result' if row.get('would_flip_result') else 'protected the win' if row.get('protected_win') else 'is a legal lineup alternative'
                result.append(f"{row.get('team')}: {row['started_player']} scored {_number(row.get('started_points')):.2f}, while {row['bench_player']} scored {_number(row.get('bench_points')):.2f} on the bench; the {_number(row.get('point_swing', abs(_number(row.get('bench_points')) - _number(row.get('started_points'))))):.2f}-point difference {outcome}.")
            elif row.get('window') and row.get('team'):
                result.append(f"{row['window']}: {row['team']} vs. {row.get('opponent', 'opponent')}, {_number(row.get('pre_window_score')):.2f}–{_number(row.get('opponent_pre_window_score')):.2f} before the window and {_number(row.get('final_score')):.2f}–{_number(row.get('opponent_final_score')):.2f} at the finish ({row.get('provenance', 'timing source unverified')}).")
            elif len(teams) == 2 and all(isinstance(t, dict) and t.get('team') for t in teams):
                first, second = sorted(teams, key=lambda t: _number(t.get('points')), reverse=True)
                verb = 'tied' if first.get('points') == second.get('points') else 'finished ahead of'
                result.append(f"{first['team']} {verb} {second['team']}, {_number(first.get('points')):.2f}–{_number(second.get('points')):.2f}.")
            elif row.get('statement'):
                result.append(str(row['statement']))
            elif row.get('team') and 'wins' in row:
                result.append(f"{row['team']}: {row.get('wins', 0)}–{row.get('losses', 0)}–{row.get('ties', 0)}, {_number(row.get('points_for')):.2f} points for.")
            elif row.get('team') and 'efficiency' in row:
                result.append(f"{row['team']} used {_number(row['efficiency']):.1%} of its best legal lineup score, leaving {_number(row.get('points_left_on_bench')):.2f} points on the bench.")
            elif row.get('player') or row.get('team'):
                subject = str(row.get('player') or row.get('team'))
                if row.get('division_name'):
                    subject = f"{row['division_name']} — {subject}"
                if row.get('player') and row.get('team'):
                    subject += f" ({row['team']})"
                points = row.get('points', row.get('fantasy_points', row.get('actual_points')))
                if points is not None:
                    result.append(f"{subject}: {_number(points):.2f} points.")
                else:
                    detail = ', '.join(str(row[k]) for k in ('position', 'status', 'injury_status', 'practice_participation', 'nfl_stat_line') if row.get(k))
                    if row.get('on_ir'):
                        detail = ', '.join(filter(None, (detail, 'IR/RESERVE')))
                    if detail:
                        result.append(f"{subject}: {detail}.")
            elif row.get('matchup') and row.get('score'):
                result.append(f"{row['matchup']}: {row['score']}.")
            else:
                for child in row.values():
                    if isinstance(child, (dict, list)):
                        visit(child)

    visit(value)
    return list(dict.fromkeys(result))[:limit]


def render_reading_packet(
    dossier: dict[str, Any], *, packet: dict[str, Any] | None = None,
    story: dict[str, Any] | None = None,
) -> str:
    context = packet or dossier
    dossier = publication_view(dossier, context)
    packet = publication_view(packet or {}, context)
    story = publication_view(story or {}, context)
    league = dossier.get('league') or {}
    title = packet.get('publication') or league.get('publication') or 'Publication'
    week = dossier.get('week', packet.get('week', 'N/A'))
    departments = packet.get('departments') or []
    lines = [f'# {title} — Week {week}', '', "## EDITOR'S BRIEF", '',
             'This is the weekly editorial reading packet. The findings below are research for publication, not final copy.', '']
    if dossier.get('information_current_through'):
        lines.extend([f"Information current through: {dossier['information_current_through']}", ''])
    if packet.get('phase'):
        lines.extend([f"Edition: {packet['phase']}.", ''])
    scoreboard = dossier.get('scoreboard') or next((d.get('data') for d in departments if d.get('feature') in {'weekly_results', 'final_scorecard'}), [])
    games = fact_lines(scoreboard, 16)
    lines.extend(['### What happened', ''])
    lines.extend(f'- {line}' for line in games)
    if not games:
        lines.append('No verified matchup summary is available in this packet. Treat missing results as unverified, not as zero scores.')
    # Bound the brief for a roughly 1–3 page reading target, without padding sparse weeks.
    lines.extend(['', '### What matters', ''])
    highlights = []
    standings = (dossier.get('rankings') or {}).get('official_standings') or next((d.get('data') for d in departments if d.get('feature') in {'official_table', 'standings'}), [])
    highlights.extend(fact_lines(standings, 3))
    highlights.extend(fact_lines(dossier.get('lineup_efficiency'), 3))
    for label, key in [('Manager of the Week', 'manager_of_the_week'), ('Top player', 'mvp_card_result'), ('Bad beat', 'bad_beat')]:
        highlights.extend(f'{label}: {line}' for line in fact_lines((dossier.get('awards') or {}).get(key), 1))
    monday = (dossier.get('game_timing') or {}).get('monday') or {}
    for finish in (monday.get('lead_changes') or [])[:3]:
        highlights.append(f"Monday changed the result: {finish.get('final_winner')} came back to beat {finish.get('final_loser')} by {_number(finish.get('final_margin')):.2f} points.")
    health = dossier.get('roster_health') or {}
    if health.get('status') == 'available':
        highlights.extend(f'Availability watch: {line}' for line in fact_lines(health.get('players'), 3))
    for department in departments:
        if department.get('feature') not in {'weekly_results', 'final_scorecard', 'official_table', 'standings'}:
            highlights.extend(f"{department.get('display_name')}: {line}" for line in fact_lines(department.get('data'), 1))
    lines.extend(f'- {line}' for line in list(dict.fromkeys(highlights))[:12])
    if not highlights:
        lines.append('No additional verified weekly highlights are available. The evidence artifacts retain the collected material for review.')
    gaps = [d for d in departments if d.get('status') == 'unavailable' or d.get('degraded')]
    if gaps:
        names = ', '.join(str(d.get('display_name') or d.get('feature')) for d in gaps[:8])
        lines.extend(['', f'Coverage is incomplete for {names}. These gaps limit the conclusions available this week; they are not automatically requests for commissioner input.'])
    # Cap unusually verbose upstream labels/facts as well as item counts.
    brief = '\n'.join(lines)
    if len(brief.split()) > 1200:
        brief = ' '.join(brief.split()[:1150]) + '\n\nFurther detail is retained in the evidence artifacts.'

    lines = [brief]
    flagship = str(league.get('tier') or '').casefold() == 'flagship'
    lines.extend(_render_health_section(health, flagship=flagship))
    if flagship:
        lines.extend(_render_flagship_stat_book(dossier.get('nfl_game_intelligence') or {}))
    lines.extend(['', '## COMMISSIONER REQUESTS', ''])
    readiness = story.get('publication_readiness')
    if readiness:
        lines.extend(['### Publication Readiness', '', 'Final publication ready: ' + ('**YES**' if readiness.get('ready_for_final_publication') else '**NO**')])
        for key, label in [('required_before_publication', 'Required Before Publication'), ('optional_enrichment', 'Optional Enrichment'), ('commissioner_judgment', 'Commissioner / Editorial Judgment'), ('visuals_to_source_or_approve', 'Visuals to Source or Approve'), ('no_action_needed', 'No Action Needed')]:
            lines.extend(['', f'### {label}'])
            rows = readiness.get(key) or []
            lines.extend(f"- {r['request']}" + (f" Why: {r['reason']}" if r.get('reason') else '') for r in rows if r.get('request'))
            if not rows:
                lines.append('- None.')
    elif league.get('tier') == 'flagship':
        lines.append('Publication Readiness was not generated. Final publication readiness has not been assessed; rerun with Story Desk and Chronicle available.')
    else:
        requests = [r for r in packet.get('commissioner_requests') or [] if not r.get('resolved') and r.get('request')]
        lines.extend(f"- {r['request']}" for r in requests)
        if not requests:
            lines.append('No unresolved human inputs are identified for this newspaper.')
    candidates = story.get('candidates') or []
    if story:
        lines.extend(['', '## STORY DESK', ''])
        if not candidates:
            lines.append('No evidence-backed story candidate cleared the desk this week.')
        for candidate in candidates:
            subjects = candidate.get('display_subjects') or []
            label = str(candidate.get('candidate_type') or 'Story').replace('_', ' ').title()
            lines.extend(['', f"### {label} — {' / '.join(subjects) if subjects else 'Names awaiting verification'}", ''])
            if not subjects:
                lines.append('Resolve the subjects from the source evidence before using this candidate in publication.')
            lines.extend(f'- {s}' for s in fact_lines(candidate.get('display_facts', candidate.get('facts')), 6))
            if any(row.get('coverage_complete') is False for row in (candidate.get('facts') or []) + (candidate.get('historical_context') or [])):
                lines.append('- Caution: Historical coverage is incomplete; recorded meetings are not a complete all-time history.')
            lines.extend(f'- Historical context: {s}' for s in fact_lines(candidate.get('historical_context'), 3))
            for label, key in [('Angle', 'editorial_angles'), ('Caution', 'cautions'), ('Suggested graphic', 'graphic_ideas')]:
                lines.extend(f'- {label}: {s}' for s in (candidate.get(key) or [])[:3])
            lines.append(f"- Evidence strength: {candidate.get('evidence_strength', 'unassessed')}.")
    for department in departments:
        lines.extend(['', f"## {department.get('display_name') or department.get('feature') or 'Department'}", '', f"Status: {department.get('status') or 'unknown'}"])
        if department.get('reason'):
            lines.append(str(department['reason']))
        lines.extend(f'- {line}' for line in fact_lines(department.get('data')))
        if department.get('data') and not fact_lines(department['data']):
            lines.append('Supporting evidence is available in publication_packet.json; no verified narrative summary is available for this department.')
    lines.extend(['', '## EVIDENCE ARTIFACTS', '', 'The workflow artifacts retain snapshot.json (collected source data), dossier.json and dossier.md (detailed research), publication_packet.json (newspaper department evidence), and story_desk.json / story_desk.md (magazine planning evidence), where applicable. No collected evidence has been removed from the source artifacts.', ''])
    return '\n'.join(lines)



def _render_health_section(
    health: dict[str, Any], *, flagship: bool
) -> list[str]:
    title = "## INJURY & ROSTER HEALTH" if flagship else "## ROSTER HEALTH"
    lines = ["", title, ""]
    status = str(health.get("status") or "not_collected")
    if status != "available":
        lines.append(
            "Roster-health data unavailable: "
            + str(health.get("error") or "upstream health source did not return data")
        )
        return lines

    players = health.get("players") or []
    if not players:
        lines.append("No rostered player health or IR/reserve flags were returned.")
        return lines

    for row in players:
        details: list[str] = []
        if row.get("status"):
            details.append(str(row["status"]))
        if row.get("injury_status"):
            details.append(str(row["injury_status"]))
        if row.get("on_ir"):
            details.append("IR/RESERVE")
        if flagship:
            if row.get("report_primary_injury"):
                details.append(str(row["report_primary_injury"]))
            if row.get("report_secondary_injury"):
                details.append(f"secondary {row['report_secondary_injury']}")
            if row.get("practice_participation"):
                details.append(str(row["practice_participation"]))
            if row.get("practice_primary_injury") and row.get("practice_primary_injury") != row.get("report_primary_injury"):
                details.append(f"practice injury {row['practice_primary_injury']}")
            if row.get("injury_start_date"):
                details.append(f"injury start {row['injury_start_date']}")
            if row.get("depth_chart_order") is not None:
                details.append(f"depth chart {row['depth_chart_order']}")
            if row.get("injury_report_updated"):
                details.append(f"official report updated {row['injury_report_updated']}")
            elif row.get("news_updated"):
                details.append(f"news updated {row['news_updated']}")
        position = row.get("position") or "N/A"
        nfl_team = row.get("nfl_team") or "FA"
        lines.append(
            f"- {row.get('team')}: {row.get('player')} "
            f"({position}, {nfl_team}) — "
            + (", ".join(details) if details else "flagged")
        )
    return lines


def _render_flagship_stat_book(intelligence: dict[str, Any]) -> list[str]:
    lines = [
        "",
        "## ACTUAL NFL STATS — SUBMITTED STARTERS",
        "",
        (
            "Use these real NFL box-score and usage figures as the default language "
            "for Ironbound/Unbound game stories. Fantasy points belong in matchup "
            "totals and result-changing lineup decisions, not as the primary "
            "description of player performance."
        ),
        "",
    ]
    statuses = intelligence.get("source_status") or {}
    if statuses:
        lines.append(
            "Source coverage: "
            + "; ".join(
                f"{name.replace('_', ' ')}={status}"
                for name, status in sorted(statuses.items())
            )
        )
        lines.append("")

    stat_book = intelligence.get("stat_book") or {}
    status = str(stat_book.get("status") or "not_collected")
    if status != "available":
        lines.append(
            "Weekly NFL stat book unavailable: "
            + str(stat_book.get("error") or "weekly player-stat source did not return data")
        )
        return lines

    records = stat_book.get("records") or []
    if not records:
        lines.append("No submitted starters matched the weekly NFL player-stat source.")
    else:
        current_team = None
        for row in records:
            fantasy_team = str(row.get("fantasy_team") or "Unknown fantasy team")
            if fantasy_team != current_team:
                lines.extend(["", f"### {fantasy_team}", ""])
                current_team = fantasy_team
            identity = f"{row.get('player')} ({row.get('position') or '?'}, {row.get('nfl_team') or 'FA'})"
            opponent = row.get("opponent")
            if opponent:
                identity += f" vs. {opponent}"
            lines.append(f"- **{identity}:** {row.get('nfl_stat_line') or 'No stat line available'}")

    missing = stat_book.get("missing_starters") or []
    if missing:
        lines.extend(
            [
                "",
                "### MANUAL VERIFICATION NEEDED",
                "",
                (
                    "These submitted starters did not match a weekly nflverse player-stat row. "
                    "Do not assume zero production; verify bye/inactive status or supply the "
                    "missing line manually before publication."
                ),
                "",
            ]
        )
        for row in missing:
            lines.append(
                f"- {row.get('fantasy_team')}: {row.get('player')} "
                f"({row.get('position') or '?'}, {row.get('nfl_team') or 'FA'})"
            )
    return lines

def read_optional_artifact(directory: Path, name: str) -> dict[str, Any] | None:
    path = directory / name
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError(f'{path} must contain an object')
    return value


def reading_packet_from_artifacts(directory: Path, dossier: dict[str, Any]) -> str:
    flagship_path = Path(directory) / "flagship_research_packet.md"
    if flagship_path.exists():
        return flagship_path.read_text(encoding="utf-8")
    return render_reading_packet(
        dossier,
        packet=read_optional_artifact(directory, "publication_packet.json"),
        story=read_optional_artifact(directory, "story_desk.json"),
    )
