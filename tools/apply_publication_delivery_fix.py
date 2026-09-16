from pathlib import Path


def replace(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Expected patch target not found in {path}: {old!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


replace(
    "editorial_desk/metrics.py",
    '''        if editorial.get("tier") == "flagship" or "division_metrics" in weekly_features
''',
    '''        if not profile
        or editorial.get("tier") == "flagship"
        or "division_metrics" in weekly_features
''',
)

replace(
    "editorial_desk/weekly_features.py",
    '''    if (
        editorial.get("tier") == "flagship"
        or "divisional_started_mvps" in weekly_contract_features
    ):
''',
    '''    if (
        not profile
        or editorial.get("tier") == "flagship"
        or "divisional_started_mvps" in weekly_contract_features
    ):
''',
)

print("Publication delivery compatibility patch applied")
