from __future__ import annotations

from collections import Counter
from typing import Any

from .feature_models import FeatureResult, ready, ready_no_items
from .preseason_features import (
    draft_results,
    dynasty_market,
    future_pick_ledger,
    offense_defense_splits,
    positional_strength,
    recruiting_class,
    rookie_draft,
    roster_age,
)

GENERIC_SUPPORT_FEATURES = {
    "first_shift",
    "paper_favorite_inputs",
    "season_prediction_inputs",
    "preseason_truth_inputs",
    "first_read_inputs",
    "parity_inputs",
    "commissioner_warning_inputs",
    "preseason_superlative_inputs",
    "team_capsules",
    "committee_poll_inputs",
    "west_context",
    "selection_committee_inputs",
    "division_board",
    "performance_index_inputs",
    "recruiting_desk",
    "opening_credits_inputs",
    "development_slate",
    "future_pick_scarcity",
}


def preseason_support(
    feature: str,
    snapshot: dict[str, Any],
    dossier: dict[str, Any],
) -> FeatureResult | None:
    """Return neutral factual support for editorially named preseason departments.

    These payloads intentionally provide evidence only. They never select a
    favorite, warning, superlative, prediction, committee winner, or editorial
    conclusion.
    """
    if feature not in GENERIC_SUPPORT_FEATURES:
        return None

    if feature == "team_capsules":
        return _team_capsules(snapshot)
    if feature == "west_context":
        return _west_context(dossier)
    if feature == "division_board":
        return _division_board(dossier)
    if feature == "recruiting_desk":
        return _recruiting_desk(snapshot)
    if feature == "development_slate":
        return _development_slate(snapshot)
    if feature == "future_pick_scarcity":
        return _future_pick_context(snapshot)

    facts = _common_fact_bundle(snapshot, dossier)
    if not facts["facts"]:
        return ready_no_items(feature, reason="No neutral preseason support facts were available")
    return ready(
        feature,
        facts,
        degraded=bool(facts["unavailable_sources"]),
        reason=(
            "Some supporting sources were unavailable"
            if facts["unavailable_sources"]
            else None
        ),
    )


def _common_fact_bundle(snapshot: dict[str, Any], dossier: dict[str, Any]) -> dict[str, Any]:
    producers = {
        "draft_results": draft_results(snapshot),
        "roster_experience": roster_age(snapshot),
        "positional_counts": positional_strength(snapshot),
        "offense_idp_split": offense_defense_splits(snapshot),
        "rookie_draft": rookie_draft(snapshot),
        "recruiting_classes": recruiting_class(snapshot),
        "future_pick_movements": future_pick_ledger(snapshot),
        "dynasty_market": dynasty_market(snapshot),
    }
    facts: dict[str, Any] = {}
    unavailable: list[str] = []
    empty: list[str] = []
    for name, result in producers.items():
        if result.status == "unavailable":
            unavailable.append(name)
        elif result.status == "ready_no_items":
            empty.append(name)
            facts[name] = result.data
        else:
            facts[name] = result.data

    rankings = dossier.get("rankings")
    if rankings not in (None, {}, []):
        facts["ranking_context"] = rankings
    next_matchups = snapshot.get("next_matchups")
    if next_matchups not in (None, {}, []):
        facts["next_matchup_context"] = next_matchups
    transactions = [
        row
        for row in (snapshot.get("transactions") or [])
        if str(row.get("status") or "complete").casefold() in {"complete", "completed"}
    ]
    if transactions:
        facts["transactions"] = transactions

    return {
        "facts": facts,
        "unavailable_sources": unavailable,
        "empty_sources": empty,
        "editorial_selection_required": True,
    }


def _team_capsules(snapshot: dict[str, Any]) -> FeatureResult:
    ages = _rows_by_roster(roster_age(snapshot))
    splits = _rows_by_roster(offense_defense_splits(snapshot))
    positions_result = positional_strength(snapshot)
    positions = positions_result.data if positions_result.status == "ready" else {}
    rookies = _rows_by_roster(recruiting_class(snapshot))
    traded_picks = future_pick_ledger(snapshot)
    pick_counts: Counter[int] = Counter()
    if traded_picks.status == "ready":
        for row in traded_picks.data:
            current = row.get("current_roster_id")
            if isinstance(current, int):
                pick_counts[current] += 1

    rows = []
    for roster in snapshot.get("rosters") or []:
        roster_id = int(roster.get("roster_id") or 0)
        rows.append(
            {
                "roster_id": roster_id,
                "team": _team_name(snapshot, roster_id),
                "roster_experience": ages.get(roster_id),
                "positional_counts": positions.get(roster_id, {}),
                "offense_idp_split": splits.get(roster_id),
                "rookie_class": rookies.get(roster_id),
                "acquired_future_pick_movements": pick_counts.get(roster_id, 0),
            }
        )
    if not rows:
        return ready_no_items("team_capsules", reason="No rosters available for capsules")
    return ready("team_capsules", rows)


def _west_context(dossier: dict[str, Any]) -> FeatureResult:
    divisions = dossier.get("divisions") or {}
    west = {
        key: value
        for key, value in divisions.items()
        if "west" in str((value or {}).get("name") or key).casefold()
    }
    ranking_rows = ((dossier.get("rankings") or {}).get("official_standings") or [])
    west_ranks = [
        row
        for row in ranking_rows
        if "west" in str(row.get("division_name") or "").casefold()
    ]
    data = {"division_context": west, "ranking_context": west_ranks}
    if not west and not west_ranks:
        return ready_no_items("west_context", reason="No West division facts were available")
    return ready("west_context", data)


def _division_board(dossier: dict[str, Any]) -> FeatureResult:
    divisions = dossier.get("divisions") or {}
    rankings = (dossier.get("rankings") or {}).get("official_standings") or []
    data = {
        "division_context": divisions,
        "ranking_context": [row for row in rankings if row.get("division_id") is not None],
    }
    if not divisions and not data["ranking_context"]:
        return ready_no_items("division_board", reason="No division facts were available")
    return ready("division_board", data)


def _recruiting_desk(snapshot: dict[str, Any]) -> FeatureResult:
    rookie = rookie_draft(snapshot)
    classes = recruiting_class(snapshot)
    picks = future_pick_ledger(snapshot)
    data = {
        "rookie_draft": _safe_data(rookie),
        "recruiting_classes": _safe_data(classes),
        "future_pick_movements": _safe_data(picks),
        "source_status": {
            "rookie_draft": rookie.status,
            "recruiting_classes": classes.status,
            "future_pick_movements": picks.status,
        },
    }
    degraded = any(status == "unavailable" for status in data["source_status"].values())
    if not any(data[key] for key in ("rookie_draft", "recruiting_classes", "future_pick_movements")):
        return ready_no_items("recruiting_desk", reason="No recruiting facts were available")
    return ready("recruiting_desk", data, degraded=degraded)


def _development_slate(snapshot: dict[str, Any]) -> FeatureResult:
    ages = roster_age(snapshot)
    rookies = recruiting_class(snapshot)
    picks = future_pick_ledger(snapshot)
    data = {
        "roster_experience": _safe_data(ages),
        "rookie_classes": _safe_data(rookies),
        "future_pick_movements": _safe_data(picks),
        "source_status": {
            "roster_experience": ages.status,
            "rookie_classes": rookies.status,
            "future_pick_movements": picks.status,
        },
    }
    degraded = any(status == "unavailable" for status in data["source_status"].values())
    if not any(data[key] for key in ("roster_experience", "rookie_classes", "future_pick_movements")):
        return ready_no_items("development_slate", reason="No development facts were available")
    return ready("development_slate", data, degraded=degraded)


def _future_pick_context(snapshot: dict[str, Any]) -> FeatureResult:
    picks = future_pick_ledger(snapshot)
    if picks.status == "unavailable":
        return ready(
            "future_pick_scarcity",
            {
                "coverage": "traded_pick_movements_only",
                "ledger": [],
                "movement_counts": {},
            },
            degraded=True,
            reason=picks.reason,
        )
    if picks.status == "ready_no_items":
        return ready_no_items(
            "future_pick_scarcity",
            reason="No traded future-pick movements; complete pick inventory was not inferred",
        )
    counts: Counter[int] = Counter()
    for row in picks.data:
        current = row.get("current_roster_id")
        if isinstance(current, int):
            counts[current] += 1
    return ready(
        "future_pick_scarcity",
        {
            "coverage": "traded_pick_movements_only",
            "ledger": picks.data,
            "movement_counts": dict(sorted(counts.items())),
            "caution": "This is not a complete future-pick inventory and should not be described as ownership scarcity without additional source data.",
        },
    )


def _rows_by_roster(result: FeatureResult) -> dict[int, dict[str, Any]]:
    if result.status != "ready" or not isinstance(result.data, list):
        return {}
    return {
        int(row["roster_id"]): row
        for row in result.data
        if isinstance(row, dict) and row.get("roster_id") is not None
    }


def _safe_data(result: FeatureResult) -> Any:
    return result.data if result.status in {"ready", "ready_no_items"} else None


def _team_name(snapshot: dict[str, Any], roster_id: int) -> str:
    users = {str(row.get("user_id")): row for row in snapshot.get("users") or []}
    for roster in snapshot.get("rosters") or []:
        if int(roster.get("roster_id") or 0) != roster_id:
            continue
        owner = users.get(str(roster.get("owner_id"))) or {}
        metadata = owner.get("metadata") or {}
        return str(metadata.get("team_name") or owner.get("display_name") or owner.get("username") or f"Roster {roster_id}")
    return f"Roster {roster_id}"
