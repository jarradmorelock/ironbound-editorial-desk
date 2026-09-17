"""Publication-only policy; collected snapshots remain unmodified evidence."""
from __future__ import annotations

from typing import Any

# Change this explicit profile rule only when the commissioner re-enables divisions.
DIVISIONS_DISABLED = frozenset({'volunteer_voice', 'rocky_top_rumble'})
DIVISION_FEATURES = frozenset({'division_metrics', 'divisional_started_mvps', 'division_pressure'})


def divisions_disabled(context: dict[str, Any]) -> bool:
    editorial = context.get('editorial') or context.get('league') or context
    profile = editorial.get('publication_profile') or {}
    key = profile.get('key') if isinstance(profile, dict) else profile
    return bool({key, editorial.get('league_key'), context.get('publication_key')} & DIVISIONS_DISABLED) or str(editorial.get('publication') or context.get('publication') or '').casefold() in {'the volunteer voice', 'volunteer voice', 'rocky top rumble'}


def publication_view(value: Any, context: dict[str, Any]) -> Any:
    """Copy and strip division metadata/derived groups at publication boundaries."""
    if not divisions_disabled(context):
        return value

    def clean(item: Any) -> Any:
        if isinstance(item, dict):
            result = {}
            for key, child in item.items():
                if key == 'divisions':
                    result[key] = []
                elif 'division' not in str(key).casefold():
                    result[key] = clean(child)
            return result
        if isinstance(item, (list, tuple)):
            return [clean(child) for child in item if not (
                isinstance(child, dict) and (child.get('feature') in DIVISION_FEATURES or child.get('candidate_type') in DIVISION_FEATURES)
            )]
        return item

    return clean(value)
