"""Standalone, read-only Sleeper team-avatar collection for magazine artwork.

Team identity is anchored to league + season + roster ID, never a mutable team
name. Full-size Sleeper CDN originals are retained unmodified, and correctly
sized PNG copies are provided for typesetting without enlarging low-res sources.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import shutil
from typing import Any
from urllib.parse import urlsplit

from PIL import Image, UnidentifiedImageError
import requests

from .config import LeagueConfig
from .sleeper import SleeperClient, USER_AGENT

CDN_ROOT = "https://sleepercdn.com/avatars"
AVATAR_ID = re.compile(r"^[a-zA-Z0-9_.-]{1,200}$")
EXTENSIONS = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp", "GIF": ".gif"}
MAX_BYTES = 12 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 30_000_000


class AvatarCollectionError(RuntimeError):
    pass


def _team_image_url(value: Any) -> str | None:
    """Validate Sleeper's team-upload URL or legacy avatar ID.

    League-specific uploads are often complete /uploads/ URLs, NOT the
    opaque account avatar IDs returned as user.avatar. Only Sleeper CDN
    resources are permitted. Unknown formats are not guessed at.
    """
    if value is None:
        return None
    candidate = str(value).strip()
    if not candidate or candidate.lower() in {"0", "none", "null", "false"}:
        return None
    if candidate.startswith("/uploads/") or candidate.startswith("/avatars/"):
        candidate = "https://sleepercdn.com" + candidate
    if AVATAR_ID.fullmatch(candidate):
        return f"{CDN_ROOT}/{candidate}"
    parts = urlsplit(candidate)
    if (parts.scheme != "https" or parts.netloc != "sleepercdn.com"
        or parts.username or parts.password or parts.fragment
        or not parts.path.startswith(("/uploads/", "/avatars/"))
        or ".." in parts.path.split("/") or "\\" in parts.path):
        return None
    return candidate


def choose_avatar(user: dict[str, Any], roster: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return a league-specific TEAM image URL, never the account avatar."""
    metadata = user.get("metadata") or {}
    roster_metadata = roster.get("metadata") or {}
    for source, value in (
        ("user.metadata.avatar", metadata.get("avatar")),
        ("user.metadata.team_avatar", metadata.get("team_avatar")),
        ("roster.metadata.avatar", roster_metadata.get("avatar")),
    ):
        url = _team_image_url(value)
        if url:
            return url, source
    return None, None


def _fetch_image(
    session: requests.Session, image_url: str, timeout: int
) -> tuple[bytes, str, tuple[int, int], bytes]:
    response = session.get(
        image_url,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT, "Accept": "image/*"},
        stream=True,
    )
    response.raise_for_status()
    content = bytearray()
    try:
        for chunk in response.iter_content(chunk_size=65536):
            content.extend(chunk)
            if len(content) > MAX_BYTES:
                raise AvatarCollectionError("Sleeper avatar exceeded 12 MB limit")
    finally:
        response.close()
    original = bytes(content)
    try:
        with Image.open(BytesIO(original)) as img:
            image_format = img.format
            size = (img.width, img.height)
            if image_format not in EXTENSIONS or not all(size):
                raise AvatarCollectionError(f"Unsupported Sleeper image format: {image_format}")
            img.load()
            png_buffer = BytesIO()
            img.convert("RGBA").save(png_buffer, format="PNG")
            publication_png = png_buffer.getvalue()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise AvatarCollectionError("CDN response was not a valid supported image") from exc
    return original, EXTENSIONS[image_format], size, publication_png


def collect_team_avatars(
    league: LeagueConfig,
    output_root: Path,
    *,
    client: SleeperClient | None = None,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """Download originals and generate a durable per-roster visual-identity manifest."""
    client = client or SleeperClient()
    session = session or requests.Session()
    league_data = client.league(league.sleeper_league_id)
    if str(league_data.get("league_id") or league.sleeper_league_id) != league.sleeper_league_id:
        raise AvatarCollectionError("Sleeper returned a different league ID")
    season = str(league_data.get("season") or "").strip()
    if not season.isdigit() or len(season) != 4:
        raise AvatarCollectionError("Sleeper league season is missing or invalid")
    users = client.users(league.sleeper_league_id)
    rosters = client.rosters(league.sleeper_league_id)
    if not isinstance(users, list) or not isinstance(rosters, list) or not rosters:
        raise AvatarCollectionError("Sleeper did not return a usable roster/user list")

    by_owner = {str(u.get("user_id")): u for u in users if isinstance(u, dict)}
    directory = Path(output_root) / league.key / season
    directory.mkdir(parents=True, exist_ok=True)
    existing = directory / "manifest.json"
    manually_provided: dict[int, dict[str, Any]] = {}
    if existing.is_file():
        prior = json.loads(existing.read_text(encoding="utf-8"))
        if (str(prior.get("league_id")) == league.sleeper_league_id
            and str(prior.get("season")) == season
            and str(prior.get("league_key")) == league.key):
            manually_provided = {
                int(row["roster_id"]): row
                for row in (prior.get("teams") or [])
                if row.get("avatar_source") == "commissioner_supplied"
                and row.get("status") == "downloaded"
            }
    records: list[dict[str, Any]] = []
    for roster in sorted(rosters, key=lambda row: int(row.get("roster_id") or 0)):
        roster_id = int(roster.get("roster_id") or 0)
        owner_id = str(roster.get("owner_id") or "")
        user = by_owner.get(owner_id) or {}
        meta = user.get("metadata") or {}
        name = str(meta.get("team_name") or user.get("display_name") or f"Roster {roster_id}")
        manual = manually_provided.get(roster_id)
        if manual:
            original = directory / str(manual.get("original_path") or "")
            image = directory / str(manual.get("image_path") or "")
            if (original.is_file() and image.is_file()
                and sha256(original.read_bytes()).hexdigest() == manual.get("sha256")):
                records.append({**manual, "team_name": name, "owner_id": owner_id})
                continue
        image_url, source = choose_avatar(user, roster)
        row: dict[str, Any] = {
            "roster_id": roster_id,
            "owner_id": owner_id,
            "team_name": name,
            "avatar_id": None,
            "team_image_url": image_url,
            "avatar_source": source,
            "status": "missing_team_upload" if not image_url else "pending",
            "team_metadata_keys": sorted((user.get("metadata") or {}).keys()),
        }
        if image_url:
            row["full_size_url"] = image_url
            try:
                data, ext, (w, h), png = _fetch_image(session, image_url, timeout)
                original_name = f"roster-{roster_id}-original{ext}"
                image_name = f"roster-{roster_id}.png"
                (directory / original_name).write_bytes(data)
                (directory / image_name).write_bytes(png)
                row.update({
                    "status": "downloaded",
                    "original_path": original_name,
                    "image_path": image_name,
                    "sha256": sha256(data).hexdigest(),
                    "width": w,
                    "height": h,
                    "resolution_warning": min(w, h) < 256,
                })
            except (requests.RequestException, AvatarCollectionError, OSError) as exc:
                row.update({"status": "download_failed", "error": str(exc)})
        records.append(row)

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "league_key": league.key,
        "league_id": league.sleeper_league_id,
        "league_name": league_data.get("name") or league.name,
        "season": season,
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "asset_kind": "verified league-specific team images only; originals and PNG derivatives",
        "teams": records,
        "expected_rosters": len(rosters),
        "downloaded": sum(r["status"] == "downloaded" for r in records),
    }
    (directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest



def import_commissioner_team_avatars(
    league: LeagueConfig, asset_root: Path, overrides_dir: Path, *, season: str
) -> dict[str, Any]:
    """Merge the commissioner's actual files into an existing Sleeper manifest.

    Files must be named roster-N-original.jpg/png/webp; a supplied image is
    never mistaken for one downloaded from Sleeper. These entries survive
    future collection runs so long as their originals remain on disk.
    """
    directory = Path(asset_root) / league.key / str(season)
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        raise AvatarCollectionError("Run collect-team-avatars before importing overrides")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("league_key") != league.key
        or str(manifest.get("league_id")) != league.sleeper_league_id
        or str(manifest.get("season")) != str(season)):
        raise AvatarCollectionError("Commissioner override manifest league/season mismatch")
    index = {int(row["roster_id"]): row for row in manifest.get("teams") or []}
    override_files = sorted(
        path for path in Path(overrides_dir).iterdir()
        if path.is_file() and re.fullmatch(
            r"roster-[0-9]+-original\.(jpg|jpeg|png|webp)", path.name, re.IGNORECASE
        )
    )
    if not override_files:
        raise AvatarCollectionError("No roster-N-original images found in override directory")
    imported = []
    for file in override_files:
        roster_id = int(file.name.split("-")[1])
        if roster_id not in index:
            raise AvatarCollectionError(f"Override roster {roster_id} is not in this league")
        raw = file.read_bytes()
        if len(raw) > MAX_BYTES:
            raise AvatarCollectionError(f"Override {file.name} exceeded size limit")
        try:
            with Image.open(BytesIO(raw)) as image:
                if image.format not in EXTENSIONS or not image.width or not image.height:
                    raise AvatarCollectionError(f"Unsupported commissioner logo: {file.name}")
                image.load()
                size = (image.width, image.height)
                png_buf = BytesIO()
                image.convert("RGBA").save(png_buf, format="PNG")
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise AvatarCollectionError(f"Invalid commissioner logo: {file.name}") from exc
        original_name = f"roster-{roster_id}-original{EXTENSIONS[image.format]}"
        (directory / original_name).write_bytes(raw)
        (directory / f"roster-{roster_id}.png").write_bytes(png_buf.getvalue())
        index[roster_id].update({
            "status": "downloaded",
            "avatar_id": None,
            "avatar_source": "commissioner_supplied",
            "team_image_url": None,
            "full_size_url": None,
            "original_path": original_name,
            "image_path": f"roster-{roster_id}.png",
            "sha256": sha256(raw).hexdigest(),
            "width": size[0],
            "height": size[1],
            "resolution_warning": min(size) < 256,
        })
        index[roster_id].pop("error", None)
        imported.append(roster_id)
    manifest["downloaded"] = sum(row.get("status") == "downloaded" for row in index.values())
    manifest["commissioner_supplied_rosters"] = sorted(
        roster for roster, row in index.items()
        if row.get("avatar_source") == "commissioner_supplied"
    )
    manifest["overrides_imported_at_utc"] = datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {"imported_roster_ids": imported, "manifest": manifest, "manifest_path": str(manifest_path)}


def attach_team_avatars(
    league: LeagueConfig,
    asset_root: Path,
    issue_dir: Path,
    *,
    season: str,
) -> dict[str, Any]:
    """Copy roster-specific PNGs into a magazine issue and attach a lookup map.

    This never changes the issue's editorial scores or predictions. The sidecar
    is also embedded in publication_packet.json, when that packet already exists.
    """
    source_dir = Path(asset_root) / league.key / str(season)
    manifest_file = source_dir / "manifest.json"
    if not manifest_file.is_file():
        raise AvatarCollectionError(f"Missing team-avatar manifest: {manifest_file}")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if (str(manifest.get("league_id")) != league.sleeper_league_id
        or str(manifest.get("league_key")) != league.key
        or str(manifest.get("season")) != str(season)):
        raise AvatarCollectionError("Team-avatar manifest league or season mismatch")

    destination = Path(issue_dir) / "publication-assets" / "team-avatars"
    destination.mkdir(parents=True, exist_ok=True)
    teams: list[dict[str, Any]] = []
    for row in manifest["teams"]:
        if row.get("status") != "downloaded":
            continue
        roster_id = int(row["roster_id"])
        source = source_dir / f"roster-{roster_id}.png"
        if not source.is_file():
            continue
        target = destination / source.name
        shutil.copyfile(source, target)
        teams.append({
            "roster_id": roster_id,
            "owner_id": row.get("owner_id"),
            "team_name": row.get("team_name"),
            "team_image_url": row.get("team_image_url"),
            "image_path": f"publication-assets/team-avatars/{source.name}",
            "width": row.get("width"),
            "height": row.get("height"),
            "resolution_warning": row.get("resolution_warning"),
            "source": row.get("avatar_source"),
        })

    attachment = {
        "schema_version": 1,
        "league_key": league.key,
        "league_id": league.sleeper_league_id,
        "season": str(season),
        "teams": teams,
        "attached": len(teams),
        "expected": manifest.get("expected_rosters"),
    }
    issue_dir = Path(issue_dir)
    (issue_dir / "team_avatars.json").write_text(
        json.dumps(attachment, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    publication_packet = issue_dir / "publication_packet.json"
    if publication_packet.exists():
        packet = json.loads(publication_packet.read_text(encoding="utf-8"))
        packet.setdefault("media_assets", {})["team_avatars"] = attachment
        publication_packet.write_text(
            json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return attachment
