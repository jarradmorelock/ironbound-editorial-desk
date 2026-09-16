import pytest

from editorial_desk.feature_models import (
    FeatureResult,
    ready,
    ready_no_items,
    unavailable,
)


def test_ready_preserves_data_and_freshness():
    result = ready(
        "health_status",
        [{"player_id": "p1", "status": "Questionable"}],
        freshness={"sleeper": "fresh"},
    )
    assert result == FeatureResult(
        feature="health_status",
        status="ready",
        data=[{"player_id": "p1", "status": "Questionable"}],
        reason=None,
        freshness={"sleeper": "fresh"},
        degraded=False,
    )


def test_ready_no_items_is_valid_empty_not_unavailable():
    result = ready_no_items(
        "lineup_flip_candidates",
        reason="No legal single substitution changed a result",
    )
    assert result.status == "ready_no_items"
    assert result.data == []
    assert result.reason == "No legal single substitution changed a result"
    assert result.degraded is False


def test_unavailable_requires_reason_and_can_carry_freshness():
    with pytest.raises(ValueError, match="reason"):
        unavailable("health_status", "")

    result = unavailable(
        "health_status",
        "Sleeper player status source failed",
        freshness={"sleeper": "stale"},
    )
    assert result.status == "unavailable"
    assert result.reason == "Sleeper player status source failed"
    assert result.freshness == {"sleeper": "stale"}


def test_ready_can_mark_preferred_dependency_degradation_without_becoming_unavailable():
    result = ready(
        "record_watch",
        [{"record_type": "high_score"}],
        reason="Historical transaction coverage is incomplete",
        degraded=True,
    )
    assert result.status == "ready"
    assert result.degraded is True
