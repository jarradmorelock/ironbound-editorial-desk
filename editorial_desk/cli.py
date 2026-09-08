from __future__ import annotations

import argparse
import os
from pathlib import Path

from .collector import collect_all
from .config import (
    ConfigurationError,
    load_leagues,
    load_publications,
    validate_publication_mappings,
)
from .emailer import (
    EmailDeliveryError,
    send_dossier_email,
    send_supplement_email,
)
from .period import PeriodDetectionError, detect_completed_period
from .supplement import generate_supplements


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

    email = subcommands.add_parser("email")
    email.add_argument("--week", type=int, required=True)
    email.add_argument("--output-dir", type=Path, required=True)

    subcommands.add_parser("completed-period")

    supplement = subcommands.add_parser("supplement")
    supplement.add_argument("--baseline-dir", type=Path, required=True)
    supplement.add_argument("--current-dir", type=Path, required=True)
    supplement.add_argument("--output-dir", type=Path, required=True)
    supplement.add_argument("--week", type=int, required=True)

    supplement_email = subcommands.add_parser("email-supplement")
    supplement_email.add_argument("--week", type=int, required=True)
    supplement_email.add_argument("--output-dir", type=Path, required=True)
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)

    if args.command == "completed-period":
        try:
            period = detect_completed_period()
        except PeriodDetectionError as exc:
            print(f"Period detection error: {exc}")
            return 1
        print(f"active={str(period['active']).lower()}")
        print(f"season={period['season']}")
        print(f"week={period['week']}")
        print(f"reason={period['reason']}")
        return 0

    if args.command == "supplement":
        generated = generate_supplements(
            args.baseline_dir,
            args.current_dir,
            args.output_dir,
            args.week,
        )
        print(f"Supplement comparison complete: {len(generated) // 2} updates")
        return 0

    if args.command in {"email", "email-supplement"}:
        if args.command == "email-supplement" and not list(
            args.output_dir.glob(f"*/week-{args.week:02d}/*/supplement.md")
        ):
            print("No newly captured information; no supplemental email sent")
            return 0
        sender = os.environ.get("IRONBOUND_GMAIL_ADDRESS", "").strip()
        app_password = os.environ.get("IRONBOUND_GMAIL_APP_PASSWORD", "")
        recipient = os.environ.get("IRONBOUND_EMAIL_RECIPIENT", "").strip() or sender
        if not sender or not app_password:
            print(
                "Email configuration error: IRONBOUND_GMAIL_ADDRESS and "
                "IRONBOUND_GMAIL_APP_PASSWORD are required"
            )
            return 2
        try:
            delivery = (
                send_dossier_email
                if args.command == "email"
                else send_supplement_email
            )
            attachment_count = delivery(
                args.output_dir,
                args.week,
                sender,
                app_password,
                recipient,
            )
        except EmailDeliveryError as exc:
            print(f"Email delivery error: {exc}")
            return 1
        print(
            f"Email delivered to {recipient} with "
            f"{attachment_count} "
            f"{'supplements' if args.command == 'email-supplement' else 'publication dossiers'}"
        )
        return 0

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
