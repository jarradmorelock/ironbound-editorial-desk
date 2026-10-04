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

    game_timing = dossier.get("game_timing") or {}
    if (game_timing.get("source_status") or {}).get("schedule") != "not_collected":
        _render_game_timing(
            lines,
            game_timing,
            flagship=(league.get("tier") == "flagship"),
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


def _render_game_timing(
    lines: list[str], timing: dict[str, Any], flagship: bool
) -> None:
    statuses = timing.get("source_status") or {}
    starter_days = timing.get("starter_game_days") or []
    day_order = {
        "Thursday": 0,
        "Friday": 1,
        "Saturday": 2,
        "Sunday": 3,
        "Monday": 4,
        "Tuesday": 5,
        "Wednesday": 6,
    }
    calendar: dict[str, list[dict[str, Any]]] = {}
    for player in starter_days:
        day = str(player.get("weekday") or "Schedule unavailable")
        calendar.setdefault(day, []).append(player)

    lines.extend(["", "## NFL Game-Day Timeline", ""])
    lines.append(
        "- Fantasy lineups and points: Sleeper; NFL schedule, box-score, and "
        "late-play context: [nflverse](https://github.com/nflverse/nflverse-data)."
    )
    lines.append(
        "- Source coverage: "
        + "; ".join(
            f"{name.replace('_', ' ')} {status}"
            for name, status in statuses.items()
        )
    )
    if calendar:
        lines.append(
            "- Submitted starters by NFL game day: "
            + "; ".join(
                f"{day} {len(players)}"
                for day, players in sorted(
                    calendar.items(),
                    key=lambda item: (day_order.get(item[0], 99), item[0]),
                )
            )
        )
    if flagship:
        for day, players in sorted(
            (
                (day, players)
                for day, players in calendar.items()
                if day not in {"Sunday", "Schedule unavailable"}
            ),
            key=lambda item: (day_order.get(item[0], 99), item[0]),
        ):
            lines.append(
                f"  - {day}: "
                + ", ".join(
                    f"{row['player']} ({row['team']})" for row in players
                )
            )

    thursday = timing.get("early_week") or timing.get("thursday") or {}
    lines.extend(["", "### Thursday Game Swing", ""])
    lines.append(
        "- This desk includes any Wednesday, Friday, or Saturday game played "
        "before the main Sunday slate and preserves each player's exact game day."
    )
    margin_suppliers = thursday.get("margin_suppliers") or []
    if margin_suppliers:
        for matchup in margin_suppliers:
            lines.append(
                f"- Margin supplied before Sunday: {matchup['final_winner']} defeated "
                f"{matchup['final_loser']} by {matchup['final_margin']:.2f}; its "
                f"early-week scoring edge was {matchup['day_edge_for_winner']:.2f}."
            )
            lines.append(f"  - Early-week starters: {_matchup_day_players(matchup)}")
    elif thursday.get("matchups"):
        lines.append(
            "- No completed matchup had its entire final margin supplied by its "
            "early-week scoring edge."
        )
    else:
        lines.append("- No submitted fantasy starters played before Sunday.")

    positive_limit = 8 if flagship else 2
    negative_limit = 8 if flagship else 2
    positives = (thursday.get("positive_performances") or [])[:positive_limit]
    negatives = (thursday.get("negative_performances") or [])[:negative_limit]
    if positives:
        lines.append("- Positive Thursday/early-week swings:")
        for player in positives:
            lines.append(f"  - {_timing_performance_line(player)}")
    if negatives:
        lines.append("- Negative Thursday/early-week swings:")
        for player in negatives:
            lines.append(f"  - {_timing_performance_line(player)}")
    if thursday.get("matchups") and not positives and not negatives:
        lines.append("- Early-week performance comparisons are awaiting final stats.")

    monday = timing.get("monday") or {}
    lines.extend(["", "### Monday Night Finish", ""])
    lead_changes = monday.get("lead_changes") or []
    tie_breakers = monday.get("tie_breakers") or []
    if lead_changes:
        for matchup in lead_changes:
            lines.append(
                f"- Monday comeback: {matchup['final_winner']} trailed "
                f"{matchup['winner_score_before_day']:.2f}-"
                f"{matchup['loser_score_before_day']:.2f} before Monday scoring, "
                f"then won by {matchup['final_margin']:.2f}."
            )
            lines.append(f"  - Monday starters: {_matchup_day_players(matchup)}")
    if tie_breakers:
        for matchup in tie_breakers:
            lines.append(
                f"- Monday tiebreak: {matchup['final_winner']} and "
                f"{matchup['final_loser']} were level at "
                f"{matchup['winner_score_before_day']:.2f} before Monday scoring; "
                f"the final margin was {matchup['final_margin']:.2f}."
            )
            lines.append(f"  - Monday starters: {_matchup_day_players(matchup)}")
    close_finishes = (monday.get("active_close_finishes") or [])[:3]
    if not lead_changes and not tie_breakers and close_finishes:
        lines.append("- Closest matchups with Monday starters active:")
        for matchup in close_finishes:
            lines.append(
                f"  - {matchup['final_winner']} over {matchup['final_loser']} "
                f"by {matchup['final_margin']:.2f}; "
                f"{_matchup_day_players(matchup)}"
            )
    if not monday.get("matchups"):
        lines.append("- No submitted fantasy starters played Monday.")
    elif not lead_changes and not tie_breakers and not close_finishes:
        lines.append("- Monday finish analysis is awaiting final fantasy scores.")

    late_limit = 10 if flagship else 2
    late_plays = (monday.get("late_play_candidates") or [])[:late_limit]
    if late_plays:
        lines.append("- Late real-life plays involving fantasy starters:")
        for play in late_plays:
            linked = ", ".join(
                f"{row['player']} ({row['team']})"
                for row in play.get("linked_fantasy_starters") or []
            )
            walkoff = "walk-off candidate; " if play.get("walkoff_candidate") else ""
            margin = play.get("smallest_linked_final_margin")
            margin_note = (
                f"; smallest linked fantasy margin {margin:.2f}"
                if margin is not None
                else ""
            )
            lines.append(
                f"  - {walkoff}Q{play.get('quarter')} {play.get('clock')}: "
                f"{play.get('description')} — linked starters: {linked}{margin_note}"
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


def _timing_performance_line(player: dict[str, Any]) -> str:
    projection = player.get("projected_points")
    difference = player.get("projection_difference")
    comparison = ""
    if projection is not None:
        comparison = f" vs. {projection:.2f} projected"
    if difference is not None:
        comparison += f" ({difference:+.2f})"
    opponent = f" vs. {player['opponent']}" if player.get("opponent") else ""
    stat_line = player.get("nfl_stat_line") or "NFL box score unavailable"
    day = f"{player['weekday']} — " if player.get("weekday") else ""
    return (
        f"{day}{player['player']} for {player['team']}: "
        f"{player['fantasy_points']:.2f} fantasy points{comparison}; "
        f"{player.get('nfl_team') or 'NFL team unavailable'}{opponent} — {stat_line}"
    )


def _matchup_day_players(matchup: dict[str, Any]) -> str:
    players = [
        _timing_performance_line(player)
        for team in matchup.get("teams") or []
        for player in team.get("players") or []
    ]
    return "; ".join(players) if players else "No linked starters"


def _timing_performance_line(player: dict[str, Any]) -> str:
    difference = player.get("projection_difference")
    difference_text = f"{difference:+.2f} vs. projection" if difference is not None else ""
    nfl_line = player.get("nfl_stat_line") or "NFL box-score detail unavailable"
    return (
        f"{player['player']} for {player['team']}: "
        f"{player['fantasy_points']:.2f} fantasy points "
        f"({difference_text}); {nfl_line}"
    )
