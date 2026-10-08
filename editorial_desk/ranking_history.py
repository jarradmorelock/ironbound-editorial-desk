from __future__ import annotations

from typing import Any, Iterable

from .chronicle_events import ChronicleEvent, make_event


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
