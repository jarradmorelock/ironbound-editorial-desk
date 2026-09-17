from __future__ import annotations

from typing import Any

from .publication_policy import publication_view
from .health import build_roster_health, render_roster_health
from .metrics import build_weekly_dossier
from .nfl_enrichment import build_nfl_game_intelligence
from .render import render_markdown
from .weekly_features import apply_weekly_features


def build_editorial_review(snapshot: dict[str, Any]) -> dict[str, Any]:
    dossier = build_weekly_dossier(snapshot)
    dossier = apply_weekly_features(snapshot, dossier)
    dossier["roster_health"] = build_roster_health(snapshot)
    dossier["market_context"] = _build_market_context(snapshot)
    dossier["source_manifest"] = _build_source_manifest()
    intelligence = build_nfl_game_intelligence(snapshot)
    if intelligence is not None:
        dossier["nfl_game_intelligence"] = intelligence
    return publication_view(dossier, snapshot)


def render_editorial_review(dossier: dict[str, Any]) -> str:
    base = render_markdown(dossier).rstrip()
    lines = [base, "", "## Weekly Magazine Features", ""]
    features = dossier.get("weekly_features") or {}

    if "divisional_mvp_nominees" in features:
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

    lines.extend(["", "### Weekly Lineup Efficiency Top 3"])
    efficiency_leaders = features.get("lineup_efficiency_top_three") or []
    if not efficiency_leaders:
        lines.append("- No lineup-efficiency results available")
    for rank, row in enumerate(efficiency_leaders, start=1):
        lines.append(
            f"- #{rank} {row.get('team')}: {float(row.get('efficiency') or 0):.1%}; "
            f"{float(row.get('actual_points') or 0):.2f} of "
            f"{float(row.get('optimal_points') or 0):.2f} possible; "
            f"{float(row.get('points_left_on_bench') or 0):.2f} points left"
        )
    lines.append(
        "- This leaderboard is independent of Manager of the Week and may include teams that lost."
    )
    lines.append(
        "- A season-to-date Top 3 can be added once multiple completed weekly packets are available."
    )

    manager = (dossier.get("awards") or {}).get("manager_of_the_week")
    lines.extend(["", "### Manager of the Week"])
    if not manager:
        lines.append("- No eligible winning manager")
    else:
        lines.append(
            f"- {manager.get('team')} — WIN — "
            f"{float(manager.get('actual_points') or 0):.2f} points; "
            f"{float(manager.get('efficiency') or 0):.1%} lineup efficiency; "
            f"score rank #{manager.get('score_rank_among_winners', '?')} among winners; "
            f"efficiency rank #{manager.get('efficiency_rank_among_winners', '?')} among winners"
        )
        evidence = (manager.get("management_tiebreak") or {}).get("evidence") or []
        if evidence:
            lines.append("- Tie-break management evidence:")
            for row in evidence:
                if row.get("type") == "projection_start_sit":
                    lines.append(
                        f"  - Started {row.get('started_player')} "
                        f"(proj. {float(row.get('started_projection') or 0):.2f}, "
                        f"scored {float(row.get('started_points') or 0):.2f}) over "
                        f"{row.get('bench_player')} "
                        f"(proj. {float(row.get('bench_projection') or 0):.2f}, "
                        f"scored {float(row.get('bench_points') or 0):.2f}); "
                        f"decision swing {float(row.get('point_swing') or 0):.2f} in a "
                        f"{float(row.get('victory_margin') or 0):.2f}-point win"
                    )
                elif row.get("type") == "transaction_start":
                    lines.append(
                        f"  - Started {row.get('transaction_type')} addition "
                        f"{row.get('player')}, who scored "
                        f"{float(row.get('points') or 0):.2f} in a "
                        f"{float(row.get('victory_margin') or 0):.2f}-point win"
                    )

    health = dossier.get("roster_health") or {
        "status": "unavailable",
        "players": [],
        "error": "roster health block was not built",
    }
    lines.extend(
        [
            "",
            *render_roster_health(
                health,
                expanded=(
                    str((dossier.get("league") or {}).get("tier") or "").casefold()
                    == "flagship"
                ),
            ),
        ]
    )

    market = dossier.get("market_context") or {}
    if market:
        lines.extend(["", "## Dynasty Daddy Market Context", ""])
        lines.append(
            f"- Model: {market.get('source_label') or market.get('source')} — "
            f"source status: {market.get('status', 'unknown')}"
        )
        rows = market.get("players") or []
        if rows:
            lines.append("- Highest-valued rostered players in this league:")
            for row in rows[:12]:
                rank = row.get("overall_rank")
                position_rank = row.get("position_rank")
                rank_text = f"overall #{rank}" if rank is not None else "overall rank unavailable"
                if position_rank is not None:
                    rank_text += f", {row.get('position') or '?'}#{position_rank}"
                lines.append(
                    f"  - {row.get('player')} — {row.get('fantasy_team')} — "
                    f"value {_market_value(row.get('trade_value'))} — {rank_text} — "
                    f"{row.get('status', 'ROSTERED')}"
                )
        elif market.get("status") == "available":
            lines.append("- No rostered players matched the selected Dynasty Daddy market feed.")
        else:
            lines.append("- Market values were unavailable for this collection; the dossier remains usable without them.")

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

    sources = dossier.get("source_manifest") or []
    if sources:
        lines.extend(["", "## Data & Sources", ""])
        lines.append(
            "These sources provide the underlying league, market, and NFL data used by the editorial desk. "
            "Editorial interpretation, selections, and commentary are produced by the publication staff."
        )
        for source in sources:
            url = str(source.get("url") or "")
            citation = str(source.get("citation") or source.get("name") or "Source")
            role = str(source.get("role") or "")
            link = f"[{url}]({url})" if url else ""
            suffix = f" — {role}" if role else ""
            lines.append(f"- {citation} {link}{suffix}".rstrip())

    lines.append("")
    return "\n".join(lines)


def _build_market_context(snapshot: dict[str, Any]) -> dict[str, Any]:
    editorial = snapshot.get("editorial") or {}
    league_format = str(editorial.get("league_format") or "").casefold()
    source_key = "redraft_daddy" if league_format == "redraft" else "dynasty_daddy"
    source_label = "Redraft Daddy" if source_key == "redraft_daddy" else "Dynasty Daddy"
    source = (snapshot.get("ranking_inputs") or {}).get(source_key) or {}
    values = source.get("players") or {}
    players = snapshot.get("players") or {}
    users = {
        str(user.get("user_id")): user for user in snapshot.get("users") or []
    }
    rows: list[dict[str, Any]] = []

    for roster in snapshot.get("rosters") or []:
        owner = users.get(str(roster.get("owner_id"))) or {}
        owner_metadata = owner.get("metadata") or {}
        fantasy_team = (
            owner_metadata.get("team_name")
            or owner.get("display_name")
            or f"Roster {roster.get('roster_id')}"
        )
        taxi = {str(player_id) for player_id in roster.get("taxi") or []}
        reserve = {str(player_id) for player_id in roster.get("reserve") or []}
        for player_id in roster.get("players") or []:
            player_id = str(player_id)
            market = values.get(player_id)
            if not market:
                continue
            player = players.get(player_id) or {}
            if player_id in taxi:
                status = "TAXI"
            elif player_id in reserve:
                status = "RESERVE"
            else:
                status = "ROSTERED"
            rows.append(
                {
                    "player_id": player_id,
                    "player": _player_name(player_id, player, market),
                    "position": player.get("position") or market.get("position"),
                    "nfl_team": player.get("team") or market.get("team"),
                    "fantasy_team": fantasy_team,
                    "manager": owner.get("display_name"),
                    "status": status,
                    "trade_value": market.get("trade_value"),
                    "position_rank": market.get("position_rank"),
                    "overall_rank": market.get("overall_rank"),
                }
            )

    rows.sort(
        key=lambda row: (
            _rank_sort(row.get("overall_rank")),
            -_numeric(row.get("trade_value")),
            str(row.get("player") or "").casefold(),
        )
    )
    return {
        "source": source_key,
        "source_label": source_label,
        "status": source.get("status", "not_collected"),
        "players": rows,
    }


def _build_source_manifest() -> list[dict[str, str]]:
    return [
        {
            "name": "Sleeper",
            "citation": "Sleeper. (n.d.). Sleeper API documentation.",
            "url": "https://docs.sleeper.com/",
            "role": "League settings, rosters, player health/status metadata, scores, transactions, standings, and projections.",
        },
        {
            "name": "Dynasty Daddy",
            "citation": "Dynasty Daddy. (n.d.). Dynasty Daddy fantasy football tools and values.",
            "url": "https://dynasty-daddy.com/",
            "role": "Dynasty and redraft player market values and ranks; WAR/cWAR charts may be supplied manually by the editorial staff.",
        },
        {
            "name": "nflverse",
            "citation": "nflverse. (n.d.). nflverse data and documentation.",
            "url": "https://nflverse.nflverse.com/",
            "role": "NFL schedules, weekly statistics, play-by-play, and snap-count context.",
        },
    ]


def _player_name(player_id: str, player: dict[str, Any], market: dict[str, Any]) -> str:
    return str(
        player.get("full_name")
        or market.get("full_name")
        or market.get("name")
        or market.get("name_id")
        or player_id
    )


def _rank_sort(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("inf")


def _numeric(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _market_value(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "unavailable"
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.1f}"


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
