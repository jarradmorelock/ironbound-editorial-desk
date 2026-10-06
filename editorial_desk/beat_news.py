"""Read the durable Discord-news ledger and map it to flagship rosters."""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


EASTERN = ZoneInfo("America/New_York")
SINCE_LAST_PRINTED_TAGS = {
    "Breaking",
    "NFL Moves",
    "Depth Chart",
    "Contract",
    "Legal Trouble",
    "Coaching / Scheme",
    "Rookie / Prospect",
    "Retirement",
}
HEALTH_TAGS = {"Injury", "Practice Report", "Game Status"}
USAGE_TAGS = {
    "Depth Chart",
    "Coaching / Scheme",
    "Fantasy Analysis",
    "Injury",
    "Game Status",
}
PREVIEW_TAGS = {"Game Status", "Practice Report", "Weather", "Start/Sit"}


def load_news_ledger(path: Path | None, *, revision: str | None = None) -> dict[str, Any] | None:
    """Load append-only accepted-story JSONL.

    None means the caller has not opted into beat reporting yet. A supplied path
    is a required source and returns an explicit unavailable status on parse/read
    failure so flagship validation can stop production instead of guessing.
    """
    if path is None:
        return None
    source_path = Path(path)
    try:
        lines = source_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return {
            "status": "unavailable",
            "source_revision": revision,
            "records": [],
            "error": str(exc),
        }

    records: list[dict[str, Any]] = []
    try:
        for line_no, line in enumerate(lines, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"line {line_no} is not a JSON object")
            records.append(row)
    except (json.JSONDecodeError, ValueError) as exc:
        return {
            "status": "unavailable",
            "source_revision": revision,
            "records": [],
            "error": str(exc),
        }

    coverage: dict[str, Any] = {}
    coverage_path = source_path.parent / "coverage.json"
    if coverage_path.exists():
        try:
            raw_coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
            if isinstance(raw_coverage, dict):
                coverage = dict(raw_coverage)
        except (OSError, json.JSONDecodeError):
            coverage = {}

    manifest: dict[str, Any] = {}
    manifest_path = source_path.parent / "manifest.json"
    if manifest_path.exists():
        try:
            raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(raw_manifest, dict):
                manifest = dict(raw_manifest)
        except (OSError, json.JSONDecodeError):
            manifest = {}
    player_index: dict[str, Any] = {}
    index_path = source_path.parent / "by-player.json"
    if index_path.exists():
        try:
            raw_index = json.loads(index_path.read_text(encoding="utf-8"))
            if isinstance(raw_index, dict):
                player_index = dict(raw_index)
        except (OSError, json.JSONDecodeError):
            player_index = {}
    if manifest and not coverage:
        coverage = {
            "durable_since": manifest.get("window_start"),
            "meaning": "Weekly news inbox snapshot; exact revision is retained in the publication packet.",
        }

    return {
        "status": "available",
        "source_repository": "jarradmorelock/Ironbound-Forum-Feed-Poster",
        "source_branch": "news-data",
        "source_revision": revision,
        "coverage": coverage,
        "ledger_manifest": manifest,
        "player_index": player_index,
        "records": records,
    }


def build_beat_report(
    snapshot: dict[str, Any],
    source: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if source is None:
        return None

    base = {
        "required": True,
        "authority": "Ironbound-Forum-Feed-Poster",
        "source_repository": source.get("source_repository"),
        "source_branch": source.get("source_branch"),
        "source_revision": source.get("source_revision"),
        "ledger_manifest": source.get("ledger_manifest") or {},
        "player_index": source.get("player_index") or {},
    }
    if source.get("status") != "available":
        return {
            **base,
            "status": "MANUAL_VERIFY",
            "error": source.get("error") or "Durable news ledger unavailable.",
            "items": [],
            "reporting_window": None,
        }

    window = _reporting_window(snapshot)
    if window is None:
        return {
            **base,
            "status": "MANUAL_VERIFY",
            "error": "NFL schedule did not provide enough date information to anchor the weekly beat-report window.",
            "items": [],
            "reporting_window": None,
        }
    start, end = window

    player_map = _player_roster_map(snapshot)
    team_names = _roster_team_names(snapshot)
    relevant: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for event in source.get("records") or []:
        event_id = str(event.get("event_id") or "")
        if not event_id or event_id in seen_ids:
            continue
        published = _timestamp(event.get("published_at"))
        if published is None or published < start or published > end:
            continue

        mapped_players: list[dict[str, Any]] = []
        for role, row in (
            ("primary", event.get("player")),
            *[("related", value) for value in (event.get("related_players") or [])],
        ):
            if not isinstance(row, dict):
                continue
            gsis_id = str(row.get("nflverse_id") or "")
            roster = player_map.get(gsis_id)
            if roster is None:
                continue
            mapped_players.append(
                {
                    "role": role,
                    "nflverse_id": gsis_id,
                    "player": row.get("name"),
                    "nfl_team": row.get("nfl_team"),
                    "sleeper_player_id": roster["sleeper_player_id"],
                    "roster_id": roster["roster_id"],
                    "fantasy_team": team_names.get(
                        roster["roster_id"],
                        f"Roster {roster['roster_id']}",
                    ),
                }
            )

        if not mapped_players:
            continue

        tags = list(((event.get("editorial") or {}).get("tags")) or [])
        source_row = event.get("source") or {}
        evidence = event.get("evidence") or {}
        editorial = event.get("editorial") or {}
        relevant.append(
            {
                "event_id": event_id,
                "published_at": event.get("published_at"),
                "accepted_at": event.get("accepted_at"),
                "source": source_row.get("name"),
                "source_url": source_row.get("url"),
                "canonical_url": source_row.get("canonical_url"),
                "original_title": evidence.get("original_title"),
                "feed_summary": evidence.get("feed_summary"),
                "headline": editorial.get("headline"),
                "thread_title": editorial.get("thread_title"),
                "tags": tags,
                "discord": dict(event.get("discord") or {}),
                "league_players": mapped_players,
                "editorial_lanes": {
                    "since_we_last_printed": bool(SINCE_LAST_PRINTED_TAGS.intersection(tags)),
                    "health_context": bool(HEALTH_TAGS.intersection(tags)),
                    "usage_context": bool(USAGE_TAGS.intersection(tags)),
                    "preview_context": bool(PREVIEW_TAGS.intersection(tags)),
                },
            }
        )
        seen_ids.add(event_id)

    relevant.sort(
        key=lambda row: (
            str(row.get("published_at") or ""),
            str(row.get("event_id") or ""),
        )
    )

    coverage = source.get("coverage") or {}
    durable_since = _timestamp(coverage.get("durable_since"))
    complete_window = durable_since is not None and durable_since <= start
    status = "READY" if complete_window else "PARTIAL_HISTORY"

    result = {
        **base,
        "status": status,
        "coverage": {
            "durable_since": coverage.get("durable_since"),
            "complete_for_reporting_window": complete_window,
            "note": coverage.get("meaning"),
        },
        "reporting_window": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "basis": "Tuesday-through-Tuesday window derived from the completed NFL week's gameday dates in America/New_York",
        },
        "source_event_count": len(source.get("records") or []),
        "relevant_event_count": len(relevant),
        "items": relevant,
        "lanes": {
            key: [row for row in relevant if (row.get("editorial_lanes") or {}).get(key)]
            for key in (
                "since_we_last_printed",
                "health_context",
                "usage_context",
                "preview_context",
            )
        },
    }
    if not complete_window:
        result["error"] = (
            "Durable beat/news history begins after the start of this issue's "
            "reporting window; earlier Discord news cannot be claimed as complete."
        )
    return result


def _reporting_window(snapshot: dict[str, Any]) -> tuple[datetime, datetime] | None:
    schedule = ((snapshot.get("nfl_context") or {}).get("schedule") or {})
    dates: list[date] = []
    for row in schedule.get("records") or []:
        raw = str(row.get("gameday") or "").strip()
        if not raw:
            continue
        try:
            dates.append(date.fromisoformat(raw))
        except ValueError:
            continue
    if not dates:
        return None

    first_game = min(dates)
    last_game = max(dates)
    # NFL regular weeks begin Thursday and normally close Monday. The weekly
    # magazine's news window begins Tuesday before the first game and closes
    # Tuesday after the final game, matching the publication cadence while
    # remaining stable on later re-runs.
    start_date = first_game - timedelta(days=2)
    end_date = last_game + timedelta(days=1)
    start = datetime.combine(start_date, time.min, tzinfo=EASTERN)
    end = datetime.combine(end_date, time.max, tzinfo=EASTERN)
    return start, end


def _player_roster_map(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    sleeper_to_gsis = {
        str(sleeper_id): str(player.get("gsis_id") or "")
        for sleeper_id, player in (snapshot.get("players") or {}).items()
        if player.get("gsis_id")
    }
    result: dict[str, dict[str, Any]] = {}
    for roster in snapshot.get("rosters") or []:
        roster_id = int(roster.get("roster_id") or 0)
        player_ids = set()
        for key in ("players", "reserve", "taxi"):
            player_ids.update(str(value) for value in (roster.get(key) or []))
        for sleeper_id in player_ids:
            gsis_id = sleeper_to_gsis.get(sleeper_id)
            if gsis_id:
                result[gsis_id] = {
                    "sleeper_player_id": sleeper_id,
                    "roster_id": roster_id,
                }
    return result


def _roster_team_names(snapshot: dict[str, Any]) -> dict[int, str]:
    users = {
        str(row.get("user_id")): row for row in snapshot.get("users") or []
    }
    names: dict[int, str] = {}
    for roster in snapshot.get("rosters") or []:
        roster_id = int(roster.get("roster_id") or 0)
        owner = users.get(str(roster.get("owner_id"))) or {}
        metadata = owner.get("metadata") or {}
        names[roster_id] = str(
            metadata.get("team_name")
            or owner.get("display_name")
            or f"Roster {roster_id}"
        )
    return names


def _timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=EASTERN)
    return parsed.astimezone(EASTERN)
