"""Private weekly commissioner audit from the Editorial Desk's Sleeper snapshots.

No second Sleeper collector, no Discord posts, and no new credentials.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from io import StringIO
import json
from pathlib import Path
from typing import Any

from .emailer import _deliver

AUDITED_LEAGUES = (
    ("ironbound_sixteen", "Ironbound Sixteen (Paid)"),
    ("free_ironbound_sixteen", "Free Ironbound / Unbound"),
)
TRANSFER_FIELDS = (
    "league", "trade_utc", "transaction_id", "pick_year", "round",
    "original_team", "traded_by", "received_by", "verification",
)
HOLDING_FIELDS = (
    "league", "pick_year", "round", "original_team",
    "current_holder", "previous_holder", "verification",
)


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _timestamp_ms(row: dict[str, Any]) -> int | None:
    for field in ("status_updated", "created"):
        val = _int(row.get(field))
        if val is not None and 1_500_000_000_000 <= val <= 4_000_000_000_000:
            return val
    return None


def _names(snapshot: dict[str, Any]) -> dict[str, str]:
    users = {
        str(u["user_id"]): str((u.get("metadata") or {}).get("team_name")
                              or u.get("display_name") or "Unnamed manager")
        for u in snapshot.get("users") or [] if u.get("user_id") is not None
    }
    return {
        str(r["roster_id"]): users.get(str(r.get("owner_id")), f"Roster {r['roster_id']}")
        for r in snapshot.get("rosters") or [] if r.get("roster_id") is not None
    }


def _team(names: dict[str, str], rid: Any) -> str:
    if rid is None:
        return "Unknown — verify in Sleeper"
    return names.get(str(rid), f"Roster {rid} — verify")


def _csv_text(rows: list[dict[str, str]], columns: tuple[str, ...]) -> str:
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\r\n", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def build_future_pick_report(
    output_root: Path, season: str, week: int, *, as_of: datetime | None = None,
) -> dict[str, Any]:
    """Last-seven-day trade delta, plus current holdings for full reconciliation.

    Fail closed when a flagship snapshot or transaction round collection is
    incomplete; otherwise an empty email would falsely mean zero transfers.
    """
    as_of = as_of or datetime.now(timezone.utc)
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone aware")
    as_of = as_of.astimezone(timezone.utc)
    current_year = _int(season)
    if current_year is None:
        raise ValueError("Invalid NFL season")
    lower_ms = int((as_of - timedelta(days=7)).timestamp() * 1000)
    upper_ms = int(as_of.timestamp() * 1000)

    transfers: list[dict[str, str]] = []
    holdings: list[dict[str, str]] = []
    notes: list[str] = []
    seen: set[tuple[str, str, int, int, str]] = set()

    for key, label in AUDITED_LEAGUES:
        source = Path(output_root) / str(season) / f"week-{week:02d}" / key / "snapshot.json"
        try:
            snapshot = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Missing or invalid audit snapshot: {source}") from exc
        if str((snapshot.get("nfl_state") or {}).get("season")) != str(season):
            raise ValueError(f"Unexpected season in audit snapshot: {source}")
        names = _names(snapshot)
        context = ((snapshot.get("flagship_sleeper") or {}).get("transactions") or {})
        if context.get("status") != "available" or not context.get("weeks"):
            raise ValueError(f"Incomplete transaction collection for {label}: {context.get('status')}")
        unique: dict[str, dict[str, Any]] = {}
        for rows in context["weeks"].values():
            for tx in rows or []:
                if not isinstance(tx, dict):
                    continue
                if str(tx.get("type") or "").lower() != "trade":
                    continue
                if str(tx.get("status") or "").lower() != "complete":
                    continue
                if tx.get("transaction_id"):
                    unique[str(tx["transaction_id"])] = tx

        undated = 0
        for tx_id, transaction in unique.items():
            timestamp = _timestamp_ms(transaction)
            picks = transaction.get("draft_picks") or []
            if timestamp is None:
                if any((_int(p.get("season")) or 0) > current_year
                       for p in picks if isinstance(p, dict)):
                    undated += 1
                continue
            if not lower_ms <= timestamp <= upper_ms:
                continue
            for pick in picks:
                if not isinstance(pick, dict):
                    continue
                year, round_number = _int(pick.get("season")), _int(pick.get("round"))
                if year is None or year <= current_year or round_number is None or round_number < 1:
                    continue
                previous, recipient = pick.get("previous_owner_id"), pick.get("owner_id")
                original = pick.get("roster_id")
                if previous is not None and recipient is not None and str(previous) == str(recipient):
                    continue
                identity = (key, tx_id, year, round_number, str(original))
                if identity in seen:
                    continue
                seen.add(identity)
                transfers.append({
                    "league": label,
                    "trade_utc": datetime.fromtimestamp(timestamp / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                    "transaction_id": tx_id,
                    "pick_year": str(year),
                    "round": str(round_number),
                    "original_team": _team(names, original),
                    "traded_by": _team(names, previous),
                    "received_by": _team(names, recipient),
                    "verification": ("Check missing prior holder" if previous is None
                                     else "Check missing recipient" if recipient is None else "OK"),
                })
        if undated:
            notes.append(f"{label}: {undated} trade(s) with future picks had no usable timestamp; verify in Sleeper.")

        active = snapshot.get("traded_picks")
        if not isinstance(active, list):
            raise ValueError(f"Current traded-pick holdings unavailable for {label}")
        for pick in active:
            if not isinstance(pick, dict):
                continue
            year, round_number = _int(pick.get("season")), _int(pick.get("round"))
            if year is None or year <= current_year or round_number is None or round_number < 1:
                continue
            holdings.append({
                "league": label, "pick_year": str(year), "round": str(round_number),
                "original_team": _team(names, pick.get("roster_id")),
                "current_holder": _team(names, pick.get("owner_id")),
                "previous_holder": _team(names, pick.get("previous_owner_id")),
                "verification": "Sleeper current traded-picks snapshot",
            })

    transfers.sort(key=lambda r: (r["trade_utc"], r["league"], r["transaction_id"], int(r["pick_year"]), int(r["round"])))
    holdings.sort(key=lambda r: (r["league"], int(r["pick_year"]), int(r["round"]), r["original_team"]))
    return {
        "season": season, "week": week,
        "start_utc": datetime.fromtimestamp(lower_ms / 1000, timezone.utc).isoformat(),
        "end_utc": as_of.isoformat(),
        "transfers": transfers, "holdings": holdings, "notes": notes,
    }


def build_future_pick_audit_email(report: dict[str, Any], sender: str, recipient: str) -> EmailMessage:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = f"Ironbound Commissioner Audit — {report['season']} Week {report['week']} future picks"
    transfers, holdings = report["transfers"], report["holdings"]
    lines = [
        "IRONBOUND FUTURE-PICK AUDIT — PRIVATE COMMISSIONER COPY", "",
        f"Review window: {report['start_utc']} through {report['end_utc']}",
        f"Future-year pick transfers: {len(transfers)}",
        f"Current traded future-pick holdings: {len(holdings)}", "",
        "NEW TRANSFERS THIS WEEK", "",
    ]
    if not transfers:
        lines.append("No future-year pick transfers identified in this week's review window.")
    for row in transfers:
        lines.extend([
            f"{row['league']} | {row['trade_utc']} | Transaction {row['transaction_id']}",
            f"  {row['pick_year']} Round {row['round']} (originally {row['original_team']})",
            f"  {row['traded_by']} -> {row['received_by']} [{row['verification']}]", "",
        ])
    lines.extend([
        "", "CURRENT HOLDINGS RECONCILIATION", "",
        "Compare the attached future-pick-holdings.csv against your audit spreadsheet.",
        "The original pick owner may differ from the manager who traded it away.",
        "Missing previous-owner values are flagged for verification, never guessed.",
        "", "Attached: future-pick-transfers.csv and future-pick-holdings.csv.",
    ])
    if report["notes"]:
        lines.extend(["", "SOURCE REVIEW FLAGS", *report["notes"]])
    message.set_content("\n".join(lines) + "\n")
    message.add_attachment(_csv_text(transfers, TRANSFER_FIELDS), subtype="csv", filename="future-pick-transfers.csv")
    message.add_attachment(_csv_text(holdings, HOLDING_FIELDS), subtype="csv", filename="future-pick-holdings.csv")
    return message


def send_future_pick_audit_email(
    output_root: Path, season: str, week: int,
    sender: str, app_password: str, recipient: str | None = None,
) -> int:
    report = build_future_pick_report(output_root, season, week)
    message = build_future_pick_audit_email(report, sender, recipient or sender)
    _deliver(message, sender, app_password)
    return sum(1 for _ in message.iter_attachments())
