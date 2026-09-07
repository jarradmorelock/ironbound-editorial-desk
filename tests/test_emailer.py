import json

import pytest

from editorial_desk.emailer import EmailDeliveryError, build_dossier_email


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
