from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from typing import Any, Iterable


class StoryModelError(ValueError):
    """Raised when a Story Desk artifact cannot be traced to evidence."""


@dataclass(frozen=True)
class StoryEvidenceRef:
    evidence_id: str
    source: str
    description: str

    def __post_init__(self) -> None:
        if not str(self.evidence_id).strip():
            raise StoryModelError("Story evidence requires a non-empty evidence_id")
        if not str(self.source).strip():
            raise StoryModelError("Story evidence requires a non-empty source")
        if not str(self.description).strip():
            raise StoryModelError("Story evidence requires a description")


@dataclass(frozen=True)
class StoryCandidate:
    candidate_id: str
    candidate_type: str
    title_concepts: tuple[str, ...] = ()
    trigger_reasons: tuple[str, ...] = ()
    evidence_refs: tuple[StoryEvidenceRef, ...] = ()
    facts: tuple[dict[str, Any], ...] = ()
    historical_context: tuple[dict[str, Any], ...] = ()
    entities: dict[str, Any] = field(default_factory=dict)
    evidence_strength: str = "supported"
    signal_score: float = 0.0
    signal_components: dict[str, float] = field(default_factory=dict)
    cautions: tuple[str, ...] = ()
    editorial_angles: tuple[str, ...] = ()
    graphic_ideas: tuple[str, ...] = ()
    depth_class: str = "brief"

    @classmethod
    def build(
        cls,
        *,
        candidate_type: str,
        evidence_refs: Iterable[StoryEvidenceRef],
        title_concepts: Iterable[str] = (),
        trigger_reasons: Iterable[str] = (),
        facts: Iterable[dict[str, Any]] = (),
        historical_context: Iterable[dict[str, Any]] = (),
        entities: dict[str, Any] | None = None,
        evidence_strength: str = "supported",
        signal_score: float = 0.0,
        signal_components: dict[str, float] | None = None,
        cautions: Iterable[str] = (),
        editorial_angles: Iterable[str] = (),
        graphic_ideas: Iterable[str] = (),
        depth_class: str = "brief",
    ) -> "StoryCandidate":
        refs = tuple(evidence_refs)
        candidate_type = str(candidate_type).strip()
        if not candidate_type:
            raise StoryModelError("Story candidate requires a candidate_type")
        return cls(
            candidate_id=_candidate_id(candidate_type, refs),
            candidate_type=candidate_type,
            title_concepts=tuple(str(value) for value in title_concepts),
            trigger_reasons=tuple(str(value) for value in trigger_reasons),
            evidence_refs=refs,
            facts=tuple(dict(value) for value in facts),
            historical_context=tuple(dict(value) for value in historical_context),
            entities=dict(entities or {}),
            evidence_strength=str(evidence_strength),
            signal_score=float(signal_score),
            signal_components={
                str(key): float(value)
                for key, value in (signal_components or {}).items()
            },
            cautions=tuple(str(value) for value in cautions),
            editorial_angles=tuple(str(value) for value in editorial_angles),
            graphic_ideas=tuple(str(value) for value in graphic_ideas),
            depth_class=str(depth_class),
        )

    def to_dict(self) -> dict[str, Any]:
        evidence_ids = {ref.evidence_id for ref in self.evidence_refs}
        for collection_name, rows in (
            ("facts", self.facts),
            ("historical_context", self.historical_context),
        ):
            for index, row in enumerate(rows):
                linked = _row_evidence_ids(row)
                provenance = str(row.get("provenance") or "").strip()
                if not linked and not provenance:
                    raise StoryModelError(
                        f"{collection_name}[{index}] requires traceable evidence "
                        "or derived-fact provenance"
                    )
                unknown = linked - evidence_ids
                if unknown:
                    raise StoryModelError(
                        f"{collection_name}[{index}] references unknown evidence: "
                        + ", ".join(sorted(unknown))
                    )
        return {
            "candidate_id": self.candidate_id,
            "candidate_type": self.candidate_type,
            "title_concepts": list(self.title_concepts),
            "trigger_reasons": list(self.trigger_reasons),
            "evidence_refs": [asdict(ref) for ref in self.evidence_refs],
            "facts": [dict(row) for row in self.facts],
            "historical_context": [dict(row) for row in self.historical_context],
            "entities": dict(self.entities),
            "evidence_strength": self.evidence_strength,
            "signal_score": self.signal_score,
            "signal_components": dict(self.signal_components),
            "cautions": list(self.cautions),
            "editorial_angles": list(self.editorial_angles),
            "graphic_ideas": list(self.graphic_ideas),
            "depth_class": self.depth_class,
        }


def _candidate_id(
    candidate_type: str, evidence_refs: Iterable[StoryEvidenceRef]
) -> str:
    core = {
        "candidate_type": str(candidate_type),
        "evidence_ids": sorted({str(ref.evidence_id) for ref in evidence_refs}),
    }
    payload = json.dumps(core, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _row_evidence_ids(row: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    evidence_id = row.get("evidence_id")
    if evidence_id not in (None, ""):
        values.add(str(evidence_id))
    raw_ids = row.get("evidence_ids") or []
    if isinstance(raw_ids, (str, bytes)):
        values.add(str(raw_ids))
    else:
        values.update(str(value) for value in raw_ids if value not in (None, ""))
    return values
