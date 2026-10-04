# Cumulative Player History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Week 3 cumulative player and rookie boards reproducible from verified player-week evidence, including explicit zero scores and as-of acquisition exclusions.

**Architecture:** Extend the existing Chronicle and canonical evidence paths instead of adding a parallel ledger. Finalized matchup rows will emit player-week facts with explicit score and membership states; the canonical resolver will reconcile Sleeper and Chronicle evidence; the flagship board builder will aggregate only eligible observed or certified-zero facts and will surface unresolved identifiers in readiness output.

**Tech Stack:** Python 3, dataclasses/dictionaries, JSONL Chronicle events, pytest, existing GitHub Actions preview workflow.

**Spec:** `docs/superpowers/specs/2026-10-04-cumulative-player-history-design.md`

## Global Constraints

- Do not infer a zero from a missing row.
- Do not relax readiness to allow unknown player-weeks.
- Do not change fantasy scoring rules or editorial ranking choices.
- Do not merge PR #32 as part of this work.
- The local manuscript builder must make no builder-stage Sleeper, Chronicle, NFL, or web lookups.
- Historical backfill must be idempotent and must not rewrite live league state.

## Review Focus

- A rostered player omitted from `players_points` becomes `CERTIFIED_ZERO`, with source evidence retained. Test in Task 1.
- A player acquired after a completed week is excluded as `NOT_YET_ACQUIRED`, rather than incorrectly blocking the board. Test in Task 1.
- A missing historical roster row remains `UNKNOWN` and blocks publication. Test in Task 3.
- Sleeper and Chronicle values that disagree remain `MANUAL_VERIFY` and block dependent totals. Test in Task 3.
- Player totals remain correct when a player changes fantasy rosters, while the packet displays the current issue team and preserves contributing roster evidence. Test in Task 4.

---

### Task 1: Pin the canonical player-week state contract with failing tests

**Files:**
- Modify: `tests/test_canonical_evidence.py`
- Modify: `tests/test_chronicle_collect.py`
- Modify: `tests/test_chronicle_backfill.py`

**Interfaces:**
- Consumes: existing matchup fixtures and Chronicle event helpers.
- Produces: executable expectations for `score_status`, `membership_status`, and evidence IDs used by later tasks.

- [ ] **Step 1: Write the failing canonical-evidence tests**

Add tests that assert:

1. A weekly matchup containing player `p0` in `players` but omitting `p0` from both points maps yields one player-week fact with `points == 0.0`, `score_status == "CERTIFIED_ZERO"`, and `membership_status == "ROSTERED"`.
2. A transaction/acquisition boundary can mark a player as `NOT_YET_ACQUIRED` for the prior week without producing a blocking unknown fact.
3. A player absent from both the finalized weekly roster and any authoritative transaction boundary remains unresolved.

- [ ] **Step 2: Write the failing Chronicle-event tests**

Assert that both live collection normalization and historical backfill preserve the player ID, zero score, score state, membership state, and source reference in `PLAYER_FANTASY_WEEK_FINAL` evidence.

- [ ] **Step 3: Run the focused tests to verify they fail**

Run:

```bash
pytest tests/test_canonical_evidence.py tests/test_chronicle_collect.py tests/test_chronicle_backfill.py -q
```

Expected: the new assertions fail because missing points are currently dropped by the canonical resolver and event evidence has no explicit state fields.

- [ ] **Step 4: Commit the failing tests**

```bash
git add tests/test_canonical_evidence.py tests/test_chronicle_collect.py tests/test_chronicle_backfill.py
git commit -m "test: define canonical player-week states"
```

### Task 2: Preserve explicit zero and membership evidence in Chronicle

**Files:**
- Modify: `editorial_desk/chronicle_collect.py:294-346`
- Modify: `editorial_desk/chronicle_backfill.py:95-170`
- Modify: `editorial_desk/chronicle_queries.py:232-268`
- Test: `tests/test_chronicle_collect.py`, `tests/test_chronicle_backfill.py`, `tests/test_chronicle_queries.py`

**Interfaces:**
- Consumes: Sleeper finalized matchup rows, including `players`, `starters`, `players_points`, and `players_points_custom`.
- Produces: `season_player_fantasy_finals()` rows containing `score_status`, `membership_status`, and the existing `event_id`/source fields.

- [ ] **Step 1: Implement state-aware event normalization**

In `_normalize_player_fantasy_finals`, form the player universe from weekly roster IDs plus both points maps. Emit `OBSERVED` when the authoritative points map contains the player, otherwise emit `CERTIFIED_ZERO` when the player is explicitly present in the finalized roster. Set `membership_status` to `ROSTERED` and retain the existing exact source reference.

- [ ] **Step 2: Apply the same event schema to historical backfill**

Extend `_historical_matchup_events` (or a focused helper it calls) to emit the same player-week events for each finalized historical matchup. Keep backfill provenance `reconstructed_from_sleeper`; do not fabricate rows when the historical roster does not identify the player.

- [ ] **Step 3: Return the new fields from Chronicle queries**

Update `ChronicleQueries.season_player_fantasy_finals()` to pass through the state and source fields without changing its filtering or ordering contract.

- [ ] **Step 4: Run the focused tests**

Run:

```bash
pytest tests/test_chronicle_collect.py tests/test_chronicle_backfill.py tests/test_chronicle_queries.py -q
```

Expected: PASS, including the new zero-state assertions.

- [ ] **Step 5: Commit the Chronicle change**

```bash
git add editorial_desk/chronicle_collect.py editorial_desk/chronicle_backfill.py editorial_desk/chronicle_queries.py tests/test_chronicle_collect.py tests/test_chronicle_backfill.py tests/test_chronicle_queries.py
git commit -m "feat: preserve player-week zero evidence"
```

### Task 3: Reconcile canonical player-week evidence and expose unresolved gaps

**Files:**
- Modify: `editorial_desk/canonical_evidence.py:304-520`
- Modify: `tests/test_canonical_evidence.py`

**Interfaces:**
- Consumes: historical Sleeper rows, Chronicle query rows from Task 2, and transaction timing from the publication snapshot.
- Produces: `canonical_league_evidence.player_weeks` with state fields, `player_week_coverage`, and unresolved/conflict details consumed by the board builder and packet readiness.

- [ ] **Step 1: Add failing reconciliation tests**

Assert that Sleeper and Chronicle agree on an observed score; that a Chronicle zero fills an absent Sleeper points entry when roster membership is explicit; that contradictory scores produce `MANUAL_VERIFY`; and that a missing player-membership fact produces an unresolved identifier rather than a zero.

- [ ] **Step 2: Implement state-aware canonicalization**

Replace the current `if score is None: continue` path with a state decision: use exact points when present, use Chronicle points when corroborating/filling, certify zero only for explicit weekly roster membership, and otherwise record an unresolved fact. Preserve the current matchup conflict behavior and add player-level conflict details.

- [ ] **Step 3: Resolve as-of acquisition boundaries**

Normalize both raw transaction `adds` maps and the existing normalized transaction shape. For a current player with an unambiguous acquisition week after the missing historical week, emit an exclusion state rather than requiring a score. If timing or destination roster is ambiguous, leave the fact unresolved.

- [ ] **Step 4: Add coverage metadata**

Return counts and identifiers for observed, certified-zero, excluded, unknown, and manual-verify rows. Keep `player_season_totals_status` unavailable whenever any eligible unknown or conflict remains.

- [ ] **Step 5: Run canonical tests**

Run:

```bash
pytest tests/test_canonical_evidence.py -q
```

Expected: PASS, with explicit state and conflict coverage.

- [ ] **Step 6: Commit the resolver change**

```bash
git add editorial_desk/canonical_evidence.py tests/test_canonical_evidence.py
git commit -m "feat: reconcile canonical player-week coverage"
```

### Task 4: Build cumulative player and rookie boards from resolved facts

**Files:**
- Modify: `editorial_desk/flagship_research.py:1620-1785`
- Modify: `editorial_desk/publication_complete.py:620-660`
- Modify: `tests/test_flagship_research.py`
- Modify: `tests/test_week2_completeness_fixes.py`

**Interfaces:**
- Consumes: state-aware `canonical_evidence.player_weeks` and coverage metadata from Task 3.
- Produces: `player_season_top_three` and `rookie_season_leaders` with `READY` status only when all eligible weeks are resolved, plus row-level evidence IDs and through-week coverage.

- [ ] **Step 1: Add failing board tests**

Cover an explicit zero row, a not-yet-acquired player, an unresolved player-week, and a player changing fantasy rosters. Assert exact cumulative points, current fantasy-team label, state-aware readiness, and rookie filtering based on draft/experience provenance.

- [ ] **Step 2: Update `_season_player_boards`**

Consume score and membership states instead of inferring completeness solely from current roster membership. Sum only `OBSERVED` and `CERTIFIED_ZERO` rows, exclude `NOT_YET_ACQUIRED`/`NOT_ROSTERED`, retain evidence IDs, and block on `UNKNOWN`/`MANUAL_VERIFY`.

- [ ] **Step 3: Strengthen packet readiness details**

Keep the existing blocking codes, but include the unresolved player-week identifiers and coverage counts in their details. Ensure a `READY` board has the requested positional rows and evidence references.

- [ ] **Step 4: Run the board and publication tests**

Run:

```bash
pytest tests/test_flagship_research.py tests/test_week2_completeness_fixes.py tests/test_publication_complete.py -q
```

Expected: PASS, including existing acquisition and offline-readiness regressions.

- [ ] **Step 5: Commit the board change**

```bash
git add editorial_desk/flagship_research.py editorial_desk/publication_complete.py tests/test_flagship_research.py tests/test_week2_completeness_fixes.py
git commit -m "feat: build cumulative boards from resolved history"
```

### Task 5: Backfill Week 3 historical evidence and verify the packet offline

**Files:**
- Modify only if required by the validated backfill path: `editorial_desk/chronicle_backfill.py`, workflow/CLI documentation, and focused tests.
- Create: an audit artifact outside the application source containing the backfill receipt and Week 3 packet comparison.

**Interfaces:**
- Consumes: retained Sleeper Weeks 1–3 historical matchup/transaction inputs and the state-aware Chronicle/canonical paths.
- Produces: idempotent historical player-week events and a preview packet whose cumulative boards are locally reproducible.

- [ ] **Step 1: Run the historical backfill in a non-live preview context**

Limit the run to `ironbound_sixteen`, season `2026`, Weeks 1–3. Verify that no live league mutation endpoint is called and that repeated backfill produces no duplicate event IDs.

- [ ] **Step 2: Run the focused local regression suite**

Run the Task 2–4 test commands again, then run the complete publication suite:

```bash
pytest tests/test_publication_complete.py tests/test_publication_offline_boundary.py tests/test_flagship_publication_acceptance.py -q
```

Expected: PASS.

- [ ] **Step 3: Run the GitHub Actions Week 3 preview**

Dispatch `mode=preview`, `week=3`, `send_email=false` on PR #32. Record the run URL, artifact digest, packet digest, and news receipt. Do not dispatch production mode.

- [ ] **Step 4: Verify cumulative readiness and magazine facts**

Confirm both season boards are `READY`, no unknown eligible player-weeks remain, each reported row has evidence IDs, and the offline acceptance comparison still matches the finished Week 3 issue’s cumulative player/rookie facts.

- [ ] **Step 5: Commit only required generic fixes and audit notes**

Use separate commits for any code defect exposed by the rerun and for local audit notes. Do not merge PR #32.

