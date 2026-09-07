from __future__ import annotations

import argparse
from pathlib import Path

from .collector import collect_all
from .config import (
    ConfigurationError,
    load_leagues,
    load_publications,
    validate_publication_mappings,
)


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Ironbound weekly editorial desk")
    subcommands = command.add_subparsers(dest="command", required=True)

    validate = subcommands.add_parser("validate-config")
    validate.add_argument("--config", type=Path, required=True)
    validate.add_argument(
        "--publications",
        type=Path,
        default=Path("config/publications.json"),
    )

    collect = subcommands.add_parser("collect")
    collect.add_argument("--config", type=Path, required=True)
    collect.add_argument(
        "--publications",
        type=Path,
        default=Path("config/publications.json"),
    )
    collect.add_argument("--week", type=int, required=True)
    collect.add_argument("--output-dir", type=Path, default=Path("output/dry-run"))
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        leagues = load_leagues(args.config)
        publications = load_publications(args.publications)
        validate_publication_mappings(leagues, publications)
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}")
        return 2

    if args.command == "validate-config":
        print(f"Configuration valid: {len(leagues)} enabled leagues")
        for league in leagues:
            if league.publication_enabled:
                print(f"- {league.name}: {league.publication} ({league.tier})")
            else:
                print(f"- {league.name}: data collection only (no publication)")
        return 0

    if args.week < 1 or args.week > 18:
        print("Week must be between 1 and 18")
        return 2
    generated = collect_all(
        leagues,
        args.week,
        args.output_dir,
        publications=publications,
    )
    print(f"Dry run complete: {len(generated)} files generated")
    return 0
