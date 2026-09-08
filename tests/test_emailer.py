import json

import pytest

from editorial_desk.emailer import (
    EmailDeliveryError,
    build_dossier_email,
    build_supplement_email,
    send_supplement_email,
)


def test_build_dossier_email_attaches_publication_packets_only(tmp_path):
    week_root = tmp_path / "2026" / "week-01"
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
