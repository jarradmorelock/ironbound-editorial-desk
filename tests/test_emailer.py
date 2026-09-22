import json

import pytest

from editorial_desk.chronicle_backup import create_chronicle_backup
from editorial_desk.cli import parser
from editorial_desk.emailer import (
    EmailDeliveryError,
    build_divisional_mvp_email,
    build_dossier_email,
    build_supplement_email,
    send_supplement_email,
)


def _weekly_packet(tmp_path, week=1):
    week_root = tmp_path / "2026" / f"week-{week:02d}"
    publication_root = week_root / "ironbound"
    publication_root.mkdir(parents=True)
    (publication_root / "dossier.md").write_text("# Weekly packet\n", encoding="utf-8")
    (publication_root / "dossier.json").write_text(
        json.dumps(
            {
                "season": "2026",
                "league": {
                    "league_key": "ironbound",
                    "configured_name": "Ironbound Sixteen",
                    "publication": "The Ironbound Weekly",
                },
            }
        ),
        encoding="utf-8",
    )
    return publication_root


def test_build_dossier_email_attaches_publication_packets_only(tmp_path):
    week_root = tmp_path / "2026" / "week-01"
    publication_root = _weekly_packet(tmp_path)
    data_only_root = week_root / "dont_tell_my_wife"
    data_only_root.mkdir()
    (data_only_root / "analysis.json").write_text("{}\n", encoding="utf-8")

    message = build_dossier_email(
        tmp_path,
        1,
        "desk@example.com",
        "reader@example.com",
    )

    assert message["To"] == "reader@example.com"
    assert message["Subject"] == (
        "Ironbound Editorial Desk — 2026 Week 1 research packets"
    )
    attachments = list(message.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_filename() == "ironbound-week-01.md"


def test_build_dossier_email_can_attach_validated_monthly_chronicle_archive(tmp_path):
    _weekly_packet(tmp_path)
    chronicle = tmp_path / "chronicle"
    (chronicle / "registry").mkdir(parents=True)
    (chronicle / "registry" / "identity.json").write_text("{}\n", encoding="utf-8")
    archive = create_chronicle_backup(
        chronicle,
        tmp_path / "chronicle-backup.zip",
        chronicle_revision="chronicle-sha-123",
    )

    message = build_dossier_email(
        tmp_path,
        1,
        "desk@example.com",
        "reader@example.com",
        chronicle_archive=archive,
    )

    attachments = list(message.iter_attachments())
    assert [part.get_filename() for part in attachments] == [
        "ironbound-week-01.md",
        "chronicle-backup.zip",
    ]
    assert attachments[-1].get_content_type() == "application/zip"
    assert "Chronicle archive" in message.get_body().get_content()


def test_build_dossier_email_rejects_invalid_chronicle_archive(tmp_path):
    _weekly_packet(tmp_path)
    archive = tmp_path / "bad.zip"
    archive.write_bytes(b"not a zip")

    with pytest.raises(EmailDeliveryError, match="Chronicle archive failed validation"):
        build_dossier_email(
            tmp_path,
            1,
            "desk@example.com",
            "reader@example.com",
            chronicle_archive=archive,
        )


def test_email_cli_accepts_optional_chronicle_archive():
    args = parser().parse_args(
        [
            "email",
            "--week",
            "7",
            "--output-dir",
            "output",
            "--chronicle-archive",
            "backups/chronicle.zip",
        ]
    )
    assert str(args.chronicle_archive) == "backups/chronicle.zip"


def test_build_dossier_email_requires_publication_packets(tmp_path):
    with pytest.raises(EmailDeliveryError, match="No publication dossiers"):
        build_dossier_email(
            tmp_path,
            1,
            "desk@example.com",
            "reader@example.com",
        )


def test_build_supplement_email_identifies_delta_only_delivery(tmp_path):
    publication_root = tmp_path / "2026" / "week-01" / "unbound"
    publication_root.mkdir(parents=True)
    (publication_root / "supplement.md").write_text(
        "# Newly captured material\n", encoding="utf-8"
    )
    (publication_root / "supplement.json").write_text(
        json.dumps(
            {
                "season": "2026",
                "league": {
                    "league_key": "unbound",
                    "configured_name": "Free Ironbound Sixteen",
                    "publication": "Unbound Weekly",
                },
            }
        ),
        encoding="utf-8",
    )

    message = build_supplement_email(
        tmp_path, 1, "desk@example.com", "reader@example.com"
    )

    assert message["Subject"] == (
        "Ironbound Editorial Desk — 2026 Week 1 supplemental updates"
    )
    assert "Only the new material is attached" in message.get_body().get_content()
    attachments = list(message.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_filename() == "unbound-week-01-supplement.md"


def test_supplement_delivery_sends_nothing_without_updates(tmp_path):
    assert (
        send_supplement_email(
            tmp_path,
            1,
            "desk@example.com",
            "unused-password",
            "reader@example.com",
        )
        == 0
    )


def _mvp_dossier(tmp_path, league_key, league_name, week=1, base_points=30.0):
    root = tmp_path / "2026" / f"week-{week:02d}" / league_key
    root.mkdir(parents=True, exist_ok=True)
    mvps = []
    for division_id, division_name in enumerate(
        ("Hammer", "Anvil", "Crucible", "Forge"), start=1
    ):
        points = base_points + division_id
        mvps.append(
            {
                "roster_id": division_id,
                "team": f"{league_name} Team {division_id}",
                "division_id": str(division_id),
                "division_name": division_name,
                "player_id": f"{league_key}-p{division_id}",
                "player": f"Player {division_id}",
                "position": "WR",
                "points": points,
                "status": "STARTED",
                "gold_foil": division_id == 4,
            }
        )
    (root / "dossier.json").write_text(
        json.dumps(
            {
                "season": "2026",
                "league": {
                    "league_key": league_key,
                    "configured_name": league_name,
                    "publication": "Weekly",
                },
                "weekly_features": {"divisional_mvp_nominees": mvps},
            }
        ),
        encoding="utf-8",
    )
    (root / "dossier.md").write_text("# dossier\n", encoding="utf-8")
    return root


def test_build_divisional_mvp_email_contains_exactly_eight_card_candidates(tmp_path):
    _mvp_dossier(tmp_path, "ironbound_sixteen", "Ironbound Sixteen", base_points=30)
    _mvp_dossier(
        tmp_path,
        "free_ironbound_sixteen",
        "Free Ironbound Sixteen",
        base_points=40,
    )

    message = build_divisional_mvp_email(
        tmp_path, 1, "desk@example.com", "reader@example.com"
    )

    assert message["Subject"] == "Ironbound Card Shop — 2026 Week 1 divisional MVPs"
    body = message.get_body().get_content()
    assert body.count("GOLD FOIL") == 2
    assert "Hammer" in body
    assert "Forge" in body
    attachments = list(message.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_filename() == "divisional-mvps-week-01.json"
    payload = json.loads(attachments[0].get_content())
    assert len(payload["leagues"]) == 2
    assert sum(len(league["mvps"]) for league in payload["leagues"]) == 8
    assert all(
        sum(1 for row in league["mvps"] if row["gold_foil"]) == 1
        for league in payload["leagues"]
    )


def test_divisional_mvp_email_rejects_nonstarter_or_wrong_gold(tmp_path):
    _mvp_dossier(tmp_path, "ironbound_sixteen", "Ironbound Sixteen", base_points=30)
    root = _mvp_dossier(
        tmp_path,
        "free_ironbound_sixteen",
        "Free Ironbound Sixteen",
        base_points=40,
    )
    path = root / "dossier.json"
    dossier = json.loads(path.read_text(encoding="utf-8"))
    dossier["weekly_features"]["divisional_mvp_nominees"][0]["status"] = "BENCH"
    path.write_text(json.dumps(dossier), encoding="utf-8")

    with pytest.raises(EmailDeliveryError, match="submitted starters"):
        build_divisional_mvp_email(
            tmp_path, 1, "desk@example.com", "reader@example.com"
        )


def test_divisional_mvp_email_cli_is_available():
    args = parser().parse_args(
        [
            "email-divisional-mvps",
            "--week",
            "2",
            "--output-dir",
            "output",
        ]
    )
    assert args.command == "email-divisional-mvps"
    assert args.week == 2
