from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Any


_TIMESTAMP_KEYS = (
    "observed_at",
    "created_at",
    "collected_at",
    "updated_at",
    "run_at",
    "timestamp",
)


@dataclass(frozen=True)
class PruneResult:
    removed: tuple[Path, ...]
    kept: tuple[Path, ...]
    skipped_unparseable: tuple[Path, ...]


def prune_diagnostics(
    chronicle_root: Path,
    now: datetime,
    retention_days: int = 30,
) -> PruneResult:
    """Delete only timestamped files under diagnostics older than retention_days."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    if int(retention_days) < 1:
        raise ValueError("retention_days must be at least 1")

    diagnostics = Path(chronicle_root) / "diagnostics"
    if not diagnostics.exists():
        return PruneResult((), (), ())

    cutoff = now - timedelta(days=int(retention_days))
    removed: list[Path] = []
    kept: list[Path] = []
    skipped: list[Path] = []

    for path in sorted(diagnostics.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file() or path.is_symlink():
            continue
        timestamp = _diagnostic_timestamp(path)
        if timestamp is None:
            skipped.append(path)
            continue
        if timestamp < cutoff:
            path.unlink()
            removed.append(path)
        else:
            kept.append(path)

    _remove_empty_directories(diagnostics)
    return PruneResult(tuple(removed), tuple(kept), tuple(skipped))


def _diagnostic_timestamp(path: Path) -> datetime | None:
    suffix = path.suffix.casefold()
    if suffix == ".json":
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        return _timestamp_from_value(value)

    if suffix == ".jsonl":
        timestamps: list[datetime] = []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            return None
        for line in lines:
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                return None
            timestamp = _timestamp_from_value(value)
            if timestamp is not None:
                timestamps.append(timestamp)
        return max(timestamps) if timestamps else None

    return None


def _timestamp_from_value(value: Any) -> datetime | None:
    if not isinstance(value, dict):
        return None
    for key in _TIMESTAMP_KEYS:
        parsed = _parse_timestamp(value.get(key))
        if parsed is not None:
            return parsed
    return None


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _remove_empty_directories(diagnostics: Path) -> None:
    directories = sorted(
        (path for path in diagnostics.rglob("*") if path.is_dir() and not path.is_symlink()),
        key=lambda item: len(item.parts),
        reverse=True,
    )
    for path in directories:
        try:
            path.rmdir()
        except OSError:
            pass
