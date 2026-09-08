from __future__ import annotations

from email.message import EmailMessage
import json
from pathlib import Path
import smtplib
from typing import Any


class EmailDeliveryError(RuntimeError):
    """Raised when a weekly email cannot be prepared or delivered."""


def build_dossier_email(
    output_root: Path,
    week: int,
    sender: str,
    recipient: str,
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
    message.set_content(
        "The weekly editorial research packets are attached.\n\n"
        + "\n".join(packet_lines)
        + "\n\nThese are research dossiers, not final publication copy. "
        "The data-only league is intentionally excluded.\n"
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
    return message


def send_dossier_email(
    output_root: Path,
    week: int,
    sender: str,
    app_password: str,
    recipient: str | None = None,
) -> int:
    recipient = recipient or sender
    message = build_dossier_email(output_root, week, sender, recipient)
    _deliver(message, sender, app_password)
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
