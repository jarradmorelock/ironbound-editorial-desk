from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Any

import requests

from .collector import collect_all as collect_base
from .config import LeagueConfig, PublicationConfig
from .nflverse import NFLVerseClient
from .reading_packet import reading_packet_from_artifacts
from .external_inputs import load_external_inputs
from .flagship_research import (
    build_flagship_research_packet,
    write_flagship_research_packet,
)
from .publication_packets import build_publication_packet
from .publication_render import write_publication_packet
from .newspaper_research import (
    build_newspaper_research_packet,
    write_newspaper_research_packet,
)
from .rankings import RankingsClient
from .review import build_editorial_review, render_editorial_review
from .sleeper import SleeperClient
from .story_artifacts import write_story_desk_artifacts
from .chronicle_queries import ChronicleQueries


def collect_all(
    leagues: list[LeagueConfig],
    week: int,
    output_root: Path,
    client: SleeperClient | None = None,
    publications: dict[str, PublicationConfig] | None = None,
    rankings_client: RankingsClient | None = None,
    nflverse_client: NFLVerseClient | None = None,
    chronicle_root: Path | None = None,
    external_inputs_dir: Path | None = None,
    chronicle_revision: str | None = None,
) -> list[Path]:
    """Run the existing collector, then enrich publication dossiers for review."""
    sleeper = client or SleeperClient()
    nflverse = nflverse_client or NFLVerseClient()
    generated = collect_base(
        leagues,
        week,
        output_root,
        client=sleeper,
        publications=publications,
        rankings_client=rankings_client,
        nflverse_client=nflverse,
    )

    snapshot_paths = {
        path.parent.name: path
        for path in generated
        if path.name == "snapshot.json" and path.exists()
    }
    publication_configs = [league for league in leagues if league.publication_enabled]
    if not publication_configs or not snapshot_paths:
        return generated

    first_snapshot = json.loads(next(iter(snapshot_paths.values())).read_text(encoding="utf-8"))
    season = str(
        (first_snapshot.get("nfl_state") or {}).get("season")
        or (first_snapshot.get("league") or {}).get("season")
        or "unknown"
    )
    shared = _collect_deep_nfl_context(nflverse, season, week)
    player_directory = sleeper.players()

    for config in publication_configs:
        snapshot_path = snapshot_paths.get(config.key)
        if snapshot_path is None:
            continue
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        if chronicle_revision:
            snapshot["chronicle_revision"] = str(chronicle_revision)
        _apply_player_context(snapshot, player_directory)
        _apply_context_scope(snapshot, shared, include_deep=config.tier == "flagship")
        _ensure_draft_context(snapshot, sleeper, config.sleeper_league_id)
        _ensure_next_matchups(snapshot, sleeper, config.sleeper_league_id, week)
        _write_json(snapshot_path, snapshot)

        dossier = build_editorial_review(snapshot)
        if chronicle_revision:
            dossier["chronicle_revision"] = str(chronicle_revision)
        directory = snapshot_path.parent
        _write_json(directory / "dossier.json", dossier)
        (directory / "dossier.md").write_text(
            render_editorial_review(dossier), encoding="utf-8"
        )

        if publications:
            profile = publications.get(config.publication_profile or "")
            if profile is None:
                continue
            if profile.tier == "newspaper":
                generated.extend(
                    _write_newspaper_packet(
                        directory,
                        snapshot,
                        dossier,
                        profile,
                        phase="weekly",
                    )
                )
            if profile.story_desk and chronicle_root is not None:
                generated.extend(
                    write_story_desk_artifacts(
                        directory,
                        snapshot,
                        dossier,
                        profile,
                        chronicle_root=chronicle_root,
                        external_inputs_dir=external_inputs_dir,
                    )
                )
            if profile.tier == "flagship":
                external_path = (
                    Path(external_inputs_dir) / f"{profile.key}.json"
                    if external_inputs_dir is not None
                    and (Path(external_inputs_dir) / f"{profile.key}.json").exists()
                    else None
                )
                external_inputs = load_external_inputs(external_path, profile.key)
                publication_assets, copied_asset_paths = _materialize_publication_assets(
                    external_inputs,
                    directory,
                )
                generated.extend(copied_asset_paths)
                story_path = directory / "story_desk.json"
                story = (
                    json.loads(story_path.read_text(encoding="utf-8"))
                    if story_path.exists()
                    else {}
                )
                flagship_packet = build_flagship_research_packet(
                    snapshot,
                    dossier,
                    story,
                    external_inputs,
                    history_root=output_root,
                    chronicle=(
                        ChronicleQueries(Path(chronicle_root))
                        if chronicle_root is not None
                        else None
                    ),
                    publication_assets=publication_assets,
                )
                if flagship_packet is not None:
                    generated.extend(
                        write_flagship_research_packet(directory, flagship_packet)
                    )

        reading_path = directory / "reading_packet.md"
        reading_path.write_text(reading_packet_from_artifacts(directory, dossier), encoding="utf-8")
        generated.append(reading_path)

    return generated


def _materialize_publication_assets(
    external_inputs,
    directory: Path,
) -> tuple[dict[str, dict[str, Any]] | None, list[Path]]:
    """Copy authoritative ranking-engine graphics into the publication package.

    Handoffs created before the image contract existed have no publication_assets
    field at all. Those legacy packets remain readable. Once the rankings engine
    advertises publication assets, every advertised image becomes required.
    """
    if not external_inputs.publication_assets:
        return None, []

    target_dir = Path(directory) / "publication-assets"
    manifest: dict[str, dict[str, Any]] = {}
    copied: list[Path] = []

    for key in ("power_rankings", "playoff_forecast"):
        row = dict((external_inputs.publication_assets or {}).get(key) or {})
        if not row:
            manifest[key] = {
                "status": "AWAITING_TUESDAY_INPUT",
                "reason": "Ranking engine did not supply this publication asset.",
            }
            continue
        source = Path(str(row.get("local_path") or ""))
        if not row.get("available") or not source.is_file():
            manifest[key] = {
                **row,
                "status": "AWAITING_TUESDAY_INPUT",
                "reason": f"Publication asset file is unavailable: {row.get('filename')}",
            }
            continue

        target_dir.mkdir(parents=True, exist_ok=True)
        destination = target_dir / str(row["filename"])
        shutil.copyfile(source, destination)
        manifest[key] = {
            **row,
            "status": "READY",
            "package_path": f"publication-assets/{destination.name}",
            "placement_policy": row.get("placement_policy")
            or "use supplied graphic unchanged",
        }
        # Do not expose the temporary editorial-input path in the durable packet.
        manifest[key].pop("local_path", None)
        manifest[key].pop("available", None)
        copied.append(destination)

    return manifest, copied


def _write_newspaper_packet(
    directory: Path,
    snapshot: dict[str, Any],
    dossier: dict[str, Any],
    publication: PublicationConfig,
    *,
    phase: str = "weekly",
) -> tuple[Path, ...]:
    packet = build_publication_packet(
        snapshot,
        dossier,
        publication,
        phase,
    )
    generated = list(write_publication_packet(directory, packet))
    research = build_newspaper_research_packet(snapshot, dossier, packet)
    generated.extend(write_newspaper_research_packet(directory, research))
    return tuple(generated)


def _collect_deep_nfl_context(
    client: NFLVerseClient, season: str, week: int
) -> dict[str, Any]:
    sources: dict[str, Any] = {}
    for name, fetcher in (
        ("player_stats", client.player_stats),
        ("snap_counts", client.snap_counts),
        ("play_by_play", client.play_by_play),
    ):
        try:
            records = fetcher(season, week)
            if not isinstance(records, list):
                raise ValueError("NFL context response was not a list")
            sources[name] = {"status": "available", "records": records}
        except (requests.RequestException, ValueError, KeyError, OSError) as exc:
            sources[name] = {
                "status": "unavailable",
                "records": [],
                "error": str(exc),
            }
    return sources


def _collect_draft_context(client: SleeperClient, league_id: str) -> dict[str, Any]:
    """Collect draft records without invoking the full flagship history pass."""
    try:
        drafts = client.drafts(league_id)
        if not isinstance(drafts, list):
            raise ValueError("Sleeper drafts response was not a list")
        records: list[dict[str, Any]] = []
        errors: dict[str, str] = {}
        for draft in drafts:
            draft_id = str(draft.get("draft_id") or "")
            if not draft_id:
                continue
            try:
                picks = client.draft_picks(draft_id)
                if not isinstance(picks, list):
                    raise ValueError("Sleeper draft-picks response was not a list")
            except (requests.RequestException, ValueError, KeyError, OSError) as exc:
                picks = []
                errors[f"{draft_id}:picks"] = str(exc)
            try:
                traded = client.draft_traded_picks(draft_id)
                if not isinstance(traded, list):
                    raise ValueError("Sleeper draft traded-picks response was not a list")
            except (requests.RequestException, ValueError, KeyError, OSError) as exc:
                traded = []
                errors[f"{draft_id}:traded_picks"] = str(exc)
            records.append(
                {
                    "draft": draft,
                    "picks": picks,
                    "traded_picks": traded,
                }
            )
        result: dict[str, Any] = {"status": "available", "records": records}
        if errors:
            result["errors"] = errors
        return result
    except (requests.RequestException, ValueError, KeyError, OSError) as exc:
        return {
            "status": "unavailable",
            "records": [],
            "error": str(exc),
        }


def _ensure_draft_context(
    snapshot: dict[str, Any], client: SleeperClient, league_id: str
) -> None:
    """Attach one normalized draft source for both flagships and newspapers."""
    existing = ((snapshot.get("flagship_sleeper") or {}).get("drafts") or {})
    if existing.get("status") == "available":
        snapshot["draft_context"] = dict(existing)
        return
    snapshot["draft_context"] = _collect_draft_context(client, league_id)


def _collect_next_matchups(
    client: SleeperClient, league_id: str, week: int
) -> dict[str, Any]:
    """Collect the following Sleeper week for Next Card/Slate departments."""
    next_week = int(week) + 1
    try:
        records = client.matchups(league_id, next_week)
        if not isinstance(records, list):
            raise ValueError("Sleeper next-week matchups response was not a list")
        return {
            "status": "available",
            "week": next_week,
            "records": records,
        }
    except (requests.RequestException, ValueError, KeyError, OSError) as exc:
        return {
            "status": "unavailable",
            "week": next_week,
            "records": [],
            "error": str(exc),
        }


def _ensure_next_matchups(
    snapshot: dict[str, Any],
    client: SleeperClient,
    league_id: str,
    week: int,
) -> None:
    snapshot["next_matchups"] = _collect_next_matchups(client, league_id, week)


def _apply_player_context(
    snapshot: dict[str, Any], player_directory: dict[str, Any]
) -> None:
    """Retain the rookie marker needed by every publication tier."""
    for player_id, player in (snapshot.get("players") or {}).items():
        source = player_directory.get(str(player_id)) or {}
        player["years_exp"] = source.get("years_exp")


def _apply_context_scope(
    snapshot: dict[str, Any],
    shared: dict[str, Any],
    *,
    include_deep: bool,
) -> None:
    context = snapshot.setdefault("nfl_context", {})
    # Complete weekly player stats are intentionally retained for every
    # publication so Free Agent of the Week can consider genuinely unrostered
    # players rather than only players already present in the league snapshot.
    context["player_stats"] = dict(shared.get("player_stats") or {})
    if include_deep:
        context["snap_counts"] = dict(shared.get("snap_counts") or {})
        context["play_by_play"] = dict(shared.get("play_by_play") or {})
    else:
        context["snap_counts"] = {"status": "not_collected", "records": []}
        context["play_by_play"] = {"status": "not_collected", "records": []}


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
