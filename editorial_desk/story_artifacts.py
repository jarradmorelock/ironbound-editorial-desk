from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .chronicle_queries import ChronicleQueries
from .config import PublicationConfig
from .external_inputs import load_external_inputs
from .story_desk import build_story_desk


def write_story_desk_artifacts(
    directory: Path,
    snapshot: dict[str, Any],
    dossier: dict[str, Any],
    publication: PublicationConfig,
    *,
    chronicle_root: Path,
    external_inputs_dir: Path | None = None,
) -> tuple[Path, ...]:
    """Write private Story Desk planning artifacts for explicitly enabled magazines.

    Visuals are suggestions only. This layer never retrieves, stores, or links image assets.
    """
    if not publication.story_desk:
        return ()

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    external_path = _external_input_path(external_inputs_dir, publication.key)
    external_inputs = load_external_inputs(external_path, publication.key)
    packet = build_story_desk(
        publication.key,
        snapshot,
        dossier,
        ChronicleQueries(Path(chronicle_root)),
        external_inputs=external_inputs,
    )
    packet = _with_headline_packages(packet)

    json_path = directory / "story_desk.json"
    markdown_path = directory / "story_desk.md"
    json_path.write_text(
        json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(_render_story_desk(packet), encoding="utf-8")
    return (json_path, markdown_path)


def _external_input_path(
    external_inputs_dir: Path | None, publication_key: str
) -> Path | None:
    if external_inputs_dir is None:
        return None
    path = Path(external_inputs_dir) / f"{publication_key}.json"
    return path if path.exists() else None


def _with_headline_packages(packet: dict[str, Any]) -> dict[str, Any]:
    result = dict(packet)
    candidates: list[dict[str, Any]] = []
    for raw in packet.get("candidates") or []:
        candidate = dict(raw)
        suggestion = _image_suggestion(candidate)
        candidate["headline_packages"] = [
            {
                "headline": str(headline),
                "image_suggestion": suggestion,
            }
            for headline in candidate.get("title_concepts") or []
            if str(headline).strip()
        ]
        candidates.append(candidate)
    result["candidates"] = candidates
    return result


def _image_suggestion(candidate: dict[str, Any]) -> str:
    candidate_type = str(candidate.get("candidate_type") or "story")
    graphic_ideas = [
        str(value).strip()
        for value in candidate.get("graphic_ideas") or []
        if str(value).strip()
    ]
    if graphic_ideas:
        return (
            "Use a story-appropriate editorial image or game-action photo, paired with "
            f"this data treatment: {graphic_ideas[0]}."
        )

    labels = {
        "rivalry_history": "the two franchises or managers facing one another",
        "injury_shock": "the affected player in game action or on the sideline",
        "reaction_transaction": "the affected player plus the acquiring fantasy franchise",
        "waiver_run": "the player at the center of the waiver rush",
        "trade_afterlife": "the principal traded player or asset in its current context",
        "trade_market_shift": "the principal players or franchises involved in the trade cluster",
        "asset_journey": "the player or draft asset at the center of the transaction chain",
        "roster_architecture": "the franchise's core players arranged as a roster-building visual",
        "dynasty_identity": "the franchise's current core with subtle past-era references",
        "historic_upset": "the winning and losing sides from the upset matchup",
        "scoring_record": "the record-setting player or franchise with a clean record-card overlay",
        "streak": "the recurring opponents with the streak count emphasized",
        "repeated_close_losses": "the franchise involved in the close-loss run",
        "former_player_matchup": "the former player facing the prior fantasy franchise",
        "playoff_rematch": "the current matchup paired with a visual callback to the prior playoff meeting",
        "lineup_catastrophe": "the benched and started players as a start-sit contrast",
        "division_pressure": "the leading division contenders in a standings-race composition",
        "cross_league_shock": "the NFL player whose event affected multiple leagues",
        "david_vs_goliath": "the two franchises presented with their official ranking contrast",
    }
    subject = labels.get(candidate_type, "the central player, manager, or franchise in the story")
    return f"Use an editorial or game-action image centered on {subject}; no image asset is collected by the Story Desk."


def _render_story_desk(packet: dict[str, Any]) -> str:
    publication_key = str(packet.get("publication_key") or "Story Desk")
    lines = [
        f"# {publication_key.replace('_', ' ').title()} Story Desk",
        "",
        f"Status: **{packet.get('status', 'unknown')}**",
        f"Candidates: **{len(packet.get('candidates') or [])}**",
        "",
        "## External Inputs",
        "",
    ]
    external = packet.get("external_inputs") or {}
    lines.append(
        "- Official Power Rankings: "
        + ("supplied" if external.get("official_power_rankings") else "not supplied")
    )
    lines.append("- WAR: " + ("supplied" if external.get("war") else "not supplied"))

    candidates = packet.get("candidates") or []
    if not candidates:
        lines.extend(["", "No evidence-backed story candidate cleared the desk this week.", ""])
        return "\n".join(lines)

    for index, candidate in enumerate(candidates, start=1):
        label = str(candidate.get("candidate_type") or "story").replace("_", " ").title()
        lines.extend(["", f"## {index}. {label}", ""])

        packages = candidate.get("headline_packages") or []
        if packages:
            lines.append("### Headline Suggestions")
            for package in packages:
                lines.append(f"- **{package.get('headline')}**")
                lines.append(f"  - Suggested visual: {package.get('image_suggestion')}")
            lines.append("")

        lines.append(
            f"- Evidence strength: **{candidate.get('evidence_strength', 'unknown')}**"
        )
        lines.append(f"- Signal score: **{candidate.get('signal_score', 0)}**")
        lines.append(f"- Depth: **{candidate.get('depth_class', 'brief')}**")

        triggers = candidate.get("trigger_reasons") or []
        if triggers:
            lines.append("- Trigger:")
            lines.extend(f"  - {value}" for value in triggers)

        facts = candidate.get("facts") or []
        if facts:
            lines.append("- Facts:")
            lines.extend(f"  - {_compact_json(row)}" for row in facts)

        history = candidate.get("historical_context") or []
        if history:
            lines.append("- Historical context:")
            lines.extend(f"  - {_compact_json(row)}" for row in history)

        cautions = candidate.get("cautions") or []
        if cautions:
            lines.append("- Cautions:")
            lines.extend(f"  - {value}" for value in cautions)

        angles = candidate.get("editorial_angles") or []
        if angles:
            lines.append("- Editorial angles:")
            lines.extend(f"  - {value}" for value in angles)

        graphics = candidate.get("graphic_ideas") or []
        if graphics:
            lines.append("- Graphic ideas:")
            lines.extend(f"  - {value}" for value in graphics)

        evidence = candidate.get("evidence_refs") or []
        lines.append("- Evidence:")
        if evidence:
            for ref in evidence:
                lines.append(
                    "  - "
                    f"{ref.get('evidence_id')} [{ref.get('source')}]: "
                    f"{ref.get('description')}"
                )
        else:
            lines.append("  - No direct evidence reference")

    lines.append("")
    return "\n".join(lines)


def _compact_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(", ", ": "))
