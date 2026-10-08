# Ranking Snapshot Carry-Forward Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve prior weekly rankings and carry them into a later research packet when the separate rankings handoff is absent.

**Architecture:** Persist each resolved weekly ranking as a Chronicle event keyed by league, season/week, and stable franchise identity. Resolve current external rankings first; otherwise use the latest earlier snapshot, strip stale movement/current-score claims, and label the packet with its carry-forward source week.

**Tech Stack:** Python 3, Chronicle JSONL events and queries, existing external-input dataclasses, pytest.

**Spec:** `docs/superpowers/specs/2026-10-07-global-research-packet-integrity.md`

## Global Constraints

- Use the current publication's external handoff when supplied.
- Carry forward only from the same publication/league and season.
- Key ranking rows by franchise identity; roster ID and names are supporting mapping fields.
- A carried rank has no current movement or current-week score unless newly supplied.
- Label ranking source and source week; if history is absent, preserve missing-ranking readiness.

## Review Focus

- Current external ranks must take precedence over carried history; test in Task 2.
- A carried snapshot must not claim movement or a new ranking score; test in Task 2.
- Never read a prior-season or another league's ranks; test in Task 1.
- Ranking gaps without any snapshot remain blocked/awaiting; test in Task 2.
- Repeat persistence must be idempotent and preserve source provenance; test in Task 1.

---

### Task 1: Store and query weekly ranking snapshots

**Files:**
- Modify: `editorial_desk/chronicle_events.py`
- Modify: `editorial_desk/chronicle_store.py`
- Modify: `editorial_desk/chronicle_queries.py`
- Create: `editorial_desk/ranking_history.py`
- Test: `tests/test_chronicle_queries.py`
- Test: `tests/test_ranking_history.py` (create)

**Interfaces:**
- Add `ChronicleQueries.power_ranking_snapshot(league_key: str, season: str, week: int) -> list[dict[str, Any]]`.
- Add `ChronicleQueries.latest_power_ranking_snapshot(league_key: str, season: str, before_week: int) -> dict[str, Any] | None`.
- Store events as `POWER_RANKING_WEEK_FINAL`, with rank rows in evidence and franchise identity in entities.

- [ ] **Step 1: Write failing tests** named `test_power_ranking_snapshot_isolated_by_league_season_week` and `test_latest_power_ranking_snapshot_ignores_future_weeks`. Assert stable franchise IDs and source metadata survive storage and queries.
- [ ] **Step 2: Run tests to verify the expected failures**

Run: `pytest tests/test_chronicle_queries.py::test_power_ranking_snapshot_isolated_by_league_season_week tests/test_chronicle_queries.py::test_latest_power_ranking_snapshot_ignores_future_weeks -q`
Expected: FAIL because Chronicle has no ranking event query.

- [ ] **Step 3: Implement event creation and queries** using the existing Chronicle event/store patterns. Ensure identical source rows are idempotent.
- [ ] **Step 4: Run focused query tests**

Run: `pytest tests/test_chronicle_queries.py tests/test_chronicle_store.py -q`
Expected: PASS.

- [ ] **Step 5: Commit** `feat: persist weekly editorial ranking snapshots`

### Task 2: Resolve and label current or carried rankings

**Files:**
- Modify: `.github/workflows/editorial-desk-dry-run.yml`
- Modify: `editorial_desk/cli.py`
- Modify: `editorial_desk/external_inputs.py`
- Modify: `editorial_desk/enriched_collector.py::collect_all`
- Modify: `editorial_desk/flagship_research.py`
- Modify: `editorial_desk/ranking_history.py`
- Test: `tests/test_external_inputs.py`
- Test: `tests/test_flagship_research.py`
- Test: `tests/test_ranking_history.py`

**Interfaces:**
- Add `resolve_power_ranking_input(current: ExternalEditorialInputs, prior_snapshot: dict[str, Any] | None, *, season: str, week: int) -> ExternalEditorialInputs`.
- Add `seed_from_prior_issue(packet_root: Path, *, season: str, week: int) -> dict[str, list[OfficialPowerRanking]]` to validate/extract same-publication ranking rows from the preceding issue artifact, keyed by publication key.
- Add optional `previous_issue_root: Path | None = None` and `persist_ranking_history: bool = False` to `enriched_collector.collect_all` and the `collect` CLI command; the workflow downloads the preceding issue artifact to this directory when available and enables persistence only for production.
- Preserve the `OfficialPowerRanking` shape; use `source_metadata` to report current versus carried-forward status and source week.

- [ ] **Step 1: Write failing tests** named `test_current_rankings_override_prior_snapshot`, `test_missing_current_rankings_carry_forward_without_movement`, `test_empty_chronicle_bootstraps_from_prior_issue_packet`, and `test_no_prior_ranking_keeps_missing_readiness`. Cover current rank precedence, no stale score/movement claim, same-publication prior-issue bootstrap, provenance text, and the existing blocked state when no source exists.
- [ ] **Step 2: Run tests to verify the expected failures**

Run: `pytest tests/test_ranking_history.py::test_current_rankings_override_prior_snapshot tests/test_ranking_history.py::test_missing_current_rankings_carry_forward_without_movement tests/test_ranking_history.py::test_empty_chronicle_bootstraps_from_prior_issue_packet tests/test_ranking_history.py::test_no_prior_ranking_keeps_missing_readiness -q`
Expected: FAIL because absent external rankings are not currently resolved from Chronicle history.

- [ ] **Step 3: Implement first-run bootstrap and ranking resolution.** Add `actions: read` permission and a workflow step that uses GitHub's artifact API to download the preceding week's editorial artifact to `previous-issue/`; pass it through `--previous-issue-dir`. `seed_from_prior_issue` returns rows only after validating publication key, season/week, and franchise identities. If Chronicle has no ranking history, use these rows for the same-publication fallback. Resolve current rankings before flagship packet construction, then persist seed/current ranking events only when `persist_ranking_history` is true. Preview may read the prior artifact but must not write Chronicle state. Mark carried rows with no movement/current score; add a plain-language packet label with the original source week. If no prior artifact is available, leave the ranking input missing.
- [ ] **Step 4: Persist the resolved current snapshot** after packet construction through `ChronicleStore`, recording current external data or carried-forward provenance for the current publication week.
- [ ] **Step 5: Run focused integration tests**

Run: `pytest tests/test_external_inputs.py tests/test_flagship_research.py tests/test_story_readiness.py -q`
Expected: PASS.

- [ ] **Step 6: Commit** `feat: carry forward prior research rankings`

### Task 3: Full verification

- [ ] **Step 1: Run the complete suite**

Run: `pytest -q`
Expected: PASS with no failures.

- [ ] **Step 2: Commit** only if integration verification required a follow-up fix.
