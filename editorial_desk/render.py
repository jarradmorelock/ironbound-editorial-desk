from __future__ import annotations

from typing import Any


def render_markdown(dossier: dict[str, Any]) -> str:
    league = dossier.get("league") or {}
    lines = [
        f"# {league.get('publication')} Week {dossier.get('week')} Research Dossier",
        "",
        f"League: {league.get('configured_name')}",
        f"Information current through: {dossier.get('information_current_through')}",
        "",
        "This is a factual dry-run research packet, not finished publication copy.",
        "",
        "## Scoreboard",
        "",
    ]
    for game in dossier.get("scoreboard") or []:
        sides = sorted(game["teams"], key=lambda row: row["points"], reverse=True)
        lines.append(
            f"- {sides[0]['team']} {sides[0]['points']:.2f}, "
            f"{sides[1]['team']} {sides[1]['points']:.2f}"
        )

    lines.extend(["", "## Lineup Efficiency", ""])
    for row in dossier.get("lineup_efficiency") or []:
        lines.append(
            f"- {row['team']}: {row['efficiency']:.1%}; "
            f"{row['points_left_on_bench']:.2f} points left"
        )

    rankings = dossier.get("rankings") or {}
    lines.extend(["", "## Rankings Desk", ""])
    if rankings.get("official_standings_status") == "season_not_started":
        lines.append("- Official standings: season has not started")
    else:
        for row in rankings.get("official_standings") or []:
            lines.append(
                f"- Official #{row['rank']} {row['team']}: "
                f"{row['wins']}-{row['losses']}-{row['ties']}, "
                f"{row['points_for']:.2f} points"
            )
    power = rankings.get("data_power_ranking") or {}
    if power.get("status") == "calculated":
        lines.append("")
        for row in power.get("rows") or []:
            lines.append(
                f"- Data power #{row['rank']} {row['team']}: "
                f"submitted projection {row['submitted_lineup_projection']:.2f}; "
                f"optimal starters {row['optimal_starting_lineup_projection']:.2f}; "
                f"record {row['win_loss_percentage']:.3f}"
            )
    elif power.get("status") == "component_inputs_collected":
        lines.append("")
        for row in power.get("rows") or []:
            lines.append(
                f"- Dynasty inputs, {row['team']}: starter-strength rank "
                f"#{row['dynasty_starter_strength_rank']}; projection rank "
                f"#{row['optimal_starting_lineup_projection_rank']}; "
                f"roster-value rank #{row['dynasty_roster_value_rank']}"
            )
    else:
        lines.append("- Data power ranking: awaiting required source data")
    lines.append(
        "- Prior published ranking: awaiting the finalized-edition archive"
    )

    median = dossier.get("league_median") or {}
    if median.get("enabled"):
        lines.extend(["", "## League Median", ""])
        lines.append(f"- Weekly median: {median['points']:.2f}")
        above = [
            row["team"]
            for row in median.get("results") or []
            if row["result"] == "win"
        ]
        lines.append(f"- Above the median: {', '.join(above) if above else 'None'}")

    divisions = dossier.get("divisions") or []
    if divisions:
        lines.extend(["", "## Division Pulse", ""])
        for division in divisions:
            record = division["head_to_head_record"]
            lines.append(
                f"- {division['division_name']}: "
                f"{division['average_points']:.2f} average points; "
                f"{record['wins']}-{record['losses']}-{record['ties']} head-to-head"
            )

    lines.extend(["", "## Featurette Candidates", ""])
    awards = dossier.get("awards") or {}
    for label, key in (
        ("MVP card result", "mvp_card_result"),
        ("Manager of the Week", "manager_of_the_week"),
        ("Bench MVP", "bench_mvp"),
        ("Bad Beat", "bad_beat"),
        ("Escape Artist", "escape_artist"),
    ):
        value = awards.get(key)
        lines.append(f"- {label}: {_short(value)}")

    flips = awards.get("result_flipping_decisions") or []
    lines.append(f"- Result-flipping lineup decisions: {len(flips)} candidate(s)")
    waivers = awards.get("waiver_star_candidates") or []
    lines.append(f"- Waiver Star: {len(waivers)} candidate(s)")

    sections = dossier.get("publication_sections") or []
    if sections:
        lines.extend(["", "## Publication Desk", ""])
        for section in sections:
            lines.append(f"- {section}")

    records = dossier.get("weekly_records") or {}
    lines.extend(["", "## Weekly Record Watch", ""])
    lines.append(f"- Highest score: {_short(records.get('highest_score'))}")
    lines.append(f"- Lowest score: {_short(records.get('lowest_score'))}")

    lines.extend(["", "## Verification and Deferred Analysis", ""])
    for item in dossier.get("deferred_until_history_exists") or []:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def _short(value: dict[str, Any] | None) -> str:
    if not value:
        return "No qualifying candidate"
    subject = value.get("player") or value.get("team") or "Candidate"
    if "points" in value:
        return f"{subject} ({value['points']:.2f} points)"
    if "efficiency" in value:
        return f"{subject} ({value['efficiency']:.1%} efficiency)"
    return str(subject)
