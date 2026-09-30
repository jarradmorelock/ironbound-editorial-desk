"""Research-only honors. Qualification is deterministic; publication is editorial.

No current/postgame projection fallback is permitted. Component scores remain
inside manager_scores and are never included in a publication packet.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from math import isfinite
from typing import Any

from .external_inputs import ExternalEditorialInputs
from .metrics import optimal_lineup, starter_slots

LABELS = {
    "IRON_BALLS": "Iron Balls",
    "MAD_BLACKSMITH": "Mad Blacksmith",
    "BONE_HEAD": "Bone Head",
    "LEFT_ON_THE_ANVIL": "Left on the Anvil",
    "GOOSED": "Goosed",
    "TEMPERED": "Tempered",
    "NO_FEAR": "No Fear",
    "GIANT_KILLER": "Giant Killer",
    "AGAINST_ALL_ODDS": "Against All Odds",
    "BY_A_RIVET": "By a Rivet",
    "HAMMER_DROP": "Hammer Drop",
    "FULL_FORGE": "Full Forge",
    "SCRAPHEAP_SAVIOR": "Scrapheap Savior",
    "HOT_OFF_THE_ANVIL": "Hot Off the Anvil",
    "CUT_BY_YOUR_OWN_BLADE": "Cut by Your Own Blade",
    "REFORGED": "Reforged",
    "ONE_MAN_FOUNDRY": "One-Man Foundry",
    "ONE_HAND_TIED": "One Hand Tied",
    "ANVIL_TO_ANVIL": "Anvil-to-Anvil",
    "FAAB_FURNACE": "FAAB Furnace",
    "THE_SPOILER": "The Spoiler",
}
PLAYER_PROJECTION_RULES = {
    "IRON_BALLS",
    "MAD_BLACKSMITH",
    "BONE_HEAD",
    "LEFT_ON_THE_ANVIL",
    "GOOSED",
    "TEMPERED",
    "FULL_FORGE",
}


def _number(value):
    try:
        result = float(value)
        return result if isfinite(result) else None
    except (ValueError, TypeError):
        return None


def _time(value):
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result if result.tzinfo else None
    except (ValueError, TypeError):
        return None


def frozen_projections(snapshot):
    """Require same-week identity and timestamped capture before first kickoff."""
    source = snapshot.get("frozen_pregame_projections") or {}
    captured, kickoff = _time(source.get("captured_at")), _time(
        source.get("first_kickoff_at")
    )
    season = str(
        (snapshot.get("league") or {}).get("season")
        or (snapshot.get("nfl_state") or {}).get("season")
    )
    valid = (
        str(source.get("season")) == season
        and source.get("week") == snapshot.get("week")
        and source.get("source")
        and captured
        and kickoff
        and captured < kickoff
    )
    if not valid:
        return (
            {},
            {},
            "Missing verified same-season/week frozen pregame capture: source, captured_at before first_kickoff_at, player_points and matchup_points. Current Sleeper projections are not a substitute.",
        )
    players = {
        str(k): _number(v) for k, v in (source.get("player_points") or {}).items()
    }
    matchups = {
        str(k): _number(v) for k, v in (source.get("matchup_points") or {}).items()
    }
    return players, matchups, None


def _games(snapshot):
    groups = defaultdict(list)
    for row in snapshot.get("matchups") or []:
        if row.get("matchup_id") is not None:
            groups[row["matchup_id"]].append(row)
    return [
        rows
        for rows in groups.values()
        if len(rows) == 2 and all(_number(r.get("points")) is not None for r in rows)
    ]


def _prior_weeks(snapshot, history=(), chronicle=None):
    week = int(snapshot.get("week") or 0)
    weeks = {}
    for d in history:
        w = int(d.get("week") or 0)
        if 0 < w < week:
            weeks[w] = [
                {**r, "matchup_id": g.get("matchup_id")}
                for g in d.get("scoreboard") or []
                for r in g.get("teams") or []
            ]
    if chronicle:
        key = (snapshot.get("editorial") or {}).get("league_key", "")
        season = str((snapshot.get("league") or {}).get("season"))
        grouped = defaultdict(list)
        for row in chronicle.season_matchup_finals(key, season):
            if 0 < int(row["week"]) < week:
                grouped[int(row["week"])].append(row)
        weeks.update(grouped)
    for raw, rows in (
        ((snapshot.get("flagship_sleeper") or {}).get("schedule") or {}).get("weeks")
        or {}
    ).items():
        if 0 < int(raw) < week:
            weeks[int(raw)] = rows
    return weeks


def _entering_rank(external, roster_id, team=None):
    row = external.ranking_for_roster(roster_id, team=team)
    return (
        row.previous_rank
        if row and row.previous_rank and row.previous_rank > 0
        else None
    )


def _current_handoff(snapshot, external):
    metadata = external.source_metadata
    week = int(snapshot.get("week") or 0)
    for key, expected in (("results_through_week", week), ("ranking_week", week + 1)):
        if key in metadata and _number(metadata[key]) != expected:
            return ExternalEditorialInputs(external.publication_key)
    return external


def manager_scores(snapshot, dossier, external, history=(), chronicle=None):
    """Internal 0..1 components; missing context is neutral and explicitly flagged.

    Record/consistency = equal parts prior H2H win rate and prior weekly
    all-play percentile. All-play normalizes scoring consistency across weeks.
    No postweek cumulative roster record is used (including median wins).
    """
    external = _current_handoff(snapshot, external)
    rows = dossier.get("lineup_efficiency") or []
    points = {
        int(m["roster_id"]): float(m["points"])
        for m in snapshot.get("matchups") or []
        if _number(m.get("points")) is not None
    }
    games = {
        int(r["roster_id"]): (r, o)
        for pair in _games(snapshot)
        for r, o in (pair, pair[::-1])
    }
    prior = _prior_weeks(snapshot, history, chronicle)
    count = max(
        len(snapshot.get("rosters") or []),
        len(external.official_power_rankings),
        max(
            (r.previous_rank or 0 for r in external.official_power_rankings), default=0
        ),
        2,
    )
    result = []
    for row in rows:
        rid = int(row["roster_id"])
        game = games.get(rid)
        if not game:
            continue
        own, opponent = game
        score = points[rid]
        other = float(opponent["points"])
        win = score > other
        opponent_team = next(
            (
                r.get("team")
                for r in rows
                if int(r["roster_id"]) == int(opponent["roster_id"])
            ),
            None,
        )
        rank = _entering_rank(external, int(opponent["roster_id"]), opponent_team)
        record, consistency = [], []
        for w, previous in sorted(prior.items()):
            me = next((r for r in previous if int(r["roster_id"]) == rid), None)
            if not me or _number(me.get("points")) is None:
                continue
            opp = next(
                (
                    r
                    for r in previous
                    if r.get("matchup_id") == me.get("matchup_id")
                    and int(r["roster_id"]) != rid
                ),
                None,
            )
            if opp and _number(opp.get("points")) is not None:
                record.append(
                    1.0
                    if float(me["points"]) > float(opp["points"])
                    else 0.5 if float(me["points"]) == float(opp["points"]) else 0.0
                )
                others = [
                    float(r["points"])
                    for r in previous
                    if int(r["roster_id"]) != rid
                    and _number(r.get("points")) is not None
                ]
                consistency.append(
                    sum(
                        (
                            1
                            if float(me["points"]) > p
                            else 0.5 if float(me["points"]) == p else 0
                        )
                        for p in others
                    )
                    / len(others)
                    if others
                    else 0.5
                )
        peers = [v for k, v in points.items() if k != rid]
        warnings = []
        if rank is None:
            warnings.append(
                "Opponent entering-week previous_rank unavailable; neutral opponent-quality component."
            )
        if len(record) < max(0, int(snapshot.get("week") or 1) - 1):
            warnings.append(
                "Incomplete entering-week history; available prior H2H/all-play results only, neutral if absent."
            )
        components = {
            "result": 1.0 if win else 0.5 if score == other else 0.0,
            "efficiency": min(1.0, max(0.0, float(row.get("efficiency") or 0))),
            "scoring": (
                sum(1 if score > p else 0.5 if score == p else 0 for p in peers)
                / len(peers)
                if peers
                else 0.5
            ),
            "record_consistency": (
                (
                    0.5 * (sum(record) / len(record))
                    + 0.5 * (sum(consistency) / len(consistency))
                )
                if record
                else 0.5
            ),
            "opponent_quality": (
                max(0.0, min(1.0, (count - rank) / (count - 1))) if rank else 0.5
            ),
        }
        total = sum(
            components[k] * v
            for k, v in {
                "result": 0.25,
                "efficiency": 0.25,
                "scoring": 0.20,
                "record_consistency": 0.15,
                "opponent_quality": 0.15,
            }.items()
        )
        result.append(
            {
                "facts": {
                    **row,
                    "head_to_head_result": (
                        "win" if win else "tie" if score == other else "loss"
                    ),
                    "victory_margin": round(abs(score - other), 2),
                    "opponent_roster_id": int(opponent["roster_id"]),
                    "opponent_entering_power_rank": rank,
                    "entering_record": {
                        "wins": record.count(1.0),
                        "losses": record.count(0.0),
                        "ties": record.count(0.5),
                    },
                    "data_warnings": warnings,
                },
                "components": components,
                "score": total,
            }
        )
    return sorted(
        result,
        key=lambda r: (
            -r["score"],
            -r["facts"]["actual_points"],
            -r["facts"]["efficiency"],
            int(r["facts"]["roster_id"]),
        ),
    )


def manager_honor(snapshot, dossier, external, history=(), chronicle=None):
    scored = manager_scores(snapshot, dossier, external, history, chronicle)
    winner = next(
        (r["facts"] for r in scored if r["facts"]["head_to_head_result"] == "win"), None
    )
    # Review-only: near-perfect lineup, top-quarter scoring, top-quarter opponent,
    # and a loss of no more than one point. Never overrides the winning manager.
    n = max(1, len(snapshot.get("rosters") or []))
    exceptional = [
        {
            **r["facts"],
            "status": "MANUAL_REVIEW",
            "reason": "Exceptional close loss; editorial review only.",
        }
        for r in scored
        if r["facts"]["head_to_head_result"] == "loss"
        and r["facts"]["victory_margin"] <= 1
        and r["components"]["efficiency"] >= 0.98
        and r["components"]["scoring"] >= 0.75
        and r["facts"]["opponent_entering_power_rank"] is not None
        and r["facts"]["opponent_entering_power_rank"] <= max(1, n // 4)
    ]
    return winner, exceptional


def _transactions(snapshot, chronicle=None):
    """Same-week additions are recent; prior drops/trades support former-player stories."""
    current = int(snapshot.get("week") or 0)
    rows = {}
    weeks = ((snapshot.get("flagship_sleeper") or {}).get("transactions") or {}).get(
        "weeks"
    ) or {}
    for raw, transactions in {
        **weeks,
        str(current): snapshot.get("transactions") or weeks.get(str(current), []),
    }.items():
        if int(raw) > current:
            continue
        for tx in transactions:
            if tx.get("status") == "complete":
                key = str(tx.get("transaction_id") or "")
                if key:
                    rows[key] = {**tx, "week": int(raw)}
    if chronicle:
        key = (snapshot.get("editorial") or {}).get("league_key", "")
        season = str((snapshot.get("league") or {}).get("season"))
        for event in chronicle.league_events(
            key, {"TRADE", "DROP", "WAIVER_ADD", "FREE_AGENT_ADD"}
        ):
            if (
                str(event.get("season")) != season
                or not 0 < int(event.get("week") or 0) <= current
            ):
                continue
            tx = event.get("evidence") or {}
            tid = str(tx.get("transaction_id") or "")
            if tid:
                rows.setdefault(
                    tid,
                    {
                        **tx,
                        "week": int(event["week"]),
                        "status": "complete",
                        "event_id": event.get("event_id"),
                    },
                )
    return list(rows.values())


def research_honors(snapshot, dossier, external, history=(), chronicle=None):
    external = _current_handoff(snapshot, external)
    winner, exceptional = manager_honor(snapshot, dossier, external, history, chronicle)
    lineup = {int(r["roster_id"]): r for r in dossier.get("lineup_efficiency") or []}
    names = {rid: r.get("team") for rid, r in lineup.items()}
    players = snapshot.get("players") or {}
    rosters = {int(r["roster_id"]): r for r in snapshot.get("rosters") or []}
    slots = starter_slots(snapshot.get("league") or {})
    projections, matchup_projections, projection_error = frozen_projections(snapshot)
    availability = {k: {"status": "AVAILABLE"} for k in LABELS}
    availability["THE_SPOILER"] = {
        "status": "UNSUPPORTED",
        "reason": "Requires late-season elimination and counterfactual playoff qualification/seeding evidence; not inferred.",
    }
    availability["FAAB_FURNACE"] = {
        "status": "MANUAL_REVIEW",
        "reason": "No established substantial-FAAB threshold; positive spend with <=1 point immediate return is review evidence only.",
    }
    needed = {
        str(p)
        for m in snapshot.get("matchups") or []
        for p in m.get("players") or []
        if str(p)
        not in {
            str(p)
            for k in ("reserve", "taxi")
            for p in rosters.get(int(m["roster_id"]), {}).get(k) or []
        }
    }
    missing = sorted(p for p in needed if projections.get(p) is None)
    player_ready = not projection_error and not missing
    if not player_ready:
        for code in PLAYER_PROJECTION_RULES:
            availability[code] = {
                "status": "UNAVAILABLE",
                "reason": projection_error
                or "Frozen pregame player projections missing for: "
                + ", ".join(missing),
            }
    matchup_ready = not projection_error and all(
        matchup_projections.get(str(m["roster_id"])) is not None
        for m in snapshot.get("matchups") or []
    )
    if not matchup_ready:
        for code in ("NO_FEAR", "AGAINST_ALL_ODDS"):
            availability[code] = {
                "status": "UNAVAILABLE",
                "reason": projection_error
                or "Missing frozen pregame matchup projection totals for completed-week rosters.",
            }
    if any(
        _entering_rank(external, int(m["roster_id"]), names.get(int(m["roster_id"])))
        is None
        for m in snapshot.get("matchups") or []
    ):
        availability["GIANT_KILLER"] = {
            "status": "PARTIAL",
            "reason": "Missing authoritative entering-week previous_rank for one or more teams.",
        }
        if availability["AGAINST_ALL_ODDS"]["status"] == "AVAILABLE":
            availability["AGAINST_ALL_ODDS"] = dict(availability["GIANT_KILLER"])
    transaction_source = (snapshot.get("flagship_sleeper") or {}).get(
        "transactions"
    ) or {}
    transaction_weeks = transaction_source.get("weeks") or {}
    current_week = int(snapshot.get("week") or 0)
    current_transactions_known = (
        "transactions" in snapshot or str(current_week) in transaction_weeks
    )
    if not current_transactions_known:
        for code in ("SCRAPHEAP_SAVIOR", "HOT_OFF_THE_ANVIL", "FAAB_FURNACE"):
            availability[code] = {
                "status": "UNAVAILABLE",
                "reason": "Completed-week transaction collection is missing.",
            }
    if not all(str(w) in transaction_weeks for w in range(1, current_week + 1)):
        availability["CUT_BY_YOUR_OWN_BLADE"] = {
            "status": "PARTIAL",
            "reason": "Full season transaction history is not confirmed; only documented former-player events can qualify.",
        }
    transactions = _transactions(snapshot, chronicle)
    prior = _prior_weeks(snapshot, history, chronicle)
    if int(snapshot.get("week") or 0) - 1 not in prior:
        availability["REFORGED"] = {
            "status": "UNAVAILABLE",
            "reason": "Previous completed-week matchup results missing.",
        }
    candidates = []
    reviews = []
    all_scores = sorted(
        (
            float(m["points"])
            for m in snapshot.get("matchups") or []
            if _number(m.get("points")) is not None
        ),
        reverse=True,
    )
    top4 = all_scores[min(3, len(all_scores) - 1)] if all_scores else float("inf")

    def add(code, rid, event, evidence, modifiers=(), status="QUALIFIED"):
        target = reviews if status == "MANUAL_REVIEW" else candidates
        target.append(
            {
                "candidate_id": f"{snapshot.get('week')}:{rid}:{event}:{code}",
                "candidate_type": code,
                "label": LABELS[code],
                "roster_id": rid,
                "team": names.get(rid),
                "event_key": event,
                "status": status,
                "modifiers": list(modifiers),
                "reason": LABELS[code]
                + " qualification supported by completed-week evidence.",
                "evidence": evidence,
            }
        )

    for pair in _games(snapshot):
        for me, opponent in (pair, pair[::-1]):
            rid = int(me["roster_id"])
            oid = int(opponent["roster_id"])
            score = float(me["points"])
            other = float(opponent["points"])
            won = score > other
            lost = score < other
            margin = round(abs(score - other), 2)
            event = f"matchup:{me['matchup_id']}"
            if not won and not lost:
                continue
            starters = [str(p) for p in me.get("starters") or [] if str(p) != "0"]
            points = {
                str(p): _number(v)
                for p, v in (
                    me.get("players_points") or me.get("players_points_custom") or {}
                ).items()
            }
            excluded = {
                str(p)
                for k in ("reserve", "taxi")
                for p in rosters.get(rid, {}).get(k) or []
            }
            bench = [
                str(p)
                for p in me.get("players") or []
                if str(p) not in set(starters) | excluded
            ]
            facts = {
                "points": score,
                "opponent_points": other,
                "margin": margin,
                "opponent_roster_id": oid,
            }
            decisions = []
            if player_ready and slots and len(starters) == len(slots):
                for starter in starters:
                    for alternative in bench:
                        if (
                            projections.get(starter) is None
                            or projections.get(alternative) is None
                            or points.get(starter) is None
                            or points.get(alternative) is None
                        ):
                            continue
                        if projections[starter] >= projections[alternative]:
                            continue
                        replacement = [p for p in starters if p != starter] + [
                            alternative
                        ]
                        _, assignment = optimal_lineup(
                            replacement, {p: 1.0 for p in replacement}, slots, players
                        )
                        if len(assignment) != len(slots):
                            continue
                        swing = round(points[starter] - points[alternative], 2)
                        if (won and swing > 0 and swing >= margin) or (
                            lost and swing < 0 and -swing >= margin
                        ):
                            decisions.append(
                                {
                                    "started_player_id": starter,
                                    "alternative_player_id": alternative,
                                    "started_projection": projections[starter],
                                    "alternative_projection": projections[alternative],
                                    "point_swing": swing,
                                    "legal_assignment": assignment,
                                }
                            )
                if decisions:
                    # Independent decisions require different starters AND different alternatives.
                    independent = False
                    for first in decisions:
                        for second in decisions:
                            removed = {
                                first["started_player_id"],
                                second["started_player_id"],
                            }
                            added = {
                                first["alternative_player_id"],
                                second["alternative_player_id"],
                            }
                            if len(removed) != 2 or len(added) != 2:
                                continue
                            replacement = [
                                p for p in starters if p not in removed
                            ] + sorted(added)
                            _, assignment = optimal_lineup(
                                replacement,
                                {p: 1.0 for p in replacement},
                                slots,
                                players,
                            )
                            if len(assignment) == len(slots):
                                independent = True
                    add(
                        (
                            "MAD_BLACKSMITH"
                            if won and independent
                            else "IRON_BALLS" if won else "BONE_HEAD"
                        ),
                        rid,
                        event + ":lineup",
                        {"decisions": decisions, **facts},
                    )
                elif (
                    lost
                    and float(lineup.get(rid, {}).get("optimal_points") or 0)
                    - float(lineup.get(rid, {}).get("actual_points") or 0)
                    > margin
                ):
                    add(
                        "LEFT_ON_THE_ANVIL",
                        rid,
                        event + ":lineup",
                        {"optimal_points": lineup[rid]["optimal_points"], **facts},
                    )
            zeros = [
                p
                for p in starters
                if projections.get(p) is not None
                and projections[p] >= 10
                and points.get(p) == 0
            ]
            if player_ready and zeros:
                qualifying = [p for p in zeros if won or margin <= projections[p]]
                if qualifying:
                    add(
                        "TEMPERED" if won else "GOOSED",
                        rid,
                        event + ":zero",
                        {"players": qualifying, **facts},
                    )
            if not won:
                continue
            own_rank = _entering_rank(external, rid, names.get(rid))
            opp_rank = _entering_rank(external, oid, names.get(oid))
            giant = (
                own_rank is not None
                and opp_rank is not None
                and own_rank - opp_rank >= 8
            )
            fear = (
                matchup_ready
                and matchup_projections[str(oid)] - matchup_projections[str(rid)] >= 15
            )
            if giant or fear:
                add(
                    (
                        "AGAINST_ALL_ODDS"
                        if giant and fear
                        else "GIANT_KILLER" if giant else "NO_FEAR"
                    ),
                    rid,
                    event + ":upset",
                    {
                        "entering_power_rank": own_rank,
                        "opponent_entering_power_rank": opp_rank,
                        "projected_deficit": (
                            matchup_projections.get(str(oid), 0)
                            - matchup_projections.get(str(rid), 0)
                            if matchup_ready
                            else None
                        ),
                        **facts,
                    },
                )
            if margin <= 1:
                add("BY_A_RIVET", rid, event, facts)
            if margin >= 50:
                add("HAMMER_DROP", rid, event, facts)
            complete = (
                bool(starters)
                and len(starters) == len(slots)
                and all(points.get(p) is not None for p in starters)
            )
            if (
                player_ready
                and complete
                and all(points[p] >= projections[p] for p in starters)
            ):
                add("FULL_FORGE", rid, event + ":lineup", facts)
            if complete:
                total = sum(points[p] for p in starters)
                dominant = [
                    p for p in starters if total > 0 and points[p] >= 0.4 * total
                ]
                if dominant:
                    add(
                        "ONE_MAN_FOUNDRY",
                        rid,
                        event + ":scoring",
                        {"player_ids": dominant, "lineup_total": total, **facts},
                    )
                lowest = sorted(starters, key=lambda p: (points[p], p))[:2]
                if len(lowest) == 2 and sum(points[p] for p in lowest) <= 5:
                    add(
                        "ONE_HAND_TIED",
                        rid,
                        event + ":two-starters",
                        {
                            "player_ids": lowest,
                            "combined_points": sum(points[p] for p in lowest),
                            **facts,
                        },
                    )
            if score >= top4 and other >= top4:
                add("ANVIL_TO_ANVIL", rid, event, facts)
            previous = prior.get(int(snapshot.get("week") or 0) - 1, [])
            prev_me = next((r for r in previous if int(r["roster_id"]) == rid), None)
            prev_opp = next(
                (
                    r
                    for r in previous
                    if prev_me
                    and r.get("matchup_id") == prev_me.get("matchup_id")
                    and int(r["roster_id"]) != rid
                ),
                None,
            )
            if (
                prev_me
                and prev_opp
                and _number(prev_me.get("points")) is not None
                and _number(prev_opp.get("points")) is not None
                and float(prev_me["points"]) < float(prev_opp["points"])
                and score - float(prev_me["points"]) >= 40
            ):
                add(
                    "REFORGED",
                    rid,
                    event,
                    {
                        "previous_points": prev_me["points"],
                        "improvement": round(score - float(prev_me["points"]), 2),
                        **facts,
                    },
                )
            for p in starters:
                if points.get(p) is None or points[p] < margin:
                    continue
                adds = [
                    t
                    for t in transactions
                    if int((t.get("adds") or {}).get(p) or 0) == rid
                    and t["week"] == int(snapshot["week"])
                ]
                # One acquisition candidate per player, even if ledger repeats an event.
                if adds:
                    tx = max(
                        adds,
                        key=lambda t: (
                            str(t.get("created") or ""),
                            str(t.get("transaction_id")),
                        ),
                    )
                    code = (
                        "HOT_OFF_THE_ANVIL"
                        if tx.get("type") == "trade"
                        else "SCRAPHEAP_SAVIOR"
                    )
                    free = (
                        tx.get("type") == "free_agent"
                        or (tx.get("settings") or {}).get("waiver_bid") == 0
                    )
                    add(
                        code,
                        rid,
                        event + ":player:" + p,
                        {
                            "player_id": p,
                            "points": points[p],
                            "transaction_id": tx.get("transaction_id"),
                            **facts,
                        },
                        ["FOUND_STEEL"] if free and code == "SCRAPHEAP_SAVIOR" else [],
                    )
                former = [
                    t
                    for t in transactions
                    if int((t.get("drops") or {}).get(p) or 0) == oid
                ]
                if former:
                    add(
                        "CUT_BY_YOUR_OWN_BLADE",
                        rid,
                        event + ":former:" + p,
                        {
                            "player_id": p,
                            "player_points": points[p],
                            "former_roster_id": oid,
                            "transaction_ids": sorted(
                                t["transaction_id"] for t in former
                            ),
                            **facts,
                        },
                    )
    for tx in transactions:
        spend = _number((tx.get("settings") or {}).get("waiver_bid"))
        if (
            tx.get("type") != "waiver"
            or tx["week"] != int(snapshot.get("week") or 0)
            or spend is None
            or spend <= 0
        ):
            continue
        for p, rid in (tx.get("adds") or {}).items():
            me = next(
                (
                    r
                    for r in snapshot.get("matchups") or []
                    if int(r["roster_id"]) == int(rid)
                ),
                {},
            )
            pts = _number((me.get("players_points") or {}).get(str(p)))
            if pts is not None and pts <= 1:
                add(
                    "FAAB_FURNACE",
                    int(rid),
                    "transaction:" + tx["transaction_id"],
                    {
                        "player_id": p,
                        "faab_spend": spend,
                        "player_points": pts,
                        "started": str(p) in [str(v) for v in me.get("starters") or []],
                    },
                    status="MANUAL_REVIEW",
                )
    return {
        "manager_of_the_week": winner,
        "exceptional_loss_review": exceptional,
        "rotating_award_candidates": sorted(
            candidates, key=lambda r: r["candidate_id"]
        ),
        "rotating_award_manual_review": reviews,
        "award_availability": availability,
        "selected_rotating_award": None,
        "rotating_award_policy": "Editor selects one or none; qualification never selects a published winner.",
    }
