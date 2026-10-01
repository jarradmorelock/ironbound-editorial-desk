# Ironbound Research Packet Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the Ironbound research packet with the approved 25-page editable template and supply verified data/readiness for its recurring editorial slots.

**Architecture:** Keep `flagship_research.py` as the factual packet assembler and Markdown renderer. Persist per-player weekly fantasy scores through Chronicle so season player boards are evidence-backed; use existing league snapshots, dossier history, and Tuesday handoffs for the other sections. Missing history, projections, or division inputs remain explicit and never become fabricated winners or partial totals presented as complete.

**Tech Stack:** Python 3, pytest, existing Sleeper snapshot/dossier structures, Chronicle JSONL event ledger and query layer.

**Spec:** `docs/superpowers/specs/2026-09-30-ironbound-research-packet-template-alignment.md`

## Global Constraints

- Do not edit or replace files under the project `sources/` directory.
- Do not change the official power-ranking engine, playoff simulation, ranking graphics, or schedule.
- Do not create or modify a PowerPoint/PDF issue in this change.
- Do not generate, redraw, or embed text into recurring or issue-specific artwork.
- Do not infer projections, historical results, divisions, or award cutoffs that the sources do not establish.
- Do not push, open a pull request, or otherwise publish the local work.

## Review Focus

- Previously completed weeks may lack player-score Chronicle events; never show a partial season leaderboard as complete. Test that such coverage is reported unavailable with a backfill/readiness reason.
- Duplicate or corrected player-week evidence must not double-count a player's total. Test event identity/idempotency and one score per season/week/roster/player.
- Division IDs or names can be absent or inconsistent. Test explicit unavailable status and never classify by team-name resemblance.
- Week-entry records may be missing from history. Test that Bad Beat/Escape Artist need manual verification instead of falling back to postgame records.
- No frozen pregame projection may exist for rookie disappointment. Test that the candidate list still carries available evidence and does not invent a projection delta.

---

### Task 1: Lock the 25-page Ironbound/Unbound spine

**Files:**
- Modify: `editorial_desk/flagship_research.py` — `flagship_editorial_spine`, packet version, structural validator, Markdown spine labels.
- Test: `tests/test_flagship_research.py`

**Interfaces:**
- Consumes: `flagship_editorial_spine(publication_key: str, week: int)` and the approved 25-page sequence in the spec.
- Produces: same 25 ordered page records for Ironbound and Unbound, with publication-specific names, game report numbers 1–6 on pages 5–7, and Power Board ranks 1–16 on pages 17–20.

- [ ] **Step 1: Add failing spine tests** asserting exact 25-page module order and page labels, all three two-report allocations, four four-team rank allocations, and identical functional allocations across both publications.
- [ ] **Step 2: Run focused tests**

  Run: `pytest tests/test_flagship_research.py -k 'spine or page or structure' -q`

  Expected: FAIL because the current spine is 22 pages and combines the honors/rookie modules.
- [ ] **Step 3: Implement the 25-page spine and validation** in `flagship_research.py`; split manager honors, player honors, and Rookie Watch into pages 12–14; place Playoff Forecast on 15, Power Rankings on 16, four Power Board pages on 17–20, Pressure Points on 21, Full Slate on 22, Division/Road Ahead on 23, Week Ahead on 24, and Sources on 25. Update the packet contract to `ironbound-production-v0.7` and keep per-publication display labels configurable.
- [ ] **Step 4: Update Markdown spine output and run focused tests**

  Run: `pytest tests/test_flagship_research.py -k 'spine or page or structure' -q`

  Expected: PASS; malformed or truncated spines fail `validate_flagship_research_packet`.
- [ ] **Step 5: Commit** as `feat: align flagship packet with 25-page template`.

### Task 2: Capture player-week fantasy scores in Chronicle

**Files:**
- Modify: `editorial_desk/chronicle_collect.py` — add idempotent player-week final events and collect them with matchup finals.
- Modify: `editorial_desk/chronicle_queries.py` — add `season_player_fantasy_finals(league_key: str, season: str) -> list[dict[str, Any]]`.
- Test: `tests/test_chronicle_collect.py`
- Test: `tests/test_chronicle_queries.py`

**Interfaces:**
- Consumes: Sleeper matchup rows (`roster_id`, `matchup_id`, `players_points` or `players_points_custom`) and the current player metadata map.
- Produces: `PLAYER_FANTASY_WEEK_FINAL` rows with `season`, `week`, `roster_id`, `player_id`, `position`, `points`, and `event_id`; stable event identity is keyed by league/season/week/roster/player.

- [ ] **Step 1: Add failing collector/query tests** for started and bench player scores, custom-points fallback, stable event IDs on repeat collection, and correct season/week filtering.
- [ ] **Step 2: Run focused Chronicle tests**

  Run: `pytest tests/test_chronicle_collect.py tests/test_chronicle_queries.py -k 'player_fantasy or matchup' -q`

  Expected: FAIL because no per-player fantasy final event or season query exists.
- [ ] **Step 3: Implement `_normalize_player_fantasy_finals(league_key, season, week, matchups, players, observed_at)`** and invoke it from `collect_pulse`; add the query method reading only `PLAYER_FANTASY_WEEK_FINAL` events. Do not infer scores from NFL box stats.
- [ ] **Step 4: Run focused Chronicle tests**

  Run: `pytest tests/test_chronicle_collect.py tests/test_chronicle_queries.py -k 'player_fantasy or matchup' -q`

  Expected: PASS; repeated collection yields the same event IDs and one query row per player-week.
- [ ] **Step 5: Commit** as `feat: persist weekly player fantasy scores`.

### Task 3: Supply divisional game labels and cumulative season player boards

**Files:**
- Modify: `editorial_desk/flagship_research.py` — `_game_research`, new division-outlook field, season player aggregators, completeness checks and Markdown output.
- Test: `tests/test_flagship_research.py`
- Test: `tests/test_chronicle_queries.py` (reuse Task 2 API; no changes unless its contract test needs extension).

**Interfaces:**
- Consumes: Task 2 `ChronicleQueries.season_player_fantasy_finals(...)`, snapshot roster divisions/player metadata, dossier `divisions`, and existing `remaining_schedule_strength` handoff.
- Produces: each game has `division_status` (`VERIFIED_DIVISIONAL`, `VERIFIED_NON_DIVISIONAL`, or `UNAVAILABLE`) plus `division_name` only when verified; packet `division_outlook` exposes division summaries and schedule-strength status; weekly honors expose `player_season_top_three` and `rookie_season_leaders` by QB/RB/WR/TE.

- [ ] **Step 1: Add failing packet tests** for same-division/different-division/missing-division matchups, ready/unavailable Road Ahead inputs, cumulative player totals across weeks, current fantasy-team labels, rookies filtered by verified experience, and absent historical score coverage.
- [ ] **Step 2: Run focused tests**

  Run: `pytest tests/test_flagship_research.py -k 'division or season_player or rookie_season' -q`

  Expected: FAIL because games have no division status, no division-outlook block exists, and season player boards are absent.
- [ ] **Step 3: Implement division evidence and season aggregation** in `flagship_research.py`. Derive divisions only from both teams' roster settings and supplied league division labels; return unavailable if either identity is missing. Aggregate Chronicle scores by player through the packet week, deduplicate `(week, roster_id, player_id)`, filter to players currently rostered for team display, and do not emit a complete leaderboard unless score coverage reaches every completed week.
- [ ] **Step 4: Run focused tests**

  Run: `pytest tests/test_flagship_research.py -k 'division or season_player or rookie_season' -q`

  Expected: PASS; incomplete player history and missing division/schedule inputs have explicit unavailable/readiness explanations.
- [ ] **Step 5: Commit** as `feat: add division and season player research`.

### Task 4: Complete weekly manager, player, and rookie honors

**Files:**
- Modify: `editorial_desk/flagship_research.py` — weekly honors assembly, helper selection logic, validation and Markdown honors sections.
- Test: `tests/test_flagship_research.py`
- Test: `tests/test_honors_registry.py` — update the existing season-team-score assertion from top single-week scores to cumulative totals.
- Test: `tests/test_weekly_features.py` only if a missing source-level candidate helper must be added there.

**Interfaces:**
- Consumes: weekly feature fields already produced by `weekly_features.py`, the current snapshot, historical dossiers/Chronicle, and the approved award rules in the spec.
- Produces: honors fields `most_efficient_manager`, `high_score`, `bad_beat_candidates`, `escape_artist_candidates`, `rookie_of_the_week`, `top_rookie_starter`, `rookie_disappointment_candidates`, `rookie_watch_top_five`, `free_agent_of_the_week`, `season_efficiency_top_three`, and corrected cumulative `season_team_score_top_three`; preserve the existing overall and started-position leaders.

- [ ] **Step 1: Add failing honors tests** for MOW exclusion in Most Efficient, different-manager/different-game Bad Beat and Escape Artist selection, entry-record priority/manual fallback, cumulative team points rather than best single-week scores, five distinct weekly player awards, rookie bench/taxi eligibility, starter-only rookie leader, projection-unavailable disappointment evidence, rookie draft-pick context, and `fantasy_team: "UNROSTERED"` for the free-agent award.
- [ ] **Step 2: Run focused tests**

  Run: `pytest tests/test_flagship_research.py tests/test_honors_registry.py tests/test_weekly_features.py tests/test_week2_completeness_fixes.py -k 'honor or award or rookie or season_team' -q`

  Expected: FAIL on missing output fields and incorrect selection/aggregation behavior.
- [ ] **Step 3: Implement manager and player/rookie research outputs**. Most Efficient skips the MOW roster; weekly high score stays distinct from cumulative team totals; Bad Beat/Escape Artist use entering records only when history verifies them and cannot share a manager or matchup. Keep Rookie of the Week eligible for STARTED/BENCH/TAXI, add a separate started-only rookie leader, and expose disappointment candidates with source evidence but no unapproved composite threshold. Attach stat lines and fantasy rookie-draft picks; set Free Agent's fantasy-team display field to `UNROSTERED`.
- [ ] **Step 4: Update packet validation and Markdown rendering** so required sections show availability reasons and optional rotating awards remain editorial choices rather than blocking completeness.
- [ ] **Step 5: Run focused tests**

  Run: `pytest tests/test_flagship_research.py tests/test_honors_registry.py tests/test_weekly_features.py tests/test_week2_completeness_fixes.py -k 'honor or award or rookie or season_team' -q`

  Expected: PASS; no award is silently duplicated, and historical coverage gaps are visible.
- [ ] **Step 6: Commit** as `feat: complete flagship honors research`.

### Task 5: Integrate readiness contracts and run regression suite

**Files:**
- Modify: `editorial_desk/flagship_research.py` — validation checks and human-readable source/readiness summaries.
- Test: `tests/test_flagship_research.py`
- Test: existing Editorial Desk suite.

**Interfaces:**
- Consumes: all packet fields from Tasks 1–4 and existing external Tuesday handoff statuses.
- Produces: `validate_flagship_research_packet(packet)` distinguishes required missing evidence, optional editorial candidates, and awaiting external Tuesday inputs; rendered Markdown names the new sections and preserves provenance/readiness.

- [ ] **Step 1: Add failing end-to-end packet tests** for the full 25-page packet, all six non-feature game recaps, divisional statuses, manager/player/rookie fields, schedule readiness, and projection/history warnings.
- [ ] **Step 2: Run the end-to-end packet test**

  Run: `pytest tests/test_flagship_research.py -q`

  Expected: FAIL until the full schema and rendering are integrated.
- [ ] **Step 3: Implement readiness rules and Markdown sections** without making optional missing inputs fatal when the spec says they may be unavailable with a reason.
- [ ] **Step 4: Run focused and full regression tests**

  Run: `pytest tests/test_flagship_research.py tests/test_chronicle_collect.py tests/test_chronicle_queries.py tests/test_weekly_features.py tests/test_week2_completeness_fixes.py -q`

  Then run: `pytest -q`

  Expected: both commands pass; no `sources/` files or magazine renders change.
- [ ] **Step 5: Commit** as `test: verify Ironbound research packet alignment`.
