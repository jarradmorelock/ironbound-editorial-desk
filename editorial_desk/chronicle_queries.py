from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Iterable


_TRANSACTION_TYPES = {
    "TRADE",
    "WAIVER_ADD",
    "FREE_AGENT_ADD",
    "DROP",
    "TRADED_PICK",
    "DRAFT_PICK",
}


class ChronicleQueries:
    """Read-only access to materialized Chronicle summaries and event ledgers."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def head_to_head(
        self, league_key: str, left_key: str, right_key: str
    ) -> dict[str, Any] | None:
        league = self._league_root(league_key)
        document = self._read_json(league / "history" / "head_to_head.json")
        pair = tuple(sorted((str(left_key), str(right_key))))
        series = next(
            (
                dict(row)
                for row in document.get("head_to_head") or []
                if tuple(
                    sorted(
                        (
                            str(row.get("identity_a") or ""),
                            str(row.get("identity_b") or ""),
                        )
                    )
                )
                == pair
            ),
            None,
        )
        if series is None:
            return None

        matchups = self._read_json(league / "history" / "matchups.json")
        playoff_meetings = [
            dict(row)
            for row in matchups.get("matchups") or []
            if str(row.get("competition") or "") == "playoffs"
            and tuple(
                sorted(
                    (
                        str(row.get("left_identity") or ""),
                        str(row.get("right_identity") or ""),
                    )
                )
            )
            == pair
        ]
        coverage = self._coverage(league_key)
        return {
            "series": series,
            "playoff_meetings": playoff_meetings,
            **coverage,
        }

    def current_streak(
        self, league_key: str, left_key: str, right_key: str
    ) -> dict[str, Any] | None:
        result = self.head_to_head(league_key, left_key, right_key)
        if result is None:
            return None
        series = result["series"]
        return {
            "identity": series.get("current_streak_identity"),
            "length": int(series.get("current_streak_length") or 0),
            "coverage_complete": result["coverage_complete"],
            "coverage_warnings": result["coverage_warnings"],
        }

    def season_records(self, league_key: str, season: str) -> dict[str, Any]:
        league = self._league_root(league_key)
        document = self._read_json(league / "history" / "seasons.json")
        records: dict[str, dict[str, Any]] = {}
        wanted = str(season)
        for row in (document.get("seasons") or {}).values():
            if str(row.get("season") or "") != wanted:
                continue
            identity = str(row.get("identity") or "")
            if identity:
                records[identity] = dict(row)
        return {
            "season": wanted,
            "records": records,
            **self._coverage(league_key),
        }

    def recent_events(
        self,
        league_key: str,
        since: str,
        event_types: Iterable[str] | None = None,
    ) -> list[dict[str, Any]]:
        wanted_types = (
            {str(value) for value in event_types} if event_types is not None else None
        )
        rows = self._read_jsonl_tree(self._league_root(league_key) / "events")
        return [
            row
            for row in rows
            if self._after(row.get("observed_at"), since)
            and (
                wanted_types is None
                or str(row.get("event_type") or "") in wanted_types
            )
        ]

    def player_events(
        self, player_id: str, since: str | None = None
    ) -> list[dict[str, Any]]:
        rows = self._read_jsonl_tree(
            self.root / "cross_league" / "nfl_player_events"
        )
        wanted = str(player_id)
        return [
            row
            for row in rows
            if str((row.get("entities") or {}).get("player_id") or "") == wanted
            and (since is None or self._after(row.get("observed_at"), since))
        ]

    def transactions_for_entity(
        self, league_key: str, entity_key: str, since: str | None = None
    ) -> list[dict[str, Any]]:
        wanted = str(entity_key)
        rows = self._read_jsonl_tree(self._league_root(league_key) / "events")
        return [
            row
            for row in rows
            if str(row.get("event_type") or "") in _TRANSACTION_TYPES
            and self._contains(row.get("entities"), wanted)
            and (since is None or self._after(row.get("observed_at"), since))
        ]

    def identity_for_roster(
        self, league_key: str, season: str, roster_id: int
    ) -> str | None:
        registry = self._read_json(self.root / "registry" / "identity.json")
        wanted_league = str(league_key)
        wanted_season = str(season)
        wanted_roster = int(roster_id)
        for collection, identity_field in (
            ("dynasty_mappings", "franchise_key"),
            ("redraft_mappings", "manager_key"),
        ):
            for row in registry.get(collection) or []:
                if (
                    str(row.get("league_key") or "") == wanted_league
                    and str(row.get("season") or "") == wanted_season
                    and int(row.get("roster_id") or 0) == wanted_roster
                ):
                    value = str(row.get(identity_field) or "").strip()
                    return value or None
        return None

    def identity_context(self, identity_key: str) -> dict[str, Any]:
        registry = self._read_json(self.root / "registry" / "identity.json")
        wanted = str(identity_key)
        aliases = (
            (registry.get("aliases") or {}).get(wanted)
            or (registry.get("manager_aliases") or {}).get(wanted)
            or []
        )
        tenures = (registry.get("manager_tenures") or {}).get(wanted) or []
        return {
            "aliases": [dict(row) for row in aliases],
            "manager_tenures": [dict(row) for row in tenures],
        }

    def league_matchups(self, league_key: str) -> list[dict[str, Any]]:
        document = self._read_json(
            self._league_root(league_key) / "history" / "matchups.json"
        )
        return [dict(row) for row in document.get("matchups") or []]

    def league_events(
        self, league_key: str, event_types: Iterable[str] | None = None
    ) -> list[dict[str, Any]]:
        wanted_types = (
            {str(value) for value in event_types} if event_types is not None else None
        )
        rows = self._read_jsonl_tree(self._league_root(league_key) / "events")
        if wanted_types is None:
            return rows
        return [
            row
            for row in rows
            if str(row.get("event_type") or "") in wanted_types
        ]

    def tracked_league_keys(self) -> tuple[str, ...]:
        root = self.root / "leagues"
        if not root.exists():
            return ()
        return tuple(sorted(path.name for path in root.iterdir() if path.is_dir()))

    def _coverage(self, league_key: str) -> dict[str, Any]:
        document = self._read_json(
            self._league_root(league_key) / "history" / "records.json"
        )
        coverage = document.get("coverage") or {}
        return {
            "coverage_complete": bool(coverage.get("complete", True)),
            "coverage_warnings": [
                str(value) for value in coverage.get("warnings") or []
            ],
        }

    def _league_root(self, league_key: str) -> Path:
        return self.root / "leagues" / self._safe_component(league_key)

    @staticmethod
    def _safe_component(value: str) -> str:
        text = str(value).strip()
        if not text or text in {".", ".."} or "/" in text or "\\" in text:
            raise ValueError(f"Unsafe Chronicle path component: {value!r}")
        return text

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"Expected JSON object in {path}")
        return value

    @staticmethod
    def _read_jsonl_tree(root: Path) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not root.exists():
            return rows
        for path in sorted(root.glob("*.jsonl"), key=lambda item: item.name):
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"Expected JSON object line in {path}")
                rows.append(value)
        return rows

    @staticmethod
    def _after(value: Any, since: str) -> bool:
        if value is None:
            return False
        try:
            return datetime.fromisoformat(str(value)) > datetime.fromisoformat(str(since))
        except ValueError:
            return False

    @classmethod
    def _contains(cls, value: Any, wanted: str) -> bool:
        if isinstance(value, dict):
            return any(cls._contains(item, wanted) for item in value.values())
        if isinstance(value, (list, tuple, set)):
            return any(cls._contains(item, wanted) for item in value)
        return str(value) == wanted
