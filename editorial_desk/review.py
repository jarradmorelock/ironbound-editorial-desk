from __future__ import annotations

from typing import Any

from .metrics import build_weekly_dossier
from .nfl_enrichment import build_nfl_game_intelligence
from .render import render_markdown
from .weekly_features import apply_weekly_features


def build_editorial_review(snapshot: dict[str, Any]) -> dict[str, Any]:
    dossier = build_weekly_dossier(snapshot)
    dossier = apply_weekly_features(snapshot, dossier)
    intelligence = build_nfl_game_intelligence(snapshot)
    if intelligence is not None:
        dossier["nfl_game_intelligence"] = intelligence
    return dossier


def render_editorial_review(dossier: dict[str, Any]) -> str:
    base = render_markdown(dossier).rstrip()
    lines = [base, "", "## Weekly Magazine Features", ""]
    features = dossier.get("weekly_features") or {}

    nominees = features.get("divisional_mvp_nominees") or []
    lines.append("### Divisional MVP Nominations")
    if not nominees:
        lines.append("- No divisional nominees available")
    for row in nominees:
        foil = " — **GOLD FOIL**" if row.get("gold_foil") else ""
        lines.append(
            f"- {row.get('division_name')}: {row.get('player')} "
            f"({row.get('position') or '?'}) — {row.get('team')} — "
            f"{_points(row.get('points'))} — {row.get('status', 'STARTED')}{foil}"
        )
    lines.append("- Card images are generated separately after commissioner review.")

    lines.extend(["", "### Top Scorers by Position"])
    leaders = features.get("top_scorers_by_position") or {}
    if not leaders:
        lines.append("- No positional leaders available")
    for position, row in sorted(leaders.items()):
        lines.append(
            f"- {position}: {row.get('player')} — {row.get('team')} — "
            f"{_points(row.get('points'))} — {row.get('status', 'UNKNOWN')}"
        )

    lines.extend(["", "### Weekly Feature Awards"])
    lines.append(
        "- Benchwarmer of the Week: "
        + _feature_line(features.get("benchwarmer_of_the_week"))
    )
    lines.append(
        "- Rookie of the Week: "
        + _feature_line(features.get("rookie_of_the_week"))
    )
    lines.append(
        "- Free Agent of the Week: "
        + _feature_line(features.get("free_agent_of_the_week"))
    )

    intelligence = dossier.get("nfl_game_intelligence")
    if intelligence:
        lines.extend(["", "## Ironbound NFL Game Intelligence", ""])
        statuses = intelligence.get("source_status") or {}
        lines.append(
            "- Source coverage: "
            + "; ".join(
                f"{name.replace('_', ' ')}={status}"
                for name, status in sorted(statuses.items())
            )
        )
        signals = intelligence.get("story_signals") or []
        if not signals:
            lines.append("- No conservative game-story signals cleared thresholds this week.")
        for signal in signals:
            label = str(signal.get("type") or "STORY_SIGNAL")
            team = signal.get("team")
            prefix = f"{label} [{team}]" if team else label
            explanation = signal.get("explanation") or "Supporting evidence available in dossier JSON."
            lines.append(f"- **{prefix}**: {explanation}")

    lines.append("")
    return "\n".join(lines)


def _feature_line(value: dict[str, Any] | None) -> str:
    if not value:
        return "No eligible candidate"
    team = value.get("team")
    position = value.get("position")
    bits = [str(value.get("player") or "Unknown")]
    if position:
        bits.append(str(position))
    if team:
        bits.append(str(team))
    bits.append(_points(value.get("points")))
    if value.get("status"):
        bits.append(str(value["status"]))
    return " — ".join(bits)


def _points(value: Any) -> str:
    try:
        return f"{float(value):.2f} pts"
    except (TypeError, ValueError):
        return "points unavailable"
