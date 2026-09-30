"""Historical Sleeper projection adapter and deterministic award audit.

Sleeper retains the projection resource for a completed week.  The adapter
validates season/week identity, scores those retained projected statistics with
the league's own scoring settings, and derives the matchup projection from the
submitted starters.  It deliberately does not pretend that a projection from a
different season/week is usable.

This module is installed from :mod:`editorial_desk.__init__` so the existing
honors contract can consume the corrected projection source without duplicating
the registry implementation.
"""

from __future__ import annotations

from collections import defaultdict
from functools import wraps
from math import isfinite
from typing import Any


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if isfinite(result) else None


def _projection_points(row: Any, scoring_settings: dict[str, Any]) -> float | None:
    """Score one Sleeper projection row with this league's scoring settings."""
    if not isinstance(row, dict):
        return None

    total = 0.0
    used = False
    for stat, weight in (scoring_settings or {}).items():
        value = _number(row.get(stat))
        multiplier = _number(weight)
        if value is None or multiplier is None:
            continue
        total += value * multiplier
        used = True
    if used:
        return round(total, 4)

    # Compatibility fallback when a league snapshot lacks scoring settings.
    reception = _number((scoring_settings or {}).get("rec"))
    if reception == 1:
        keys = ("pts_ppr", "pts_half_ppr", "pts_std")
    elif reception == 0.5:
        keys = ("pts_half_ppr", "pts_ppr", "pts_std")
    else:
        keys = ("pts_std", "pts_half_ppr", "pts_ppr")
    for key in keys:
        value = _number(row.get(key))
        if value is not None:
            return value
    return None


def _retained_sleeper_projections(snapshot: dict[str, Any]):
    source = ((snapshot.get("ranking_inputs") or {}).get("sleeper_projections") or {})
    if not source:
        return None

    season = str(
        (snapshot.get("league") or {}).get("season")
        or (snapshot.get("nfl_state") or {}).get("season")
        or ""
    )
    week = int(snapshot.get("week") or 0)
    try:
        same_week = int(source.get("week")) == week
    except (TypeError, ValueError):
        same_week = False

    if (
        source.get("status") != "available"
        or str(source.get("season") or "") != season
        or not same_week
    ):
        return (
            {},
            {},
            "Sleeper retained projections are unavailable or do not match the issue's same-season/week identity.",
        )

    scoring = (snapshot.get("league") or {}).get("scoring_settings") or {}
    player_points = {
        str(player_id): _projection_points(row, scoring)
        for player_id, row in (source.get("players") or {}).items()
    }
    player_points = {
        player_id: points
        for player_id, points in player_points.items()
        if points is not None
    }
    if not player_points:
        return (
            {},
            {},
            "Sleeper retained same-season/week projection resource contains no scoreable player projections.",
        )

    matchup_points: dict[str, float] = {}
    for matchup in snapshot.get("matchups") or []:
        roster_id = matchup.get("roster_id")
        starters = [
            str(player_id)
            for player_id in matchup.get("starters") or []
            if str(player_id) != "0"
        ]
        if roster_id is None or not starters:
            continue
        values = [player_points.get(player_id) for player_id in starters]
        if all(value is not None for value in values):
            matchup_points[str(roster_id)] = round(sum(values), 4)

    return player_points, matchup_points, None


def retained_or_legacy_projections(snapshot: dict[str, Any], legacy_loader):
    """Prefer Sleeper's retained issue-week resource; preserve legacy fixtures."""
    retained = _retained_sleeper_projections(snapshot)
    if retained is not None:
        return retained
    return legacy_loader(snapshot)


def _games(snapshot: dict[str, Any]) -> list[list[dict[str, Any]]]:
    grouped: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for row in snapshot.get("matchups") or []:
        if row.get("matchup_id") is not None:
            grouped[row["matchup_id"]].append(row)
    return [
        rows
        for rows in grouped.values()
        if len(rows) == 2 and all(_number(row.get("points")) is not None for row in rows)
    ]


def build_award_audit(
    snapshot: dict[str, Any],
    labels: dict[str, str],
    availability: dict[str, dict[str, Any]],
    candidates: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
) -> dict[str, Any]:
    """Explain qualified, failed, and unavailable outcomes for every rule."""
    by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
    review_by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        by_code[str(row.get("candidate_type"))].append(row)
    for row in reviews:
        review_by_code[str(row.get("candidate_type"))].append(row)

    audit: dict[str, Any] = {}
    games = _games(snapshot)
    for code, label in labels.items():
        status = (availability.get(code) or {}).get("status", "UNAVAILABLE")
        reason = (availability.get(code) or {}).get("reason")
        qualified = by_code.get(code, [])
        manual = review_by_code.get(code, [])
        evaluations: list[dict[str, Any]] = []

        # Margin rules are especially easy to audit numerically, so preserve a
        # row for every winning matchup instead of only the qualifying event.
        if code in {"BY_A_RIVET", "HAMMER_DROP"} and status == "AVAILABLE":
            threshold = 1.0 if code == "BY_A_RIVET" else 50.0
            for pair in games:
                ordered = sorted(
                    pair,
                    key=lambda row: float(row.get("points") or 0),
                    reverse=True,
                )
                winner_points = float(ordered[0].get("points") or 0)
                loser_points = float(ordered[1].get("points") or 0)
                if winner_points <= loser_points:
                    continue
                margin = round(winner_points - loser_points, 2)
                passed = margin <= threshold if code == "BY_A_RIVET" else margin >= threshold
                evaluations.append(
                    {
                        "roster_id": int(ordered[0]["roster_id"]),
                        "matchup_id": ordered[0].get("matchup_id"),
                        "result": "QUALIFIED" if passed else "NOT_QUALIFIED",
                        "metrics": {"margin": margin, "threshold": threshold},
                    }
                )
        elif qualified:
            evaluations.extend(
                {
                    "roster_id": row.get("roster_id"),
                    "result": "QUALIFIED",
                    "metrics": row.get("evidence") or {},
                }
                for row in qualified
            )
        elif manual:
            evaluations.extend(
                {
                    "roster_id": row.get("roster_id"),
                    "result": "MANUAL_REVIEW",
                    "metrics": row.get("evidence") or {},
                }
                for row in manual
            )
        elif status != "AVAILABLE":
            evaluations.append({"result": status, "reason": reason})
        else:
            evaluations.append(
                {
                    "result": "NOT_QUALIFIED",
                    "reason": "No completed-week event met the deterministic qualification rule.",
                }
            )

        audit[code] = {
            "label": label,
            "availability": status,
            "availability_reason": reason,
            "qualified_candidate_ids": [row["candidate_id"] for row in qualified],
            "manual_review_candidate_ids": [row["candidate_id"] for row in manual],
            "evaluations": evaluations,
        }
    return audit


def install() -> None:
    """Install the corrected source adapter once for all honors consumers."""
    from . import honors

    if getattr(honors, "_historical_awards_adapter_installed", False):
        return

    legacy_loader = honors.frozen_projections
    original_research = honors.research_honors

    def projection_loader(snapshot):
        return retained_or_legacy_projections(snapshot, legacy_loader)

    @wraps(original_research)
    def research_with_audit(snapshot, dossier, external, history=(), chronicle=None):
        result = original_research(snapshot, dossier, external, history, chronicle)
        result["award_audit"] = build_award_audit(
            snapshot,
            honors.LABELS,
            result.get("award_availability") or {},
            result.get("rotating_award_candidates") or [],
            result.get("rotating_award_manual_review") or [],
        )
        return result

    honors.frozen_projections = projection_loader
    honors.research_honors = research_with_audit
    honors._historical_awards_adapter_installed = True
