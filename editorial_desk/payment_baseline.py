"""Compare commissioner-only payment log state to Sleeper trade evidence.

The spreadsheet itself and its payment information are NEVER stored in this
public repository. A redacted, compact baseline is supplied through an Actions
secret. Only Paid Ironbound is reconciled against this baseline.
"""
from __future__ import annotations

import json
import re
from typing import Any


BASELINE_FIELDS = (
    "draft_year", "workbook_team", "sleeper_team", "roster_id",
    "picks_traded_workbook", "payment_workbook",
    "outgoing_trade_ids", "review_flags",
)


def _namekey(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _roster_identity(snapshot: dict[str, Any]) -> tuple[dict[str, str], dict[str, set[str]]]:
    users = {
        str(u.get("user_id")): u
        for u in (snapshot.get("users") or [])
        if u.get("user_id") is not None
    }
    names: dict[str, str] = {}
    alias_to_rosters: dict[str, set[str]] = {}
    for row in snapshot.get("rosters") or []:
        if row.get("roster_id") is None:
            continue
        roster_id = str(row["roster_id"])
        user = users.get(str(row.get("owner_id")), {})
        metadata = user.get("metadata") or {}
        official = str(metadata.get("team_name") or user.get("display_name") or f"Roster {roster_id}")
        names[roster_id] = official
        # Only exact normalized Sleeper names/handles are accepted. Never
        # fuzzy-match payment records to the wrong manager.
        for candidate in (official, metadata.get("team_name"), user.get("display_name")):
            alias = _namekey(candidate)
            if alias:
                alias_to_rosters.setdefault(alias, set()).add(roster_id)
    return names, alias_to_rosters


def _outgoing_picks(snapshot: dict[str, Any], current_season: int) -> tuple[dict[tuple[int, str], set[str]], list[str]]:
    context = ((snapshot.get("flagship_sleeper") or {}).get("transactions") or {})
    if context.get("status") != "available" or not isinstance(context.get("weeks"), dict):
        raise ValueError("Cannot compare commissioner baseline with incomplete Sleeper transaction history")
    outgoing: dict[tuple[int, str], set[str]] = {}
    unknown: set[str] = set()
    seen: set[tuple[str, int, int, str]] = set()
    for transactions in context["weeks"].values():
        for trade in transactions or []:
            if not isinstance(trade, dict) or str(trade.get("type") or "").lower() != "trade":
                continue
            if str(trade.get("status") or "").lower() != "complete":
                continue
            transaction_id = str(trade.get("transaction_id") or "").strip()
            if not transaction_id:
                continue
            for pick in trade.get("draft_picks") or []:
                if not isinstance(pick, dict):
                    continue
                try:
                    year = int(pick.get("season"))
                    round_number = int(pick.get("round"))
                except (TypeError, ValueError):
                    continue
                if year <= current_season or round_number < 1:
                    continue
                dedupe = (transaction_id, year, round_number, str(pick.get("roster_id")))
                if dedupe in seen:
                    continue
                seen.add(dedupe)
                prior, recipient = pick.get("previous_owner_id"), pick.get("owner_id")
                if prior is None:
                    unknown.add(f"{transaction_id}: {year} Rd {round_number} original roster {pick.get('roster_id')}")
                    continue
                if recipient is not None and str(prior) == str(recipient):
                    continue
                outgoing.setdefault((year, str(prior)), set()).add(transaction_id)
    return outgoing, sorted(unknown)


def compare_paid_baseline(
    snapshot: dict[str, Any],
    baseline_json: str | None,
    *,
    current_season: int,
) -> dict[str, Any]:
    """Report workbook-vs-Sleeper differences without changing payment state.

    YES is a historical flag. An old YES with no current-year Sleeper trade is
    not a discrepancy. A NO with a verified outgoing trade is a review flag.
    Unpaid means 'marked unpaid in the uploaded snapshot', not a debt finding.
    """
    if not baseline_json or not baseline_json.strip():
        return {"status": "not_configured", "rows": [], "flagged": [], "unknown_senders": []}
    try:
        baseline = json.loads(baseline_json)
    except json.JSONDecodeError as exc:
        raise ValueError("Commissioner payment baseline secret is not valid JSON") from exc
    if not isinstance(baseline, dict) or baseline.get("schema_version") != 1:
        raise ValueError("Invalid commissioner payment baseline schema")
    if baseline.get("league_key") != "ironbound_sixteen":
        raise ValueError("Payment baseline must explicitly be for Paid Ironbound")
    if not isinstance(baseline.get("seasons"), dict) or not baseline["seasons"]:
        raise ValueError("Commissioner payment baseline has no future seasons")
    if not re.fullmatch(r"\\d{4}-\\d{2}-\\d{2}", str(baseline.get("recorded_as_of") or "")):
        raise ValueError("Commissioner payment baseline requires an as-of date")

    names, aliases = _roster_identity(snapshot)
    outgoing, unknown_senders = _outgoing_picks(snapshot, current_season)
    rows: list[dict[str, str]] = []
    flagged: list[dict[str, str]] = []
    covered: set[tuple[int, str]] = set()
    for year_text, entries in sorted(baseline["seasons"].items()):
        try:
            year = int(year_text)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid draft season in payment baseline") from exc
        if year <= current_season or not isinstance(entries, list) or not entries:
            raise ValueError("Payment baseline must contain nonempty future-year team rows")
        seen_names: set[str] = set()
        for entry in entries:
            if not isinstance(entry, dict) or not str(entry.get("team") or "").strip():
                raise ValueError("Invalid payment baseline team row")
            team = str(entry["team"]).strip()
            team_key = _namekey(team)
            if team_key in seen_names:
                raise ValueError(f"Duplicate payment baseline team in {year}")
            seen_names.add(team_key)
            if type(entry.get("picks_traded")) is not bool or type(entry.get("paid")) is not bool:
                raise ValueError("Payment baseline statuses must be booleans")
            candidates = aliases.get(team_key, set())
            matched = next(iter(candidates)) if len(candidates) == 1 else None
            if matched is not None:
                covered.add((year, matched))
            trade_ids = sorted(outgoing.get((year, matched), set())) if matched is not None else []
            flags = []
            if matched is None:
                flags.append("UNMATCHED_TEAM")
            if trade_ids and not entry["picks_traded"]:
                flags.append("TRADE_NOT_MARKED_IN_WORKBOOK")
            if entry["picks_traded"] and not entry["paid"]:
                flags.append("WORKBOOK_PAYMENT_MARKED_UNPAID")
            result = {
                "draft_year": str(year),
                "workbook_team": team,
                "sleeper_team": names.get(matched, "Unmatched — review manually"),
                "roster_id": matched or "",
                "picks_traded_workbook": "Yes" if entry["picks_traded"] else "No",
                "payment_workbook": "Paid" if entry["paid"] else "Unpaid",
                "outgoing_trade_ids": ", ".join(trade_ids),
                "review_flags": "; ".join(flags) or "OK",
            }
            rows.append(result)
            if flags:
                flagged.append(result)

    # The workbook may not yet have a tab for a newly tradeable season.
    # Preserve that as an explicit review item, not an implicit 'No'.
    for (year, rid), ids in sorted(outgoing.items()):
        if (year, rid) in covered:
            continue
        result = {
            "draft_year": str(year), "workbook_team": "Not found",
            "sleeper_team": names.get(rid, f"Roster {rid}"),
            "roster_id": rid,
            "picks_traded_workbook": "Not tracked",
            "payment_workbook": "Not tracked",
            "outgoing_trade_ids": ", ".join(sorted(ids)),
            "review_flags": "OUTGOING_PICK_NOT_MATCHED_TO_BASELINE",
        }
        rows.append(result)
        flagged.append(result)

    rows.sort(key=lambda row: (int(row["draft_year"]), row["workbook_team"], row["sleeper_team"]))
    flagged.sort(key=lambda row: (int(row["draft_year"]), row["workbook_team"], row["sleeper_team"]))
    return {
        "status": "configured",
        "recorded_as_of": baseline["recorded_as_of"],
        "rows": rows,
        "flagged": flagged,
        "unknown_senders": unknown_senders,
    }
