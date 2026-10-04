from pathlib import Path

WORKFLOW = Path(".github/workflows/editorial-desk-chronicle.yml")


def text():
    return WORKFLOW.read_text(encoding="utf-8")


def test_chronicle_workflow_serializes_writers_and_uses_data_branch():
    value = text()
    assert "group: editorial-chronicle-writer" in value
    assert "cancel-in-progress: false" in value
    assert "ref: chronicle-data" in value
    assert "path: chronicle-data" in value
    assert "contents: write" in value
    assert "--chronicle-root ../chronicle-data" in value
    assert "git push --force" not in value


def test_chronicle_workflow_has_daily_baseline_and_three_wed_sun_pulses():
    value = text()
    assert '17 6 * * *' in value
    assert '17 12 * * 0,3-6' in value
    assert '17 17 * * 0,3-6' in value
    assert '17 21 * * 0,3-6' in value
