from dataclasses import FrozenInstanceError

import pytest

from editorial_desk.story_models import (
    StoryCandidate,
    StoryEvidenceRef,
    StoryModelError,
)


def _evidence(evidence_id: str):
    return StoryEvidenceRef(
        evidence_id=evidence_id,
        source="chronicle",
        description=f"Evidence {evidence_id}",
    )


def test_candidate_id_is_deterministic_from_type_and_core_evidence_ids():
    first = StoryCandidate.build(
        candidate_type="reaction_transaction",
        evidence_refs=(_evidence("status-1"), _evidence("tx-9")),
    )
    reordered = StoryCandidate.build(
        candidate_type="reaction_transaction",
        evidence_refs=(_evidence("tx-9"), _evidence("status-1")),
    )
    different = StoryCandidate.build(
        candidate_type="reaction_transaction",
        evidence_refs=(_evidence("status-1"), _evidence("tx-10")),
    )

    assert first.candidate_id == reordered.candidate_id
    assert first.candidate_id != different.candidate_id


def test_candidate_serialization_accepts_evidence_linked_and_derived_facts():
    candidate = StoryCandidate.build(
        candidate_type="rivalry_history",
        evidence_refs=(_evidence("game-1"),),
        facts=(
            {"statement": "Week 1 meeting", "evidence_id": "game-1"},
            {
                "statement": "All-time series summary",
                "provenance": "chronicle_derived",
                "coverage_complete": True,
            },
        ),
        historical_context=(
            {
                "statement": "Prior playoff meeting",
                "evidence_ids": ["game-1"],
            },
        ),
    )

    payload = candidate.to_dict()

    assert payload["candidate_id"] == candidate.candidate_id
    assert payload["facts"][0]["evidence_id"] == "game-1"
    assert payload["facts"][1]["provenance"] == "chronicle_derived"


def test_candidate_serialization_rejects_untraceable_fact_rows():
    candidate = StoryCandidate.build(
        candidate_type="rivalry_history",
        evidence_refs=(_evidence("game-1"),),
        facts=({"statement": "Unsupported factual claim"},),
    )

    with pytest.raises(StoryModelError, match="traceable evidence"):
        candidate.to_dict()


def test_candidate_serialization_rejects_unknown_evidence_reference():
    candidate = StoryCandidate.build(
        candidate_type="rivalry_history",
        evidence_refs=(_evidence("game-1"),),
        facts=({"statement": "Wrong link", "evidence_id": "missing"},),
    )

    with pytest.raises(StoryModelError, match="unknown evidence"):
        candidate.to_dict()


def test_story_models_are_frozen():
    evidence = _evidence("game-1")
    candidate = StoryCandidate.build(
        candidate_type="rivalry_history",
        evidence_refs=(evidence,),
    )

    with pytest.raises(FrozenInstanceError):
        evidence.source = "changed"
    with pytest.raises(FrozenInstanceError):
        candidate.signal_score = 99.0
