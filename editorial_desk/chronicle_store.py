from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable

from .chronicle_events import ChronicleEvent


@dataclass(frozen=True)
class AppendResult:
    added: int
    skipped: int
    paths: tuple[Path, ...]


class ChronicleStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def append_events(self, events: Iterable[ChronicleEvent]) -> AppendResult:
        grouped: dict[Path, list[ChronicleEvent]] = {}
        for event in events:
            grouped.setdefault(
                self._event_path(event.league_key, event.season), []
            ).append(event)

        added = 0
        skipped = 0
        changed_paths: list[Path] = []
        for path, incoming in sorted(grouped.items(), key=lambda item: str(item[0])):
            existing = {row["event_id"]: row for row in self._read_jsonl(path)}
            before_count = len(existing)
            for event in incoming:
                row = event.to_dict()
                if event.event_id in existing:
                    skipped += 1
                    continue
                existing[event.event_id] = row
                added += 1
            if len(existing) == before_count:
                continue
            rows = [existing[key] for key in sorted(existing)]
            payload = "".join(
                json.dumps(
                    row,
                    sort_keys=True,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
                for row in rows
            )
            self._atomic_write_text(path, payload)
            changed_paths.append(path)
        return AppendResult(
            added=added,
            skipped=skipped,
            paths=tuple(changed_paths),
        )

    def read_events(
        self, league_key: str | None, season: str
    ) -> list[dict[str, Any]]:
        return self._read_jsonl(self._event_path(league_key, season))

    def read_current_state(self, scope: str) -> dict[str, Any]:
        return self._read_json(self._current_state_path(scope))

    def write_current_state(self, scope: str, state: dict[str, Any]) -> Path:
        path = self._current_state_path(scope)
        self._atomic_write_json(path, state)
        return path

    def write_manifest(self, run_id: str, manifest: dict[str, Any]) -> Path:
        path = self.root / "manifests" / f"{self._safe_component(run_id)}.json"
        self._atomic_write_json(path, manifest)
        return path

    def read_coverage(self) -> dict[str, Any]:
        return self._read_json(self.root / "coverage" / "live_observation.json")

    def write_coverage(self, value: dict[str, Any]) -> Path:
        path = self.root / "coverage" / "live_observation.json"
        self._atomic_write_json(path, value)
        return path

    def _event_path(self, league_key: str | None, season: str) -> Path:
        safe_season = self._safe_component(season)
        if league_key is None:
            return (
                self.root
                / "cross_league"
                / "nfl_player_events"
                / f"{safe_season}.jsonl"
            )
        return (
            self.root
            / "leagues"
            / self._safe_component(league_key)
            / "events"
            / f"{safe_season}.jsonl"
        )

    def _current_state_path(self, scope: str) -> Path:
        return (
            self.root
            / "diagnostics"
            / "current_state"
            / f"{self._safe_component(scope)}.json"
        )

    @staticmethod
    def _safe_component(value: str) -> str:
        text = str(value).strip()
        if not text or text in {".", ".."} or "/" in text or "\\" in text:
            raise ValueError(f"Unsafe Chronicle path component: {value!r}")
        return text

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"Expected JSON object in {path}")
        return value

    def _atomic_write_json(self, path: Path, value: dict[str, Any]) -> None:
        payload = (
            json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)
            + "\n"
        )
        self._atomic_write_text(path, payload)

    @staticmethod
    def _atomic_write_text(path: Path, payload: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
        except Exception:
            try:
                tmp_path.unlink(missing_ok=True)
            finally:
                raise
