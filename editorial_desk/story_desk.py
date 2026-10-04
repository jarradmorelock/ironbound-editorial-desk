from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Iterable

from .chronicle_queries import ChronicleQueries
from .external_inputs import ExternalEditorialInputs
from .story_models import StoryCandidate, StoryEvidenceRef
from .story_presentation import present_story_candidate


STORY_DESK_PUBLICATIONS = {"ironbound_weekly", "unbound_weekly"}
_TRANSACTION_TYPES = {"TRADE", "WAIVER_ADD", "FREE_AGENT_ADD", "DROP"}
_ADD_TYPES = {"WAIVER_ADD", "FREE_AGENT_ADD"}
_SEVERE_STATUSES = {"out", "ir", "injured reserve", "doubtful", "pup", "suspended"}


def build_story_desk(
    publication_key: str,
    snapshot: dict[str, Any],
    dossier: dict[str, Any],
    chronicle: ChronicleQueries,
    *,
    external_inputs: ExternalEditorialInputs | None = None,
    observed_since: str | None = None,
    max_candidates: int = 20,
) -> dict[str, Any]:
    publication_key = str(publication_key)
    if publication_key not in STORY_DESK_PUBLICATIONS:
        return {
            "schema_version": 1,
            "publication_key": publication_key,
            "status": "disabled",
            "candidates": [],
            "external_inputs": _external_status(external_inputs),
        }

    league_key = str((snapshot.get("editorial") or {}).get("league_key") or "")
    season = str(
        (snapshot.get("nfl_state") or {}).get("season")
        or (snapshot.get("league") or {}).get("season")
        or ""
    )
    week = int(snapshot.get("week") or 0)
    context = _DeskContext(
        publication_key=publication_key,
        league_key=league_key,
        season=season,
        week=week,
        snapshot=snapshot,
        dossier=dossier,
        chronicle=chronicle,
        external_inputs=external_inputs,
        observed_since=observed_since,
    )

    producers = (
        _rivalry_history,
        _injury_shock,
        _reaction_transaction,
        _waiver_run,
        _trade_afterlife,
        _trade_market_shift,
        _asset_journey,
        _roster_architecture,
        _dynasty_identity,
        _historic_upset,
        _scoring_record,
        _streak,
        _repeated_close_losses,
        _former_player_matchup,
        _playoff_rematch,
        _lineup_catastrophe,
        _division_pressure,
        _cross_league_shock,
        _david_vs_goliath,
    )
    candidates: list[StoryCandidate] = []
    for producer in producers:
        candidate = producer(context)
        if candidate is not None:
            candidates.append(candidate)

    unique = {candidate.candidate_id: candidate for candidate in candidates}
    presented = [
        present_story_candidate(candidate, publication_key)
        for candidate in unique.values()
    ]
    ordered = sorted(
        presented,
        key=lambda row: (-row.signal_score, row.candidate_type, row.candidate_id),
    )[: max(0, min(int(max_candidates), 20))]
    return {
        "schema_version": 1,
        "publication_key": publication_key,
        "league_key": league_key,
        "season": season,
        "week": week,
        "status": "available",
        "candidate_count": len(ordered),
        "candidates": [candidate.to_dict() for candidate in ordered],
        "external_inputs": _external_status(external_inputs),
    }


class _DeskContext:
    def __init__(
        self,
        *,
        publication_key: str,
        league_key: str,
        season: str,
        week: int,
        snapshot: dict[str, Any],
        dossier: dict[str, Any],
        chronicle: ChronicleQueries,
        external_inputs: ExternalEditorialInputs | None,
        observed_since: str | None,
    ) -> None:
        self.publication_key = publication_key
        self.league_key = league_key
        self.season = season
        self.week = week
        self.snapshot = snapshot
        self.dossier = dossier
        self.chronicle = chronicle
        self.external_inputs = external_inputs
        self.observed_since = observed_since
        self.rosters = {
            int(row.get("roster_id") or 0): row for row in snapshot.get("rosters") or []
        }
        self.identities = {
            roster_id: chronicle.identity_for_roster(league_key, season, roster_id)
            for roster_id in self.rosters
        }
        self.players = snapshot.get("players") or {}
        self.current_games = _current_games(self)
        self.league_events = chronicle.league_events(league_key) if league_key else []
        self.recent_events = [
            row for row in self.league_events if _event_is_recent(row, observed_since)
        ]
        self.player_roster = {
            str(player_id): roster_id
            for roster_id, roster in self.rosters.items()
            for player_id in roster.get("players") or []
        }
        self.player_week = _player_week_rows(snapshot)


def _rivalry_history(ctx: _DeskContext) -> StoryCandidate | None:
    best: tuple[float, StoryCandidate] | None = None
    for game in ctx.current_games:
        left, right = game["left_identity"], game["right_identity"]
        if not left or not right:
            continue
        history = ctx.chronicle.head_to_head(ctx.league_key, left, right)
        if not history:
            continue
        series = history["series"]
        games = int(series.get("games") or 0)
        if games < 4:
            continue
        playoff_games = int(series.get("playoff_games") or 0)
        ref = _derived_ref(
            f"chronicle:h2h:{ctx.league_key}:{min(left, right)}:{max(left, right)}",
            "Materialized head-to-head series",
        )
        candidate = _candidate(
            "rivalry_history",
            (ref,),
            score=games + playoff_games * 2,
            components={"series_games": games, "playoff_games": playoff_games},
            facts=(
                {
                    "statement": f"The series contains {games} recorded meetings.",
                    "provenance": "chronicle_derived",
                    "coverage_complete": history.get("coverage_complete"),
                },
            ),
            historical_context=tuple(
                {
                    "statement": "Recorded playoff meeting",
                    "provenance": "chronicle_derived",
                    "event_id": row.get("event_id"),
                }
                for row in history.get("playoff_meetings") or []
            ),
            entities={"identities": [left, right]},
        )
        best = _best(best, candidate)
    return best[1] if best else None


def _injury_shock(ctx: _DeskContext) -> StoryCandidate | None:
    market = _market_values(ctx.dossier)
    candidates: list[tuple[float, StoryCandidate]] = []
    for player_id, roster_id in ctx.player_roster.items():
        for event in reversed(ctx.chronicle.player_events(player_id, since=ctx.observed_since)):
            if str(event.get("event_type") or "") != "PLAYER_STATUS_CHANGE":
                continue
            status = str((event.get("after") or {}).get("injury_status") or "").casefold()
            if status not in _SEVERE_STATUSES:
                continue
            week_row = ctx.player_week.get(player_id) or {}
            started = bool(week_row.get("started"))
            value = float((market.get(player_id) or {}).get("trade_value") or 0)
            score = 5.0 + (3.0 if started else 0.0) + min(value / 4000.0, 3.0)
            ref = _event_ref(event)
            candidates.append(
                (
                    score,
                    _candidate(
                        "injury_shock",
                        (ref,),
                        score=score,
                        components={
                            "severe_status": 1,
                            "started": int(started),
                            "market_value_signal": min(value / 4000.0, 3.0),
                        },
                        facts=(
                            {
                                "statement": f"Status changed to {status or 'unavailable'}.",
                                "evidence_id": ref.evidence_id,
                            },
                        ),
                        entities={"player_id": player_id, "roster_id": roster_id},
                        cautions=(
                            "Observed status sequence does not establish medical cause, severity beyond the source label, or future availability.",
                        ),
                    ),
                )
            )
            break
    return max(candidates, key=lambda item: (item[0], item[1].candidate_id))[1] if candidates else None


def _reaction_transaction(ctx: _DeskContext) -> StoryCandidate | None:
    choices: list[tuple[float, StoryCandidate]] = []
    for player_id, roster_id in ctx.player_roster.items():
        statuses = [
            event
            for event in ctx.chronicle.player_events(player_id, since=ctx.observed_since)
            if str(event.get("event_type") or "") == "PLAYER_STATUS_CHANGE"
            and str((event.get("after") or {}).get("injury_status") or "").casefold()
            in _SEVERE_STATUSES
        ]
        for status_event in statuses:
            status_time = _timestamp(status_event.get("observed_at"))
            if status_time is None:
                continue
            later = [
                event
                for event in ctx.recent_events
                if str(event.get("event_type") or "") in {"TRADE", "WAIVER_ADD", "FREE_AGENT_ADD"}
                and _event_roster_id(event) == roster_id
                and _within_hours(status_time, _timestamp(event.get("observed_at")), 72)
            ]
            if not later:
                continue
            transaction = sorted(later, key=lambda row: str(row.get("observed_at") or ""))[0]
            status_ref, tx_ref = _event_ref(status_event), _event_ref(transaction)
            hours = max(
                0.0,
                (_timestamp(transaction.get("observed_at")) - status_time).total_seconds() / 3600.0,
            )
            score = 8.0 + max(0.0, (72.0 - hours) / 24.0)
            choices.append(
                (
                    score,
                    _candidate(
                        "reaction_transaction",
                        (status_ref, tx_ref),
                        score=score,
                        components={"sequence_events": 2, "hours_apart_signal": max(0, 72 - hours)},
                        facts=(
                            {
                                "statement": "A roster transaction was observed after a severe player-status change.",
                                "evidence_ids": [status_ref.evidence_id, tx_ref.evidence_id],
                            },
                        ),
                        entities={"player_id": player_id, "roster_id": roster_id},
                        cautions=(
                            "The timing supports sequence only. It does not prove the status change caused the transaction or reveal manager motive.",
                        ),
                    ),
                )
            )
    return max(choices, key=lambda item: (item[0], item[1].candidate_id))[1] if choices else None


def _waiver_run(ctx: _DeskContext) -> StoryCandidate | None:
    grouped: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for league_key in ctx.chronicle.tracked_league_keys():
        for event in ctx.chronicle.league_events(league_key, _ADD_TYPES):
            if not _event_is_recent(event, ctx.observed_since):
                continue
            player_id = str((event.get("entities") or {}).get("player_id") or "")
            if player_id:
                grouped[player_id].append((league_key, event))
    choices = []
    for player_id, rows in grouped.items():
        leagues = sorted({league for league, _ in rows})
        if len(leagues) < 2:
            continue
        refs = tuple(_event_ref(event) for _, event in rows)
        score = 4.0 + len(leagues) * 2.0 + min(len(rows), 4)
        choices.append(
            _candidate(
                "waiver_run",
                refs,
                score=score,
                components={"league_count": len(leagues), "add_events": len(rows)},
                entities={"player_id": player_id, "league_keys": leagues},
                facts=(
                    {
                        "statement": f"The player was added in {len(leagues)} tracked leagues.",
                        "evidence_ids": [ref.evidence_id for ref in refs],
                    },
                ),
            )
        )
    return max(choices, key=lambda row: (row.signal_score, row.candidate_id), default=None)


def _trade_afterlife(ctx: _DeskContext) -> StoryCandidate | None:
    choices = []
    for player_id, row in ctx.player_week.items():
        points = float(row.get("points") or 0)
        if points < 20:
            continue
        trades = [
            event
            for event in ctx.chronicle.transactions_for_entity(ctx.league_key, player_id)
            if str(event.get("event_type") or "") == "TRADE"
        ]
        if not trades:
            continue
        latest = max(trades, key=lambda event: str(event.get("observed_at") or ""))
        trade_ref = _event_ref(latest)
        week_ref = _snapshot_ref(ctx, f"player-week:{player_id}", "Current fantasy player-week result")
        score = points / 4.0 + min(len(trades), 3)
        choices.append(
            _candidate(
                "trade_afterlife",
                (trade_ref, week_ref),
                score=score,
                components={"current_points": points, "trade_count": len(trades)},
                entities={"player_id": player_id, "roster_id": row.get("roster_id")},
                facts=(
                    {
                        "statement": f"The previously traded player scored {points:.1f} fantasy points this week.",
                        "evidence_ids": [trade_ref.evidence_id, week_ref.evidence_id],
                    },
                ),
            )
        )
    return max(choices, key=lambda row: (row.signal_score, row.candidate_id), default=None)


def _trade_market_shift(ctx: _DeskContext) -> StoryCandidate | None:
    trades = [event for event in ctx.recent_events if str(event.get("event_type") or "") == "TRADE"]
    if len(trades) < 4:
        return None
    refs = tuple(_event_ref(event) for event in trades)
    return _candidate(
        "trade_market_shift",
        refs,
        score=5.0 + len(trades),
        components={"recent_trade_events": len(trades)},
        facts=(
            {
                "statement": f"Chronicle recorded {len(trades)} recent trade events in the league.",
                "evidence_ids": [ref.evidence_id for ref in refs],
            },
        ),
    )


def _asset_journey(ctx: _DeskContext) -> StoryCandidate | None:
    choices = []
    for player_id in ctx.player_roster:
        transactions = ctx.chronicle.transactions_for_entity(ctx.league_key, player_id)
        if len(transactions) < 3:
            continue
        refs = tuple(_event_ref(event) for event in transactions)
        choices.append(
            _candidate(
                "asset_journey",
                refs,
                score=4.0 + len(transactions),
                components={"transaction_events": len(transactions)},
                entities={"player_id": player_id},
                facts=(
                    {
                        "statement": f"The player appears in {len(transactions)} recorded transaction events.",
                        "evidence_ids": [ref.evidence_id for ref in refs],
                    },
                ),
            )
        )
    return max(choices, key=lambda row: (row.signal_score, row.candidate_id), default=None)


def _roster_architecture(ctx: _DeskContext) -> StoryCandidate | None:
    choices = []
    for roster_id, roster in ctx.rosters.items():
        positions = Counter(
            str((ctx.players.get(str(player_id)) or {}).get("position") or "")
            for player_id in roster.get("players") or []
        )
        positions.pop("", None)
        if not positions:
            continue
        position, count = positions.most_common(1)[0]
        roster_size = max(len(roster.get("players") or []), 1)
        if count < 6 or count / roster_size <= 0.5:
            continue
        ref = _snapshot_ref(ctx, f"roster:{roster_id}:architecture", "Current roster positional construction")
        concentration = count / roster_size
        choices.append(
            _candidate(
                "roster_architecture",
                (ref,),
                score=count + concentration * 5,
                components={"position_count": count, "roster_share": concentration},
                entities={"roster_id": roster_id, "position": position},
                facts=(
                    {
                        "statement": f"Roster {roster_id} carries {count} {position} players ({concentration:.0%} of its listed players).",
                        "evidence_id": ref.evidence_id,
                    },
                ),
            )
        )
    return max(choices, key=lambda row: (row.signal_score, row.candidate_id), default=None)


def _dynasty_identity(ctx: _DeskContext) -> StoryCandidate | None:
    if str((ctx.snapshot.get("editorial") or {}).get("league_format") or "").casefold() != "dynasty":
        return None
    choices = []
    for roster_id, identity in ctx.identities.items():
        if not identity:
            continue
        context = ctx.chronicle.identity_context(identity)
        aliases = context.get("aliases") or []
        tenures = context.get("manager_tenures") or []
        if len(aliases) < 2 and len(tenures) < 2:
            continue
        ref = _derived_ref(f"chronicle:identity:{identity}", "Stable franchise identity registry")
        score = 4.0 + len(aliases) + len(tenures)
        choices.append(
            _candidate(
                "dynasty_identity",
                (ref,),
                score=score,
                components={"alias_count": len(aliases), "manager_tenures": len(tenures)},
                entities={"identity": identity, "roster_id": roster_id},
                historical_context=(
                    {
                        "statement": "Franchise aliases and manager tenures changed across recorded seasons.",
                        "provenance": "chronicle_derived",
                    },
                ),
            )
        )
    return max(choices, key=lambda row: (row.signal_score, row.candidate_id), default=None)


def _historic_upset(ctx: _DeskContext) -> StoryCandidate | None:
    records = ctx.chronicle.season_records(ctx.league_key, ctx.season).get("records") or {}
    choices = []
    for game in ctx.current_games:
        winner, loser = _winner_loser(game)
        if not winner or not loser:
            continue
        winner_record = records.get(winner["identity"]) or {}
        loser_record = records.get(loser["identity"]) or {}
        wp = _win_pct(winner_record)
        lp = _win_pct(loser_record)
        if lp - wp < 0.4:
            continue
        ref = game["evidence_ref"]
        score = 5.0 + (lp - wp) * 10 + float(game["margin"]) / 10.0
        choices.append(
            _candidate(
                "historic_upset",
                (ref,),
                score=score,
                components={"record_gap": lp - wp, "margin": float(game["margin"])},
                entities={"winner": winner["identity"], "loser": loser["identity"]},
                facts=(
                    {
                        "statement": "The current-week winner entered with a materially worse season record than the opponent.",
                        "provenance": "chronicle_derived",
                    },
                ),
            )
        )
    return max(choices, key=lambda row: (row.signal_score, row.candidate_id), default=None)


def _scoring_record(ctx: _DeskContext) -> StoryCandidate | None:
    records = [event for event in ctx.recent_events if str(event.get("event_type") or "") == "RECORD_SET"]
    if not records:
        return None
    event = records[-1]
    ref = _event_ref(event)
    value = float((event.get("evidence") or {}).get("value") or 0)
    return _candidate(
        "scoring_record",
        (ref,),
        score=9.0 + min(value / 100.0, 3.0),
        components={"record_event": 1, "record_value_signal": min(value / 100.0, 3.0)},
        facts=(
            {
                "statement": "Chronicle recorded a scoring record event.",
                "evidence_id": ref.evidence_id,
            },
        ),
        entities=dict(event.get("entities") or {}),
    )


def _streak(ctx: _DeskContext) -> StoryCandidate | None:
    choices = []
    for game in ctx.current_games:
        left, right = game["left_identity"], game["right_identity"]
        if not left or not right:
            continue
        streak = ctx.chronicle.current_streak(ctx.league_key, left, right)
        if not streak or int(streak.get("length") or 0) < 3:
            continue
        length = int(streak["length"])
        ref = _derived_ref(
            f"chronicle:streak:{ctx.league_key}:{min(left, right)}:{max(left, right)}",
            "Materialized head-to-head streak",
        )
        choices.append(
            _candidate(
                "streak",
                (ref,),
                score=5.0 + length,
                components={"streak_length": length},
                entities={"identity": streak.get("identity"), "opponents": [left, right]},
                facts=(
                    {
                        "statement": f"The materialized series has a current streak of {length} games.",
                        "provenance": "chronicle_derived",
                    },
                ),
            )
        )
    return max(choices, key=lambda row: (row.signal_score, row.candidate_id), default=None)


def _repeated_close_losses(ctx: _DeskContext) -> StoryCandidate | None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ctx.chronicle.league_matchups(ctx.league_key):
        loser = str(row.get("loser_identity") or "")
        margin = float(row.get("margin") or 0)
        if loser and 0 < margin <= 5:
            grouped[loser].append(row)
    choices = []
    for identity, rows in grouped.items():
        if len(rows) < 3:
            continue
        refs = tuple(
            _derived_ref(
                str(row.get("event_id") or f"chronicle:matchup:{identity}:{index}"),
                "Materialized close-loss matchup",
            )
            for index, row in enumerate(rows)
        )
        avg_margin = sum(float(row.get("margin") or 0) for row in rows) / len(rows)
        choices.append(
            _candidate(
                "repeated_close_losses",
                refs,
                score=5.0 + len(rows) + max(0.0, 5 - avg_margin),
                components={"close_losses": len(rows), "average_margin": avg_margin},
                entities={"identity": identity},
                historical_context=(
                    {
                        "statement": f"Chronicle contains {len(rows)} losses by five points or fewer.",
                        "evidence_ids": [ref.evidence_id for ref in refs],
                    },
                ),
            )
        )
    return max(choices, key=lambda row: (row.signal_score, row.candidate_id), default=None)


def _former_player_matchup(ctx: _DeskContext) -> StoryCandidate | None:
    choices = []
    for game in ctx.current_games:
        roster_pair = {game["left_roster_id"], game["right_roster_id"]}
        for player_id, current_roster in ctx.player_roster.items():
            if current_roster not in roster_pair:
                continue
            opponent = next(iter(roster_pair - {current_roster}), None)
            if opponent is None:
                continue
            trades = [
                event
                for event in ctx.chronicle.transactions_for_entity(ctx.league_key, player_id)
                if str(event.get("event_type") or "") == "TRADE"
            ]
            relevant = [
                event
                for event in trades
                if int((event.get("entities") or {}).get("from_roster_id") or 0) == opponent
                and int((event.get("entities") or {}).get("to_roster_id") or current_roster) == current_roster
            ]
            if not relevant:
                continue
            event = relevant[-1]
            trade_ref, game_ref = _event_ref(event), game["evidence_ref"]
            points = float((ctx.player_week.get(player_id) or {}).get("points") or 0)
            choices.append(
                _candidate(
                    "former_player_matchup",
                    (trade_ref, game_ref),
                    score=5.0 + min(points / 5.0, 6.0),
                    components={"former_team_matchup": 1, "current_points": points},
                    entities={"player_id": player_id, "current_roster_id": current_roster, "former_roster_id": opponent},
                    facts=(
                        {
                            "statement": "A currently rostered player is facing a roster that previously traded that player away.",
                            "evidence_ids": [trade_ref.evidence_id, game_ref.evidence_id],
                        },
                    ),
                )
            )
    return max(choices, key=lambda row: (row.signal_score, row.candidate_id), default=None)


def _playoff_rematch(ctx: _DeskContext) -> StoryCandidate | None:
    choices = []
    for game in ctx.current_games:
        left, right = game["left_identity"], game["right_identity"]
        if not left or not right:
            continue
        history = ctx.chronicle.head_to_head(ctx.league_key, left, right)
        meetings = (history or {}).get("playoff_meetings") or []
        if not meetings:
            continue
        refs = tuple(
            _derived_ref(str(row.get("event_id") or "playoff-meeting"), "Materialized prior playoff meeting")
            for row in meetings
        ) + (game["evidence_ref"],)
        choices.append(
            _candidate(
                "playoff_rematch",
                refs,
                score=7.0 + len(meetings) * 2.0,
                components={"prior_playoff_meetings": len(meetings)},
                entities={"identities": [left, right]},
                historical_context=(
                    {
                        "statement": f"The current opponents have {len(meetings)} recorded playoff meeting(s).",
                        "provenance": "chronicle_derived",
                    },
                ),
            )
        )
    return max(choices, key=lambda row: (row.signal_score, row.candidate_id), default=None)


def _lineup_catastrophe(ctx: _DeskContext) -> StoryCandidate | None:
    rows = [
        row
        for row in ctx.dossier.get("lineup_flip_candidates") or []
        if row.get("would_flip_result") and float(row.get("point_swing") or 0) >= 10
    ]
    if not rows:
        return None
    row = max(rows, key=lambda value: float(value.get("point_swing") or 0))
    roster_id = int(row.get("roster_id") or 0)
    swing = float(row.get("point_swing") or 0)
    ref = _dossier_ref(ctx, f"lineup-flip:{roster_id}", "Result-flipping lineup decision evidence")
    return _candidate(
        "lineup_catastrophe",
        (ref,),
        score=5.0 + swing / 3.0,
        components={"point_swing": swing, "would_flip_result": 1},
        entities={"roster_id": roster_id},
        facts=(
            {
                "statement": f"A legal alternative lineup would have changed the result by a {swing:.1f}-point swing.",
                "evidence_id": ref.evidence_id,
            },
        ),
    )


def _division_pressure(ctx: _DeskContext) -> StoryCandidate | None:
    settings = (ctx.snapshot.get("league") or {}).get("settings") or {}
    if int(settings.get("divisions") or 0) <= 0:
        return None
    rows = [
        row
        for row in ctx.dossier.get("division_metrics") or []
        if float(row.get("gap") or 999) <= 1
    ]
    if not rows:
        return None
    refs = tuple(
        _dossier_ref(
            ctx,
            f"division:{row.get('division_id')}",
            f"Division pressure metrics for {row.get('division_name') or row.get('division_id')}",
        )
        for row in rows
    )
    return _candidate(
        "division_pressure",
        refs,
        score=6.0 + len(rows) * 2.0,
        components={"tight_divisions": len(rows), "division_count": int(settings.get("divisions") or 0)},
        facts=(
            {
                "statement": f"{len(rows)} division(s) have a recorded gap of one game or less in the supplied division metrics.",
                "evidence_ids": [ref.evidence_id for ref in refs],
            },
        ),
    )


def _cross_league_shock(ctx: _DeskContext) -> StoryCandidate | None:
    choices = []
    for player_id in ctx.player_roster:
        statuses = [
            event
            for event in ctx.chronicle.player_events(player_id, since=ctx.observed_since)
            if str(event.get("event_type") or "") == "PLAYER_STATUS_CHANGE"
            and str((event.get("after") or {}).get("injury_status") or "").casefold()
            in _SEVERE_STATUSES
        ]
        for status in statuses:
            status_time = _timestamp(status.get("observed_at"))
            if status_time is None:
                continue
            league_rows: list[tuple[str, dict[str, Any]]] = []
            for league_key in ctx.chronicle.tracked_league_keys():
                for event in ctx.chronicle.league_events(league_key, _TRANSACTION_TYPES):
                    if not _event_has_entity(event, player_id):
                        continue
                    event_time = _timestamp(event.get("observed_at"))
                    if event_time and event_time > status_time:
                        league_rows.append((league_key, event))
            leagues = sorted({league for league, _ in league_rows})
            if len(leagues) < 2:
                continue
            refs = (_event_ref(status),) + tuple(_event_ref(event) for _, event in league_rows)
            choices.append(
                _candidate(
                    "cross_league_shock",
                    refs,
                    score=8.0 + len(leagues) * 2.0,
                    components={"league_count": len(leagues), "reaction_events": len(league_rows)},
                    entities={"player_id": player_id, "league_keys": leagues},
                    facts=(
                        {
                            "statement": f"Transactions involving the player followed the status change in {len(leagues)} tracked leagues.",
                            "evidence_ids": [ref.evidence_id for ref in refs],
                        },
                    ),
                    cautions=(
                        "Cross-league timing shows a reaction cluster, not proof that every manager acted because of the status change.",
                    ),
                )
            )
    return max(choices, key=lambda row: (row.signal_score, row.candidate_id), default=None)


def _david_vs_goliath(ctx: _DeskContext) -> StoryCandidate | None:
    external = ctx.external_inputs
    if external is None or not external.power_rankings_supplied:
        return None
    choices = []
    for game in ctx.current_games:
        left, right = game["left_identity"], game["right_identity"]
        if not left or not right:
            continue
        left_rank, right_rank = external.ranking_for(left), external.ranking_for(right)
        if left_rank is None or right_rank is None:
            continue
        gap = abs(left_rank - right_rank)
        if gap < 8:
            continue
        ref = StoryEvidenceRef(
            evidence_id=f"external:{ctx.publication_key}:power-rankings:{min(left, right)}:{max(left, right)}",
            source="external_official_power_rankings",
            description="User-supplied official Power Rankings",
        )
        choices.append(
            _candidate(
                "david_vs_goliath",
                (ref, game["evidence_ref"]),
                score=5.0 + gap,
                components={"official_rank_gap": gap},
                entities={"identities": [left, right], "ranks": [left_rank, right_rank]},
                facts=(
                    {
                        "statement": f"The user-supplied official rankings place the opponents {gap} positions apart.",
                        "evidence_id": ref.evidence_id,
                    },
                ),
            )
        )
    return max(choices, key=lambda row: (row.signal_score, row.candidate_id), default=None)


def _candidate(
    candidate_type: str,
    refs: Iterable[StoryEvidenceRef],
    *,
    score: float,
    components: dict[str, float],
    facts: Iterable[dict[str, Any]] = (),
    historical_context: Iterable[dict[str, Any]] = (),
    entities: dict[str, Any] | None = None,
    cautions: Iterable[str] = (),
) -> StoryCandidate:
    return StoryCandidate.build(
        candidate_type=candidate_type,
        evidence_refs=tuple(refs),
        title_concepts=(candidate_type.replace("_", " ").title(),),
        trigger_reasons=(f"Objective {candidate_type.replace('_', ' ')} threshold cleared.",),
        facts=tuple(facts),
        historical_context=tuple(historical_context),
        entities=entities or {},
        evidence_strength="strong" if len(tuple(refs)) >= 2 else "supported",
        signal_score=float(score),
        signal_components=components,
        cautions=tuple(cautions),
        depth_class="brief",
    )


def _best(
    current: tuple[float, StoryCandidate] | None, candidate: StoryCandidate
) -> tuple[float, StoryCandidate]:
    value = (candidate.signal_score, candidate)
    if current is None or candidate.signal_score > current[0]:
        return value
    return current


def _current_games(ctx: _DeskContext) -> list[dict[str, Any]]:
    grouped: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for row in ctx.snapshot.get("matchups") or []:
        grouped[row.get("matchup_id")].append(row)
    games: list[dict[str, Any]] = []
    for matchup_id, rows in sorted(grouped.items(), key=lambda item: str(item[0])):
        if len(rows) != 2:
            continue
        left, right = sorted(rows, key=lambda row: int(row.get("roster_id") or 0))
        left_id, right_id = int(left.get("roster_id") or 0), int(right.get("roster_id") or 0)
        left_points, right_points = float(left.get("points") or 0), float(right.get("points") or 0)
        games.append(
            {
                "matchup_id": matchup_id,
                "left_roster_id": left_id,
                "right_roster_id": right_id,
                "left_identity": ctx.identities.get(left_id),
                "right_identity": ctx.identities.get(right_id),
                "left_points": left_points,
                "right_points": right_points,
                "margin": abs(left_points - right_points),
                "evidence_ref": _snapshot_ref(ctx, f"matchup:{matchup_id}", "Current completed fantasy matchup"),
            }
        )
    return games


def _winner_loser(game: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    left = {"identity": game.get("left_identity"), "points": game.get("left_points")}
    right = {"identity": game.get("right_identity"), "points": game.get("right_points")}
    if not left["identity"] or not right["identity"] or left["points"] == right["points"]:
        return None, None
    return (left, right) if float(left["points"]) > float(right["points"]) else (right, left)


def _player_week_rows(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for matchup in snapshot.get("matchups") or []:
        roster_id = int(matchup.get("roster_id") or 0)
        starters = {str(value) for value in matchup.get("starters") or []}
        points = {str(key): float(value or 0) for key, value in (matchup.get("players_points") or {}).items()}
        for player_id, value in points.items():
            rows[player_id] = {
                "roster_id": roster_id,
                "points": value,
                "started": player_id in starters,
            }
    return rows


def _market_values(dossier: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("player_id")): row
        for row in (dossier.get("market_context") or {}).get("players") or []
        if row.get("player_id") is not None
    }


def _win_pct(record: dict[str, Any]) -> float:
    wins = float(record.get("wins") or 0)
    losses = float(record.get("losses") or 0)
    ties = float(record.get("ties") or 0)
    games = wins + losses + ties
    return (wins + 0.5 * ties) / games if games else 0.0


def _external_status(external: ExternalEditorialInputs | None) -> dict[str, Any]:
    return {
        "official_power_rankings": bool(external and external.power_rankings_supplied),
        "playoff_odds": bool(external and external.playoff_odds_supplied),
        "usage": bool(external and external.usage_supplied),
        "war": bool(external and external.war_supplied),
        "cwar": bool(external and external.cwar_supplied),
    }


def _event_ref(event: dict[str, Any]) -> StoryEvidenceRef:
    return StoryEvidenceRef(
        evidence_id=str(event.get("event_id") or event.get("source_ref") or "unknown-event"),
        source=str(event.get("source") or "chronicle_event"),
        description=str(event.get("event_type") or event.get("source_ref") or "Chronicle event"),
    )


def _derived_ref(evidence_id: str, description: str) -> StoryEvidenceRef:
    return StoryEvidenceRef(evidence_id=str(evidence_id), source="chronicle_derived", description=description)


def _snapshot_ref(ctx: _DeskContext, suffix: str, description: str) -> StoryEvidenceRef:
    return StoryEvidenceRef(
        evidence_id=f"snapshot:{ctx.league_key}:{ctx.season}:{ctx.week}:{suffix}",
        source="weekly_snapshot",
        description=description,
    )


def _dossier_ref(ctx: _DeskContext, suffix: str, description: str) -> StoryEvidenceRef:
    return StoryEvidenceRef(
        evidence_id=f"dossier:{ctx.league_key}:{ctx.season}:{ctx.week}:{suffix}",
        source="weekly_dossier",
        description=description,
    )


def _event_is_recent(event: dict[str, Any], since: str | None) -> bool:
    if since is None:
        return True
    event_time, since_time = _timestamp(event.get("observed_at")), _timestamp(since)
    return bool(event_time and since_time and event_time > since_time)


def _timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _within_hours(start: datetime, end: datetime | None, hours: float) -> bool:
    return bool(end and end >= start and (end - start).total_seconds() <= hours * 3600)


def _event_roster_id(event: dict[str, Any]) -> int:
    entities = event.get("entities") or {}
    for key in ("roster_id", "to_roster_id"):
        if entities.get(key) is not None:
            try:
                return int(entities[key])
            except (TypeError, ValueError):
                pass
    return 0


def _event_has_entity(event: dict[str, Any], wanted: str) -> bool:
    def contains(value: Any) -> bool:
        if isinstance(value, dict):
            return any(contains(item) for item in value.values())
        if isinstance(value, (list, tuple, set)):
            return any(contains(item) for item in value)
        return str(value) == str(wanted)

    return contains(event.get("entities") or {})
