from __future__ import annotations

import argparse
from pathlib import Path

from .collector import collect_all
from .config import ConfigurationError, load_leagues


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Ironbound weekly editorial desk")
    subcommands = command.add_subparsers(dest="command", required=True)

    validate = subcommands.add_parser("validate-config")
    validate.add_argument("--config", type=Path, required=True)

    collect = subcommands.add_parser("collect")
    collect.add_argument("--config", type=Path, required=True)
    collect.add_argument("--week", type=int, required=True)
    collect.add_argument("--output-dir", type=Path, default=Path("output/dry-run"))
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        leagues = load_leagues(args.config)
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}")
        return 2

    if args.command == "validate-config":
        print(f"Configuration valid: {len(leagues)} enabled leagues")
        for league in leagues:
            print(f"- {league.name}: {league.publication} ({league.tier})")
        return 0

    if args.week < 1 or args.week > 18:
        print("Week must be between 1 and 18")
        return 2
    generated = collect_all(leagues, args.week, args.output_dir)
    print(f"Dry run complete: {len(generated)} files generated")
    return 0
