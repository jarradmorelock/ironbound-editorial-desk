from __future__ import annotations

from datetime import datetime, timezone
from email.message import EmailMessage
import json
from pathlib import Path
import smtplib
from typing import Any

from .chronicle_backup import (
    ChronicleBackupError,
    validate_chronicle_backup,
    write_monthly_backup_receipt,
)


class EmailDeliveryError(RuntimeError):
    """Raised when a weekly email cannot be prepared or delivered."""


def build_dossier_email(
    output_root: Path,
    week: int,
    sender: str,
    recipient: str,
    extra_attachments: tuple[Path, ...] = (),
    chronicle_archive: Path | None = None,
) -> EmailMessage:
    dossier_paths = sorted(output_root.glob(f"*/week-{week:02d}/*/dossier.md"))
    if not dossier_paths:
        raise EmailDeliveryError(
            f"No publication dossiers found for week {week} under {output_root}"
        )

    packets: list[tuple[Path, dict[str, Any]]] = []
    seasons: set[str] = set()
    for markdown_path in dossier_paths:
        dossier_path = markdown_path.with_suffix(".json")
        try:
            dossier = json.loads(dossier_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            raise EmailDeliveryError(
                f"Cannot read the matching dossier data for {markdown_path}"
            ) from exc
        packets.append((markdown_path, dossier))
        seasons.add(str(dossier.get("season") or "unknown"))

    if len(seasons) != 1:
        raise EmailDeliveryError("Weekly email contains more than one season")
    season = seasons.pop()

    attachments = _attachment_paths(extra_attachments, chronicle_archive)
    archive_paths = tuple(path for path in attachments if path.suffix.lower() == ".zip")
    for archive_path in archive_paths:
        validation = validate_chronicle_backup(archive_path)
        if not validation.valid:
            raise EmailDeliveryError(
                "Chronicle archive failed validation: "
                + "; ".join(validation.errors)
            )

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = (
        f"Ironbound Editorial Desk — {season} Week {week} research packets"
    )

    packet_lines = []
    for _, dossier in packets:
        league = dossier.get("league") or {}
        packet_lines.append(
            f"- {league.get('publication')}: {league.get('configured_name')}"
        )
    archive_note = (
        "\nA validated Chronicle archive is attached as this month's recovery copy.\n"
        if archive_paths
        else ""
    )
    message.set_content(
        "The weekly editorial research packets are attached.\n\n"
        + "\n".join(packet_lines)
        + "\n\nThese are research dossiers, not final publication copy. "
        "The data-only league is intentionally excluded.\n"
        + archive_note
    )

    for markdown_path, dossier in packets:
        league = dossier.get("league") or {}
        league_key = str(league.get("league_key") or markdown_path.parent.name)
        filename = f"{league_key}-week-{week:02d}.md"
        message.add_attachment(
            markdown_path.read_text(encoding="utf-8"),
            subtype="markdown",
            filename=filename,
        )
    for path in attachments:
        if path.suffix.lower() == ".zip":
            maintype, subtype = "application", "zip"
        else:
            maintype, subtype = "application", "octet-stream"
        message.add_attachment(
            path.read_bytes(),
            maintype=maintype,
            subtype=subtype,
            filename=path.name,
        )
    return message


def send_dossier_email(
    output_root: Path,
    week: int,
    sender: str,
    app_password: str,
    recipient: str | None = None,
    extra_attachments: tuple[Path, ...] = (),
    chronicle_archive: Path | None = None,
    monthly_receipt_root: Path | None = None,
    chronicle_revision: str | None = None,
    accepted_at: datetime | None = None,
) -> int:
    recipient = recipient or sender
    attachments = _attachment_paths(extra_attachments, chronicle_archive)
    receipt_requested = monthly_receipt_root is not None or chronicle_revision is not None
    receipt_archive: Path | None = None
    if receipt_requested:
        if monthly_receipt_root is None or not str(chronicle_revision or "").strip():
            raise EmailDeliveryError(
                "Monthly Chronicle receipt requires receipt root and Chronicle revision"
            )
        zip_paths = tuple(path for path in attachments if path.suffix.lower() == ".zip")
        if len(zip_paths) != 1:
            raise EmailDeliveryError(
                "Monthly Chronicle receipt requires exactly one ZIP attachment"
            )
        receipt_archive = zip_paths[0]
        validation = validate_chronicle_backup(
            receipt_archive, expected_revision=str(chronicle_revision)
        )
        if not validation.valid:
            raise EmailDeliveryError(
                "Chronicle archive failed validation: "
                + "; ".join(validation.errors)
            )
        if accepted_at is not None and (
            accepted_at.tzinfo is None or accepted_at.utcoffset() is None
        ):
            raise EmailDeliveryError("SMTP acceptance time must be timezone-aware")

    message = build_dossier_email(
        output_root,
        week,
        sender,
        recipient,
        extra_attachments=attachments,
    )
    _deliver(message, sender, app_password)

    if receipt_requested and receipt_archive is not None:
        receipt_time = accepted_at or datetime.now(timezone.utc)
        try:
            write_monthly_backup_receipt(
                Path(monthly_receipt_root),
                accepted_at=receipt_time,
                chronicle_revision=str(chronicle_revision),
                archive_path=receipt_archive,
            )
        except (ChronicleBackupError, OSError, ValueError) as exc:
            # SMTP has already accepted the message. Raising here intentionally
            # keeps the missing receipt visible; a retry may duplicate the mail.
            raise EmailDeliveryError(
                "Email was accepted but monthly Chronicle receipt could not be persisted: "
                f"{exc}"
            ) from exc
    return sum(1 for _ in message.iter_attachments())


def build_supplement_email(
    output_root: Path,
    week: int,
    sender: str,
    recipient: str,
) -> EmailMessage:
    supplement_paths = sorted(
        output_root.glob(f"*/week-{week:02d}/*/supplement.md")
    )
    if not supplement_paths:
        raise EmailDeliveryError(
            f"No supplemental updates found for week {week} under {output_root}"
        )

    packets: list[tuple[Path, dict[str, Any]]] = []
    seasons: set[str] = set()
    for markdown_path in supplement_paths:
        metadata_path = markdown_path.with_suffix(".json")
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            raise EmailDeliveryError(
                f"Cannot read the matching supplement data for {markdown_path}"
            ) from exc
        packets.append((markdown_path, metadata))
        seasons.add(str(metadata.get("season") or "unknown"))

    if len(seasons) != 1:
        raise EmailDeliveryError("Supplemental email contains more than one season")
    season = seasons.pop()

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = (
        f"Ironbound Editorial Desk — {season} Week {week} supplemental updates"
    )
    packet_lines = []
    for _, metadata in packets:
        league = metadata.get("league") or {}
        packet_lines.append(
            f"- {league.get('publication')}: {league.get('configured_name')}"
        )
    message.set_content(
        "The Wednesday backup found information that was not available in "
        "Tuesday night's research packets. Only the new material is attached.\n\n"
        + "\n".join(packet_lines)
        + "\n\nIf a publication is not listed, its Tuesday packet did not need an update.\n"
    )

    for markdown_path, metadata in packets:
        league = metadata.get("league") or {}
        league_key = str(league.get("league_key") or markdown_path.parent.name)
        filename = f"{league_key}-week-{week:02d}-supplement.md"
        message.add_attachment(
            markdown_path.read_text(encoding="utf-8"),
            subtype="markdown",
            filename=filename,
        )
    return message


def send_supplement_email(
    output_root: Path,
    week: int,
    sender: str,
    app_password: str,
    recipient: str | None = None,
) -> int:
    supplement_paths = list(
        output_root.glob(f"*/week-{week:02d}/*/supplement.md")
    )
    if not supplement_paths:
        return 0
    recipient = recipient or sender
    message = build_supplement_email(output_root, week, sender, recipient)
    _deliver(message, sender, app_password)
    return sum(1 for _ in message.iter_attachments())


def _attachment_paths(
    extra_attachments: tuple[Path, ...],
    chronicle_archive: Path | None,
) -> tuple[Path, ...]:
    paths = [Path(path) for path in extra_attachments]
    if chronicle_archive is not None:
        archive = Path(chronicle_archive)
        if archive not in paths:
            paths.append(archive)
    for path in paths:
        if not path.is_file():
            raise EmailDeliveryError(f"Attachment not found: {path}")
    return tuple(paths)


def _deliver(message: EmailMessage, sender: str, app_password: str) -> None:
    password = app_password.replace(" ", "")
    if not password:
        raise EmailDeliveryError("The Gmail app password is empty")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
            smtp.login(sender, password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailDeliveryError(f"Gmail delivery failed: {exc}") from exc
