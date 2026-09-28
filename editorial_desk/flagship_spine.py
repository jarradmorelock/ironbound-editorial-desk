"""Shared weekly flagship magazine spine with brand-specific display names."""

from __future__ import annotations

from typing import Any


CANONICAL_WEEKLY_SPINE = (
    (1, "COVER"),
    (2, "CONTENTS"),
    (3, "LEAD_FEATURE"),
    (4, "LEAD_FEATURE"),
    (5, "GAME_REPORTS"),
    (6, "GAME_REPORTS"),
    (7, "GAME_REPORTS"),
    (8, "SECONDARY_FEATURE"),
    (9, "USAGE_DESK"),
    (10, "ROSTER_HEALTH"),
    (11, "MARKET_DESK"),
    (12, "HONORS_ROOKIE"),
    (13, "POWER_BOARD"),
    (14, "POWER_BOARD"),
    (15, "POWER_BOARD"),
    (16, "POWER_BOARD"),
    (17, "PLAYOFF_FORECAST"),
    (18, "POWER_RANKINGS"),
    (19, "PRESSURE_POINTS"),
    (20, "FULL_SLATE"),
    (21, "DIVISION_ROAD_AHEAD"),
    (22, "SOURCES"),
)

DISPLAY_NAMES = {
    "ironbound_weekly": {
        "COVER": "The Ironbound Weekly",
        "CONTENTS": "Inside the Issue",
        "LEAD_FEATURE": "Lead Feature",
        "GAME_REPORTS": "Week Game Reports",
        "SECONDARY_FEATURE": "Divisional Feature",
        "USAGE_DESK": "The Usage Desk",
        "ROSTER_HEALTH": "Roster Health",
        "MARKET_DESK": "The Transaction Desk",
        "HONORS_ROOKIE": "Honors & Rookie Watch",
        "POWER_BOARD": "The Power Board",
        "PLAYOFF_FORECAST": "Playoff Forecast",
        "POWER_RANKINGS": "Power Rankings",
        "PRESSURE_POINTS": "Pressure Points",
        "FULL_SLATE": "The Full Slate",
        "DIVISION_ROAD_AHEAD": "Division of Death",
        "SOURCES": "Sources & Model Notes",
    },
    "unbound_weekly": {
        "COVER": "Unbound Weekly",
        "CONTENTS": "Inside the Issue",
        "LEAD_FEATURE": "Lead Feature",
        "GAME_REPORTS": "Week Game Reports",
        "SECONDARY_FEATURE": "Second Feature",
        "USAGE_DESK": "Usage Desk",
        "ROSTER_HEALTH": "Availability Watch",
        "MARKET_DESK": "Market Moves",
        "HONORS_ROOKIE": "Honors & Rookie Watch",
        "POWER_BOARD": "The Power Board",
        "PLAYOFF_FORECAST": "Playoff Forecast",
        "POWER_RANKINGS": "Power Rankings",
        "PRESSURE_POINTS": "The Pressure Points",
        "FULL_SLATE": "The Full Slate",
        "DIVISION_ROAD_AHEAD": "Under Tension",
        "SOURCES": "Sources & Model Notes",
    },
}


def flagship_spine(publication_key: str) -> list[dict[str, Any]]:
    names = DISPLAY_NAMES.get(publication_key)
    if names is None:
        raise ValueError(f"Unknown flagship publication: {publication_key}")
    return [
        {
            "page": page,
            "module": module,
            "display_name": names[module],
        }
        for page, module in CANONICAL_WEEKLY_SPINE
    ]
