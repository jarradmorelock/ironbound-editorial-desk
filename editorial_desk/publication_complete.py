from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .external_inputs import ExternalEditorialInputs


CONTRACT_VERSION = "publication-complete-v1"
FLAGSHIP_PUBLICATIONS = {"ironbound_weekly", "unbound_weekly"}
NEWSPAPER_PUBLICATIONS = {
    "ballad_crier",
    "the_stampede",
    "volunteer_voice",
    "saturday_standard",
    "hollywood_beat",
}


def _publication_key(snapshot: dict[str, Any], research: dict[str, Any]) -> str:
    profile = ((snapshot.get("editorial") or {}).get("publication_profile") or {})
    return str(
        research.get("publication_key")
        or (profile.get("key") if isinstance(profile, dict) else profile)
        or ""
    )


def _issue_identity(
    snapshot: dict[str, Any],
    research: dict[str, Any],
    source_manifest: dict[str, Any],
) -> dict[str, Any]:
    publication_key = _publication_key(snapshot, research)
    season = str(
        research.get("season")
        or (snapshot.get("nfl_state") or {}).get("season")
        or (snapshot.get("league") or {}).get("season")
        or ""
    )
    week = int(research.get("week") or snapshot.get("week") or 0)
    return {
        "publication_key": publication_key,
        "league_key": str((snapshot.get("editorial") or {}).get("league_key") or ""),
        "season": season,
        "week": week,
        "information_cutoff": source_manifest.get("information_cutoff"),
    }


def _split_flagship_honors(honors: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    manager_keys = {
        "manager_of_the_week",
        "most_efficient_manager",
        "high_score",
        "low_score",
        "bad_beat",
        "escape_artist",
        "weekly_efficiency_top_three",
        "season_efficiency_top_three",
        "season_team_score_top_three",
        "rotating_award_candidates",
        "rotating_award_manual_review",
        "award_availability",
        "award_audit",
        "selected_rotating_award",
        "rotating_award_policy",
        "exceptional_loss_review",
    }
    player_keys = {
        "overall_player_of_the_week",
        "started_position_leaders",
        "benchwarmer_of_the_week",
        "player_season_top_three",
    }
    rookie_keys = {
        "rookie_of_the_week",
        "rookie_watch_top_five",
        "rookie_season_leaders",
        "rookie_disappointment_candidates",
        "rookie_disappointment_status",
        "top_rookie_starter",
    }
    return (
        {key: honors.get(key) for key in manager_keys if key in honors},
        {key: honors.get(key) for key in player_keys if key in honors},
        {key: honors.get(key) for key in rookie_keys if key in honors},
    )


def _feature_evidence(research: dict[str, Any]) -> dict[str, Any]:
    game = research.get("game_coverage") or {}
    story = research.get("story_desk") or {}
    return {
        "cover_candidates": list(game.get("cover_candidates") or []),
        "story_candidates": list(story.get("candidates") or []),
        "story_status": story.get("status"),
        "context_events": research.get("context_events") or {},
    }


def _sources_and_notes(
    source_manifest: dict[str, Any],
    research: dict[str, Any],
) -> dict[str, Any]:
    return {
        "information_cutoff": source_manifest.get("information_cutoff"),
        "measured_sources": {
            "sleeper": source_manifest.get("sleeper") or {},
            "nflverse": source_manifest.get("nflverse") or {},
        },
        "model_sources": {
            "rankings": source_manifest.get("rankings") or {},
        },
        "time_sensitive": {
            "health": True,
            "beat_news": source_manifest.get("beat_news") or {},
        },
        "editorial_notes": list(
            ((research.get("tuesday_external_inputs") or {}).get("notes") or [])
        ),
    }


def _newspaper_departments(
    publication_key: str,
    research: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    departments: dict[str, dict[str, Any]] = {}
    for raw in research.get("sections") or research.get("departments") or []:
        if not isinstance(raw, dict) or not raw.get("feature"):
            continue
        row = dict(raw)
        feature = str(row.get("feature") or "")
        if publication_key == "volunteer_voice" and feature == "league_wide_started_mvp":
            row["display_name"] = "King of the Hill"
            data = row.get("data")
            if isinstance(data, dict):
                row["data"] = {
                    **data,
                    "award_key": "KING_OF_THE_HILL",
                    "display_name": "King of the Hill",
                }
        departments[feature] = row
    return departments


def _newspaper_required_departments(
    publication_key: str,
    departments: dict[str, dict[str, Any]],
) -> list[str]:
    from .newspaper_research import PROFILE_CONTRACTS

    contract = PROFILE_CONTRACTS.get(publication_key) or {}
    required = list(contract.get("required") or [])
    conditional = set(contract.get("conditional") or [])
    for feature in conditional:
        row = departments.get(feature)
        if row and row.get("required_in_phase", True):
            required.append(feature)
    return list(dict.fromkeys(required))


def _newspaper_department_problem(
    feature: str,
    row: dict[str, Any],
) -> str | None:
    status = str(row.get("status") or "").lower()
    if status == "ready_no_items":
        return None
    if status != "ready":
        return str(row.get("reason") or status or "department missing")

    data = row.get("data")
    if feature == "lineup_flip_candidates":
        if not isinstance(data, list) or not data:
            return "ready lineup-flip department contains no evaluated decisions; use ready_no_items for a true quiet week"
        required = {
            "started_player",
            "bench_player",
            "started_points",
            "bench_points",
            "hypothetical_team_points",
            "would_flip_result",
        }
        for item in data:
            if not isinstance(item, dict) or not required <= set(item) or item.get("would_flip_result") is not True:
                return "lineup-flip evidence must include legal starter/bench points, hypothetical final, and would_flip_result=true"
        return None

    if feature == "health_status":
        if not isinstance(data, list) or not data:
            return "ready health department contains no rows; use ready_no_items when the roster is healthy"
        for item in data:
            if not isinstance(item, dict):
                return "health evidence contains a non-object row"
            if not (item.get("player") or item.get("player_id")):
                return "health evidence is missing player identity"
            if not (item.get("team") or item.get("fantasy_team")):
                return "health evidence is missing fantasy team"
            if not any(
                item.get(key) not in (None, "", False)
                for key in (
                    "status",
                    "injury_status",
                    "game_designation",
                    "injury",
                    "practice_participation",
                    "on_ir",
                    "on_reserve",
                )
            ):
                return "health evidence has no status, injury, practice, or reserve signal"
        return None

    if feature == "league_wide_started_mvp":
        if not isinstance(data, dict) or not data:
            return "league-wide started-player honor is missing"
        if str(data.get("status") or "").upper() != "STARTED":
            return "league-wide honor must identify a started player"
        for field in ("player", "team", "points"):
            if data.get(field) in (None, ""):
                return f"league-wide honor is missing {field}"
        return None

    if feature == "league_median":
        if not isinstance(data, dict) or data.get("points") is None:
            return "median department is missing the computed median line"
        return None

    if feature in {"idp_position_metrics", "workload_stat_lines"}:
        if not isinstance(data, dict) or not data:
            return f"{feature} is marked ready without any metric rows"
        return None

    if data in (None, {}, [], ()):
        return "department is marked ready but contains no evidence; use ready_no_items when collection succeeded with no qualifying items"
    return None


def build_publication_complete_packet(
    snapshot: dict[str, Any],
    dossier: dict[str, Any],
    research_packet: dict[str, Any],
    external: ExternalEditorialInputs | None,
    *,
    canonical_evidence: dict[str, Any],
    transaction_evidence: dict[str, Any],
    source_manifest: dict[str, Any],
    health: dict[str, Any],
    publication_assets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile the publication-facing factual boundary.

    This function only reshapes already-collected/normalized evidence. It does
    not perform research or call any external client.
    """
    issue = _issue_identity(snapshot, research_packet, source_manifest)
    key = issue["publication_key"]
    evidence_index = dict(canonical_evidence.get("evidence_index") or {})

    packet: dict[str, Any] = {
        "schema_version": 1,
        "contract_version": CONTRACT_VERSION,
        "issue_identity": issue,
        "source_manifest": dict(source_manifest),
        "evidence_index": evidence_index,
        "canonical_league_evidence": canonical_evidence,
        "transaction_desk": transaction_evidence,
        "roster_health": health,
        "publication_assets": dict(publication_assets or {}),
    }

    if key in FLAGSHIP_PUBLICATIONS:
        honors = dict(research_packet.get("weekly_honors") or {})
        manager, player, rookie = _split_flagship_honors(honors)
        game_coverage = research_packet.get("game_coverage") or {}
        ranking_assets = research_packet.get("ranking_publication_assets") or {}
        packet.update(
            {
                "profile_tier": "flagship",
                "game_dossiers": list(game_coverage.get("games") or []),
                "feature_evidence": _feature_evidence(research_packet),
                "usage_desk": dict(research_packet.get("usage_desk") or {}),
                "manager_honors": manager,
                "player_honors": player,
                "rookie_watch": rookie,
                "division_report": {
                    "canonical": canonical_evidence.get("division_summary") or {},
                    "outlook": research_packet.get("division_outlook") or {},
                    "remaining_schedule_strength": research_packet.get("remaining_schedule_strength") or {},
                },
                "power_board": dict(research_packet.get("power_board") or {}),
                "playoff_forecast": dict(research_packet.get("playoff_odds_chart") or {}),
                "power_rankings": dict(research_packet.get("power_rankings_chart") or {}),
                "week_ahead": dict(research_packet.get("weekly_matchup_forecast") or {}),
                "sources_and_model_notes": _sources_and_notes(source_manifest, research_packet),
                "publication_assets": dict(
                    publication_assets
                    or ranking_assets.get("assets")
                    or {}
                ),
                "optional_market": dict(
                    ((research_packet.get("roster_market") or {}).get("sleeper_platform_rates") or {})
                ),
            }
        )
    else:
        departments = _newspaper_departments(key, research_packet)
        packet.update(
            {
                "profile_tier": "newspaper",
                "departments": departments,
                "required_departments": _newspaper_required_departments(key, departments),
                "sources_and_model_notes": _sources_and_notes(source_manifest, research_packet),
            }
        )

    packet["readiness"] = validate_publication_complete_packet(packet)
    return packet


def _block(
    blocking: list[dict[str, Any]],
    section: str,
    code: str,
    detail: str,
) -> None:
    blocking.append({"section": section, "code": code, "detail": detail})


def _flagship_readiness(packet: dict[str, Any]) -> dict[str, Any]:
    blocking: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    optional: list[dict[str, Any]] = []

    games = packet.get("game_dossiers") or []
    if len(games) != 8:
        _block(blocking, "game_dossiers", "INCOMPLETE_MATCHUPS", f"{len(games)}/8 completed matchup dossiers")

    canonical = packet.get("canonical_league_evidence") or {}
    coverage = canonical.get("coverage") or {}
    if coverage.get("status") != "READY":
        _block(
            blocking,
            "historical_league_facts",
            "INCOMPLETE_HISTORY",
            str(coverage.get("reason") or coverage.get("status") or "historical coverage unavailable"),
        )

    transactions = packet.get("transaction_desk") or {}
    if (transactions.get("coverage") or {}).get("status") != "READY":
        _block(
            blocking,
            "transaction_desk",
            "INCOMPLETE_TRANSACTION_HISTORY",
            str((transactions.get("coverage") or {}).get("status") or "unavailable"),
        )
    if transactions.get("unresolved_pick_provenance"):
        _block(
            blocking,
            "transaction_desk",
            "UNRESOLVED_PICK_PROVENANCE",
            f"{len(transactions.get('unresolved_pick_provenance') or [])} transferred pick(s) have unresolved provenance",
        )

    health = packet.get("roster_health") or {}
    if health.get("status") not in {"READY", "READY_NO_ITEMS"}:
        _block(
            blocking,
            "roster_health",
            "HEALTH_NOT_READY",
            str(health.get("status") or "unavailable"),
        )

    manager = packet.get("manager_honors") or {}
    for key in ("manager_of_the_week", "season_efficiency_top_three", "season_team_score_top_three"):
        if not manager.get(key):
            _block(blocking, "manager_honors", f"MISSING_{key.upper()}", f"{key} is unavailable")

    player = packet.get("player_honors") or {}
    if not player.get("overall_player_of_the_week"):
        _block(blocking, "player_honors", "MISSING_OVERALL_PLAYER", "overall player of the week unavailable")
    position = player.get("started_position_leaders") or {}
    missing_positions = [key for key in ("QB", "RB", "WR", "TE") if not position.get(key)]
    if missing_positions:
        _block(
            blocking,
            "player_honors",
            "MISSING_POSITION_WINNERS",
            "missing distinct position winners: " + ", ".join(missing_positions),
        )
    season_board = player.get("player_season_top_three") or {}
    if season_board.get("status") != "READY":
        _block(blocking, "player_honors", "PLAYER_SEASON_BOARD_NOT_READY", str(season_board.get("reason") or season_board.get("status")))

    rookie = packet.get("rookie_watch") or {}
    if len(rookie.get("rookie_watch_top_five") or []) < 5:
        _block(blocking, "rookie_watch", "ROOKIE_TOP_FIVE_NOT_READY", "fewer than five rookie weekly rows")
    rookie_season = rookie.get("rookie_season_leaders") or {}
    if rookie_season.get("status") != "READY":
        _block(blocking, "rookie_watch", "ROOKIE_SEASON_BOARD_NOT_READY", str(rookie_season.get("reason") or rookie_season.get("status")))

    division = packet.get("division_report") or {}
    canonical_division = division.get("canonical") or {}
    outlook = division.get("outlook") or {}
    if canonical_division.get("status") != "READY" or outlook.get("division_status") != "READY":
        _block(blocking, "division_report", "DIVISION_EVIDENCE_NOT_READY", "canonical or forward-looking division evidence unavailable")

    for section in ("power_rankings", "playoff_forecast"):
        if (packet.get(section) or {}).get("status") != "READY":
            _block(blocking, section, "AUTHORITATIVE_HANDOFF_NOT_READY", "authoritative ranking handoff is unavailable")

    assets = packet.get("publication_assets") or {}
    for asset_key in ("power_rankings", "playoff_forecast"):
        row = assets.get(asset_key) or {}
        if row.get("status") != "READY" or not row.get("package_path"):
            _block(blocking, "publication_assets", f"MISSING_{asset_key.upper()}_ASSET", f"{asset_key} supplied graphic unavailable")

    week_ahead = packet.get("week_ahead") or {}
    if week_ahead.get("status") != "READY" or len(week_ahead.get("rows") or []) != 8:
        _block(blocking, "week_ahead", "INCOMPLETE_WEEK_AHEAD", f"{len(week_ahead.get('rows') or [])}/8 matchup forecast rows")

    optional_market = packet.get("optional_market") or {}
    if optional_market and optional_market.get("status") not in {"READY", "available"}:
        optional.append(
            {
                "section": "optional_market",
                "code": "OPTIONAL_MARKET_UNAVAILABLE",
                "detail": str(optional_market.get("note") or optional_market.get("status")),
            }
        )

    beat = (packet.get("source_manifest") or {}).get("beat_news") or {}
    if beat.get("status") == "PARTIAL":
        warnings.append(
            {
                "section": "beat_news",
                "code": "PARTIAL_HISTORY",
                "detail": "Durable beat/news history does not cover the entire issue window.",
            }
        )

    return {
        "publication_ready": not blocking,
        "status": "READY" if not blocking else "BLOCKED",
        "profile_tier": "flagship",
        "blocking_gaps": blocking,
        "warnings": warnings,
        "optional_gaps": optional,
    }


def _newspaper_readiness(packet: dict[str, Any]) -> dict[str, Any]:
    blocking: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    required = list(packet.get("required_departments") or [])
    departments = packet.get("departments") or {}

    for feature in required:
        row = departments.get(feature)
        if row is None:
            _block(
                blocking,
                feature,
                "MISSING_REQUIRED_DEPARTMENT",
                "required publication department is absent from the research packet",
            )
            continue
        problem = _newspaper_department_problem(feature, row)
        if problem:
            _block(
                blocking,
                feature,
                "INCOMPLETE_DEPARTMENT_EVIDENCE",
                problem,
            )

    canonical = packet.get("canonical_league_evidence") or {}
    if (canonical.get("coverage") or {}).get("status") not in {"READY", "NOT_APPLICABLE"}:
        _block(
            blocking,
            "historical_league_facts",
            "INCOMPLETE_HISTORY",
            str((canonical.get("coverage") or {}).get("reason") or "unavailable"),
        )

    transaction_features = {"waiver_impact", "transactions", "future_picks", "rookie_draft"}
    if transaction_features.intersection(required):
        transactions = packet.get("transaction_desk") or {}
        if (transactions.get("coverage") or {}).get("status") != "READY":
            _block(
                blocking,
                "transaction_desk",
                "INCOMPLETE_TRANSACTION_HISTORY",
                str((transactions.get("coverage") or {}).get("status") or "unavailable"),
            )

    if "health_status" in required:
        health = packet.get("roster_health") or {}
        if health.get("status") not in {"READY", "READY_NO_ITEMS"}:
            _block(
                blocking,
                "health_status",
                "HEALTH_NOT_READY",
                str(health.get("status") or "unavailable"),
            )

    beat = (packet.get("source_manifest") or {}).get("beat_news") or {}
    if beat.get("status") == "PARTIAL":
        warnings.append(
            {
                "section": "beat_news",
                "code": "PARTIAL_HISTORY",
                "detail": "Beat history is partial.",
            }
        )
    return {
        "publication_ready": not blocking,
        "status": "READY" if not blocking else "BLOCKED",
        "profile_tier": "newspaper",
        "blocking_gaps": blocking,
        "warnings": warnings,
        "optional_gaps": [],
    }


def validate_publication_complete_packet(packet: dict[str, Any]) -> dict[str, Any]:
    key = str((packet.get("issue_identity") or {}).get("publication_key") or "")
    if key in FLAGSHIP_PUBLICATIONS:
        return _flagship_readiness(packet)
    if key in NEWSPAPER_PUBLICATIONS:
        return _newspaper_readiness(packet)
    return {
        "publication_ready": False,
        "status": "BLOCKED",
        "profile_tier": "unsupported",
        "blocking_gaps": [
            {
                "section": "publication_profile",
                "code": "UNSUPPORTED_PROFILE",
                "detail": f"No publication-complete contract exists for {key!r}.",
            }
        ],
        "warnings": [],
        "optional_gaps": [],
    }


def render_publication_complete_packet(packet: dict[str, Any]) -> str:
    issue = packet.get("issue_identity") or {}
    readiness = packet.get("readiness") or {}
    lines = [
        f"# {issue.get('publication_key') or 'Publication'} — Week {issue.get('week')} Publication-Complete Packet",
        "",
        f"Contract: **{packet.get('contract_version')}**",
        f"Publication ready: **{'YES' if readiness.get('publication_ready') else 'NO'}**",
        f"Information cutoff: {issue.get('information_cutoff') or 'unknown'}",
        "",
        "## Blocking Gaps",
    ]
    gaps = readiness.get("blocking_gaps") or []
    lines.extend(
        f"- {row.get('section')}: {row.get('code')} — {row.get('detail')}"
        for row in gaps
    )
    if not gaps:
        lines.append("- None.")
    lines.extend(["", "## Warnings"])
    warnings = readiness.get("warnings") or []
    lines.extend(
        f"- {row.get('section')}: {row.get('code')} — {row.get('detail')}"
        for row in warnings
    )
    if not warnings:
        lines.append("- None.")
    lines.extend(["", "## Offline Boundary", ""])
    lines.append(
        "All factual research, reconciliation, and calculations end in this packet. "
        "Downstream manuscript and slide builders must not perform new research."
    )
    return "\n".join(lines) + "\n"


def write_publication_complete_packet(
    directory: Path,
    packet: dict[str, Any],
) -> tuple[Path, Path]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "publication_complete_packet.json"
    markdown_path = directory / "publication_complete_packet.md"
    json_path.write_text(
        json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_publication_complete_packet(packet), encoding="utf-8")
    return json_path, markdown_path


def validate_offline_consumability(packet: dict[str, Any]) -> dict[str, Any]:
    """Validate a packet using only the supplied object; no research clients accepted."""
    readiness = validate_publication_complete_packet(packet)
    return {
        "research_calls": 0,
        "required_departments_ready": bool(readiness.get("publication_ready")),
        "readiness": readiness,
    }
