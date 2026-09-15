from editorial_desk.enriched_collector import _apply_player_context


def test_player_context_adds_years_experience_to_newspaper_snapshot():
    snapshot = {
        "players": {
            "rookie": {"full_name": "Rookie", "position": "RB"},
            "vet": {"full_name": "Veteran", "position": "WR"},
        }
    }
    directory = {
        "rookie": {"years_exp": 0, "age": 21},
        "vet": {"years_exp": 5, "age": 28},
    }

    _apply_player_context(snapshot, directory)

    assert snapshot["players"]["rookie"]["years_exp"] == 0
    assert snapshot["players"]["vet"]["years_exp"] == 5
