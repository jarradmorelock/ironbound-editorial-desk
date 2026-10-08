from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Any, Iterable

from .chronicle_events import ChronicleEvent, make_event
from .external_inputs import ExternalEditorialInputs, OfficialPowerRanking


def ranking_snapshot_events(
    league_key: str,
    season: str,
    week: int,
    rows: Iterable[dict[str, Any]],
    *,
    source_metadata: dict[str, Any],
    observed_at: str,
    provenance: str = "source_exact",
) -> list[ChronicleEvent]:
    """Create idempotent Chronicle events for one resolved ranking snapshot."""
    events = []
    for raw in rows:
        row = dict(raw)
        franchise_key = str(row.get("franchise_key") or "").strip()
        rank = int(row.get("rank") or 0)
        if not franchise_key or rank <= 0:
            continue
        evidence = {
            "rank": rank,
            "roster_id": row.get("roster_id"),
            "team": row.get("team"),
            "score": row.get("score"),
            "previous_rank": row.get("previous_rank"),
            "movement": row.get("movement"),
            "components": dict(row.get("components") or {}),
            "source_metadata": dict(source_metadata),
        }
        source = str(source_metadata.get("source") or source_metadata.get("label") or "editorial_power_rankings")
        source_ref = (
            f"league:{league_key}:season:{season}:week:{int(week)}:"
            f"franchise:{franchise_key}:rank:{rank}"
        )
        events.append(make_event(
            event_type="POWER_RANKING_WEEK_FINAL",
            source=source,
            source_ref=source_ref,
            league_key=league_key,
            season=str(season),
            week=int(week),
            provenance=provenance,
            entities={"franchise_key": franchise_key},
            observed_at=observed_at,
            evidence=evidence,
        ))
    return events


def resolve_power_ranking_input(
    current: ExternalEditorialInputs,
    prior_snapshot: dict[str, Any] | None,
    *,
    season: str,
    week: int,
) -> ExternalEditorialInputs:
    """Prefer current rankings; otherwise carry a prior order without stale claims."""
    metadata = dict(current.source_metadata)
    if current.official_power_rankings:
        metadata.update({
            "ranking_status": "current",
            "ranking_source_week": int(week),
            "carried_from_week": None,
        })
        return replace(current, source_metadata=metadata)
    if not prior_snapshot:
        return current
    source_week = int(prior_snapshot.get("week") or 0)
    if source_week <= 0 or source_week >= int(week):
        return current
    rows = prior_snapshot.get("rows") or []
    rankings = []
    for raw in rows:
        row = dict(raw)
        franchise_key = str(row.get("franchise_key") or "").strip() or None
        rank = int(row.get("rank") or 0)
        if not franchise_key or rank <= 0:
            continue
        rankings.append(OfficialPowerRanking(
            franchise_key=franchise_key,
            rank=rank,
            roster_id=int(row["roster_id"]) if row.get("roster_id") is not None else None,
            team=str(row.get("team") or "") or None,
            previous_rank=None,
            movement=None,
            score=None,
            components={},
        ))
    if not rankings:
        return current
    prior_metadata = dict(prior_snapshot.get("source_metadata") or {})
    original_source_week = int(prior_metadata.get("ranking_source_week") or source_week)
    prior_label = str(prior_metadata.get("label") or prior_metadata.get("source") or "Power Rankings")
    metadata.update(prior_metadata)
    metadata.update({
        "label": f"{prior_label} carried forward from Week {source_week}",
        "ranking_status": "carried_forward",
        "ranking_source_week": original_source_week,
        "carried_from_week": source_week,
    })
    return replace(
        current,
        official_power_rankings=tuple(sorted(rankings, key=lambda row: (row.rank, row.franchise_key or ""))),
        source_metadata=metadata,
        notes=tuple(current.notes) + (f"Power rankings carried forward from Week {source_week} of the {season} season.",),
    )


def seed_from_prior_issue(
    packet_root: Path, *, season: str, week: int
) -> dict[str, list[OfficialPowerRanking]]:
    """Read validated ranking rows from the immediately preceding issue packet."""
    if int(week) <= 1:
        return {}
    issue_week = int(week) - 1
    root = Path(packet_root) / str(season) / f"week-{issue_week:02d}"
    if not root.is_dir():
        return {}
    seeded: dict[str, list[OfficialPowerRanking]] = {}
    packet_paths = set(root.rglob("publication_complete_packet.json"))
    packet_paths.update(root.rglob("flagship_research_packet.json"))
    for path in sorted(packet_paths):
        try:
            packet = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            str(packet.get("season") or "") != str(season)
            or int(packet.get("week") or 0) != issue_week
        ):
            continue
        publication_key = str(packet.get("publication_key") or "").strip()
        chart = packet.get("power_rankings_chart") or {}
        raw_rows = chart.get("rows") or []
        if not publication_key or not isinstance(raw_rows, list) or not raw_rows:
            continue
        rankings: list[OfficialPowerRanking] = []
        franchises: set[str] = set()
        ranks: set[int] = set()
        valid = True
        for raw in raw_rows:
            if not isinstance(raw, dict):
                valid = False
                break
            franchise_key = str(raw.get("franchise_key") or "").strip()
            try:
                rank = int(raw.get("rank") or 0)
            except (TypeError, ValueError):
                valid = False
                break
            if not franchise_key or rank <= 0 or franchise_key in franchises or rank in ranks:
                valid = False
                break
            franchises.add(franchise_key)
            ranks.add(rank)
            rankings.append(OfficialPowerRanking(
                franchise_key=franchise_key,
                rank=rank,
                roster_id=int(raw["roster_id"]) if raw.get("roster_id") is not None else None,
                team=str(raw.get("team") or "") or None,
                previous_rank=None,
                movement=None,
                score=None,
                components={},
            ))
        if valid:
            seeded[publication_key] = sorted(rankings, key=lambda row: (row.rank, row.franchise_key or ""))
    return seeded
