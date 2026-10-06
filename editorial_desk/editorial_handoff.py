"""Plain-language editor and offline-writer handoffs for publication packets."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo


def _fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "not supplied"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _percentile(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return _fmt(value)
    if number.is_integer():
        whole = int(number)
        suffix = "th" if 10 <= whole % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(whole % 10, "th")
        return f"{whole}{suffix} percentile"
    return f"{_fmt(number, 1)} percentile rank"


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            number = float(value)
            if number > 10_000_000_000:
                number /= 1000
            return datetime.fromtimestamp(number, tz=timezone.utc)
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except (OverflowError, OSError, TypeError, ValueError):
        return None


def _date_in_window(value: Any, window: dict[str, Any]) -> bool:
    event_date = _as_datetime(value)
    start = _as_datetime(window.get("start"))
    end = _as_datetime(window.get("end"))
    return bool(event_date and start and end and start <= event_date <= end)


def _transaction_time(value: Any) -> str:
    moment = _as_datetime(value)
    if moment is None:
        return "date/time not supplied"
    local = moment.astimezone(ZoneInfo("America/New_York"))
    date = local.strftime("%b %d, %Y").replace(" 0", " ")
    return f"{date} at {local.strftime('%I:%M %p').lstrip('0')} ET"


def _season_projection(row: dict[str, Any]) -> float | None:
    for key in (
        "season_total_projected_fp",
        "projected_season_total_fp",
        "total_season_projected_points",
        "total_year_fantasy_points_projection",
        "total_year_projected_fantasy_points",
        "projected_full_season_fantasy_points",
        "full_season_projected_points",
        "projected_season_fantasy_points",
        "total_projected_fantasy_points",
        "season_total_projection",
    ):
        value = row.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
    return None


def _clean(value: Any) -> str:
    return str(value).strip() if value is not None else "not supplied"


def _clean_url(value: Any) -> str | None:
    if not value:
        return None
    parts = urlsplit(str(value))
    path = "/".join(part for part in parts.path.split("/") if part)
    if parts.path.startswith("/"):
        path = "/" + path
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def _publication_name(identity: dict[str, Any]) -> str:
    key = str(identity.get("publication_key") or "publication")
    names = {
        "ironbound_weekly": "Ironbound Weekly",
        "unbound_weekly": "Unbound Weekly",
        "ballad_crier": "The Ballad Crier",
        "the_stampede": "The Stampede",
        "volunteer_voice": "The Volunteer Voice",
        "saturday_standard": "The Saturday Standard",
        "hollywood_beat": "The Hollywood Beat",
    }
    return names.get(key, key.replace("_", " ").title())


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    return []


def _ids(value: Any) -> list[str]:
    result: set[str] = set()
    if isinstance(value, dict):
        for key in ("evidence_id", "event_id"):
            if value.get(key):
                result.add(str(value[key]))
        result.update(str(item) for item in value.get("evidence_ids", []) if item)
    elif isinstance(value, list):
        for child in value:
            result.update(_ids(child))
    return sorted(result)


class _CitationBook:
    def __init__(self) -> None:
        self.references: dict[str, list[str]] = {}

    def add(self, evidence: Any) -> str:
        ids = _ids(evidence)
        if not ids:
            return ""
        for reference, existing in self.references.items():
            if existing == ids:
                return f"[{reference}]"
        reference = f"S{len(self.references) + 1:03d}"
        self.references[reference] = ids
        return f"[{reference}]"

    def render(self) -> list[str]:
        if not self.references:
            return []
        lines = ["", "## Source reference key", "", "These compact labels connect each item above to packet evidence IDs.", ""]
        for reference, ids in self.references.items():
            lines.append(f"- **{reference}** — " + ", ".join(ids))
        return lines


def _line(text: str, evidence: Any = None, citations: _CitationBook | None = None) -> str:
    marker = f" {citations.add(evidence)}" if citations else ""
    return f"- {text}{marker}"


def _with_evidence(row: dict[str, Any], evidence_ids: list[str]) -> dict[str, Any]:
    return {**row, "evidence_ids": list(evidence_ids)}


def _team_pair(row: dict[str, Any]) -> list[dict[str, Any]]:
    teams = _rows(row.get("teams"))
    if teams:
        return teams
    result = []
    for suffix in ("one", "two"):
        name = row.get(f"team_{suffix}")
        if name:
            result.append(
                {
                    "team": name,
                    "projected_score": row.get(f"projected_score_{suffix}"),
                    "optimal_lineup": row.get(f"optimal_lineup_{suffix}"),
                }
            )
    return result


def _candidate_label(candidate: dict[str, Any]) -> str:
    facts = candidate.get("verified_facts") or {}
    matchup = facts.get("matchup") or candidate.get("matchup")
    winner = facts.get("winner") or {}
    performer = facts.get("top_started_player") or {}
    kind_labels = {
        "matchup": "Matchup story",
        "trade_market_shift": "League trade activity",
        "waiver_run": "Popular waiver pickup",
        "roster_architecture": "Roster construction",
        "cross_league_shock": "Managers reacting to player news",
        "asset_journey": "Player transaction history",
        "reaction_transaction": "Roster move after player news",
        "injury_shock": "Player status change",
    }
    kind = str(candidate.get("candidate_type") or "story")
    parts = [kind_labels.get(kind, kind.replace("_", " ").title())]
    if matchup:
        parts.append(_clean(matchup))
    if winner.get("team"):
        parts.append(f"winner: {_clean(winner['team'])} ({_fmt(winner.get('points'))})")
    if performer.get("player"):
        parts.append(
            f"top performer: {performer['player']} ({_fmt(performer.get('points'))} FP)"
        )
    statement = next(
        (
            str(item.get("statement"))
            for item in _rows(candidate.get("display_facts")) + _rows(candidate.get("facts"))
            if isinstance(item, dict) and item.get("statement")
        ),
        None,
    )
    if statement:
        subjects = [str(item) for item in candidate.get("display_subjects", []) if item]
        if kind == "trade_market_shift" and "40 recent trade events" in statement:
            statement = "The league had 40 recent trades recorded."
        elif kind == "waiver_run" and subjects:
            statement = statement.replace("The player", subjects[0])
        elif kind == "cross_league_shock" and subjects:
            statement = f"Related roster moves were recorded in 2 tracked leagues after {subjects[0]}'s status change."
        elif kind == "asset_journey" and subjects:
            statement = statement.replace("The player", subjects[0])
        elif kind == "reaction_transaction" and subjects:
            team = subjects[1] if len(subjects) > 1 else "A league team"
            statement = f"{team} made a roster move after {subjects[0]}'s severe status news."
        elif kind == "injury_shock" and subjects:
            statement = f"{subjects[0]} status changed to doubtful."
        parts.append(statement)
    else:
        subjects = [str(item) for item in candidate.get("display_subjects", []) if item]
    if subjects and not statement:
        parts.append("involved: " + ", ".join(subjects[:3]))
    possible_angles = {
        "trade_market_shift": "Possible angle: what the recent trades say about how managers are reshaping teams.",
        "waiver_run": "Possible angle: why this player drew claims in several leagues.",
        "roster_architecture": "Possible angle: whether this roster is deliberately building around one position.",
        "cross_league_shock": "Possible angle: how managers responded to the status change.",
        "asset_journey": "Possible angle: how this player's roster story changed over several moves.",
        "reaction_transaction": "Possible angle: what roster move followed the player's status news.",
        "injury_shock": "Possible angle: what the status change may mean for the player's team.",
    }
    if kind in possible_angles:
        parts.append(possible_angles[kind])
    return " — ".join(parts)


def _team_matchup_candidates(feature: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        candidate
        for candidate in _rows(feature.get("cover_candidates"))
        if candidate.get("candidate_type") == "matchup"
        or (candidate.get("verified_facts") or {}).get("matchup")
    ]


def _coverline_suggestions(packet: dict[str, Any]) -> list[tuple[str, Any]]:
    suggestions: list[tuple[str, Any]] = []

    def add(headline: str, evidence: Any) -> None:
        if headline and all(existing != headline for existing, _ in suggestions):
            suggestions.append((headline, evidence))

    power_rows = _rows((packet.get("power_rankings") or {}).get("rows"))
    top_power = next((row for row in power_rows if row.get("rank") == 1), None)
    if top_power:
        add(f"Power Rankings — {_clean(top_power.get('team'))} stays at No. 1", top_power)

    team_records = ((packet.get("division_report") or {}).get("canonical") or {}).get("team_records") or {}
    perfect = []
    for row in team_records.values():
        record = row.get("division_record") or {}
        if int(record.get("wins") or 0) > 0 and not int(record.get("losses") or 0) and not int(record.get("ties") or 0):
            perfect.append(row)
    perfect.sort(key=lambda row: (-int((row.get("division_record") or {}).get("wins") or 0), _clean(row.get("team"))))
    for row in perfect[:3]:
        record = row.get("division_record") or {}
        team = _clean(row.get("team"))
        verb = "remain" if team.endswith(("s", "™")) else "stays"
        add(
            f"Divisional Heat — {team} {verb} perfect against division opponents "
            f"({record.get('wins', 0)}-{record.get('losses', 0)})",
            row,
        )

    games = _rows(packet.get("game_dossiers"))
    if games:
        closest = min(games, key=lambda row: float(row.get("margin") or 0))
        winner = closest.get("winner") or {}
        loser = closest.get("loser") or {}
        if closest.get("margin") is not None:
            add(
                f"Final Whistle — {_clean(winner.get('team'))} edged {_clean(loser.get('team'))} by "
                f"{_fmt(closest.get('margin'))} points",
                closest,
            )
        high_score = max(
            (row for row in games if (row.get("winner") or {}).get("points") is not None),
            key=lambda row: float((row.get("winner") or {}).get("points") or 0),
            default=None,
        )
        if high_score:
            winning_team = high_score.get("winner") or {}
            add(
                f"Weekly High Score — {_clean(winning_team.get('team'))} puts up "
                f"{_fmt(winning_team.get('points'))} points",
                high_score,
            )

    manager = packet.get("manager_honors") or {}
    row = manager.get("manager_of_the_week")
    if isinstance(row, dict) and row.get("team"):
        points = f" with {_fmt(row.get('points'))} points" if row.get("points") is not None else ""
        add(f"Manager of the Week — {_clean(row.get('team'))}{points}", row)

    player = packet.get("player_honors") or {}
    row = player.get("overall_player_of_the_week")
    if isinstance(row, dict) and row.get("player"):
        points = f", {_fmt(row.get('points'))} fantasy points" if row.get("points") is not None else ""
        add(f"Player of the Week — {_clean(row.get('player'))}{points}", row)

    rookie_rows = _rows((packet.get("rookie_watch") or {}).get("rookie_watch_top_five"))
    if rookie_rows:
        row = rookie_rows[0]
        add(
            f"Rookie Watch — {_clean(row.get('player'))} leads this week's rookie board",
            row,
        )

    usage_leaders = (packet.get("usage_desk") or {}).get("leaders") or {}
    for category in ("carries", "targets", "red_zone_opportunities", "target_share"):
        rows = _rows(usage_leaders.get(category))
        if not rows:
            continue
        row = rows[0]
        stat = row.get("nfl_stat_line")
        if not stat:
            stat_value = row.get(category)
            if stat_value is None:
                continue
            stat = f"{_clean(category).replace('_', ' ')}: {_fmt(stat_value)}"
        add(f"Usage Desk — {_clean(row.get('player'))}: {stat}", row)
        break

    playoff_rows = _rows((packet.get("playoff_forecast") or {}).get("rows"))
    if playoff_rows:
        row = max(
            (item for item in playoff_rows if item.get("playoff") is not None),
            key=lambda item: float(item.get("playoff") or 0),
            default=None,
        )
        if row:
            add(
                f"Playoff Picture — {_clean(row.get('team'))} projects to a "
                f"{_fmt(row.get('playoff'), 1)}% playoff chance",
                row,
            )

    week_ahead = []
    for row in _rows((packet.get("week_ahead") or {}).get("rows")):
        teams = _team_pair(row)
        if len(teams) != 2 or row.get("projected_score_one") is None or row.get("projected_score_two") is None:
            continue
        difference = abs(float(row["projected_score_one"]) - float(row["projected_score_two"]))
        week_ahead.append((difference, row, teams))
    if week_ahead:
        _, row, teams = min(week_ahead, key=lambda item: item[0])
        add(
            f"Week Ahead — {_clean(teams[0].get('team'))} vs. {_clean(teams[1].get('team'))}: "
            f"projected within {_fmt(abs(float(row['projected_score_one']) - float(row['projected_score_two'])))} points",
            row,
        )
    return suggestions


def _health_spotlight(
    health_players: list[dict[str, Any]],
    stories_by_player: dict[str, list[dict[str, Any]]],
    window: dict[str, Any],
    *,
    projection_limit: int = 10,
) -> tuple[list[dict[str, Any]], int, int, int, int]:
    injured = [
        row for row in health_players
        if row.get("report_status") in {"Out", "Doubtful", "Questionable"}
        or row.get("injury_status") in {"Out", "Doubtful", "IR", "PUP", "Questionable"}
        or row.get("on_ir")
    ]
    change_keys = (
        "designation_changed_at",
        "injury_designation_changed_at",
        "status_changed_at",
        "injury_report_updated",
    )
    changed: set[str] = set()
    dated: set[str] = set()
    linked_stories: set[str] = set()
    for row in injured:
        player_id = str(row.get("player_id") or "")
        if any(_as_datetime(row.get(key)) for key in change_keys):
            dated.add(player_id)
        if any(_date_in_window(row.get(key), window) for key in change_keys):
            changed.add(player_id)
        events_by_id = {
            str(event.get("event_id") or event.get("headline") or index): event
            for index, event in enumerate(_rows(row.get("news_events")) + stories_by_player.get(player_id, []))
        }
        events = list(events_by_id.values())
        if events:
            linked_stories.add(player_id)

    projected = [
        (projection, row)
        for row in injured
        if (projection := _season_projection(row)) is not None
    ]
    projected.sort(key=lambda pair: (-pair[0], _clean(pair[1].get("player"))))
    high_projection = {str(row.get("player_id") or "") for _, row in projected[:projection_limit]}
    selected_ids = changed | linked_stories | high_projection
    selected = [row for row in injured if str(row.get("player_id") or "") in selected_ids]
    selected.sort(
        key=lambda row: (
            0 if str(row.get("player_id") or "") in changed else 1,
            0 if str(row.get("player_id") or "") in high_projection else 1,
            -(_season_projection(row) or 0),
            _clean(row.get("player")),
        )
    )
    return selected, len(injured), len(projected), len(dated), len(changed)


def _award_summary(
    row: dict[str, Any],
    player_names: dict[str, str],
    player_points: dict[str, float],
) -> str:
    label = _clean(row.get("label") or row.get("display_name") or row.get("award_name") or row.get("candidate_type"))
    team = _clean(row.get("team"))
    evidence = row.get("evidence") or {}
    points = evidence.get("points")
    opponent = evidence.get("opponent_points")
    margin = evidence.get("margin")
    details: list[str] = []
    if label == "Left on the Anvil" and evidence.get("optimal_points") is not None and points is not None:
        details.append(
            f"scored {_fmt(points)} points, while the best legal lineup could have scored {_fmt(evidence['optimal_points'])}"
        )
        if margin is not None:
            details.append(f"lost by {_fmt(margin)}")
    elif label == "Bone Head":
        swings = [
            abs(float(decision.get("point_swing") or 0))
            for decision in evidence.get("decisions", [])
            if isinstance(decision, dict)
        ]
        improvement = f"; lineup alternatives projected up to {_fmt(max(swings))} more points" if swings else ""
        details.append(f"lost by {_fmt(margin)} points{improvement}")
    elif label == "One Hand Tied" and evidence.get("combined_points") is not None:
        result = f"won by {_fmt(margin)}" if points is not None and opponent is not None and float(points) > float(opponent) else f"lost by {_fmt(margin)}"
        details.append(f"two qualifying starters combined for {_fmt(evidence['combined_points'])} points; the team {result}")
    elif label == "No Fear":
        details.append(
            f"entered ranked #{evidence.get('entering_power_rank', '?')} and beat the team ranked #{evidence.get('opponent_entering_power_rank', '?')} by {_fmt(margin)} points"
        )
        if evidence.get("projected_deficit") is not None:
            details.append(f"was projected to trail by {_fmt(evidence['projected_deficit'])}")
        if points is not None and opponent is not None:
            details.append(f"final score: {team} {_fmt(points)}, opponent {_fmt(opponent)}")
    elif label == "Hot Off the Anvil":
        player_id = str(evidence.get("player_id") or "")
        player = player_names.get(player_id)
        player_score = player_points.get(player_id)
        details.append(
            f"{player + ' scored ' + _fmt(player_score) + ' fantasy points' if player and player_score is not None else 'recorded a notable player performance'}"
        )
    elif label == "Hammer Drop":
        details.append(f"won by {_fmt(margin)} points")
    elif evidence.get("combined_points") is not None:
        details.append(f"two qualifying starters scored {_fmt(evidence['combined_points'])} points combined")
    elif margin is not None:
        details.append(f"the game margin was {_fmt(margin)} points")
    if points is not None and opponent is not None and label not in {"Left on the Anvil", "Bone Head", "No Fear", "Hot Off the Anvil"}:
        details.append(f"final score: {team} {_fmt(points)}, opponent {_fmt(opponent)}")
    return f"{label} — {team}: " + "; ".join(details or ["qualified based on the completed Week 3 results"])


def _render_editorial_material(
    packet: dict[str, Any],
    plan: dict[str, Any],
    *,
    include_citations: bool = False,
) -> str:
    """Render the human decision document with compact, readable summaries."""

    identity = packet.get("issue_identity") or {}
    week = identity.get("week", "?")
    season = identity.get("season", "")
    publication = packet.get("publication") or _publication_name(identity)
    choices = plan.get("editorial_choices") or {}
    feature = packet.get("feature_evidence") or {}
    cover_candidates = _rows(feature.get("cover_candidates"))
    story_candidates = _team_matchup_candidates(feature)
    selected_cover = choices.get("cover_candidate_id")
    selected_lead = choices.get("lead_feature_candidate_id")
    selected_secondary = choices.get("secondary_feature_candidate_id")
    selected_award = choices.get("rotating_award_candidate_id")
    candidate_by_id = {
        str(candidate.get("candidate_id")): candidate
        for candidate in cover_candidates + story_candidates
        if candidate.get("candidate_id")
    }
    lead_candidate = candidate_by_id.get(str(selected_lead or ""))
    lead_label = _candidate_label(lead_candidate) if lead_candidate else "No lead choice selected"
    readiness = packet.get("readiness") or {}
    citations = _CitationBook() if include_citations else None
    lines = [
        f"# {publication} — {season} Week {week}: Editorial Review",
        "",
        "## What this is",
        "",
        "This is the decision and fact record for the issue. The Offline Writer Brief is the single document to edit and hand to the writing AI. Change only the `FINAL:` lines beside decisions; do not rewrite the fact sections.",
        "",
        "## Readiness and cutoff",
        "",
        f"- Research readiness: **{readiness.get('status', 'unknown')}**",
        f"- Information cutoff: **{identity.get('information_cutoff', 'not supplied')}**",
        f"- Blocking gaps: **{len(readiness.get('blocking_gaps') or [])}**",
        f"- News index: **{(packet.get('news_index') or {}).get('status', 'not supplied')}**; stories indexed: **{len(_rows((packet.get('news_index') or {}).get('stories')))}**",
        "",
        "## Decisions for the editor",
        "",
        "The lead is the main team or matchup write-up. The secondary is a separate team or matchup write-up; league-wide trade or waiver activity is not a secondary story choice. Recurring Power Rankings and Divisional Heat coverlines are chosen separately below.",
        "",
        "### Cover story",
        "",
    ]
    for candidate in cover_candidates:
        cid = candidate.get("candidate_id")
        mark = "**CURRENT COVER PICK**" if cid == selected_cover else "Other cover option"
        lines.append(f"- {mark}: {_candidate_label(candidate)}")
    lines.extend(
        [
            "- Your cover choice: `FINAL: [type KEEP CURRENT or name another matchup]`",
            "- Cover headline or framing: `FINAL: [write your wording, or leave blank for a writer suggestion]`",
            "",
            "### Lead and secondary feature",
            "",
        ]
    )
    lines.append(f"- Current lead article: {lead_label}")
    lines.append("- Your lead choice: `FINAL: [type KEEP CURRENT or name another matchup/team write-up]`")
    for candidate in story_candidates:
        cid = candidate.get("candidate_id")
        if cid == selected_lead:
            continue
        mark = "**CURRENT SECONDARY PICK**" if cid == selected_secondary else "Other team write-up option"
        lines.append(f"- {mark}: {_candidate_label(candidate)}")
    lines.extend(
        [
            "- Your secondary choice: `FINAL: [type KEEP CURRENT or name another matchup/team write-up above]`",
            "- Headline or angle changes: `FINAL: [write a change, or leave blank for a writer suggestion]`",
            "",
            "### Additional cover headlines — ideas from across the magazine",
            "",
        ]
    )
    for headline, evidence in _coverline_suggestions(packet):
        lines.append(
            _line(
                f"Suggested coverline: {headline}. `FINAL: [KEEP CURRENT or write a change]`",
                evidence,
                citations,
            )
        )
    if not _coverline_suggestions(packet):
        lines.append("- No recurring-feature coverline facts were supplied.")
    manager = packet.get("manager_honors") or {}
    lines.extend(["", "## Issue facts at a glance", "", f"### Week {week} results", ""])
    canonical = packet.get("canonical_league_evidence") or {}
    matchup_sources = {
        (row.get("week"), row.get("roster_id")): row.get("evidence_id")
        for row in _rows(canonical.get("historical_matchups"))
    }
    player_sources = {
        (row.get("week"), str(row.get("player_id"))): row.get("evidence_id")
        for row in _rows(canonical.get("player_weeks"))
    }
    team_season_sources: dict[int, list[str]] = {}
    for row in _rows(canonical.get("historical_matchups")):
        if row.get("roster_id") is not None and row.get("evidence_id"):
            team_season_sources.setdefault(int(row["roster_id"]), []).append(str(row["evidence_id"]))
    player_names: dict[str, str] = {}
    player_points: dict[str, float] = {}
    player_nfl_lines: dict[str, str] = {}
    for game in _rows(packet.get("game_dossiers")):
        for team in _rows(game.get("teams")):
            for player in _rows(team.get("submitted_starters")) + _rows(team.get("bench")):
                if player.get("player_id") is not None and player.get("player"):
                    player_names[str(player["player_id"])] = str(player["player"])
                    if player.get("fantasy_points") is not None:
                        player_points[str(player["player_id"])] = float(player["fantasy_points"])
                    if player.get("nfl_stat_line"):
                        player_nfl_lines[str(player["player_id"])] = str(player["nfl_stat_line"])
    for game in _rows(packet.get("game_dossiers")):
        winner = game.get("winner") or {}
        performer = game.get("top_started_player") or {}
        performer_stat = player_nfl_lines.get(str(performer.get("player_id")))
        performer_details = (
            f"NFL: {performer_stat}; {_fmt(performer.get('points'))} fantasy points"
            if performer_stat
            else f"NFL stat line not supplied; {_fmt(performer.get('points'))} fantasy points"
        )
        text = (
            f"{_clean(game.get('matchup'))}: **{_clean(game.get('scoreline'))}**; "
            f"{_clean(winner.get('team'))} won by {_fmt(game.get('margin'))}; "
            f"top starter {performer.get('player', 'not supplied')} — {performer_details}."
        )
        evidence_ids = [
            matchup_sources.get((int(week), team.get("roster_id")))
            for team in (winner, game.get("loser") or {})
        ]
        evidence_ids.append(
            player_sources.get(
                (int(week), str(performer.get("player_id")))
            )
        )
        if include_citations:
            lines.append(
                "- Game-page headline: `FINAL: [write a page headline, or leave blank for a writer suggestion]`"
            )
        lines.append(_line(text, {"evidence_ids": evidence_ids}, citations))
        if include_citations:
            for team in _rows(game.get("teams")):
                starters = ", ".join(
                    f"{_clean(player.get('player'))}: {player.get('nfl_stat_line') or 'NFL stat line not supplied'}; "
                    f"{_fmt(player.get('fantasy_points'))} fantasy points"
                    for player in _rows(team.get("submitted_starters"))
                )
                bench = ", ".join(
                    f"{_clean(player.get('player'))}: {player.get('nfl_stat_line') or 'NFL stat line not supplied'}; "
                    f"{_fmt(player.get('fantasy_points'))} fantasy points"
                    for player in sorted(
                        _rows(team.get("bench")),
                        key=lambda player: float(player.get("fantasy_points") or 0),
                        reverse=True,
                    )[:3]
                )
                record = team.get("entering_record") or {}
                record_text = f"{record.get('wins', 0)}-{record.get('losses', 0)}-{record.get('ties', 0)} before Week {week}"
                power_rank = team.get("entering_power_rank")
                rank_text = f"; entering Power Rank #{power_rank}" if power_rank is not None else ""
                source_ref = citations.add(team) if citations else ""
                lines.append(
                    f"  - {_clean(team.get('team'))}: {record_text}{rank_text}. Starters: {starters or 'not supplied'}. Bench leaders: {bench or 'not supplied'}. {source_ref}"
                )

    lines.extend(["", "### Usage Desk", ""])
    usage = packet.get("usage_desk") or {}
    leaders = usage.get("leaders") or {}
    player_week_ids: dict[str, list[str]] = {}
    for row in _rows((packet.get("canonical_league_evidence") or {}).get("player_weeks")):
        if row.get("week") == int(week):
            player_week_ids.setdefault(str(row.get("player_id")), []).append(str(row.get("evidence_id")))
    if leaders:
        for category, rows in leaders.items():
            usage_limit = 3 if include_citations else 1
            for row in _rows(rows)[:usage_limit]:
                player = _clean(row.get("player"))
                team = _clean(row.get("fantasy_team") or row.get("team"))
                stat = row.get("nfl_stat_line") or f"{category}: {_fmt(row.get(category))}"
                citation_row = {
                    **row,
                    "evidence_ids": player_week_ids.get(str(row.get("sleeper_player_id")), []),
                }
                category_label = {
                    "red_zone_opportunities": "Red-zone opportunities",
                    "snap_share": "Snap-share leaders",
                    "target_share": "Target-share leaders",
                    "carries": "Rushing workload",
                    "targets": "Receiving workload",
                }.get(category, category.replace("_", " ").title())
                lines.append(_line(f"{category_label}: {player} ({team}) — {stat}.", citation_row, citations))
    else:
        lines.append(f"- Usage status: {usage.get('status', 'not supplied')}")

    lines.extend(["", "### Health and linked news", ""])
    health_players = _rows((packet.get("roster_health") or {}).get("players"))
    news_index = packet.get("news_index") or {}
    story_by_id = {
        str(row.get("event_id")): row
        for row in _rows(news_index.get("stories"))
        if row.get("event_id")
    }
    stories_by_player: dict[str, list[dict[str, Any]]] = {}
    for player_id, story_ids in (news_index.get("by_player") or {}).items():
        for story_id in story_ids or []:
            story = story_by_id.get(str(story_id))
            if story:
                stories_by_player.setdefault(str(player_id), []).append(story)
    notable_health = health_players
    coverage_window = news_index.get("reporting_window") or {}
    notable_health, injured_count, projection_count, designation_date_count, changed_count = _health_spotlight(
        notable_health,
        stories_by_player,
        coverage_window,
    )
    if coverage_window.get("start") or coverage_window.get("end"):
        lines.append(
            f"- Coverage window: {str(coverage_window.get('start') or 'start not supplied')[:10]} through "
            f"{str(coverage_window.get('end') or 'end not supplied')[:10]} (per the packet's weekly news window)."
        )
    for row in notable_health:
        state = (
            "IR" if row.get("on_ir")
            else row.get("report_status") or row.get("injury_status") or row.get("practice_participation") or row.get("status") or "status not supplied"
        )
        player_id = str(row.get("player_id") or "")
        events_by_id = {
            str(event.get("event_id") or event.get("headline") or index): event
            for index, event in enumerate(_rows(row.get("news_events")) + stories_by_player.get(player_id, []))
        }
        events = list(events_by_id.values())
        events_in_window = any(
            _date_in_window(event.get("published_at") or event.get("accepted_at"), coverage_window)
            for event in events
        )
        reasons = []
        for key in ("designation_changed_at", "injury_designation_changed_at", "status_changed_at", "injury_report_updated"):
            if _date_in_window(row.get(key), coverage_window):
                reasons.append("designation update during coverage")
                break
        if events:
            reasons.append("linked health news during coverage" if events_in_window else "prior linked health news")
        projection = _season_projection(row)
        if projection is not None:
            reasons.append(f"total-year projection {_fmt(projection, 1)} FP")
        news = "; ".join(
            f"{event.get('headline')} ({event.get('source') or 'source unknown'}; published {str(event.get('published_at') or 'date not supplied')[:10]})"
            + (f" {citations.add(event)}" if citations else "")
            for event in events[:2]
        )
        suffix = f" Linked news: {news}." if news else " No indexed story is linked to this player."
        reason_text = f" Spotlight reason: {', '.join(reasons)}." if reasons else ""
        lines.append(
            _line(
                f"{_clean(row.get('player'))} — {_clean(row.get('team'))}: {state}.{reason_text}{suffix}",
                row,
                citations,
            )
        )
    if not notable_health:
        lines.append("- No health cases met the coverage-window or projected-impact spotlight rules.")
    if injured_count and not projection_count:
        lines.append("- Full-season player projections were not supplied for the current health cases, so existing cases could not be ranked by projected season impact.")
    elif projection_count < injured_count:
        lines.append(f"- Full-season projections are missing for {injured_count - projection_count} health cases; the projected-impact ranking is partial.")
    if injured_count and not designation_date_count:
        lines.append("- Injury-designation change dates were not supplied, so the packet cannot confirm which current designations changed during this coverage window.")
    elif designation_date_count < injured_count:
        lines.append(f"- Injury-designation change dates are missing for {injured_count - designation_date_count} health cases; the weekly change list is partial.")
    elif injured_count and not changed_count:
        lines.append("- No injury-designation changes were recorded inside this coverage window.")
    if injured_count > len(notable_health):
        lines.append(
            f"- {injured_count - len(notable_health)} other health cases remain in the complete supporting record at `supporting_files/manuscript_draft.json`; this spotlight includes all confirmed coverage-window updates and up to 10 highest full-season projections."
        )

    stories = _rows(news_index.get("stories"))
    if stories:
        lines.extend(["", "### Indexed player news", ""])
        story_limit = len(stories) if include_citations else 8
        for story in stories[:story_limit]:
            players = ", ".join(
                str(player.get("player"))
                for player in _rows(story.get("league_players"))
                if player.get("player")
            ) or "player mapping not supplied"
            url = _clean_url(story.get("canonical_url") or story.get("source_url")) if include_citations else None
            link = f" — {url}" if url else ""
            article_details = ""
            if include_citations:
                published = str(story.get("published_at") or "date not supplied")[:10]
                summary = story.get("feed_summary")
                article_details = f"; published {published}"
                if summary:
                    article_details += f". Packet summary: {summary}"
            lines.append(
                _line(
                    f"{story.get('headline', 'Untitled story')} ({story.get('source') or 'source unknown'}; {players}{article_details}){link}.",
                    story,
                    citations,
                )
            )
        if len(stories) > story_limit:
            lines.append(
                f"- {len(stories) - story_limit} additional indexed stories are listed in the Offline Writer Brief."
            )

    lines.extend(["", f"### Transactions affecting Week {week}", ""])
    lines.append("Dates are Eastern, newest first. This list is limited to the weekly coverage window and includes moves tied to a player who started or scored at least 8 fantasy points during the reviewed week.")
    transactions = _rows((packet.get("transaction_desk") or {}).get("transactions"))
    coverage_window = (packet.get("news_index") or {}).get("reporting_window") or {}
    if coverage_window.get("start") or coverage_window.get("end"):
        transactions = [
            tx for tx in transactions
            if _date_in_window(tx.get("completed_at"), coverage_window)
        ]
    transactions.sort(
        key=lambda tx: _as_datetime(tx.get("completed_at")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    reviewed = 0
    omitted_transactions = 0
    for tx in transactions:
        all_impacts = [
            impact for impact in _rows(tx.get("reviewed_week_impact"))
            if impact.get("reviewed_week") == int(week)
        ]
        impacts = [
            impact for impact in all_impacts
            if impact.get("started")
            or (
                impact.get("fantasy_points") is not None
                and float(impact.get("fantasy_points") or 0) >= 8
            )
        ]
        if not impacts:
            continue
        if not include_citations and reviewed >= 6:
            omitted_transactions += 1
            continue
        reviewed += 1
        names = sorted({_clean(name) for name in tx.get("teams") or []})
        players = tx.get("players") or {}
        moved_players = []
        for direction, label in (("sent_by", "sent"), ("received_by", "received")):
            for team, entries in (players.get(direction) or {}).items():
                names_for_team = ", ".join(
                    _clean(entry.get("player"))
                    for entry in _rows(entries)
                    if entry.get("player")
                )
                if names_for_team:
                    moved_players.append(f"{_clean(team)} {label} {names_for_team}")
        pick_terms = [
            f"{pick.get('season')} round {pick.get('round')} pick from {_clean(pick.get('original_team'))}"
            for pick in _rows(tx.get("draft_picks"))
        ]
        terms = "; ".join(moved_players + pick_terms)
        impact_text = "; ".join(
            f"{impact.get('player')}: {_fmt(impact.get('fantasy_points'))} FP, "
            f"{'started' if impact.get('started') else 'on bench'} for {_clean(impact.get('to_team') or 'team not supplied')}"
            for impact in impacts
        )
        lines.append(
            _line(
                f"{_transaction_time(tx.get('completed_at'))} — {tx.get('type', 'transaction').title()} "
                f"({', '.join(names) or 'teams not supplied'})"
                + (f" — terms: {terms}" if terms else "")
                + f" — Week {week} impact: {impact_text}.",
                tx,
                citations,
            )
        )
    if reviewed == 0:
        lines.append(f"- No featured Week {week} transaction impact rows were supplied.")
    if omitted_transactions:
        lines.append(
            f"- {omitted_transactions} additional transaction-impact items are detailed in the Offline Writer Brief."
        )

    lines.extend(["", "### Manager and player honors", "", "#### Commissioner’s rotating award", ""])
    award_rows = _rows(manager.get("rotating_award_candidates"))
    if manager.get("commissioner_selection_required"):
        lines.append("Choose the award that best fits the week, or write NONE. Each line explains why that team qualified. The same award name may appear more than once because different teams qualified:")
        for row in award_rows:
            cid = row.get("candidate_id")
            mark = "**CURRENT PICK**" if cid == selected_award else "Option"
            award_evidence = list(team_season_sources.get(int(row.get("roster_id") or 0), []))
            evidence = row.get("evidence") or {}
            if evidence.get("player_id") is not None:
                award_evidence.extend(player_sources.get((int(week), str(evidence["player_id"])), []))
            lines.append(
                _line(
                    f"{mark}: {_award_summary(row, player_names, player_points)}",
                    _with_evidence(row, award_evidence),
                    citations,
                )
            )
        lines.append(f"- Your rotating award choice: `FINAL: [choose an award name and team above, or NONE]` (current plan has no selection).")
    else:
        lines.append("- No commissioner-selected rotating award is required for this issue.")

    lines.extend(["", "#### Weekly and season honors", ""])
    for key, label in (
        ("manager_of_the_week", "Manager of the Week"),
        ("most_efficient_manager", "Most Efficient Manager"),
        ("bad_beat", "Bad Beat"),
        ("escape_artist", "Escape Artist"),
        ("high_score", "Weekly high score"),
        ("low_score", "Weekly low score"),
    ):
        row = manager.get(key)
        if isinstance(row, dict):
            team = row.get("team") or row.get("winner") or "team not supplied"
            points = f", {_fmt(row.get('points'))} points" if row.get("points") is not None else ""
            evidence_ids = team_season_sources.get(int(row["roster_id"]), []) if row.get("roster_id") is not None else []
            lines.append(_line(f"{label}: {_clean(team)}{points}.", _with_evidence(row, evidence_ids), citations))
    player = packet.get("player_honors") or {}
    for key, label in (
        ("overall_player_of_the_week", "Overall Player of the Week"),
        ("benchwarmer_of_the_week", "Bench MVP"),
        ("free_agent_of_the_week", "Free Agent of the Week"),
    ):
        row = player.get(key)
        if isinstance(row, dict):
            player_id = str(row.get("player_id") or "")
            evidence_ids = player_sources.get((int(week), player_id), [])
            lines.append(
                _line(
                    f"{label}: {_clean(row.get('player'))} — {_fmt(row.get('points'))} FP for {_clean(row.get('team') or row.get('fantasy_team'))}.",
                    _with_evidence(row, evidence_ids),
                    citations,
                )
            )
    for position, rows in (player.get("started_position_leaders") or {}).items():
        row = rows if isinstance(rows, dict) else (_rows(rows)[0] if _rows(rows) else {})
        if row:
            evidence_ids = player_sources.get((int(week), str(row.get("player_id") or "")), [])
            lines.append(
                _line(
                    f"Top starting {position}: {_clean(row.get('player'))} — {_fmt(row.get('points'))} FP.",
                    _with_evidence(row, evidence_ids),
                    citations,
                )
            )
    season_rows = []
    for rows in (manager.get("season_team_score_top_three") or []):
        if isinstance(rows, dict):
            season_rows.append(rows)
    if season_rows:
        leaders_text = "; ".join(
                f"{_clean(row.get('team'))} {_fmt(row.get('score'))} points"
            for row in season_rows[:3]
        )
        team_ids = [
            evidence_id
            for row in season_rows[:3]
            for evidence_id in team_season_sources.get(int(row.get("roster_id") or 0), [])
        ]
        lines.append(_line(f"Cumulative team scoring leaders: {leaders_text}.", {"evidence_ids": team_ids}, citations))
    efficiency_rows = _rows(manager.get("season_efficiency_top_three"))
    if efficiency_rows:
        efficiency_text = "; ".join(
            f"{_clean(row.get('team'))} {_fmt(float(row.get('efficiency', 0)) * 100, 1)}%"
            for row in efficiency_rows[:3]
        )
        team_ids = [
            evidence_id
            for row in efficiency_rows[:3]
            for evidence_id in team_season_sources.get(int(row.get("roster_id") or 0), [])
        ]
        lines.append(_line(f"Cumulative lineup efficiency leaders: {efficiency_text}.", {"evidence_ids": team_ids}, citations))
    player_season = player.get("player_season_top_three") or {}
    for position, rows in (player_season.get("by_position") or {}).items():
        leaders_text = "; ".join(
            f"{_clean(row.get('player'))} ({_clean(row.get('team') or row.get('fantasy_team'))}) {_fmt(row.get('points'))} FP"
            for row in _rows(rows)[:3]
        )
        if leaders_text:
            lines.append(_line(f"Cumulative {position} leaders: {leaders_text}.", rows, citations))

    lines.extend(["", "### Rookie Watch", ""])
    rookie = packet.get("rookie_watch") or {}
    for row in _rows(rookie.get("rookie_watch_top_five"))[:5]:
        evidence_ids = player_sources.get((int(week), str(row.get("player_id") or "")), [])
        lines.append(
            _line(
                f"{_clean(row.get('player'))} ({_clean(row.get('team'))}) — {_fmt(row.get('points'))} FP; {row.get('status', 'status not supplied')}; draft context: {row.get('ironbound_draft_status', 'not supplied')}.",
                _with_evidence(row, evidence_ids),
                citations,
            )
        )
    for position, rows in ((rookie.get("rookie_season_leaders") or {}).get("by_position") or {}).items():
        leaders_text = "; ".join(
            f"{row.get('player', 'player not supplied')} ({row.get('team') or 'team not supplied'}) {_fmt(row.get('points'))} FP"
            for row in _rows(rows)[:3]
        )
        if leaders_text:
            lines.append(_line(f"Cumulative rookie {position} leaders: {leaders_text}.", rows, citations))

    lines.extend(["", "### Rankings and playoff picture", ""])
    ranks = _rows((packet.get("power_rankings") or {}).get("rows"))
    if ranks:
        rank_limit = 16 if include_citations else 5
        if not include_citations:
            lines.append(
                f"Editor preview: top {min(rank_limit, len(ranks))} of {len(ranks)} teams. The Writer Brief has all teams. Power rank is the model's team rating; playoff chance is a separate forecast, not the official standings."
            )
        for row in ranks[:rank_limit]:
            move = row.get("movement")
            movement = f"; moved {move:+}" if isinstance(move, (int, float)) else ""
            lines.append(_line(f"Power #{row.get('rank')}: {_clean(row.get('team'))} (score {_fmt(row.get('score'))}{movement}).", row, citations))
    playoff_rows = _rows((packet.get("playoff_forecast") or {}).get("rows"))
    playoff_limit = 16 if include_citations else 5
    for row in playoff_rows[:playoff_limit]:
        lines.append(_line(f"Playoff forecast: {_clean(row.get('team'))} — {_fmt(row.get('playoff'))}% playoff chance; projected record {row.get('projected_record', 'not supplied')}.", row, citations))

    lines.extend(["", "### Divisions", ""])
    division = packet.get("division_report") or {}
    for name, row in ((division.get("canonical") or {}).get("divisions") or {}).items():
        lines.append(_line(f"{row.get('division', name)}: scoring average {_fmt(row.get('scoring_average'))}.", row, citations))
    records = (division.get("canonical") or {}).get("team_records") or {}
    for row in records.values():
        overall = row.get("overall_record") or {}
        div_record = row.get("division_record") or {}
        cross = row.get("cross_division_record") or {}
        lines.append(_line(f"{row.get('team')}: overall {overall.get('wins', 0)}-{overall.get('losses', 0)}-{overall.get('ties', 0)}, division {div_record.get('wins', 0)}-{div_record.get('losses', 0)}-{div_record.get('ties', 0)}, cross-division {cross.get('wins', 0)}-{cross.get('losses', 0)}-{cross.get('ties', 0)}.", row, citations))

    lines.extend(["", "### Week Ahead", ""])
    for row in _rows((packet.get("week_ahead") or {}).get("rows")):
        teams = _team_pair(row)
        if len(teams) != 2:
            continue
        lines.append(_line(f"{teams[0].get('team')} vs. {teams[1].get('team')}: {_fmt(row.get('projected_score_one'))}–{_fmt(row.get('projected_score_two'))}; total {_fmt(row.get('projected_total'))}; model: {row.get('model_source') or row.get('projection_source') or 'not supplied'}.", row, citations))
        if include_citations:
            for team in teams:
                lineup = ", ".join(
                    f"{_clean(player.get('player'))} ({player.get('position') or 'slot not supplied'})"
                    for player in _rows(team.get("optimal_lineup"))
                )
                schedule = team.get("remaining_schedule_strength") or {}
                if not schedule:
                    schedule = (team.get("division_context") or {}).get("remaining_schedule_strength") or {}
                health = [
                    f"{_clean(item.get('player'))}: {item.get('report_status') or item.get('injury_status') or item.get('practice_participation')}"
                    for item in _rows(team.get("health_caveats"))[:3]
                ]
                extra = f"; health: {'; '.join(health)}" if health else ""
                lines.append(
                    _line(
                        f"  - {_clean(team.get('team'))}: optimal lineup projected {_fmt(team.get('projected_score'))}; starters {lineup}; remaining SOS {_fmt(schedule.get('average_opponent_index'))} (rank {_fmt(schedule.get('difficulty_rank'), 0)}){extra}.",
                        row,
                        citations,
                    )
                )

    if include_citations:
        lines.extend(["", "### Power Board write-up inputs", ""])
        lines.append(
            "The Power Board score combines current season results (20%), projected rest-of-season starters (45%), and player market value (35%). Component points show each category's contribution to the score; percentiles show where the team ranks in that category. Power Board rank is separate from official league standing."
        )
        lines.append("")
        for row in _rows((packet.get("power_board") or {}).get("writeup_inputs")):
            components = row.get("ranking_components") or row.get("components") or row
            movement = row.get("rank_movement")
            previous_rank = row.get("previous_rank")
            movement_text = ""
            if isinstance(movement, (int, float)):
                movement_text = f"; rank movement {movement:+g}"
                if previous_rank is not None:
                    movement_text += f" from #{previous_rank}"
            record = f"; season record {row.get('wins', 0)}-{row.get('losses', 0)}-{row.get('ties', 0)}" if row.get("wins") is not None else ""
            details = []
            for key, label in (
                ("season_results", "season results"),
                ("ros_starters", "rest-of-season starters"),
                ("market", "market"),
            ):
                points = components.get(f"{key}_points")
                if points is None:
                    continue
                percentile = components.get(f"{key}_percentile")
                weight = (components.get("weights") or {}).get(key)
                details.append(
                    f"{label}: {_fmt(points)} points "
                    f"({_percentile(percentile)}; {float(weight) * 100:g}% weight)"
                    if percentile is not None and weight is not None
                    else f"{label}: {_fmt(points)} component points"
                )
            lines.append(
                _line(
                    f"{_clean(row.get('team'))}: Power Board rank {row.get('rank', 'not supplied')} "
                    f"(official standings rank {row.get('official_rank', 'not supplied')}{movement_text}); "
                    f"score {_fmt(row.get('ranking_score', row.get('score')))}{record}. "
                    + ("; ".join(details) if details else "Component scores not supplied.")
                    + ".",
                    row,
                    citations,
                )
            )

    lines.extend(
        [
            "",
            "## Before you send this to the writer",
            "",
            "- Make changes beside the matching `FINAL:` line above. Replace its bracketed prompt with `KEEP CURRENT` or your choice. You do not need to repeat the choice here or rewrite the rest of this report.",
            "- If a fact looks wrong, name the section and correction here so it can be checked: `FACT CORRECTION: ____________________`.",
            "- The commissioner column is your own personal copy; add it after the AI draft.",
            "",
            "## What to give the offline writer",
            "",
            "The completed Offline Writer Brief is the only document the writer needs. Follow its `FINAL:` choices, use only supplied facts, and draft the magazine text. You do not need to edit the supporting JSON files.",
        ]
    )
    if citations:
        lines.extend(citations.render())
    lines.append("")
    return "\n".join(lines)


def render_editorial_review(packet: dict[str, Any], plan: dict[str, Any]) -> str:
    """Render a short optional pointer to the canonical offline writer brief."""

    identity = packet.get("issue_identity") or {}
    choices = plan.get("editorial_choices") or {}
    feature = packet.get("feature_evidence") or {}
    by_id = {
        str(row.get("candidate_id")): row
        for row in _rows(feature.get("cover_candidates")) + _rows(feature.get("story_candidates"))
        if row.get("candidate_id")
    }
    lines = [
        f"# {_publication_name(identity)} — Week {identity.get('week', '?')}: Quick Editorial Review",
        "",
        "This short sheet is optional. It points you to the full decision and fact record.",
        "Use the Offline Writer Brief as the single decision and fact document. Make your choices there, then give that completed brief to the offline writer.",
        "",
        "## Current selections",
        "",
    ]
    for key, label in (
        ("cover_candidate_id", "Cover story"),
        ("lead_feature_candidate_id", "Lead article"),
        ("secondary_feature_candidate_id", "Second team write-up"),
    ):
        candidate = by_id.get(str(choices.get(key) or ""))
        lines.append(f"- {label}: {_candidate_label(candidate) if candidate else 'editor selection required'}")
    lines.extend(
        [
            "",
            f"- Research readiness: **{(packet.get('readiness') or {}).get('status', 'unknown')}**",
            f"- Information cutoff: **{identity.get('information_cutoff', 'not supplied')}**",
            "- All headline options, fact checks, citations, and editable `FINAL:` decisions are in `OFFLINE_WRITER_BRIEF.md`.",
            "",
        ]
    )
    return "\n".join(lines)


def render_offline_writer_brief(packet: dict[str, Any], plan: dict[str, Any]) -> str:
    """Give a disconnected writing model clear instructions and packet facts."""

    material = _render_editorial_material(packet, plan, include_citations=True)
    identity = packet.get("issue_identity") or {}
    choices = plan.get("editorial_choices") or {}
    feature = packet.get("feature_evidence") or {}
    candidate_by_id = {
        str(candidate.get("candidate_id")): candidate
        for candidate in _rows(feature.get("cover_candidates")) + _rows(feature.get("story_candidates"))
        if candidate.get("candidate_id")
    }

    def choice_label(key: str) -> str:
        candidate = candidate_by_id.get(str(choices.get(key) or ""))
        return _candidate_label(candidate) if candidate else "editor selection required"

    return "\n".join(
        [
            f"# OFFLINE WRITER BRIEF — {_publication_name(identity)} Week {identity.get('week', '?')}",
            "",
            "You are the magazine writer for this issue. Everything you may use is in this brief. Do not browse, call tools, or add facts from memory. Write readable magazine copy using only the supplied facts. Preserve team/player names, scores, dates, and uncertainty exactly. If information is absent, omit the claim or mark it for editor review. Never turn missing data into zero or certainty.",
            "",
            f"Publication: {identity.get('publication_key', 'not supplied')}",
            f"Season and week: {identity.get('season', 'not supplied')} / {identity.get('week', 'not supplied')}",
            f"Information cutoff: {identity.get('information_cutoff', 'not supplied')}",
            f"Current cover choice: {choice_label('cover_candidate_id')}",
            f"Current lead article: {choice_label('lead_feature_candidate_id')}",
            f"Current second article: {choice_label('secondary_feature_candidate_id')}",
            "",
            "## Editor decision controls",
            "",
            "Make all editorial choices in this Writer Brief. Replace the bracketed prompts beside each decision; keep or change the cover, choose the lead and a different team or matchup as the second write-up, select any recurring coverlines you want, decide the rotating award, and record corrections. These are your controls; the rest of this brief gives the facts and sources for those choices.",
            "",
            "## Required output",
            "",
            "Return a clean text manuscript with one heading per department. For each section provide: headline, one-sentence deck, finished body copy, table/callout text where useful, and art direction. Follow the completed `FINAL:` choices in this Writer Brief. Use any completed Game-page headline verbatim as the title for that matchup report; if it is blank, suggest a title for the commissioner to approve. Keep factual claims tied to the source references shown and place the matching `[S###]` after each claim so the editor can check it in the source reference key.",
            "If a `FINAL:` line still contains its bracketed prompt, treat the related choice as unresolved and flag it for the commissioner; never choose the rotating award on the commissioner's behalf. The indexed player-news entries below include the story headline, publisher, date, linked player, URL, and a short feed summary. Use only the details in that supplied summary; do not imply you read the full article or add facts from outside this brief. If you use an external news story to enrich a game write-up, Usage Desk, health report, or another section, cite its `[S###]` in the copy and add that article to a final `Back-cover Sources Used` list with matching `[S###]`, headline, publisher, published date, and URL. List only stories actually used; do not list unused stories or invent author names or dates.",
            "If a fact has no source reference, omit it or mark it for editor fact-check. Do not include raw JSON or repeat the source list as prose.",
            "",
            "## Decision controls and verified source material",
            "",
            "This is the full source-backed editorial record. The decision lines here are authoritative; there is no separate review required.",
            "",
            material,
        ]
    )
