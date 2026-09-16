from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
from typing import Any
import zipfile


BACKUP_SCHEMA_VERSION = 1
MANIFEST_NAME = "BACKUP_MANIFEST.json"
_EXCLUDED_ROOTS = frozenset(
    {
        ".cache",
        ".git",
        ".pytest_cache",
        "__pycache__",
        "backups",
        "cache",
        "diagnostics",
        "tmp",
    }
)


class ChronicleBackupError(RuntimeError):
    """Raised when a Chronicle backup cannot be created or safely restored."""


@dataclass(frozen=True)
class BackupValidationResult:
    valid: bool
    errors: tuple[str, ...]
    chronicle_revision: str | None
    file_count: int


def create_chronicle_backup(
    chronicle_root: Path,
    output_path: Path,
    *,
    chronicle_revision: str,
    created_at: str | None = None,
) -> Path:
    """Create and validate an atomic ZIP of permanent Chronicle state."""
    root = Path(chronicle_root)
    output = Path(output_path)
    revision = str(chronicle_revision).strip()
    if not root.is_dir():
        raise ChronicleBackupError(f"Chronicle root does not exist: {root}")
    if not revision:
        raise ChronicleBackupError("Chronicle revision is required")

    files = _permanent_files(root, output)
    manifest_files: dict[str, dict[str, object]] = {}
    for relative, path in files:
        payload = path.read_bytes()
        manifest_files[relative] = {
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size": len(payload),
        }

    ledger_metadata = _ledger_metadata(root)
    manifest = {
        "schema_version": BACKUP_SCHEMA_VERSION,
        "schema_versions": {
            "backup": BACKUP_SCHEMA_VERSION,
            "chronicle_events": ledger_metadata["schema_versions"],
        },
        "chronicle_revision": revision,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "leagues": ledger_metadata["leagues"],
        "seasons": ledger_metadata["seasons"],
        "event_counts": ledger_metadata["event_counts"],
        # The archive is published only after validate_chronicle_backup succeeds.
        "validation_status": "validated",
        "files": manifest_files,
        "excluded_roots": sorted(_EXCLUDED_ROOTS),
    }
    manifest_payload = (
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")

    output.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
    )
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        with zipfile.ZipFile(
            tmp_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for relative, path in files:
                archive.writestr(relative, path.read_bytes())
            archive.writestr(MANIFEST_NAME, manifest_payload)

        validation = validate_chronicle_backup(
            tmp_path, expected_revision=revision
        )
        if not validation.valid:
            raise ChronicleBackupError(
                "Created Chronicle backup failed validation: "
                + "; ".join(validation.errors)
            )
        os.replace(tmp_path, output)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    return output


def validate_chronicle_backup(
    archive_path: Path,
    *,
    expected_revision: str | None = None,
) -> BackupValidationResult:
    """Validate manifest shape, archive membership, sizes, and SHA-256 checksums."""
    path = Path(archive_path)
    errors: list[str] = []
    revision: str | None = None
    file_count = 0
    try:
        with zipfile.ZipFile(path, "r") as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                errors.append("Archive contains duplicate member names")
            if MANIFEST_NAME not in names:
                errors.append("Backup manifest is missing")
                return BackupValidationResult(False, tuple(errors), None, 0)

            try:
                manifest = json.loads(archive.read(MANIFEST_NAME))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                errors.append(f"Backup manifest is invalid JSON: {exc}")
                return BackupValidationResult(False, tuple(errors), None, 0)
            if not isinstance(manifest, dict):
                errors.append("Backup manifest must be a JSON object")
                return BackupValidationResult(False, tuple(errors), None, 0)

            if manifest.get("schema_version") != BACKUP_SCHEMA_VERSION:
                errors.append(
                    "Unsupported backup schema version: "
                    f"{manifest.get('schema_version')!r}"
                )
            if manifest.get("validation_status") != "validated":
                errors.append("Backup manifest is not marked validated")
            schema_versions = manifest.get("schema_versions")
            if not isinstance(schema_versions, dict):
                errors.append("Backup manifest schema_versions entry must be an object")
            elif schema_versions.get("backup") != BACKUP_SCHEMA_VERSION:
                errors.append("Backup manifest schema_versions.backup is invalid")

            for field in ("leagues", "seasons"):
                value = manifest.get(field)
                if not isinstance(value, list) or any(
                    not isinstance(item, str) for item in value
                ):
                    errors.append(f"Backup manifest {field} entry must be a string list")
            event_counts = manifest.get("event_counts")
            if not isinstance(event_counts, dict):
                errors.append("Backup manifest event_counts entry must be an object")

            revision_value = manifest.get("chronicle_revision")
            revision = str(revision_value) if revision_value is not None else None
            if not revision:
                errors.append("Backup manifest has no Chronicle revision")
            if expected_revision is not None and revision != str(expected_revision):
                errors.append(
                    "Chronicle revision mismatch: "
                    f"expected {expected_revision}, found {revision}"
                )

            files = manifest.get("files")
            if not isinstance(files, dict):
                errors.append("Backup manifest files entry must be an object")
                return BackupValidationResult(False, tuple(errors), revision, 0)
            file_count = len(files)

            expected_names = set(files) | {MANIFEST_NAME}
            actual_names = set(names)
            for unexpected in sorted(actual_names - expected_names):
                errors.append(f"Unexpected archive member: {unexpected}")
            for missing in sorted(expected_names - actual_names):
                errors.append(f"Archive member missing: {missing}")

            for name, metadata in sorted(files.items()):
                if not _safe_archive_name(name):
                    errors.append(f"Unsafe archive member path: {name}")
                    continue
                if name not in actual_names:
                    continue
                if not isinstance(metadata, dict):
                    errors.append(f"Invalid manifest metadata for {name}")
                    continue
                payload = archive.read(name)
                expected_size = metadata.get("size")
                if expected_size != len(payload):
                    errors.append(
                        f"Size mismatch for {name}: expected {expected_size}, found {len(payload)}"
                    )
                expected_hash = str(metadata.get("sha256") or "")
                actual_hash = hashlib.sha256(payload).hexdigest()
                if expected_hash != actual_hash:
                    errors.append(f"Checksum mismatch for {name}")
    except (FileNotFoundError, zipfile.BadZipFile, OSError) as exc:
        errors.append(f"Backup archive cannot be read: {exc}")

    return BackupValidationResult(
        valid=not errors,
        errors=tuple(errors),
        chronicle_revision=revision,
        file_count=file_count,
    )


def restore_chronicle_backup(
    archive_path: Path,
    destination: Path,
    *,
    expected_revision: str | None = None,
) -> tuple[Path, ...]:
    """Restore only after full archive validation succeeds."""
    validation = validate_chronicle_backup(
        archive_path, expected_revision=expected_revision
    )
    if not validation.valid:
        raise ChronicleBackupError(
            "Chronicle backup validation failed: " + "; ".join(validation.errors)
        )

    target = Path(destination)
    if target.exists() and any(target.iterdir()):
        raise ChronicleBackupError(
            f"Restore destination must be absent or empty: {target}"
        )

    with zipfile.ZipFile(Path(archive_path), "r") as archive:
        manifest = json.loads(archive.read(MANIFEST_NAME))
        names = sorted((manifest.get("files") or {}).keys())
        written: list[Path] = []
        target.mkdir(parents=True, exist_ok=True)
        for name in names:
            if not _safe_archive_name(name):
                raise ChronicleBackupError(f"Unsafe archive member path: {name}")
            path = target.joinpath(*PurePosixPath(name).parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(name))
            written.append(path)
    return tuple(written)


def _permanent_files(root: Path, output_path: Path) -> list[tuple[str, Path]]:
    output_resolved = output_path.resolve(strict=False)
    rows: list[tuple[str, Path]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        if not relative.parts or relative.parts[0] in _EXCLUDED_ROOTS:
            continue
        if path.resolve(strict=False) == output_resolved:
            continue
        name = relative.as_posix()
        if not _safe_archive_name(name):
            raise ChronicleBackupError(f"Unsafe Chronicle path: {name}")
        rows.append((name, path))
    return rows


def _ledger_metadata(root: Path) -> dict[str, Any]:
    leagues_root = root / "leagues"
    leagues = sorted(
        path.name for path in leagues_root.iterdir() if path.is_dir()
    ) if leagues_root.exists() else []

    seasons: set[str] = set()
    schema_versions: set[int] = set()
    league_counts: dict[str, int] = {}
    total = 0

    for league_key in leagues:
        count = 0
        events_root = leagues_root / league_key / "events"
        if events_root.exists():
            for path in sorted(events_root.glob("*.jsonl")):
                seasons.add(path.stem)
                rows = _read_event_rows(path)
                count += len(rows)
                for row in rows:
                    version = row.get("schema_version")
                    if isinstance(version, int):
                        schema_versions.add(version)
        league_counts[league_key] = count
        total += count

    cross_count = 0
    cross_root = root / "cross_league" / "nfl_player_events"
    if cross_root.exists():
        for path in sorted(cross_root.glob("*.jsonl")):
            seasons.add(path.stem)
            rows = _read_event_rows(path)
            cross_count += len(rows)
            for row in rows:
                version = row.get("schema_version")
                if isinstance(version, int):
                    schema_versions.add(version)
    total += cross_count

    return {
        "leagues": leagues,
        "seasons": sorted(seasons),
        "schema_versions": sorted(schema_versions),
        "event_counts": {
            "cross_league": cross_count,
            "leagues": league_counts,
            "total": total,
        },
    }


def _read_event_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ChronicleBackupError(f"Cannot read Chronicle ledger {path}: {exc}") from exc
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ChronicleBackupError(
                f"Invalid Chronicle event JSON in {path} line {number}: {exc.msg}"
            ) from exc
        if not isinstance(value, dict):
            raise ChronicleBackupError(
                f"Chronicle event in {path} line {number} is not an object"
            )
        rows.append(value)
    return rows


def _safe_archive_name(name: str) -> bool:
    if not isinstance(name, str) or not name or "\\" in name:
        return False
    path = PurePosixPath(name)
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)
