from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any

SCHEMA_VERSION = 1


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def event_id_for(identity: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(identity).encode("utf-8")).hexdigest()[:24]


@dataclass(frozen=True)
class ChronicleEvent:
    event_id: str
    schema_version: int
    event_type: str
    league_key: str | None
    season: str
    week: int | None
    occurred_at: str | None
    observed_at: str
    observed_before: str | None
    observed_after: str | None
    source: str
    source_ref: str
    provenance: str
    entities: dict[str, Any]
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    evidence: dict[str, Any]
    cross_league_key: str | None = None
    correction_of: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_event(
    *,
    event_type: str,
    source: str,
    source_ref: str,
    league_key: str | None,
    season: str,
    week: int | None,
    provenance: str,
    entities: dict[str, Any],
    observed_at: str,
    occurred_at: str | None = None,
    observed_before: str | None = None,
    observed_after: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
    cross_league_key: str | None = None,
    correction_of: str | None = None,
) -> ChronicleEvent:
    identity: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "event_type": event_type,
        "league_key": league_key,
        "season": season,
        "week": week,
        "source": source,
        "source_ref": source_ref,
        "entities": entities,
        "before": before,
        "after": after,
        "occurred_at": occurred_at,
    }
    if provenance == "observed_live":
        identity["observed_before"] = observed_before
    if correction_of is not None:
        identity["correction_of"] = correction_of

    return ChronicleEvent(
        event_id=event_id_for(identity),
        schema_version=SCHEMA_VERSION,
        event_type=event_type,
        league_key=league_key,
        season=season,
        week=week,
        occurred_at=occurred_at,
        observed_at=observed_at,
        observed_before=observed_before,
        observed_after=observed_after,
        source=source,
        source_ref=source_ref,
        provenance=provenance,
        entities=entities,
        before=before,
        after=after,
        evidence=evidence or {},
        cross_league_key=cross_league_key,
        correction_of=correction_of,
    )
