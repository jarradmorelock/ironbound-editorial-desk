from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path

from .chronicle_backfill import run_backfill, run_materialize
from .chronicle_backup import (
    ChronicleBackupError,
    create_chronicle_backup,
    monthly_archive_due,
)
from .chronicle_collect import collect_pulse
from .chronicle_store import ChronicleStore
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
from .enriched_collector import collect_all
from .period import PeriodDetectionError, detect_completed_period
from .retention import prune_diagnostics
from .sleeper import SleeperClient
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
    collect.add_argument("--chronicle-root", type=Path)
    collect.add_argument("--chronicle-revision")
    collect.add_argument("--external-inputs-dir", type=Path)

    chronicle = subcommands.add_parser("chronicle-collect")
    chronicle.add_argument("--config", type=Path, required=True)
    chronicle.add_argument("--week", type=int, required=True)
    chronicle.add_argument("--chronicle-root", type=Path, required=True)
    chronicle.add_argument("--finalize-matchups", action="store_true")

    backfill = subcommands.add_parser("chronicle-backfill")
    backfill.add_argument("--config", type=Path, required=True)
    backfill.add_argument("--chronicle-root", type=Path, required=True)

    materialize = subcommands.add_parser("chronicle-materialize")
    materialize.add_argument("--chronicle-root", type=Path, required=True)

    identity_report = subcommands.add_parser("chronicle-identity-report")
    identity_report.add_argument("--chronicle-root", type=Path, required=True)

    prune = subcommands.add_parser("chronicle-prune-diagnostics")
    prune.add_argument("--chronicle-root", type=Path, required=True)
    prune.add_argument("--retention-days", type=int, default=30)

    monthly_due = subcommands.add_parser("chronicle-monthly-backup-due")
    monthly_due.add_argument("--chronicle-root", type=Path, required=True)

    backup = subcommands.add_parser("chronicle-backup")
    backup.add_argument("--chronicle-root", type=Path, required=True)
    backup.add_argument("--output", type=Path, required=True)
    backup.add_argument("--chronicle-revision", required=True)

    email = subcommands.add_parser("email")
    email.add_argument("--week", type=int, required=True)
    email.add_argument("--output-dir", type=Path, required=True)
    email.add_argument("--chronicle-archive", type=Path)
    email.add_argument("--monthly-receipt-root", type=Path)
    email.add_argument("--chronicle-revision")

    subcommands.add_parser("completed-period")

    supplement = subcommands.add_parser("supplement")
    supplement.add_argument("--baseline-dir", type=Path, required=True)
    supplement.add_argument("--current-dir", type=Path, required=True)
    supplement.add_argument("--output-dir", type=Path, required=True)
    supplement.add_argument("--week", type=int, required=True)
    supplement.add_argument("--chronicle-root", type=Path)
    supplement.add_argument("--baseline-time")

    supplement_email = subcommands.add_parser("email-supplement")
    supplement_email.add_argument("--week", type=int, required=True)
    supplement_email.add_argument("--output-dir", type=Path, required=True)
    return command


def _print_ambiguities(rows) -> None:
    for row in rows:
        candidates = ", ".join(row.candidate_franchise_keys) or "none"
        print(
            "UNRESOLVED "
            f"league={row.league_key} season={row.season} roster={row.roster_id} "
            f"owner={row.owner_id or 'none'} candidates={candidates} "
            f"reason={row.reason}"
        )


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

    if args.command == "chronicle-monthly-backup-due":
        due = monthly_archive_due(
            args.chronicle_root,
            datetime.now(timezone.utc),
        )
        print(f"due={str(due).lower()}")
        return 0

    if args.command == "chronicle-backup":
        try:
            archive = create_chronicle_backup(
                args.chronicle_root,
                args.output,
                chronicle_revision=args.chronicle_revision,
            )
        except (ChronicleBackupError, OSError, ValueError) as exc:
            print(f"Chronicle backup error: {exc}")
            return 1
        print(f"archive={archive}")
        return 0

    if args.command == "chronicle-prune-diagnostics":
        try:
            result = prune_diagnostics(
                args.chronicle_root,
                datetime.now(timezone.utc),
                retention_days=args.retention_days,
            )
        except ValueError as exc:
            print(f"Retention error: {exc}")
            return 2
        print(
            "Chronicle diagnostics pruned: "
            f"{len(result.removed)} removed, "
            f"{len(result.kept)} kept, "
            f"{len(result.skipped_unparseable)} skipped as unparseable"
        )
        return 0

    if args.command == "supplement":
        generated = generate_supplements(
            args.baseline_dir,
            args.current_dir,
            args.output_dir,
            args.week,
            chronicle_root=args.chronicle_root,
            baseline_time=args.baseline_time,
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
            if args.command == "email":
                attachment_count = send_dossier_email(
                    args.output_dir,
                    args.week,
                    sender,
                    app_password,
                    recipient,
                    chronicle_archive=args.chronicle_archive,
                    monthly_receipt_root=args.monthly_receipt_root,
                    chronicle_revision=args.chronicle_revision,
                )
            else:
                attachment_count = send_supplement_email(
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

    if args.command == "chronicle-materialize":
        result = run_materialize(ChronicleStore(args.chronicle_root))
        _print_ambiguities(result.unresolved_ambiguities)
        print(
            "Chronicle materialization complete: "
            f"{result.record_events_added} record event(s) added, "
            f"{len(result.failed_leagues)} league failure(s)"
        )
        return 1 if result.failed_leagues or result.unresolved_ambiguities else 0

    if args.command == "chronicle-identity-report":
        registry = ChronicleStore(args.chronicle_root).read_identity_registry()
        rows = registry.unresolved_ambiguities()
        if not rows:
            print("Chronicle identity report: no unresolved ambiguities")
            return 0
        _print_ambiguities(rows)
        print(f"Chronicle identity report: {len(rows)} unresolved mapping(s)")
        return 1

    try:
        leagues = load_leagues(args.config)
        publications = None
        if args.command not in {"chronicle-collect", "chronicle-backfill"}:
            publications = load_publications(
                getattr(args, "publications", Path("config/publications.json"))
            )
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

    if args.command == "chronicle-backfill":
        result = run_backfill(
            leagues,
            SleeperClient(),
            ChronicleStore(args.chronicle_root),
        )
        _print_ambiguities(result.unresolved_ambiguities)
        for warning in result.warnings:
            print(f"WARNING {warning}")
        print(
            "Chronicle backfill complete: "
            f"{result.added_events} added, {result.skipped_events} skipped, "
            f"{len(result.failed_leagues)} league failure(s), "
            f"{len(result.unresolved_ambiguities)} unresolved mapping(s)"
        )
        return 1 if result.failed_leagues or result.unresolved_ambiguities else 0

    if args.week < 1 or args.week > 18:
        print("Week must be between 1 and 18")
        return 2

    if args.command == "chronicle-collect":
        manifest = collect_pulse(
            leagues,
            SleeperClient(),
            ChronicleStore(args.chronicle_root),
            args.week,
            datetime.now(timezone.utc).isoformat(),
            finalize_matchups=args.finalize_matchups,
        )
        failed = [
            key
            for key, row in manifest["leagues"].items()
            if row["status"] != "fresh"
        ]
        print(
            f"Chronicle collection complete: {manifest['event_counts']['added']} added, "
            f"{manifest['event_counts']['skipped']} skipped, {len(failed)} league failure(s)"
        )
        return 1 if leagues and len(failed) == len(leagues) else 0

    generated = collect_all(
        leagues,
        args.week,
        args.output_dir,
        publications=publications or {},
        chronicle_root=args.chronicle_root,
        external_inputs_dir=args.external_inputs_dir,
        chronicle_revision=args.chronicle_revision,
    )
    print(f"Dry run complete: {len(generated)} files generated")
    return 0
