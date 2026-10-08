# Global Player Week History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate every league's cumulative player and rookie boards from Sleeper's finalized week-by-week player scores, with correct historical roster ownership and explicit gaps.

**Architecture:** Add a shared Sleeper history collector that reads every completed week through the report week. Production persists normalized score and correction events to Chronicle; preview uses the same fetched rows without writing. Flagship research consumes the resolved rows and existing coverage checks.

**Tech Stack:** Python 3, Sleeper API client, Chronicle JSONL event store, pytest.

**Spec:** `docs/superpowers/specs/2026-10-07-global-research-packet-integrity.md`

## Global Constraints

- Use Sleeper `players_points` or `players_points_custom` as the fantasy-score source; do not reconstruct fantasy points from NFL stats.
- Keep records keyed by league, season, week, roster ID, and player ID.
- An explicit `0.0` is a score; an absent score key is a coverage gap, never an inferred zero.
- Preview cannot write Chronicle state; production collection is repeatable and records corrections as linked events.
- Apply the same collection path to every configured league and publication profile.

## Review Focus

- A player traded mid-season must be attributed to the roster shown in each week's matchup; test in Task 2.
- Explicit zero and absent player score must differ; test in Task 1.
- A later Sleeper correction must resolve to the newest event without erasing provenance; test in Task 1.
- Missing week data must keep cumulative totals unavailable and name the week; test in Task 3.
- Preview must return complete fetched history without changing Chronicle files; test in Task 3.

---

### Task 1: Normalize exact weekly score events and corrections

**Files:**
- Modify: `editorial_desk/chronicle_collect.py::_normalize_player_fantasy_finals`
- Modify: `editorial_desk/chronicle_queries.py::season_player_fantasy_finals`
- Test: `tests/test_chronicle_collect.py`
- Test: `tests/test_chronicle_queries.py`

**Interfaces:**
- Extend `_normalize_player_fantasy_finals(league_key, season, week, matchups, players, observed_at, existing_rows=())` to detect whether a stored natural-key score needs a linked correction event.
- Keep `ChronicleQueries.season_player_fantasy_finals(league_key, season)` returning rows with `week`, `roster_id`, `player_id`, `position`, `points`, and `event_id`; resolve correction chains before returning rows.

- [ ] **Step 1: Write failing tests** named `test_player_finals_do_not_infer_missing_score_as_zero` and `test_player_score_correction_resolves_to_latest_value`. Assert an explicit zero is retained, a player missing from both Sleeper point maps is not assigned zero, and a correction linked by `correction_of` becomes the returned score.
- [ ] **Step 2: Run tests to verify the expected failures**

Run: `pytest tests/test_chronicle_collect.py::test_player_finals_do_not_infer_missing_score_as_zero tests/test_chronicle_queries.py::test_player_score_correction_resolves_to_latest_value -q`
Expected: FAIL because the normalizer currently defaults missing score keys to `0.0` and the query returns base events without applying corrections.

- [ ] **Step 3: Implement normalization and correction resolution** in `chronicle_collect.py` and `chronicle_queries.py`. Emit base events only for player IDs with an explicit Sleeper point-map value. When a stored natural-key score changes, append a new event with `correction_of` set to the previously resolved event ID. Resolve correction chains by that link and preserve source/observation data.
- [ ] **Step 4: Run the focused tests**

Run: `pytest tests/test_chronicle_collect.py tests/test_chronicle_queries.py -q`
Expected: PASS.

- [ ] **Step 5: Commit** `fix: preserve exact sleeper player week scores`

### Task 2: Backfill completed weeks for every configured league

**Files:**
- Modify: `editorial_desk/chronicle_collect.py::collect_pulse`
- Modify: `editorial_desk/sleeper.py::SleeperClient.matchups` only if a small typed helper is needed
- Test: `tests/test_chronicle_collect.py`

**Interfaces:**
- Keep `collect_pulse(leagues, client, store, week, observed_at, *, finalize_matchups=False)` as the production entry point.
- Add `_collect_player_week_history(client, league_key, sleeper_league_id, season, through_week, players, observed_at, current_week_matchups=None, existing_rows=()) -> tuple[list[dict[str, Any]], list[ChronicleEvent], dict[str, Any]]` in `chronicle_collect.py`. It returns resolved score rows, events to append, and per-week coverage; it reuses the requested week's already-fetched matchup response.

- [ ] **Step 1: Write failing tests** named `test_finalized_pulse_backfills_player_finals_for_all_completed_weeks` and `test_finalized_pulse_backfill_covers_each_configured_league`. Use distinct weekly roster IDs and points; assert one event per explicitly scored player/week/roster, including a traded player under different roster IDs.
- [ ] **Step 2: Run tests to verify the expected failures**

Run: `pytest tests/test_chronicle_collect.py::test_finalized_pulse_backfills_player_finals_for_all_completed_weeks tests/test_chronicle_collect.py::test_finalized_pulse_backfill_covers_each_configured_league -q`
Expected: FAIL because `collect_pulse` currently finalizes only the requested week's player rows.

- [ ] **Step 3: Implement the shared backfill** to fetch matchup responses for Weeks 1 through the finalized report week for each configured league, normalize through Task 1, append events, and record per-week coverage/warnings in the run manifest. Do not backfill future weeks or apply historical lineups/transactions through this score-only path.
- [ ] **Step 4: Run the collector tests**

Run: `pytest tests/test_chronicle_collect.py -q`
Expected: PASS.

- [ ] **Step 5: Commit** `feat: backfill sleeper player week history`

### Task 3: Use the same history in preview and publication boards

**Files:**
- Modify: `editorial_desk/enriched_collector.py::collect_all`
- Modify: `editorial_desk/flagship_research.py::build_flagship_research_packet` and `_season_player_boards`
- Test: `tests/test_flagship_research.py`
- Test: `tests/test_enriched_collector.py` (create)
- Test: `tests/test_chronicle_history_e2e.py`

**Interfaces:**
- Add `player_week_history: list[dict[str, Any]] | None = None` to `build_flagship_research_packet`; when omitted, retain the current Chronicle-only behavior for callers/tests that do not provide a live collection.
- `collect_all` uses the shared history collector for preview's read-only rows and passes resolved rows to each applicable packet; production reads the just-backfilled Chronicle rows and must not duplicate them in board aggregation.

- [ ] **Step 1: Write failing test** `test_preview_uses_week_history_without_chronicle_writes` in `tests/test_enriched_collector.py`; extend existing `test_season_player_boards_merge_current_week_and_report_missing_history` in `tests/test_flagship_research.py` to assert a missing week remains incomplete and is named. Assert preview cumulative totals use multiple Sleeper weeks while Chronicle files remain byte-for-byte unchanged.
- [ ] **Step 2: Run tests to verify the expected failures**

Run: `pytest tests/test_enriched_collector.py::test_preview_uses_week_history_without_chronicle_writes tests/test_flagship_research.py::test_season_player_boards_merge_current_week_and_report_missing_history -q`
Expected: FAIL because packet construction currently reads prior scores only from Chronicle events.

- [ ] **Step 3: Implement read-only preview integration** and deduplicate live and stored score rows by league/season/week/roster/player with correction resolution before aggregation. Preserve existing `UNAVAILABLE`/gap language for incomplete weeks.
- [ ] **Step 4: Run the focused integration tests**

Run: `pytest tests/test_flagship_research.py tests/test_chronicle_history_e2e.py -q`
Expected: PASS.

- [ ] **Step 5: Commit** `feat: use complete player week history in research packets`

### Task 4: Full verification

**Files:** No additional files.

- [ ] **Step 1: Run the complete suite**

Run: `pytest -q`
Expected: PASS with no failures.

- [ ] **Step 2: Commit** only if the integration verification required a follow-up fix, using a message that names the fix.
