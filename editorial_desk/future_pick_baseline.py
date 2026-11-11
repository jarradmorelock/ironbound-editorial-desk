"""Conservative comparison of Sleeper trades to a private commissioner workbook baseline.

No contact/payment amounts and no name guessing. This file contains only logic;
the baseline JSON is supplied as a private GitHub Actions secret.
"""
from __future__ import annotations

import re
from typing import Any


REVIEW_FIELDS = ("draft_year", "team", "workbook_picks_traded",
                 "workbook_payment_status", "sleeper_evidence", "finding")


def _canonical(name: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(name or "").lower())


def compare_paid_baseline(
    baseline: dict[str, Any], snapshot: dict[str, Any],
    all_trades: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if baseline.get("league_key") != "ironbound_sixteen":
        raise ValueError("Baseline applies only to Paid Ironbound")
    seasons = baseline.get("seasons")
    if not isinstance(seasons, dict) or not seasons:
        raise ValueError("Baseline missing seasons")
    as_of = str(baseline.get("recorded_as_of") or "unknown")
    rosters = snapshot.get("rosters") or []
    users = {str(u.get("user_id")): u for u in snapshot.get("users") or []}
    roster_to_aliases: dict[str, set[str]] = {}
    for roster in rosters:
        rid = str(roster.get("roster_id") or "")
        user = users.get(str(roster.get("owner_id"))) or {}
        aliases = (
            (roster.get("metadata") or {}).get("team_name"),
            (user.get("metadata") or {}).get("team_name"),
            user.get("display_name"),
        )
        roster_to_aliases[rid] = {_canonical(x) for x in aliases if x}
    # Multiple exact matches are ambiguous; do not guess from row order.
    team_to_roster: dict[str, set[str]] = {}
    for rid, aliases in roster_to_aliases.items():
        for alias in aliases:
            team_to_roster.setdefault(alias, set()).add(rid)

    evidence: set[tuple[str, int]] = set()
    ambiguous_picks: list[str] = []
    for tx in all_trades.values():
        for pick in tx.get("draft_picks") or []:
            if not isinstance(pick, dict):
                continue
            try:
                year = int(pick.get("season"))
                rnd = int(pick.get("round"))
            except (TypeError, ValueError):
                continue
            prior = pick.get("previous_owner_id")
            next_owner = pick.get("owner_id")
            if prior is not None and next_owner is not None and str(prior) != str(next_owner):
                evidence.add((str(prior), year))
            elif prior is None:
                ambiguous_picks.append(f"{tx.get('transaction_id', '?')}: {year} round {rnd} lacks previous owner")
    rows: list[dict[str, str]] = []
    flagged: list[dict[str, str]] = []
    for year_str, teams in sorted(seasons.items()):
        try:
            year = int(year_str)
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid baseline season") from exc
        if not isinstance(teams, list) or len(teams) != 16:
            raise ValueError(f"Baseline {year} must contain all 16 paid league teams")
        seen_teams: set[str] = set()
        for raw in teams:
            team = str(raw.get("team") or "").strip()
            normalized = _canonical(team)
            if not normalized or normalized in seen_teams:
                raise ValueError(f"Invalid or repeated baseline team name in {year}")
            seen_teams.add(normalized)
            traded = raw.get("picks_traded")
            paid = raw.get("paid")
            if not isinstance(traded, bool) or not isinstance(paid, bool):
                raise ValueError("Baseline values must be booleans")
            matches = team_to_roster.get(normalized, set())
            roster_id = next(iter(matches)) if len(matches) == 1 else None
            if roster_id is None:
                source = "unresolved team mapping"
                finding = "REVIEW: exact Sleeper team name not found or ambiguous"
            elif (roster_id, year) in evidence:
                source = "outgoing pick trade recorded"
                finding = "REVIEW: workbook says No but Sleeper shows a trade" if not traded else "Consistent with recorded trade"
            else:
                source = "no outgoing pick found in inspected season"
                finding = "Not independently verified; earlier-season trades may exist" if traded else "No conflict in inspected trades"

            if traded and not paid:
                finding += "; REVIEW: traded pick year recorded unpaid"
            row = {
                "draft_year": str(year), "team": team,
                "workbook_picks_traded": "Yes" if traded else "No",
                "workbook_payment_status": "Paid" if paid else "Unpaid",
                "sleeper_evidence": source, "finding": finding,
            }
            rows.append(row)
            if "REVIEW" in finding:
                flagged.append(row)
    return {
        "baseline_date": as_of, "rows": rows, "flagged": flagged,
        "ambiguous_picks": ambiguous_picks,
        "matched_team_count": len({r["team"] for r in rows if r["sleeper_evidence"] != "unresolved team mapping"}),
        "coverage": "Current 2026 league transaction history only; earlier years not disproved",
    }
