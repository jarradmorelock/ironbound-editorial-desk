from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


def generate_supplements(
    baseline_root: Path,
    current_root: Path,
    output_root: Path,
    week: int,
) -> list[Path]:
    generated = []
    pattern = f"*/week-{week:02d}/*/dossier.json"
    for current_path in sorted(current_root.glob(pattern)):
        relative = current_path.relative_to(current_root)
        baseline_path = baseline_root / relative
        if not baseline_path.exists():
            continue
        baseline = _read_json(baseline_path)
        current = _read_json(current_path)
        lines = _supplement_lines(baseline, current)
        if not lines:
            continue
        directory = output_root / relative.parent
        directory.mkdir(parents=True, exist_ok=True)
        markdown_path = directory / "supplement.md"
        metadata_path = directory / "supplement.json"
        league = current.get("league") or {}
        header = [
            f"# {league.get('publication')} Week {week} Supplemental Research",
            "",
            f"League: {league.get('configured_name')}",
            f"Tuesday baseline: {baseline.get('information_current_through')}",
            f"Backup collection: {current.get('information_current_through')}",
            "",
            "This supplement contains only material that was not present in the "
            "Tuesday packet.",
            "",
        ]
        markdown_path.write_text("\n".join(header + lines) + "\n", encoding="utf-8")
        metadata_path.write_text(
            json.dumps(
                {
                    "season": current.get("season"),
                    "week": week,
                    "league": league,
                    "baseline_information_current_through": baseline.get(
                        "information_current_through"
                    ),
                    "information_current_through": current.get(
                        "information_current_through"
                    ),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        generated.extend((markdown_path, metadata_path))
    return generated


def _supplement_lines(
    baseline: dict[str, Any], current: dict[str, Any]
) -> list[str]:
    sections = []
    _add_source_updates(sections, baseline, current)
    _add_score_updates(sections, baseline, current)
    _add_new_awards(sections, baseline, current)
    _add_ranking_updates(sections, baseline, current)
    _add_transaction_updates(sections, baseline, current)
    _add_health_updates(sections, baseline, current)
    _add_timing_updates(sections, baseline, current)
    return [line for section in sections for line in section]


def _add_source_updates(
    sections: list[list[str]],
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> None:
    sources = (
        (
            "NFL",
            ((baseline.get("game_timing") or {}).get("source_status") or {}),
            ((current.get("game_timing") or {}).get("source_status") or {}),
        ),
        (
            "Ranking",
            ((baseline.get("rankings") or {}).get("sources") or {}),
            ((current.get("rankings") or {}).get("sources") or {}),
        ),
        (
            "Flagship",
            (
                (baseline.get("flagship_supplement") or {}).get("source_status")
                or {}
            ),
            (
                (current.get("flagship_supplement") or {}).get("source_status")
                or {}
            ),
        ),
    )
    changes = []
    for source_group, before, after in sources:
        changes.extend(
            f"- {source_group} {name.replace('_', ' ')}: "
            f"{before.get(name, 'not collected')} → {status}"
            for name, status in after.items()
            if status == "available" and before.get(name) != status
        )
    if changes:
        sections.append(["## Newly Available Sources", "", *changes, ""])


def _add_health_updates(
    sections: list[list[str]],
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> None:
    before = baseline.get("roster_health") or {}
    after = current.get("roster_health") or {}
    if after.get("status") != "available":
        return

    old_rows = {
        (int(row.get("roster_id") or 0), str(row.get("player_id") or "")): row
        for row in before.get("players") or []
    }
    changes: list[str] = []
    for row in after.get("players") or []:
        identity = (int(row.get("roster_id") or 0), str(row.get("player_id") or ""))
        old = old_rows.get(identity)
        if old == row:
            continue
        details = []
        if row.get("status"):
            details.append(str(row["status"]))
        if row.get("injury_status"):
            details.append(str(row["injury_status"]))
        if row.get("on_ir"):
            details.append("IR/RESERVE")
        if row.get("practice_participation"):
            details.append(str(row["practice_participation"]))
        changes.append(
            f"- {row.get('team')}: {row.get('player')} — "
            f"{', '.join(details) if details else 'health status changed'}"
        )

    if changes:
        sections.append(["## Roster Health Updates", "", *changes, ""])


def _add_ranking_updates(
    sections: list[list[str]],
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> None:
    before = ((baseline.get("rankings") or {}).get("data_power_ranking") or {})
    after = ((current.get("rankings") or {}).get("data_power_ranking") or {})
    if before.get("status") == after.get("status") or not after.get("rows"):
        return
    rows = []
    for row in after["rows"]:
        rank = row.get("rank")
        prefix = f"#{rank} " if rank is not None else ""
        rows.append(
            f"- {prefix}{row.get('team')}: submitted projection "
            f"{_format_number(row.get('submitted_lineup_projection'))}; "
            f"optimal projection "
            f"{_format_number(row.get('optimal_starting_lineup_projection'))}"
        )
    sections.append(["## Newly Calculated Ranking Evidence", "", *rows, ""])


def _add_transaction_updates(
    sections: list[list[str]],
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> None:
    before = baseline.get("transactions") or {}
    after = current.get("transactions") or {}
    old_ids = {
        str(row.get("transaction_id")) for row in before.get("records") or []
    }
    new_rows = [
        row
        for row in after.get("records") or []
        if str(row.get("transaction_id")) not in old_ids
    ]
    if not new_rows:
        return
    lines = []
    for row in new_rows:
        adds = len(row.get("adds") or {})
        drops = len(row.get("drops") or {})
        lines.append(
            f"- New {str(row.get('type') or 'transaction').replace('_', ' ')} "
            f"record: {adds} add(s), {drops} drop(s); "
            f"transaction ID {row.get('transaction_id')}"
        )
    sections.append(["## Newly Recorded League Activity", "", *lines, ""])


def _add_score_updates(
    sections: list[list[str]],
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> None:
    before = {
        str(row.get("matchup_id")): row for row in baseline.get("scoreboard") or []
    }
    changes = []
    for game in current.get("scoreboard") or []:
        matchup_id = str(game.get("matchup_id"))
        old = before.get(matchup_id)
        if old and _score_signature(old) == _score_signature(game):
            continue
        sides = sorted(
            game.get("teams") or [], key=lambda row: row.get("points", 0), reverse=True
        )
        if len(sides) == 2:
            changes.append(
                f"- Matchup {matchup_id}: {sides[0]['team']} "
                f"{sides[0]['points']:.2f}, {sides[1]['team']} "
                f"{sides[1]['points']:.2f}"
            )
    if changes:
        sections.append(["## Scoreboard Updates", "", *changes, ""])


def _add_new_awards(
    sections: list[list[str]],
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> None:
    before = baseline.get("awards") or {}
    after = current.get("awards") or {}
    changes = []
    for label, key in (
        ("MVP Card Result", "mvp_card_result"),
        ("Manager of the Week", "manager_of_the_week"),
        ("Bench MVP", "bench_mvp"),
        ("Bad Beat", "bad_beat"),
        ("Escape Artist", "escape_artist"),
    ):
        value = after.get(key)
        if value and value != before.get(key):
            changes.append(f"- {label}: {_subject_line(value)}")
    for label, key, identity in (
        (
            "Result-flipping lineup decision",
            "result_flipping_decisions",
            lambda row: (row.get("roster_id"), row.get("started_player_id"), row.get("bench_player_id")),
        ),
        (
            "Waiver Star candidate",
            "waiver_star_candidates",
            lambda row: (row.get("transaction_id"), row.get("player_id")),
        ),
    ):
        old_ids = {identity(row) for row in before.get(key) or []}
        for row in after.get(key) or []:
            if identity(row) not in old_ids:
                changes.append(f"- {label}: {_subject_line(row)}")
    if changes:
        sections.append(["## Newly Calculated Features", "", *changes, ""])


def _add_timing_updates(
    sections: list[list[str]],
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> None:
    old_timing = baseline.get("game_timing") or {}
    new_timing = current.get("game_timing") or {}
    lines = ["## New NFL Game-Day Evidence", ""]
    early_old = old_timing.get("early_week") or old_timing.get("thursday") or {}
    early_new = new_timing.get("early_week") or new_timing.get("thursday") or {}
    monday_old = old_timing.get("monday") or {}
    monday_new = new_timing.get("monday") or {}

    _append_new_matchups(
        lines,
        "Thursday/early-week margin supplier",
        early_old.get("margin_suppliers") or [],
        early_new.get("margin_suppliers") or [],
    )
    _append_new_performances(
        lines,
        "Positive Thursday/early-week swing",
        early_old.get("positive_performances") or [],
        early_new.get("positive_performances") or [],
    )
    _append_new_performances(
        lines,
        "Negative Thursday/early-week swing",
        early_old.get("negative_performances") or [],
        early_new.get("negative_performances") or [],
    )
    _append_new_matchups(
        lines,
        "Monday lead change",
        monday_old.get("lead_changes") or [],
        monday_new.get("lead_changes") or [],
    )
    _append_new_matchups(
        lines,
        "Monday tiebreak",
        monday_old.get("tie_breakers") or [],
        monday_new.get("tie_breakers") or [],
    )

    old_plays = {
        (str(row.get("game_id")), str(row.get("play_id")))
        for row in monday_old.get("late_play_candidates") or []
    }
    for play in monday_new.get("late_play_candidates") or []:
        identity = (str(play.get("game_id")), str(play.get("play_id")))
        if identity in old_plays:
            continue
        linked = ", ".join(
            f"{row.get('player')} ({row.get('team')})"
            for row in play.get("linked_fantasy_starters") or []
        )
        margin = play.get("smallest_linked_final_margin")
        margin_text = f"; linked fantasy margin {margin:.2f}" if margin is not None else ""
        lines.append(
            f"- New late-play candidate: Q{play.get('quarter')} "
            f"{play.get('clock')} — {play.get('description')} — {linked}{margin_text}"
        )

    old_players = {
        (int(row.get("roster_id") or 0), str(row.get("player_id"))): row
        for row in old_timing.get("starter_game_days") or []
    }
    new_stat_lines = []
    for row in new_timing.get("starter_game_days") or []:
        identity = (int(row.get("roster_id") or 0), str(row.get("player_id")))
        old = old_players.get(identity) or {}
        if row.get("nfl_stat_line") and not old.get("nfl_stat_line"):
            new_stat_lines.append(row)
    non_sunday = [
        row for row in new_stat_lines if str(row.get("weekday")) != "Sunday"
    ]
    top_scorers = sorted(
        new_stat_lines, key=lambda row: row.get("fantasy_points", 0), reverse=True
    )[:5]
    relevant = {}
    for row in non_sunday + top_scorers:
        relevant[(row.get("roster_id"), row.get("player_id"))] = row
    limit = 20 if ((current.get("league") or {}).get("tier") == "flagship") else 10
    for row in list(relevant.values())[:limit]:
        lines.append(f"- New NFL box score: {_performance_line(row)}")

    if len(lines) > 2:
        lines.append("")
        sections.append(lines)


def _append_new_matchups(
    lines: list[str],
    label: str,
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
) -> None:
    old_ids = {str(row.get("matchup_id")) for row in before}
    for row in after:
        if str(row.get("matchup_id")) in old_ids:
            continue
        lines.append(
            f"- {label}: {row.get('final_winner')} over {row.get('final_loser')} "
            f"by {_format_number(row.get('final_margin'))}"
        )


def _append_new_performances(
    lines: list[str],
    label: str,
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
) -> None:
    identity: Callable[[dict[str, Any]], tuple[Any, Any]] = lambda row: (
        row.get("roster_id"),
        row.get("player_id"),
    )
    old_ids = {identity(row) for row in before}
    for row in after:
        if identity(row) not in old_ids:
            lines.append(f"- {label}: {_performance_line(row)}")


def _performance_line(row: dict[str, Any]) -> str:
    difference = row.get("projection_difference")
    difference_text = (
        f" ({difference:+.2f} vs. projection)"
        if difference is not None
        else ""
    )
    return (
        f"{row.get('weekday') or 'Day unknown'} — {row.get('player')} for "
        f"{row.get('team')}: {_format_number(row.get('fantasy_points'))} fantasy "
        f"points{difference_text}; {row.get('nfl_stat_line') or 'NFL stat line unavailable'}"
    )


def _subject_line(value: dict[str, Any]) -> str:
    subject = value.get("player") or value.get("team") or "Candidate"
    if value.get("points") is not None:
        return f"{subject} ({_format_number(value.get('points'))} points)"
    if value.get("efficiency") is not None:
        return f"{subject} ({float(value['efficiency']):.1%} efficiency)"
    return str(subject)


def _score_signature(game: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(
        sorted(
            (int(row.get("roster_id") or 0), float(row.get("points") or 0))
            for row in game.get("teams") or []
        )
    )


def _format_number(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "not available"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
