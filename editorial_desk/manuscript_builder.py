"""Offline issue planning and manuscript compilation.

This module deliberately has no research clients.  It consumes a completed
publication packet and emits editorial choices plus evidence-bound structured
sections for human editing and downstream layout.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


class ManuscriptValidationError(ValueError):
    """Raised when a plan or draft would leave the packet's evidence boundary."""


_SECTION_DEFINITIONS: tuple[tuple[str, str, str], ...] = (
    ("cover", "Cover", "feature_evidence.cover_candidates"),
    ("lead_feature", "Lead Feature", "feature_evidence.cover_candidates"),
    ("secondary_feature", "Secondary Feature", "feature_evidence.story_candidates"),
    ("weekly_results", "Weekly Results", "game_dossiers"),
    ("usage_desk", "Usage Desk", "usage_desk"),
    ("roster_health", "Roster Health", "roster_health"),
    ("transaction_desk", "Transaction Desk", "transaction_desk"),
    ("manager_honors", "Manager Honors", "manager_honors"),
    ("player_honors", "Player Honors", "player_honors"),
    ("rookie_watch", "Rookie Watch", "rookie_watch"),
    ("rankings", "Power Rankings and Playoff Forecast", "power_rankings"),
    ("division_report", "Division Report", "division_report"),
    ("week_ahead", "Week Ahead", "week_ahead"),
    ("sources", "Sources and Model Notes", "sources_and_model_notes"),
)


def _packet_id(packet: dict[str, Any]) -> str:
    encoded = json.dumps(packet, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "packet:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _path_value(packet: dict[str, Any], path: str) -> Any:
    value: Any = packet
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _evidence_ids(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        evidence_id = value.get("evidence_id")
        if evidence_id:
            found.add(str(evidence_id))
        evidence_ids = value.get("evidence_ids")
        if isinstance(evidence_ids, (list, tuple, set)):
            found.update(str(item) for item in evidence_ids if item)
        for child in value.values():
            found.update(_evidence_ids(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_evidence_ids(child))
    return found


def _candidate_id(row: Any) -> str | None:
    return str(row.get("candidate_id")) if isinstance(row, dict) and row.get("candidate_id") else None


def _choose_candidate(rows: Iterable[Any], requested: str | None) -> dict[str, Any] | None:
    candidates = [row for row in rows if isinstance(row, dict)]
    if requested:
        for row in candidates:
            if _candidate_id(row) == requested:
                return dict(row)
        raise ManuscriptValidationError(f"unknown editorial candidate: {requested}")
    return dict(candidates[0]) if candidates else None


def _section_plan(
    section_id: str,
    title: str,
    source_path: str,
    facts: Any,
    *,
    candidate_id: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "section_id": section_id,
        "title": title,
        "source_paths": [source_path],
        "evidence_ids": sorted(_evidence_ids(facts)),
    }
    if candidate_id:
        row["candidate_id"] = candidate_id
    return row


def build_issue_plan(
    packet: dict[str, Any],
    *,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create deterministic editorial choices without copying packet facts."""

    readiness = packet.get("readiness") or {}
    if not readiness.get("publication_ready"):
        raise ManuscriptValidationError("publication packet is not publication-ready")

    overrides = dict(overrides or {})
    feature = packet.get("feature_evidence") or {}
    cover = _choose_candidate(
        feature.get("cover_candidates") or [],
        overrides.get("cover_candidate_id"),
    )
    if cover is None:
        raise ManuscriptValidationError("packet has no cover candidate")
    story = _choose_candidate(
        feature.get("story_candidates") or [],
        overrides.get("secondary_feature_candidate_id"),
    )

    cover_id = _candidate_id(cover)
    choices = {
        "cover_candidate_id": cover_id,
        "lead_feature_candidate_id": overrides.get("lead_feature_candidate_id") or cover_id,
        "secondary_feature_candidate_id": _candidate_id(story),
        "cover_direction": overrides.get("cover_direction") or "feature-led",
        "section_emphasis": list(overrides.get("section_emphasis") or []),
        "rotating_award_candidate_id": overrides.get("rotating_award_candidate_id"),
        "expansion_recommendation": overrides.get("expansion_recommendation") or "none",
    }
    if choices["lead_feature_candidate_id"] != cover_id:
        available = {_candidate_id(row) for row in feature.get("cover_candidates") or []}
        if choices["lead_feature_candidate_id"] not in available:
            raise ManuscriptValidationError(
                f"unknown editorial candidate: {choices['lead_feature_candidate_id']}"
            )

    sections: list[dict[str, Any]] = []
    for section_id, title, source_path in _SECTION_DEFINITIONS:
        facts = _path_value(packet, source_path)
        if section_id == "cover":
            facts = [cover]
        elif section_id == "lead_feature":
            lead = _choose_candidate(
                feature.get("cover_candidates") or [],
                choices["lead_feature_candidate_id"],
            )
            facts = [lead] if lead else []
        elif section_id == "secondary_feature":
            facts = [story] if story else []
        elif section_id == "transaction_desk":
            facts = packet.get("transaction_desk") or {}
        sections.append(
            _section_plan(
                section_id,
                title,
                source_path,
                facts,
                candidate_id=_candidate_id(facts[0]) if isinstance(facts, list) and facts and section_id in {"cover", "lead_feature", "secondary_feature"} else None,
            )
        )

    return {
        "schema_version": 1,
        "plan_type": "offline_issue_plan",
        "packet_id": _packet_id(packet),
        "issue_identity": dict(packet.get("issue_identity") or {}),
        "editorial_choices": choices,
        "sections": sections,
    }


def _validate_plan(packet: dict[str, Any], plan: dict[str, Any]) -> None:
    if plan.get("packet_id") != _packet_id(packet):
        raise ManuscriptValidationError("issue plan does not belong to this packet")
    available = _evidence_ids(packet)
    unknown = sorted(set(plan.get("editorial_choices", {}).get("evidence_ids", [])) - available)
    if unknown:
        raise ManuscriptValidationError("unknown evidence IDs: " + ", ".join(unknown))
    for section in plan.get("sections") or []:
        missing = sorted(set(section.get("evidence_ids") or []) - available)
        if missing:
            raise ManuscriptValidationError("unknown evidence IDs: " + ", ".join(missing))


def _copy_for_section(packet: dict[str, Any], section: dict[str, Any]) -> Any:
    source_path = (section.get("source_paths") or [""])[0]
    facts = _path_value(packet, source_path)
    candidate_id = section.get("candidate_id")
    if candidate_id and isinstance(facts, list):
        facts = [row for row in facts if _candidate_id(row) == candidate_id]
    return facts


def build_manuscript_draft(
    packet: dict[str, Any],
    issue_plan: dict[str, Any],
) -> dict[str, Any]:
    """Compile structured, evidence-bound manuscript sections offline."""

    _validate_plan(packet, issue_plan)
    sections: list[dict[str, Any]] = []
    available = _evidence_ids(packet)
    for plan_section in issue_plan.get("sections") or []:
        facts = _copy_for_section(packet, plan_section)
        evidence_ids = sorted(_evidence_ids(facts))
        unknown = sorted(set(evidence_ids) - available)
        if unknown:
            raise ManuscriptValidationError("unknown evidence IDs: " + ", ".join(unknown))
        sections.append(
            {
                "section_id": plan_section.get("section_id"),
                "title": plan_section.get("title"),
                "source_paths": list(plan_section.get("source_paths") or []),
                "evidence_ids": evidence_ids,
                "facts": facts if isinstance(facts, list) else [facts],
                "copy": {"headline": "", "deck": "", "body_blocks": [], "callouts": []},
                "art_direction": {},
                "warnings": [],
            }
        )
    return {
        "schema_version": 1,
        "manuscript_type": "offline_manuscript_draft",
        "status": "DRAFT",
        "packet_id": _packet_id(packet),
        "issue_plan": issue_plan,
        "sections": sections,
        "from_the_ironbound_desk": None,
    }


def _markdown(draft: dict[str, Any]) -> str:
    identity = draft.get("issue_plan", {}).get("issue_identity", {})
    lines = [
        f"# {identity.get('publication_key', 'Publication')} "
        f"Week {identity.get('week', '')} Manuscript Draft",
        "",
        "Offline draft generated from the publication-complete packet.",
        "",
    ]
    for section in draft.get("sections") or []:
        lines.extend(
            [
                f"## {section.get('title')}",
                "",
                f"Evidence: {', '.join(section.get('evidence_ids') or []) or 'none'}",
                "",
                "Headline: [editorial copy required]",
                "",
            ]
        )
    return "\n".join(lines)


def write_offline_manuscript(
    packet_path: Path,
    output_dir: Path,
    *,
    issue_plan: dict[str, Any] | None = None,
) -> tuple[Path, Path, Path]:
    """Read one packet and write the plan plus draft artifacts locally."""

    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    plan = issue_plan or build_issue_plan(packet)
    draft = build_manuscript_draft(packet, plan)
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_path = output_dir / "issue_plan.json"
    draft_path = output_dir / "manuscript_draft.json"
    markdown_path = output_dir / "manuscript_draft.md"
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    draft_path.write_text(json.dumps(draft, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(_markdown(draft), encoding="utf-8")
    return plan_path, draft_path, markdown_path
