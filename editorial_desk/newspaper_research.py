from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .publication_policy import publication_view
from .reading_packet import fact_lines


PROFILE_CONTRACTS: dict[str, dict[str, Any]] = {
    "ballad_crier": {
        "label": "Ballad Crier weekly research contract",
        "required": [
            "weekly_results",
            "league_median",
            "game_window_context",
            "final_scorecard",
            "lineup_flip_candidates",
            "standings",
            "ranking_movement",
            "weekly_honors",
            "player_position_leaders",
            "waiver_impact",
            "health_status",
            "record_watch",
            "next_matchups",
        ],
        "editorial_notes": [
            "Lead with the strongest verified weekly diagnosis: late comeback, close finish, high score, or other result-changing event.",
            "Keep Weekly Rounds focused on lineup decisions that actually flipped or protected a result; do not substitute generic efficiency.",
            "Ward Report is required research even when it is not used as a full printed block.",
        ],
    },
    "hollywood_beat": {
        "label": "Hollywood Beat weekly research contract",
        "required": [
            "weekly_results",
            "league_median",
            "standings",
            "lead_inputs",
            "hollywood_board",
            "game_window_context",
            "weekly_honors",
            "player_position_leaders",
            "lineup_flip_candidates",
            "lineup_efficiency",
            "waiver_impact",
            "health_status",
            "weekly_briefs",
            "next_matchups",
        ],
        "editorial_notes": [
            "The Hollywood Board should have evidence for Top Billing, Scene Stealer, Plot Twist, and Bad Beat when the week supports them.",
            "Late Show material should identify the fantasy swing and retain real NFL stat context when available.",
            "Dynasty trades, future rights, and rookie-draft material are conditional weekly stories, not mandatory filler.",
        ],
    },
    "saturday_standard": {
        "label": "Saturday Standard weekly research contract",
        "required": [
            "weekly_results",
            "opening_statement_inputs",
            "game_window_context",
            "weekly_ledger",
            "division_metrics",
            "ranking_movement",
            "lineup_efficiency",
            "lineup_flip_candidates",
            "waiver_impact",
            "divisional_started_mvps",
            "manager_of_week",
            "idp_position_metrics",
            "weekly_desk_honors",
            "dynasty_market_values",
            "health_status",
        ],
        "conditional": [
            "transactions",
            "rookie_draft",
            "future_picks",
            "next_matchups",
        ],
        "editorial_notes": [
            "East/West division evidence is active and intentional for this publication.",
            "Treat IDP production as first-class evidence alongside offensive production.",
            "Transfer Portal, recruiting, future-pick, and next-week modules are conditional; include them when there is meaningful weekly material.",
        ],
    },
    "volunteer_voice": {
        "label": "Volunteer Voice weekly research contract",
        "required": [
            "weekly_results",
            "record_watch",
            "manager_decision_evidence",
            "official_table",
            "league_median",
            "ranking_movement",
            "league_wide_started_mvp",
            "manager_of_week",
            "bench_leaders",
            "rookie_of_week",
            "free_agent_of_week",
            "lineup_efficiency",
            "bad_beat",
            "escape_artist",
            "waiver_impact",
            "bench_blast",
            "health_status",
            "next_matchups",
        ],
        "editorial_notes": [
            "Rocky Top Rumble divisions are disabled. Treat any Sleeper division metadata as dormant configuration, not publication evidence.",
            "Keep the family-league packet compact: lead result, decision desk, table/median, league-wide honors, efficiency, notebook, and next-week support.",
            "Mountain MVP is the league-wide top started-player honor; do not manufacture divisional or gold-foil awards from dormant divisions.",
        ],
        "forbid_divisions": True,
    },
    "the_stampede": {
        "label": "Stampede weekly research contract",
        "required": [
            "weekly_results",
            "standings",
            "ranking_movement",
            "lineup_efficiency",
            "manager_of_week",
            "bad_beat",
            "escape_artist",
            "bench_leaders",
            "lineup_flip_candidates",
            "waiver_impact",
            "workload_stat_lines",
            "health_status",
            "record_watch",
            "next_matchups",
        ],
        "editorial_notes": [
            "What a Way to Make a Living is a real-NFL workload department, not a fantasy-points leaderboard.",
            "Workload leaders must come from players rostered in the 9-to-5 league.",
            "Mystery Mine / Health Board is required research even when the weekly print layout uses only the most relevant alerts.",
        ],
    },
}


def build_newspaper_research_packet(
    snapshot: dict[str, Any],
    dossier: dict[str, Any],
    publication_packet: dict[str, Any],
) -> dict[str, Any]:
    key = str(publication_packet.get("publication_key") or "")
    contract = PROFILE_CONTRACTS.get(key)
    if contract is None:
        return publication_view(
            {
                "schema_version": 1,
                "contract_version": "newspaper-research-v1",
                "publication_key": key,
                "publication": publication_packet.get("publication"),
                "week": publication_packet.get("week"),
                "status": "UNSUPPORTED_PROFILE",
                "sections": publication_packet.get("departments") or [],
                "validation": {
                    "contract_valid": False,
                    "research_complete": False,
                    "manual_verify": [f"No newspaper research contract exists for {key!r}."],
                },
            },
            publication_packet,
        )

    raw_encoded = json.dumps(publication_packet, sort_keys=True).casefold()
    raw_division_leak = (
        any(
            str(row.get("feature") or "") in {"division_metrics", "divisional_started_mvps"}
            for row in publication_packet.get("departments") or []
        )
        or '"division_id"' in raw_encoded
        or '"division_name"' in raw_encoded
    )

    packet = publication_view(
        {
            "schema_version": 1,
            "contract_version": "newspaper-research-v1",
            "publication_key": key,
            "publication": publication_packet.get("publication"),
            "week": publication_packet.get("week"),
            "information_current_through": dossier.get("information_current_through"),
            "contract_label": contract["label"],
            "editorial_notes": list(contract.get("editorial_notes") or []),
            "sections": list(publication_packet.get("departments") or []),
            "health": dossier.get("roster_health") or {},
            "source_status": _source_status(snapshot, dossier),
            "input_forbidden_group_leak": raw_division_leak,
        },
        publication_packet,
    )
    packet["validation"] = validate_newspaper_research_packet(packet)
    return packet


def validate_newspaper_research_packet(packet: dict[str, Any]) -> dict[str, Any]:
    key = str(packet.get("publication_key") or "")
    contract = PROFILE_CONTRACTS.get(key) or {}
    sections = packet.get("sections") or []
    by_feature = {str(row.get("feature") or ""): row for row in sections}
    checks: list[dict[str, Any]] = []
    manual: list[str] = []

    for feature in contract.get("required") or []:
        section = by_feature.get(feature)
        present = section is not None
        checks.append(
            {
                "name": f"required_{feature}",
                "passed": present,
                "detail": "present" if present else "missing from publication contract",
            }
        )
        if not present:
            manual.append(f"Required department {feature!r} is missing from the newspaper contract.")
            continue
        if section.get("status") == "unavailable":
            manual.append(
                f"{section.get('display_name') or feature}: source unavailable"
                + (f" ({section.get('reason')})" if section.get("reason") else "")
            )

    if contract.get("forbid_divisions"):
        encoded = json.dumps(packet, sort_keys=True).casefold()
        division_leak = bool(packet.get("input_forbidden_group_leak")) or (
            "division_metrics" in by_feature
            or "divisional_started_mvps" in by_feature
            or '"division_id"' in encoded
            or '"division_name"' in encoded
        )
        checks.append(
            {
                "name": "divisions_disabled",
                "passed": not division_leak,
                "detail": "dormant Sleeper divisions suppressed" if not division_leak else "division data leaked into Volunteer Voice",
            }
        )
        if division_leak:
            manual.append("Volunteer Voice contains dormant Rocky Top division data; suppress it before publication.")

    return {
        "contract_valid": all(row["passed"] for row in checks),
        "research_complete": not manual and all(row["passed"] for row in checks),
        "checks": checks,
        "manual_verify": manual,
        "conditional_departments": list(contract.get("conditional") or []),
    }


def render_newspaper_research_packet(packet: dict[str, Any]) -> str:
    lines = [
        f"# {packet.get('publication') or packet.get('publication_key')} — Week {packet.get('week')} Research Packet",
        "",
        f"Contract: **{packet.get('contract_label')}**",
        "",
        "## RESEARCH READINESS",
        "",
    ]
    validation = packet.get("validation") or {}
    lines.append("Contract valid: **" + ("YES" if validation.get("contract_valid") else "NO") + "**")
    lines.append("Research complete: **" + ("YES" if validation.get("research_complete") else "NO") + "**")
    if packet.get("information_current_through"):
        lines.append(f"Information current through: {packet['information_current_through']}")

    lines.extend(["", "### Manual Verification"])
    manual = validation.get("manual_verify") or []
    lines.extend(f"- {row}" for row in manual)
    if not manual:
        lines.append("- None.")

    lines.extend(["", "### Editorial Contract"])
    lines.extend(f"- {row}" for row in packet.get("editorial_notes") or [])

    source_status = packet.get("source_status") or {}
    lines.extend(["", "### Source Coverage"])
    for name, status in source_status.items():
        lines.append(f"- {name.replace('_', ' ').title()}: {status}")

    for section in packet.get("sections") or []:
        feature = str(section.get("feature") or "")
        title = str(section.get("display_name") or feature or "Department")
        lines.extend(["", f"## {title}", "", f"Status: **{section.get('status') or 'unknown'}**"])
        if section.get("reason"):
            lines.append(str(section["reason"]))
        data = section.get("data")
        custom = _render_feature(feature, data)
        if custom:
            lines.extend(custom)
        else:
            facts = fact_lines(data, 16)
            lines.extend(f"- {row}" for row in facts)
            if data not in (None, [], {}, ()) and not facts:
                lines.extend(f"- {row}" for row in _compact_evidence(data))

    lines.extend(
        [
            "",
            "## HANDOFF RULE",
            "",
            "This packet is research for the named newspaper, not final copy. Use the paper's voice and layout only after the required evidence is verified. Do not invent a missing department, injury status, lineup decision, NFL stat line, ranking, or transaction.",
            "",
        ]
    )
    return "\n".join(lines)


def write_newspaper_research_packet(
    directory: Path, packet: dict[str, Any]
) -> tuple[Path, Path]:
    directory = Path(directory)
    json_path = directory / "newspaper_research_packet.json"
    markdown_path = directory / "newspaper_research_packet.md"
    json_path.write_text(
        json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_newspaper_research_packet(packet), encoding="utf-8")
    return json_path, markdown_path


def _source_status(snapshot: dict[str, Any], dossier: dict[str, Any]) -> dict[str, str]:
    nfl = snapshot.get("nfl_context") or {}
    health = dossier.get("roster_health") or {}
    return {
        "sleeper_week": "available" if snapshot.get("matchups") is not None else "unavailable",
        "nfl_player_stats": str((nfl.get("player_stats") or {}).get("status") or "not_collected"),
        "health": str(health.get("status") or "not_collected"),
        "next_matchups": str((snapshot.get("next_matchups") or {}).get("status") or "not_collected"),
    }


def _render_feature(feature: str, data: Any) -> list[str]:
    if feature == "league_median" and isinstance(data, dict):
        points = data.get("points")
        lines = [f"- Median line: {float(points):.2f}" if points is not None else "- Median line unavailable."]
        above = [row.get("team") for row in data.get("results") or [] if row.get("result") == "win"]
        if above:
            lines.append("- Above median: " + ", ".join(str(name) for name in above))
        return lines

    if feature == "workload_stat_lines" and isinstance(data, dict):
        lines = []
        for label, row in data.items():
            player = row.get("player_display_name") or row.get("player_name") or row.get("player_id")
            team = row.get("fantasy_team") or "unmapped"
            field = {
                "passing_attempts": "attempts",
                "passing_yards": "passing_yards",
                "passing_touchdowns": "passing_tds",
                "rushing_attempts": "carries",
                "rushing_yards": "rushing_yards",
                "rushing_touchdowns": "rushing_tds",
                "receptions": "receptions",
                "targets": "targets",
                "receiving_yards": "receiving_yards",
                "receiving_touchdowns": "receiving_tds",
            }.get(label)
            value = row.get(field) if field else None
            lines.append(f"- {label.replace('_', ' ').title()}: {player} ({team}) — {value}")
        return lines

    if feature in {"player_position_leaders", "idp_position_metrics"} and isinstance(data, dict):
        lines = []
        for position, row in data.items():
            status = row.get("status") or ""
            lines.append(
                f"- {position}: {row.get('player')} — {row.get('team')} — {float(row.get('points') or 0):.2f} FP"
                + (f" — {status}" if status else "")
            )
        return lines

    if feature == "game_window_context" and isinstance(data, list):
        lines = []
        for row in data:
            swing = "RESULT SWUNG" if row.get("swung_result") else "final-window context"
            remaining = ", ".join(
                f"{player.get('player')} {float(player.get('points') or 0):.2f}"
                for player in row.get("remaining_players") or []
            )
            lines.append(
                f"- {row.get('team')} vs {row.get('opponent')}: "
                f"{float(row.get('pre_window_score') or 0):.2f}-"
                f"{float(row.get('opponent_pre_window_score') or 0):.2f} before {row.get('window')}; "
                f"final {float(row.get('final_score') or 0):.2f}-"
                f"{float(row.get('opponent_final_score') or 0):.2f}; {swing}"
                + (f"; remaining players: {remaining}" if remaining else "")
            )
        return lines

    return []


def _compact_evidence(value: Any, limit: int = 12) -> list[str]:
    """Human-readable last-resort rendering for structured newspaper evidence."""
    rows: list[str] = []

    def visit(item: Any, prefix: str = "") -> None:
        if len(rows) >= limit:
            return
        if isinstance(item, list):
            for child in item:
                visit(child, prefix)
        elif isinstance(item, dict):
            scalar = {
                str(key): child
                for key, child in item.items()
                if not isinstance(child, (dict, list)) and child not in (None, "")
            }
            if scalar:
                text = ", ".join(
                    f"{key.replace('_', ' ')}={child}"
                    for key, child in list(scalar.items())[:8]
                )
                rows.append((prefix + text).strip())
            for key, child in item.items():
                if isinstance(child, (dict, list)):
                    visit(child, prefix=f"{key.replace('_', ' ')}: ")

    visit(value)
    return rows[:limit]
