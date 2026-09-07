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
