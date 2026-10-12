"""Evidence-only editorial leads derived from authoritative ranking handoffs."""
from __future__ import annotations

from typing import Any


def build_ranking_story_context(
    rankings: list[dict[str, Any]],
    standings: list[dict[str, Any]],
    playoff_odds: list[dict[str, Any]],
) -> dict[str, Any]:
    """Never infer movement without a verified prior rank or playoff trend without history."""
    by_roster = {int(row["roster_id"]): row for row in standings if row.get("roster_id") is not None}
    odds_by_roster = {int(row["roster_id"]): row for row in playoff_odds if row.get("roster_id") is not None}
    if not rankings:
        return {"status": "unavailable", "reason": "Awaiting authoritative publisher handoff", "rows": [], "angles": []}
    rows = []
    for item in sorted(rankings, key=lambda row: int(row["rank"])):
        rid = int(item["roster_id"])
        standing = by_roster.get(rid, {})
        odds = odds_by_roster.get(rid, {})
        movement = item.get("movement")
        previous_rank = item.get("previous_rank")
        if previous_rank is not None:
            expected = int(previous_rank) - int(item["rank"])
            if movement is not None and int(movement) != expected:
                raise ValueError(f"Ranking movement mismatch for roster {rid}")
            movement = expected
        else:
            movement = None
        standing_rank = standing.get("rank")
        row = {
            "roster_id": rid, "team": item.get("team"),
            "power_rank": int(item["rank"]), "previous_power_rank": previous_rank,
            "power_rank_movement": movement,
            "standing_rank": standing_rank,
            "rank_vs_standings": int(standing_rank) - int(item["rank"]) if standing_rank is not None else None,
            "record": {
                "wins": standing.get("wins"), "losses": standing.get("losses"),
                "ties": standing.get("ties"), "points_for": standing.get("points_for")
            },
            "power_score": item.get("score"), "components": item.get("components") or {},
            "playoff_odds": odds,
        }
        rows.append(row)
    climbers = sorted([r for r in rows if r["power_rank_movement"] is not None and r["power_rank_movement"] > 0],
                      key=lambda r: (-r["power_rank_movement"], r["power_rank"]))
    fallers = sorted([r for r in rows if r["power_rank_movement"] is not None and r["power_rank_movement"] < 0],
                     key=lambda r: (r["power_rank_movement"], r["power_rank"]))
    discrepancies = sorted([r for r in rows if r["rank_vs_standings"] is not None and abs(r["rank_vs_standings"]) >= 3],
                           key=lambda r: (-abs(r["rank_vs_standings"]), r["power_rank"]))
    angles = []
    for label, items in (("power_risers", climbers[:3]), ("power_fallers", fallers[:3]),
                         ("standings_vs_power_disagreement", discrepancies[:3])):
        for row in items:
            angles.append({"type": label, "roster_id": row["roster_id"], "team": row["team"],
                           "power_rank": row["power_rank"], "previous_power_rank": row["previous_power_rank"],
                           "movement": row["power_rank_movement"], "standing_rank": row["standing_rank"],
                           "record": row["record"], "playoff_odds": row["playoff_odds"],
                           "source": "authoritative rankings + Sleeper official standings",
                           "note": "Editorial lead for verification, not automatically generated news copy."})
    return {"status": "ready", "authority": "external_power_rankings",
            "rows": rows, "angles": angles,
            "cautions": ["Power ranking is not the official standings table.",
                         "Playoff odds are forward-looking estimates, not guaranteed outcomes.",
                         "Rank movement requires a previous publisher rank."]}
