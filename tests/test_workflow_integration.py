from pathlib import Path

from editorial_desk.cli import parser


ROOT = Path(__file__).resolve().parents[1]
WEEKLY = ROOT / ".github" / "workflows" / "editorial-desk-dry-run.yml"
CHRONICLE = ROOT / ".github" / "workflows" / "editorial-desk-chronicle.yml"
README = ROOT / "README.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _assert_order(text: str, *needles: str) -> None:
    positions = [text.index(needle) for needle in needles]
    assert positions == sorted(positions), list(zip(needles, positions))


def test_both_chronicle_writer_workflows_share_serialized_concurrency_group():
    for path in (WEEKLY, CHRONICLE):
        text = _text(path)
        assert "group: editorial-chronicle-writer" in text
        assert "cancel-in-progress: false" in text


def test_tuesday_workflow_pins_chronicle_before_editorial_collection_and_delivery():
    text = _text(WEEKLY)
    assert "contents: write" in text
    assert "path: app" in text
    assert "ref: chronicle-data" in text
    assert "path: chronicle-data" in text
    assert "--finalize-matchups" in text
    assert "--chronicle-root ../chronicle-data" in text
    assert "--chronicle-revision \"${{ steps.chronicle_sha.outputs.sha }}\"" in text
    assert "--monthly-receipt-root ../chronicle-data" in text
    assert "--external-inputs-dir editorial-inputs" in text
    assert "git add" in text and "backup_receipts" in text

    _assert_order(
        text,
        "Run tests",
        "Determine this run's job and completed week",
        "Finalize completed week into Chronicle",
        "Materialize finalized Chronicle history",
        "Commit finalized Chronicle revision",
        "Capture pinned Chronicle SHA",
        "Collect complete weekly dossiers",
        "Build monthly Chronicle archive when due",
        "Email complete publication dossiers",
        "Save Tuesday packet as Wednesday baseline",
    )


def test_tuesday_baseline_records_pinned_sha_and_event_cutoff():
    text = _text(WEEKLY)
    assert "chronicle-baseline.json" in text
    assert '"chronicle_sha"' in text
    assert '"baseline_time"' in text
    assert "steps.chronicle_sha.outputs.sha" in text


def test_wednesday_updates_chronicle_then_uses_ledger_since_tuesday_baseline():
    text = _text(WEEKLY)
    assert "Collect Wednesday Chronicle pulse" in text
    assert "Commit Wednesday Chronicle changes" in text
    assert "Read Tuesday Chronicle baseline" in text
    assert "--chronicle-root ../chronicle-data" in text
    assert "--baseline-time" in text
    assert "refusing to send a duplicate full packet" in text
    _assert_order(
        text,
        "Restore Tuesday packet for Wednesday comparison",
        "Collect Wednesday Chronicle pulse",
        "Commit Wednesday Chronicle changes",
        "Read Tuesday Chronicle baseline",
        "Collect Wednesday comparison",
        "Build delta-only Wednesday supplements",
        "Email only newly captured Wednesday material",
    )


def test_diagnostic_pruning_occurs_after_monthly_backup_decision():
    text = _text(WEEKLY)
    assert "chronicle-prune-diagnostics" in text
    assert text.index("Build monthly Chronicle archive when due") < text.index(
        "Prune expired Chronicle diagnostics"
    )


def test_cli_supports_backup_due_build_receipt_email_and_ledger_supplement():
    due = parser().parse_args(
        ["chronicle-monthly-backup-due", "--chronicle-root", "chronicle-data"]
    )
    assert due.chronicle_root == Path("chronicle-data")

    backup = parser().parse_args(
        [
            "chronicle-backup",
            "--chronicle-root",
            "chronicle-data",
            "--output",
            "backup.zip",
            "--chronicle-revision",
            "abc123",
        ]
    )
    assert backup.output == Path("backup.zip")
    assert backup.chronicle_revision == "abc123"

    email = parser().parse_args(
        [
            "email",
            "--week",
            "7",
            "--output-dir",
            "output",
            "--chronicle-archive",
            "backup.zip",
            "--monthly-receipt-root",
            "chronicle-data",
            "--chronicle-revision",
            "abc123",
        ]
    )
    assert email.monthly_receipt_root == Path("chronicle-data")
    assert email.chronicle_revision == "abc123"

    supplement = parser().parse_args(
        [
            "supplement",
            "--baseline-dir",
            "baseline",
            "--current-dir",
            "current",
            "--output-dir",
            "supplements",
            "--week",
            "7",
            "--chronicle-root",
            "chronicle-data",
            "--baseline-time",
            "2026-09-15T22:00:00+00:00",
        ]
    )
    assert supplement.chronicle_root == Path("chronicle-data")
    assert supplement.baseline_time == "2026-09-15T22:00:00+00:00"


def test_readme_documents_story_desk_manual_inputs_without_owning_rankings_workflow():
    text = _text(README).casefold()
    assert "story desk" in text
    assert "external-inputs-dir" in text
    assert "power rankings" in text
    assert "manual" in text or "user-supplied" in text
    assert "does not fetch" in text or "does not own" in text or "separate workflow" in text
