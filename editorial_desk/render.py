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
    for row in flips:
        lines.append(
            f"  - {row['team']}: {row['bench_player']} "
            f"({row['bench_points']:.2f}) over {row['started_player']} "
            f"({row['started_points']:.2f}) at {row['slot']} would have changed "
            f"the score to {row['revised_team_score']:.2f}-"
            f"{row['opponent_score']:.2f}"
        )
    waivers = awards.get("waiver_star_candidates") or []
    lines.append(f"- Waiver Star: {len(waivers)} candidate(s)")
    for row in waivers:
        bid = (
            f"; FAAB {row['faab']}"
            if row.get("faab") is not None
            else ""
        )
        lines.append(
            f"  - {row['player']} for {row['team']}: {row['points']:.2f} points; "
            f"victory margin {row['victory_margin']:.2f}{bid}"
        )

    flagship = dossier.get("flagship_supplement")
    if flagship:
        _render_flagship_sourcebook(lines, flagship)

    sections = dossier.get("publication_sections") or []
    if sections:
        lines.extend(["", "## Publication Desk", ""])
        for section in sections:
            lines.append(f"- {section}")

    records = dossier.get("weekly_records") or {}
    lines.extend(["", "## Weekly Record Watch", ""])
    lines.append(f"- Highest score: {_short(records.get('highest_score'))}")
    lines.append(f"- Lowest score: {_short(records.get('lowest_score'))}")
    lines.append(f"- Largest margin: {_short_margin(records.get('largest_margin'))}")
    lines.append(f"- Closest finish: {_short_margin(records.get('smallest_margin'))}")

    lines.extend(["", "## Verification and Deferred Analysis", ""])
    for item in dossier.get("deferred_until_history_exists") or []:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def _render_flagship_sourcebook(
    lines: list[str], flagship: dict[str, Any]
) -> None:
    statuses = flagship.get("source_status") or {}
    lines.extend(["", "## Flagship Sleeper Sourcebook", ""])
    lines.append(
        "- Source coverage: "
        + "; ".join(
            f"{name.replace('_', ' ')} {status}"
            for name, status in statuses.items()
        )
    )

    lines.extend(["", "### Current Lineup Evidence", ""])
    for team in flagship.get("current_week_lineups") or []:
        lines.append(
            f"- {team['team']}: {team['actual_points']:.2f} actual; "
            f"{team['submitted_projection']:.2f} submitted-lineup projection"
        )
        starters = ", ".join(
            f"{row.get('slot') or 'STARTER'} {row['player']} "
            f"{row['points']:.2f} (proj. {row['projected_points']:.2f})"
            for row in team.get("starters") or []
        )
        lines.append(f"  - Starters: {starters or 'No submitted lineup'}")
        bench = (team.get("bench") or [])[:3]
        if bench:
            lines.append(
                "  - Bench leaders: "
                + ", ".join(
                    f"{row['player']} {row['points']:.2f} "
                    f"(proj. {row['projected_points']:.2f})"
                    for row in bench
                )
            )

    season_records = flagship.get("season_records") or {}
    lines.extend(["", "### Season Record Book", ""])
    if season_records.get("status") != "calculated":
        lines.append("- Season records: awaiting completed scores")
    else:
        lines.append(
            f"- Weeks with scores: {season_records.get('weeks_with_scores', 0)}"
        )
        lines.append(
            "- Highest team score: "
            + _week_record_line(season_records.get("highest_team_score"))
        )
        lines.append(
            "- Lowest team score: "
            + _week_record_line(season_records.get("lowest_team_score"))
        )
        lines.append(
            "- Highest player score: "
            + _week_record_line(season_records.get("highest_player_score"))
        )
        lines.append(
            "- Highest score in a starting lineup: "
            + _week_record_line(
                season_records.get("highest_started_player_score")
            )
        )
        for position, row in (
            season_records.get("started_player_records_by_position") or {}
        ).items():
            lines.append(
                f"  - {position} starter high: {_week_record_line(row)}"
            )

    schedule = flagship.get("schedule") or {}
    lines.extend(["", "### Schedule and Division Desk", ""])
    lines.append(
        f"- Sleeper schedule coverage: {schedule.get('weeks_collected', 0)} weeks; "
        f"regular season through Week {schedule.get('regular_season_end')}"
    )
    for row in schedule.get("strength") or []:
        full_rank = row.get("full_schedule_difficulty_rank")
        remaining_rank = row.get("remaining_schedule_difficulty_rank")
        lines.append(
            f"- {row['team']}: full schedule difficulty "
            f"{_rank_label(full_rank)} (average opponent rank "
            f"{_decimal(row.get('full_schedule_average_opponent_rank'))}); "
            f"remaining {_rank_label(remaining_rank)} (average opponent rank "
            f"{_decimal(row.get('remaining_average_opponent_rank'))})"
        )
    for row in schedule.get("division_context") or []:
        lines.append(
            f"- {row['division_name']}: division strength "
            f"{_rank_label(row.get('division_strength_rank'))}; full-schedule "
            f"difficulty {_rank_label(row.get('full_schedule_difficulty_rank'))}; "
            f"interdivision record {row['interdivision_wins']}-"
            f"{row['interdivision_losses']}-{row['interdivision_ties']}"
        )

    preview = flagship.get("next_week") or {}
    lines.extend(["", f"### Week {preview.get('week') or 'Next'} Slate", ""])
    if not preview.get("games"):
        lines.append(f"- Preview data: {preview.get('status', 'not collected')}")
    for game in preview.get("games") or []:
        sides = game.get("teams") or []
        if len(sides) != 2:
            continue
        lines.append(
            f"- {sides[0]['team']} (submitted "
            f"{sides[0].get('submitted_projection', 0):.2f}; optimal "
            f"{sides[0].get('optimal_projection', 0):.2f}) vs. "
            f"{sides[1]['team']} (submitted "
            f"{sides[1].get('submitted_projection', 0):.2f}; optimal "
            f"{sides[1].get('optimal_projection', 0):.2f})"
        )

    ledger = flagship.get("transaction_ledger") or {}
    summary = ledger.get("season_summary") or {}
    lines.extend(["", "### League Activity Ledger", ""])
    lines.append(
        f"- Season activity: {summary.get('completed', 0)} completed moves; "
        f"{summary.get('trades', 0)} trades; {summary.get('waivers', 0)} waivers; "
        f"{summary.get('free_agents', 0)} free-agent additions"
    )
    recent = ledger.get("recent_records") or []
    lines.append(
        f"- Last {ledger.get('recent_window_days', 7)} days: "
        f"{len(recent)} completed move(s)"
    )
    for transaction in recent:
        lines.append(f"  - {_transaction_line(transaction)}")
    season_trades = [
        row for row in ledger.get("records") or [] if row.get("type") == "trade"
    ]
    if season_trades:
        lines.append("- Season trade file:")
        for transaction in season_trades:
            lines.append(f"  - {_transaction_line(transaction)}")

    drafts = flagship.get("draft_archive") or []
    lines.extend(["", "### Draft Archive", ""])
    if not drafts:
        lines.append("- No draft records returned")
    for draft in drafts:
        label = draft.get("name") or draft.get("draft_id") or "Draft"
        lines.append(
            f"- {label}: {draft.get('season')} {draft.get('type')}; "
            f"{draft.get('pick_count', 0)} picks; "
            f"{draft.get('traded_pick_count', 0)} draft-pick trades"
        )
        if draft.get("first_round"):
            lines.append(
                "  - First round: "
                + "; ".join(
                    f"#{pick['pick_no']} {pick['player']} to {pick['team']}"
                    for pick in draft["first_round"]
                )
            )

    brackets = flagship.get("playoff_brackets") or {}
    lines.extend(["", "### Playoff Bracket Archive", ""])
    lines.append(
        f"- Winners bracket: {len(brackets.get('winners') or [])} records; "
        f"consolation bracket: {len(brackets.get('losers') or [])} records"
    )
    for label, key in (("Winners", "winners"), ("Consolation", "losers")):
        for game in brackets.get(key) or []:
            lines.append(
                f"  - {label} round {game.get('r')}, match {game.get('m')}: "
                f"{game.get('t1_team') or 'TBD'} vs. "
                f"{game.get('t2_team') or 'TBD'}; "
                f"winner {game.get('w_team') or 'TBD'}"
            )

    picks = flagship.get("traded_pick_ledger") or []
    lines.extend(["", "### Future Pick Ledger", ""])
    if not picks:
        lines.append("- No currently traded future picks")
    for pick in picks:
        lines.append(
            f"- {pick.get('season')} Round {pick.get('round')}: "
            f"{pick.get('current_team')} owns {pick.get('original_team')}'s pick "
            f"(previously held by {pick.get('previous_team')})"
        )

    availability = flagship.get("roster_availability") or []
    lines.extend(["", "### Roster Availability Watch", ""])
    if not availability:
        lines.append("- No player availability flags returned")
    for row in availability:
        detail = ", ".join(
            str(value)
            for value in (
                row.get("status"),
                row.get("injury_status"),
                row.get("practice_participation"),
            )
            if value
        )
        lines.append(
            f"- {row['team']}: {row['player']} ({row.get('position') or 'N/A'}, "
            f"{row.get('nfl_team') or 'FA'}) — {detail or 'flagged'}"
        )


def _short(value: dict[str, Any] | None) -> str:
    if not value:
        return "No qualifying candidate"
    subject = value.get("player") or value.get("team") or "Candidate"
    if "points" in value:
        return f"{subject} ({value['points']:.2f} points)"
    if "efficiency" in value:
        return f"{subject} ({value['efficiency']:.1%} efficiency)"
    return str(subject)


def _short_margin(value: dict[str, Any] | None) -> str:
    if not value:
        return "No completed matchup"
    winner = value.get("winner") or {}
    loser = value.get("loser") or {}
    return (
        f"{winner.get('team')} over {loser.get('team')} "
        f"by {value.get('margin', 0):.2f}"
    )


def _rank_label(value: Any) -> str:
    return f"#{value}" if value is not None else "not available"


def _decimal(value: Any) -> str:
    return f"{value:.3f}" if isinstance(value, (int, float)) else "not available"


def _transaction_line(transaction: dict[str, Any]) -> str:
    timestamp = transaction.get("occurred_at") or "time unavailable"
    moves = ", ".join(
        f"{move['player']}: {move['from_team']} to {move['to_team']}"
        for move in transaction.get("player_moves") or []
    )
    picks = ", ".join(
        f"{pick.get('season')} R{pick.get('round')} "
        f"({pick.get('original_team')} original) to {pick.get('to_team')}"
        for pick in transaction.get("draft_picks") or []
    )
    details = "; ".join(value for value in (moves, picks) if value)
    if transaction.get("faab_bid") is not None:
        details = f"{details}; FAAB {transaction['faab_bid']}".strip("; ")
    return f"{timestamp} — {transaction.get('type')}: {details or 'no item detail'}"


def _week_record_line(value: dict[str, Any] | None) -> str:
    if not value:
        return "No qualifying record"
    subject = value.get("player") or value.get("team") or "Record"
    return f"{subject}, {value.get('points', 0):.2f} points in Week {value.get('week')}"
