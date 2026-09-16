import json

import pytest

from editorial_desk.external_inputs import ExternalInputError, load_external_inputs


def _write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_missing_external_input_path_returns_empty_valid_object(tmp_path):
    result = load_external_inputs(None, "ironbound_weekly")

    assert result.publication_key == "ironbound_weekly"
    assert result.official_power_rankings == ()
    assert result.war == ()
    assert result.notes == ()
    assert result.source_metadata == {}
    assert result.power_rankings_supplied is False
    assert result.war_supplied is False


def test_valid_external_input_packet_preserves_authoritative_rankings_and_metadata(tmp_path):
    path = _write(
        tmp_path / "ironbound.json",
        {
            "publication_key": "ironbound_weekly",
            "official_power_rankings": [
                {"franchise_key": "franchise:a", "rank": 1},
                {"franchise_key": "franchise:b", "rank": 15},
            ],
            "war": [
                {"franchise_key": "franchise:a", "value": 2.4},
            ],
            "notes": ["Commissioner-supplied context"],
            "source_metadata": {"label": "Ironbound Power Rankings", "week": 7},
        },
    )

    result = load_external_inputs(path, "ironbound_weekly")

    assert [(row.franchise_key, row.rank) for row in result.official_power_rankings] == [
        ("franchise:a", 1),
        ("franchise:b", 15),
    ]
    assert result.war == ({"franchise_key": "franchise:a", "value": 2.4},)
    assert result.source_metadata["week"] == 7
    assert result.power_rankings_supplied is True
    assert result.war_supplied is True


@pytest.mark.parametrize(
    "rankings,match",
    [
        (
            [
                {"franchise_key": "franchise:a", "rank": 1},
                {"franchise_key": "franchise:b", "rank": 1},
            ],
            "Duplicate official rank",
        ),
        (
            [
                {"franchise_key": "franchise:a", "rank": 0},
            ],
            "positive integer",
        ),
        (
            [
                {"franchise_key": "franchise:a", "rank": 1},
                {"franchise_key": "franchise:a", "rank": 2},
            ],
            "Duplicate franchise_key",
        ),
    ],
)
def test_invalid_or_duplicate_rankings_raise(tmp_path, rankings, match):
    path = _write(
        tmp_path / "invalid.json",
        {
            "publication_key": "ironbound_weekly",
            "official_power_rankings": rankings,
        },
    )

    with pytest.raises(ExternalInputError, match=match):
        load_external_inputs(path, "ironbound_weekly")


def test_publication_key_mismatch_raises(tmp_path):
    path = _write(
        tmp_path / "wrong.json",
        {
            "publication_key": "unbound_weekly",
            "official_power_rankings": [],
        },
    )

    with pytest.raises(ExternalInputError, match="publication_key"):
        load_external_inputs(path, "ironbound_weekly")


def test_loader_rejects_non_object_json_instead_of_guessing(tmp_path):
    path = _write(tmp_path / "list.json", [1, 2, 3])

    with pytest.raises(ExternalInputError, match="JSON object"):
        load_external_inputs(path, "ironbound_weekly")
