# Saturday Offense and IDP Board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Include the existing Starter Offense / IDP Board work in the global research-packet fix and keep it required for Saturday Standard.

**Architecture:** Apply the user's saved four-file diff to the isolated current-main branch, verify its test first, then carry its feature calculation and publication contract through unchanged unless current-main integration requires a small adjustment.

**Tech Stack:** Python 3, publication JSON configuration, Sleeper matchup data, pytest.

**Spec:** `docs/superpowers/specs/2026-10-07-global-research-packet-integrity.md`

## Global Constraints

- Preserve current roster composition counts in `offense_defense_splits`.
- Split starters by the existing offense and IDP position sets.
- Use Sleeper's weekly `players_points` values and report starter totals and each group's top scorer.
- Register the feature as required for Saturday Standard.
- Leave the original dirty checkout untouched; apply only the saved four-file patch to the isolated branch.

## Review Focus

- Empty offense or defense starter groups return no MVP and a zero total; test in Task 1.
- Players with non-offense/non-IDP positions do not enter either total; test in Task 1.
- Missing matchup data retains existing roster-composition output without inventing starter totals; test in Task 1.
- The publication contract requires the feature; test in Task 1.
- All four user-provided modifications are represented in the implementation diff; verify in Task 1.

---

### Task 1: Integrate and verify the saved feature change

**Files:**
- Modify: `config/publications.json`
- Modify: `editorial_desk/preseason_features.py::offense_defense_splits`
- Test: `tests/test_preseason_features.py`
- Test: `tests/test_publication_contracts.py`

**Interfaces:**
- Keep `offense_defense_splits(snapshot: dict[str, Any]) -> FeatureResult`.
- Preserve existing fields and add `starter_offense_points`, `starter_defense_points`, `starter_offense_mvp`, `starter_defense_mvp`, and `starter_split_source` when matchup data exists.

- [ ] **Step 1: Apply only the test hunks from `/private/tmp/starter-offense-idp.patch`** and run `test_offense_defense_split_adds_starter_totals_and_mvps_from_matchups` and `test_saturday_standard_keeps_divisions_and_idp_first_class` to confirm the expected failures.
- [ ] **Step 2: Apply the production/config hunks from the saved patch** and preserve the current-main surrounding changes.
- [ ] **Step 3: Run focused tests**

Run: `pytest tests/test_preseason_features.py tests/test_publication_contracts.py -q`
Expected: PASS.

- [ ] **Step 4: Review the diff** against `/private/tmp/starter-offense-idp.patch`; verify the four intended files changed and no user changes were dropped.
- [ ] **Step 5: Commit** `feat: add saturday starter offense and idp board`

### Task 2: Full verification

- [ ] **Step 1: Run the complete suite**

Run: `pytest -q`
Expected: PASS with no failures.

- [ ] **Step 2: Commit** only if integration verification required a follow-up fix.
