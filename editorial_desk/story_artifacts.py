from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .chronicle_queries import ChronicleQueries
from .config import PublicationConfig
from .metrics import _team_directory
from .external_inputs import load_external_inputs
from .story_desk import build_story_desk


_WAR_RELEVANT = {
    "trade_afterlife",
    "trade_market_shift",
    "asset_journey",
    "roster_architecture",
    "dynasty_identity",
    "division_pressure",
}
_USAGE_RELEVANT = {
    "injury_shock",
    "reaction_transaction",
    "trade_afterlife",
    "roster_architecture",
    "historic_upset",
    "scoring_record",
    "former_player_matchup",
    "playoff_rematch",
    "lineup_catastrophe",
    "cross_league_shock",
}
_GAME_CONTEXT_RELEVANT = {
    "rivalry_history",
    "injury_shock",
    "reaction_transaction",
    "trade_afterlife",
    "historic_upset",
    "scoring_record",
    "former_player_matchup",
    "playoff_rematch",
    "lineup_catastrophe",
    "cross_league_shock",
}
_HISTORY_RELEVANT = {
    "rivalry_history",
    "trade_afterlife",
    "asset_journey",
    "dynasty_identity",
    "historic_upset",
    "streak",
    "repeated_close_losses",
    "former_player_matchup",
    "playoff_rematch",
}
_JUDGMENT_REQUESTS = {
    "rivalry_history": "Approve the rivalry framing or add commissioner-known context that is not captured in Chronicle.",
    "reaction_transaction": "Review the sequence framing and confirm that the magazine should not imply manager motive or causation beyond the recorded timing.",
    "trade_afterlife": "Approve the trade-afterlife angle and add any commissioner context that materially changes how the original deal should be described.",
    "trade_market_shift": "Approve whether the recent trade cluster deserves feature treatment or should remain a market sidebar.",
    "asset_journey": "Confirm whether the recorded asset journey has any league context or nickname worth adding before publication.",
    "dynasty_identity": "Approve the franchise-identity framing and add any relevant manager-era context not present in the registry.",
    "former_player_matchup": "Approve whether the former-player connection is editorially meaningful enough to feature.",
    "playoff_rematch": "Approve the rematch framing and add any remembered playoff context not represented by the recorded result.",
    "division_pressure": "Approve whether the division race merits feature treatment this week.",
    "cross_league_shock": "Review the cross-league framing and confirm that it does not imply unsupported causation between the NFL event and fantasy-manager actions.",
}


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
    packet = _with_display_subjects(packet, snapshot, ChronicleQueries(Path(chronicle_root)))
    packet = _with_headline_packages(packet)
    packet = _with_publication_readiness(packet, snapshot)

    json_path = directory / "story_desk.json"
    markdown_path = directory / "story_desk.md"
    json_path.write_text(
        json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(_render_story_desk(packet), encoding="utf-8")
    return (json_path, markdown_path)


def _with_display_subjects(packet, snapshot, chronicle):
    """Resolve display names while retaining all stable IDs and evidence verbatim."""
    teams = _team_directory(snapshot)
    players = snapshot.get("players") or {}
    editorial = snapshot.get("editorial") or {}
    league_key = str(editorial.get("league_key") or "")
    season = str((snapshot.get("nfl_state") or {}).get("season") or (snapshot.get("league") or {}).get("season") or "")
    identities = {}
    for roster_id, team in teams.items():
        identity = chronicle.identity_for_roster(league_key, season, roster_id)
        if identity:
            identities[identity] = team.get("team")

    def resolve(key, value):
        if isinstance(value, dict):
            return [name for k, v in value.items() for name in resolve(k, v)]
        if isinstance(value, list):
            return [name for v in value for name in resolve(key, v)]
        if value is None:
            return []
        if key == "player_id":
            player = players.get(str(value)) or {}
            name = player.get("full_name") or " ".join(str(player.get(k) or "") for k in ("first_name", "last_name")).strip()
            return [name] if name else []
        if key.endswith("roster_id"):
            try:
                name = (teams.get(int(value)) or {}).get("team")
            except (TypeError, ValueError):
                name = None
            return [name] if name and not name.startswith("Roster ") else []
        if key in {"identity", "identities", "winner", "loser", "opponents", "franchise_key", "manager_key"}:
            if identities.get(str(value)):
                return [identities[str(value)]]
            aliases = chronicle.identity_context(str(value)).get("aliases") or []
            aliases = [row for row in aliases if str(row.get("season") or "") <= season and row.get("name")]
            if aliases:
                return [max(aliases, key=lambda row: str(row.get("season") or ""))["name"]]
        return []

    candidates = []
    for candidate in packet.get("candidates") or []:
        facts = []
        for fact in candidate.get("facts") or []:
            statement = str(fact.get("statement") or "")
            # Only replace explicit roster references, never bare numeric IDs.
            statement = re.sub(
                r"\bRoster (\d+)\b",
                lambda match: str((teams.get(int(match.group(1))) or {}).get("team") or match.group(0)),
                statement,
            )
            facts.append({**fact, "statement": statement})
        candidates.append({
            **candidate,
            "display_subjects": list(dict.fromkeys(resolve("entities", candidate.get("entities") or {}))),
            "display_facts": facts,
        })
    return {**packet, "candidates": candidates}


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


def _with_publication_readiness(
    packet: dict[str, Any], snapshot: dict[str, Any]
) -> dict[str, Any]:
    """Add a commissioner-facing pre-publication request list.

    The list is deliberately relevance-aware: missing optional inputs are requested
    only when at least one current Story Desk candidate can use them. Required
    items are limited to inputs that block the flagship magazine's final form.
    """
    result = dict(packet)
    candidates = [dict(row) for row in packet.get("candidates") or []]
    candidate_types = {
        str(row.get("candidate_type") or "") for row in candidates if row.get("candidate_type")
    }
    external = packet.get("external_inputs") or {}
    nfl_context = snapshot.get("nfl_context") or {}

    required: list[dict[str, Any]] = []
    optional: list[dict[str, Any]] = []
    judgment: list[dict[str, Any]] = []
    visuals: list[dict[str, Any]] = []
    no_action: list[dict[str, Any]] = []

    if external.get("official_power_rankings"):
        no_action.append(
            {
                "input": "official_power_rankings",
                "request": "Official Power Rankings are already supplied for the final magazine ranking section.",
            }
        )
    else:
        required.append(
            {
                "input": "official_power_rankings",
                "request": "Supply this week's official Power Rankings before final publication.",
                "reason": "The final Ironbound/Unbound magazine requires the separate official Power Rankings section and the Editorial Desk does not generate or replace it.",
            }
        )

    for input_key, label in (
        ("playoff_odds", "Playoff Odds"),
        ("usage", "Dynasty Daddy usage"),
        ("war", "WAR"),
        ("cwar", "cWAR"),
    ):
        if external.get(input_key):
            no_action.append(
                {
                    "input": input_key,
                    "request": f"{label} input is already supplied for the flagship research packet.",
                }
            )
        else:
            required.append(
                {
                    "input": input_key,
                    "request": f"Supply this week's {label} from the Tuesday rankings/data delivery.",
                    "reason": (
                        "The flagship production contract passes this external input through; "
                        "the Editorial Desk does not recreate it."
                    ),
                }
            )

    _append_nflverse_readiness(
        no_action,
        optional,
        nfl_context,
        candidate_types,
    )

    history_candidates = [
        row for row in candidates if str(row.get("candidate_type") or "") in _HISTORY_RELEVANT
    ]
    if history_candidates:
        no_action.append(
            {
                "input": "chronicle_history",
                "request": "Chronicle history is already available for the current history-aware Story Desk candidates.",
            }
        )
        if any(_candidate_has_incomplete_coverage(row) for row in history_candidates):
            optional.append(
                {
                    "input": "historical_context",
                    "request": "Add commissioner-known historical context or a source if you want the feature to go beyond the Chronicle coverage currently recorded.",
                    "reason": "Chronicle contains usable history, but at least one candidate explicitly carries incomplete historical coverage.",
                }
            )

    for candidate in candidates:
        candidate_type = str(candidate.get("candidate_type") or "")
        request = _JUDGMENT_REQUESTS.get(candidate_type)
        if request:
            judgment.append(
                {
                    "candidate_id": candidate.get("candidate_id"),
                    "candidate_type": candidate_type,
                    "request": request,
                }
            )

        packages = candidate.get("headline_packages") or []
        suggestions = [
            str(row.get("image_suggestion") or "").strip()
            for row in packages
            if str(row.get("image_suggestion") or "").strip()
        ]
        if suggestions:
            visuals.append(
                {
                    "candidate_id": candidate.get("candidate_id"),
                    "candidate_type": candidate_type,
                    "request": f"Source or approve this visual direction: {suggestions[0]}",
                }
            )

    result["publication_readiness"] = {
        "ready_for_final_publication": not required,
        "required_before_publication": required,
        "optional_enrichment": optional,
        "commissioner_judgment": judgment,
        "visuals_to_source_or_approve": visuals,
        "no_action_needed": no_action,
    }
    return result


def _append_nflverse_readiness(
    no_action: list[dict[str, Any]],
    optional: list[dict[str, Any]],
    nfl_context: dict[str, Any],
    candidate_types: set[str],
) -> None:
    player_stats_available = _source_available(nfl_context.get("player_stats"))
    snap_counts_available = _source_available(nfl_context.get("snap_counts"))
    play_by_play_available = _source_available(nfl_context.get("play_by_play"))

    if player_stats_available:
        no_action.append(
            {
                "input": "nflverse_player_stats",
                "request": "nflverse weekly player statistics are already available; no separate stat pull is needed.",
            }
        )
    elif candidate_types & _USAGE_RELEVANT:
        optional.append(
            {
                "input": "player_stat_context",
                "request": "Provide an alternate verified weekly stat source only if you want deeper player-production context for the affected feature.",
                "reason": "nflverse player statistics were not available for a current player-focused candidate.",
            }
        )

    if snap_counts_available:
        no_action.append(
            {
                "input": "nflverse_snap_counts",
                "request": "nflverse snap-count context is already available; no separate usage-stat pull is needed.",
            }
        )
    elif candidate_types & _USAGE_RELEVANT:
        optional.append(
            {
                "input": "usage_context",
                "request": "Provide or approve an alternate usage/snap source if you want deeper usage analysis for the affected feature.",
                "reason": "nflverse snap counts are unavailable and a current candidate can benefit from usage context.",
            }
        )

    if play_by_play_available:
        no_action.append(
            {
                "input": "nflverse_play_by_play",
                "request": "nflverse play-by-play context is already available; no separate game-context pull is needed.",
            }
        )
    elif candidate_types & _GAME_CONTEXT_RELEVANT:
        optional.append(
            {
                "input": "game_context",
                "request": "Provide or approve an alternate game-context source if you want deeper game-script detail for the affected feature.",
                "reason": "nflverse play-by-play is unavailable and a current candidate can benefit from game context.",
            }
        )


def _source_available(raw: Any) -> bool:
    return isinstance(raw, dict) and str(raw.get("status") or "").casefold() == "available"


def _candidate_has_incomplete_coverage(candidate: dict[str, Any]) -> bool:
    for key in ("facts", "historical_context"):
        for row in candidate.get(key) or []:
            if isinstance(row, dict) and row.get("coverage_complete") is False:
                return True
    return False


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
    lines.append("- Playoff Odds: " + ("supplied" if external.get("playoff_odds") else "not supplied"))
    lines.append("- Usage: " + ("supplied" if external.get("usage") else "not supplied"))
    lines.append("- WAR: " + ("supplied" if external.get("war") else "not supplied"))
    lines.append("- cWAR: " + ("supplied" if external.get("cwar") else "not supplied"))

    readiness = packet.get("publication_readiness")
    if readiness:
        lines.extend(
            [
                "",
                "## Publication Readiness / Commissioner Requests",
                "",
                "Final publication ready: "
                + ("**YES**" if readiness.get("ready_for_final_publication") else "**NO**"),
            ]
        )
        _render_request_bucket(
            lines,
            "Required Before Publication",
            readiness.get("required_before_publication") or [],
        )
        _render_request_bucket(
            lines,
            "Optional Enrichment",
            readiness.get("optional_enrichment") or [],
        )
        _render_request_bucket(
            lines,
            "Commissioner / Editorial Judgment",
            readiness.get("commissioner_judgment") or [],
        )
        _render_request_bucket(
            lines,
            "Visuals to Source or Approve",
            readiness.get("visuals_to_source_or_approve") or [],
        )
        _render_request_bucket(
            lines,
            "No Action Needed",
            readiness.get("no_action_needed") or [],
        )

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


def _render_request_bucket(
    lines: list[str], title: str, rows: list[dict[str, Any]]
) -> None:
    lines.extend(["", f"### {title}"])
    if not rows:
        lines.append("- None.")
        return
    for row in rows:
        request = str(row.get("request") or "").strip()
        reason = str(row.get("reason") or "").strip()
        lines.append(f"- {request}")
        if reason:
            lines.append(f"  - Why: {reason}")


def _compact_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(", ", ": "))
