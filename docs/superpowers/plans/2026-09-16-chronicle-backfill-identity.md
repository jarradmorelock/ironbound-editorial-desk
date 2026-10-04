# Chronicle Backfill and Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-season Sleeper renewal-chain backfill, explicit identity bootstrap/ambiguity handling, alias and manager-tenure history, live-observation coverage boundaries, correction-aware materialization, and continuously updated all-time Chronicle indexes.

**Architecture:** Historical ingestion uses the same Event Ledger model as live collection. A registry maps each season's Sleeper roster/owner records to stable internal identities. Auto-mapping uses conservative evidence and refuses ambiguous franchise continuity rather than guessing. Backfill writes source events; materializers derive head-to-head, records, streaks, seasons, and transactions from combined historical + live ledger records.

**Tech Stack:** Python 3.12, dataclasses/json/pathlib, existing `SleeperClient`, pytest.

**Spec:** `docs/superpowers/specs/2026-09-16-editorial-desk-v2-final-design.md`

## Global Constraints

- Backfill seeds the same living Chronicle future seasons continue to update.
- Dynasty history follows franchise identity; manager tenure is a separate query layer.
- Redraft history follows stable manager identity within that league.
- Team/manager display-name aliases are preserved by season.
- Ambiguous dynasty continuity is surfaced for manual override, never guessed.
- Ephemeral historical health/practice/lineup transitions are never fabricated.
- Derived totals are rebuilt from evidence, never incremented from stale materialized totals.
- Correction events supersede source facts without deleting original audit records.

---

## File map

**Create**
- `editorial_desk/chronicle_identity.py`
- `editorial_desk/chronicle_backfill.py`
- `editorial_desk/chronicle_materialize.py`
- `tests/test_chronicle_identity.py`
- `tests/test_chronicle_backfill.py`
- `tests/test_chronicle_materialize.py`
- `tests/test_chronicle_history_e2e.py`
- `tests/fixtures/chronicle_history/`

**Modify**
- `editorial_desk/sleeper.py`
- `editorial_desk/chronicle_store.py`
- `editorial_desk/chronicle_collect.py`
- `editorial_desk/cli.py`
- `README.md`

---

### Task 1: Define stable identity registry and conservative auto-mapping

**Files:**
- Create: `editorial_desk/chronicle_identity.py`
- Test: `tests/test_chronicle_identity.py`

**Interfaces:**
- `IdentityRegistry.empty() -> IdentityRegistry`
- `bootstrap_dynasty_season(...) -> IdentityBootstrapResult`
- `bootstrap_redraft_season(...) -> IdentityBootstrapResult`
- `apply_override(override: IdentityOverride) -> None`
- `franchise_for(league_key, season, roster_id) -> str`
- `manager_for(league_key, season, owner_id) -> str`
- `aliases(identity_key) -> list[AliasRecord]`
- `manager_tenures(franchise_key) -> list[ManagerTenure]`

**Auto-mapping policy:**
- Redraft: stable Sleeper `owner_id` is the primary manager key.
- Dynasty: continuity candidates may use prior-season roster slot, stable owner continuity, renewal-chain season adjacency, and explicit registry history.
- If multiple candidates are plausible or owner change + roster-slot evidence conflicts, mark `ambiguous` and require manual override.
- Display/team names are never identity keys.

- [ ] **Step 1: Write failing dynasty rename/owner-change test**

```python
def test_dynasty_history_follows_franchise_when_override_confirms_owner_change():
    registry = IdentityRegistry.empty()
    first = registry.register_dynasty_season(
        league_key="demo", season="2025", roster_id=3, owner_id="u1", team_name="Old Name"
    )
    registry.apply_override(IdentityOverride(
        league_key="demo", season="2026", roster_id=3,
        franchise_key=first.franchise_key, reason="confirmed ownership transfer"
    ))
    second = registry.register_dynasty_season(
        league_key="demo", season="2026", roster_id=3, owner_id="u2", team_name="New Name"
    )
    assert first.franchise_key == second.franchise_key
    assert [a.name for a in registry.aliases(first.franchise_key)] == ["Old Name", "New Name"]
```

- [ ] **Step 2: Write failing ambiguity test**

Construct a new season where prior roster slot suggests Franchise A but stable owner moved to a slot mapped to Franchise B. Assert bootstrap returns an ambiguity record and creates no guessed mapping.

- [ ] **Step 3: Write redraft continuity test**

Same owner ID in 2025/2026 with different team names resolves to one manager key; a different owner does not.

- [ ] **Step 4: Implement registry dataclasses + JSON serialization**

Store franchise registry and manager registry separately. Persist aliases, season mappings, manager tenures, overrides, and unresolved ambiguities.

- [ ] **Step 5: Run tests and commit**

```bash
python -m pytest tests/test_chronicle_identity.py -q
git add editorial_desk/chronicle_identity.py tests/test_chronicle_identity.py
git commit -m "feat: add conservative Chronicle identity registry"
```

---

### Task 2: Discover Sleeper renewal-chain seasons safely

**Files:**
- Modify: `editorial_desk/sleeper.py`
- Create: `editorial_desk/chronicle_backfill.py`
- Test: `tests/test_chronicle_backfill.py`

**Interfaces:**
- `discover_seasons(client, current_league_id) -> list[SeasonRef]` oldest -> newest.

- [ ] **Step 1: Write 2024 -> 2025 -> 2026 fixture traversal test**

Assert every league ID appears once and null/missing `previous_league_id` terminates traversal.

- [ ] **Step 2: Add cycle-protection test**

Malformed renewal loop raises `BackfillError` with the repeated league ID.

- [ ] **Step 3: Implement traversal using existing read-only `league()`**

Preserve Sleeper league ID, season, name, previous ID, and settings/metadata needed by identity bootstrap.

- [ ] **Step 4: Run tests and commit**

```bash
python -m pytest tests/test_chronicle_backfill.py -q
git add editorial_desk/sleeper.py editorial_desk/chronicle_backfill.py tests/test_chronicle_backfill.py
git commit -m "feat: discover historical Sleeper seasons"
```

---

### Task 3: Backfill historical source evidence

**Files:**
- Modify: `editorial_desk/chronicle_backfill.py`
- Test: `tests/test_chronicle_backfill.py`
- Create/expand: `tests/fixtures/chronicle_history/`

**Interfaces:**
- `backfill_season(client, season_ref, league_config, registry) -> BackfillSeasonResult`
- Result: `events`, `identity_updates`, `ambiguities`, `warnings`.

- [ ] **Step 1: Build fixture season with regular season, playoffs, trade, waiver, rookie draft, and traded future pick**

Use stable Sleeper-style IDs and explicit bracket rows.

- [ ] **Step 2: Write historical normalization tests**

Assert matchup/transaction/draft/pick events exist, provenance is `source_exact` or `reconstructed_from_sleeper`, and no historical `PLAYER_STATUS_CHANGE` is fabricated.

- [ ] **Step 3: Implement fetch loop**

Fetch:

```text
league/users/rosters
matchups weeks 1-18
transactions weeks 1-18
drafts + draft picks + draft traded picks
league traded picks
winners/losers brackets
```

Missing optional historical endpoints become warnings and coverage limitations.

- [ ] **Step 4: Preserve exact transaction times where source supplies them**

Do not convert exact Sleeper timestamps into reconstructed observation times.

- [ ] **Step 5: Run tests and commit**

```bash
python -m pytest tests/test_chronicle_backfill.py -q
git add editorial_desk/chronicle_backfill.py tests/test_chronicle_backfill.py tests/fixtures/chronicle_history
git commit -m "feat: backfill historical Sleeper evidence"
```

---

### Task 4: Materialize correction-aware living historical indexes

**Files:**
- Create: `editorial_desk/chronicle_materialize.py`
- Test: `tests/test_chronicle_materialize.py`

**Interfaces:**
- `effective_events(events) -> list[dict[str, Any]]`
- `materialize_league(events, registry) -> MaterializedLeagueHistory`
- Writes `matchups.json`, `records.json`, `seasons.json`, `transactions.json`, identity summary JSON.

- [ ] **Step 1: Write 13-1-1 -> 14-1-1 test**

```python
def test_new_live_result_updates_backfilled_series():
    history = materialize_league(backfilled_events + [new_live_win], registry)
    series = history.head_to_head[("franchise_a", "franchise_b")]
    assert (series.wins_a, series.wins_b, series.ties) == (14, 1, 1)
```

- [ ] **Step 2: Add streak reset and playoff separation tests**

All-time series includes both competition types while rows retain `regular_season` vs `playoffs`; current streak follows chronological effective results.

- [ ] **Step 3: Add correction-event test**

Original erroneous matchup event remains in ledger; a correction record with `correction_of=<event_id>` causes `effective_events()` and materialized history to use corrected fact exactly once.

- [ ] **Step 4: Implement materializer from ledger + registry only**

Never use previous materialized totals as inputs.

- [ ] **Step 5: Add coverage metadata**

Include `coverage_start_season`, `coverage_complete`, `coverage_warnings`, and live-observation-start references where relevant.

- [ ] **Step 6: Run tests and commit**

```bash
python -m pytest tests/test_chronicle_materialize.py -q
git add editorial_desk/chronicle_materialize.py tests/test_chronicle_materialize.py
git commit -m "feat: materialize living Chronicle history"
```

---

### Task 5: Persist identity registry and ambiguity reports

**Files:**
- Modify: `editorial_desk/chronicle_store.py`
- Modify: `editorial_desk/chronicle_identity.py`
- Test: `tests/test_chronicle_identity.py`
- Test: `tests/test_chronicle_store.py`

**Interfaces:**
- Registry files: `registry/franchises.json`, `registry/managers.json`, `registry/ambiguities.json`.

- [ ] **Step 1: Write round-trip registry test**

Serialize/load mappings, aliases, tenures, override, and unresolved ambiguity without information loss.

- [ ] **Step 2: Implement store helpers**

Use same atomic JSON write primitive as other Chronicle state.

- [ ] **Step 3: Run tests and commit**

```bash
python -m pytest tests/test_chronicle_identity.py tests/test_chronicle_store.py -q
git add editorial_desk/chronicle_store.py editorial_desk/chronicle_identity.py tests/test_chronicle_identity.py tests/test_chronicle_store.py
git commit -m "feat: persist Chronicle identity registry"
```

---

### Task 6: Add backfill/materialization/override CLI

**Files:**
- Modify: `editorial_desk/cli.py`
- Create: `tests/test_chronicle_backfill_cli.py`
- Modify: `README.md`

**Interfaces:**

```text
python -m editorial_desk chronicle-backfill --config ... --chronicle-root ...
python -m editorial_desk chronicle-materialize --chronicle-root ...
python -m editorial_desk chronicle-identity-report --chronicle-root ...
```

Manual registry overrides are edited in the documented registry override structure and then `chronicle-materialize` rebuilds derived indexes. Later Phase 4 places destructive/re-backfill modes behind backup gating.

- [ ] **Step 1: Write parser/orchestration tests**

Assert all configured leagues, including publication-disabled ones, are traversed oldest -> newest.

- [ ] **Step 2: Add ambiguity fail-safe test**

Backfill may append unambiguous source events but must exit nonzero before publishing identity-dependent derived totals for a league with unresolved dynasty identity ambiguity.

- [ ] **Step 3: Implement commands**

`chronicle-identity-report` prints unresolved ambiguity keys and exact season/roster/owner evidence needed for manual resolution.

- [ ] **Step 4: Test rerun idempotency**

Second backfill after no source change adds zero events and produces byte-identical derived JSON.

- [ ] **Step 5: Run tests and commit**

```bash
python -m pytest tests/test_chronicle_backfill_cli.py tests/test_chronicle_backfill.py tests/test_chronicle_materialize.py -q
git add editorial_desk/cli.py tests/test_chronicle_backfill_cli.py README.md
git commit -m "feat: add Chronicle historical bootstrap commands"
```

---

### Task 7: Build multi-season end-to-end history fixture

**Files:**
- Create: `tests/test_chronicle_history_e2e.py`
- Expand: `tests/fixtures/chronicle_history/`

- [ ] **Step 1: Fixture scenario**

Include dynasty rename, ownership transfer, one ambiguous transition resolved by override, redraft returning manager/new team name, trade, waiver, playoff meeting, future-pick trade, renewal, and one new live matchup.

- [ ] **Step 2: Assertions**

Verify stable identities, historical aliases, manager tenure, all-time record update, streak, playoff labeling, transaction season, future-pick history, no fabricated historical health, and incomplete coverage labeling where a fixture endpoint is intentionally absent.

- [ ] **Step 3: Run and commit**

```bash
python -m pytest tests/test_chronicle_history_e2e.py -q
git add tests/test_chronicle_history_e2e.py tests/fixtures/chronicle_history
git commit -m "test: verify multi-season Chronicle continuity"
```

---

### Task 8: Phase 2 verification gate

- [ ] **Step 1: Run complete suite**

Run: `python -m pytest -q`

- [ ] **Step 2: Run fixture backfill twice and compare tree hashes**

Expected second run: zero added events and byte-identical registry/history output.

- [ ] **Step 3: Verify materializer inputs**

Code review confirms materializers depend only on effective ledger events + registry, never prior materialized counters.

- [ ] **Step 4: Verify unresolved identity ambiguity cannot silently publish all-time claims**

Run ambiguity fixture and expect explicit nonzero/report behavior.

- [ ] **Step 5: Commit verification fixes only if needed**

```bash
git add -A
git commit -m "test: close Chronicle backfill regressions"
```
