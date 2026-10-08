# Research Output ZIP Email Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Email the complete generated research packet for a week as one ZIP attachment instead of separate Markdown and image attachments.

**Architecture:** Build the archive from the current season/week publication directories under `output/primary`, preserve relative file paths, attach it in `build_dossier_email`, and retain the Actions artifact as the downloadable run copy. Monthly Chronicle backup remains a separately governed recovery attachment.

**Tech Stack:** Python 3 `zipfile`, `EmailMessage`, GitHub Actions, pytest.

**Spec:** `docs/superpowers/specs/2026-10-07-global-research-packet-integrity.md`

## Global Constraints

- Include all generated files for the requested season/week, including JSON, Markdown, images, and supporting files.
- Preserve each league directory and relative paths in the ZIP.
- Attach exactly one weekly research ZIP; do not attach per-league Markdown or image files separately.
- Keep the existing GitHub Actions artifact upload and monthly Chronicle receipt validation/handling.

## Review Focus

- Multiple leagues and nested publication assets must all be included; test in Task 1.
- Older weeks under the same output root must not leak into the requested ZIP; test in Task 1.
- Missing or empty publication directories must raise `EmailDeliveryError`; test in Task 1.
- Monthly Chronicle backup remains validated and attachable as before; test in Task 2.
- ZIP attachment must be named with season and week and use `application/zip`; test in Task 2.

---

### Task 1: Build a complete current-week research archive

**Files:**
- Modify: `editorial_desk/emailer.py`
- Test: `tests/test_emailer.py`

**Interfaces:**
- Add `_build_research_archive(output_root: Path, season: str, week: int) -> bytes` to `emailer.py`.
- Keep `build_dossier_email(output_root, week, sender, recipient, extra_attachments=(), chronicle_archive=None)` as the email builder.

- [ ] **Step 1: Write failing tests** named `test_research_archive_contains_all_current_week_files_once` and `test_research_archive_excludes_other_weeks`. Create multiple league folders with Markdown, JSON, image, and support files plus a separate older-week directory; inspect archive member names and bytes.
- [ ] **Step 2: Run tests to verify the expected failures**

Run: `pytest tests/test_emailer.py::test_research_archive_contains_all_current_week_files_once tests/test_emailer.py::test_research_archive_excludes_other_weeks -q`
Expected: FAIL because the email builder currently attaches generated reading Markdown and images separately and creates no complete research archive.

- [ ] **Step 3: Implement `_build_research_archive`** from the current season/week directories discovered from the dossier set. Preserve relative paths below `output_root`; include every file in those publication directories exactly once.
- [ ] **Step 4: Run archive tests**

Run: `pytest tests/test_emailer.py -q`
Expected: PASS for archive content and week isolation.

- [ ] **Step 5: Commit** `feat: archive weekly research outputs for email`

### Task 2: Attach the ZIP and retain existing recovery behavior

**Files:**
- Modify: `editorial_desk/emailer.py::build_dossier_email`
- Test: `tests/test_emailer.py`
- Verify: `.github/workflows/editorial-desk-dry-run.yml`

- [ ] **Step 1: Write failing tests** named `test_build_dossier_email_attaches_one_research_zip` and `test_build_dossier_email_preserves_monthly_chronicle_archive`. Assert research attachments contain one season/week ZIP, that it contains all generated files, and that an optional validated Chronicle recovery ZIP is still attached.
- [ ] **Step 2: Run tests to verify the expected failures**

Run: `pytest tests/test_emailer.py::test_build_dossier_email_attaches_one_research_zip tests/test_emailer.py::test_build_dossier_email_preserves_monthly_chronicle_archive -q`
Expected: FAIL because Markdown and PNG attachments are currently separate.

- [ ] **Step 3: Implement email attachment behavior** to attach the archive as `application/zip`, remove separate weekly Markdown and publication-asset attachments, and update the email body to identify the ZIP and included leagues. Keep monthly backup validation and its recovery note unchanged. Keep the workflow's complete artifact upload step unchanged.
- [ ] **Step 4: Run email and workflow integration tests**

Run: `pytest tests/test_emailer.py tests/test_workflow_integration.py -q`
Expected: PASS.

- [ ] **Step 5: Commit** `feat: email complete research output as zip`

### Task 3: Full verification

- [ ] **Step 1: Run the complete suite**

Run: `pytest -q`
Expected: PASS with no failures.

- [ ] **Step 2: Commit** only if integration verification required a follow-up fix.
