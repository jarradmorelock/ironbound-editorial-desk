# Chronicle Backfill and Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-season Sleeper renewal-chain backfill, stable dynasty franchise/redraft manager identity, alias preservation, live-observation coverage markers, and continuously rebuildable all-time Chronicle indexes.

**Architecture:** Historical ingestion uses the same Event Ledger model as live collection. A registry layer maps yearly Sleeper roster/owner IDs to stable identities; backfill produces historical source events, and materializers derive head-to-head, records, streaks, seasons, and transaction views from combined backfilled + live events.

**Tech Stack:** Python 3.12, standard library dataclasses/json/pathlib, existing `SleeperClient`, pytest.

**Spec:** `docs/superpowers/specs/2026-09-16-editorial-desk-v2-final-design.md`

## Global Constraints

- Backfill seeds the same living Chronicle future seasons continue to update.
- Dynasty history follows franchise identity; manager tenure is separate.
- Redraft history follows stable manager identity within the league.
- Historical aliases are preserved with time bounds.
- Ephemeral historical status changes are never fabricated.
- Derived all-time numbers are materialized from evidence, never stored as stale constants.

---

## File map

**Create**
- `editorial_desk/chronicle_identity.py` — stable identity registry and alias/tenure mapping.
- `editorial_desk/chronicle_backfill.py` — renewal-chain traversal and historical event normalization.
- `editorial_desk/chronicle_materialize.py` — derived matchup/record/season/transaction indexes.
- `tests/test_chronicle_identity.py`
- `tests/test_chronicle_backfill.py`
- `tests/test_chronicle_materialize.py`
- `tests/fixtures/chronicle_history/` — synthetic multi-season Sleeper fixtures.

**Modify**
- `editorial_desk/sleeper.py` — expose safe helpers needed by backfill without changing read-only behavior.
- `editorial_desk/chronicle_store.py` — registry/history read/write helpers.
- `editorial_desk/cli.py` — add `chronicle-backfill` and `chronicle-materialize` commands.
- `README.md`

---

### Task 1: Add stable identity registry primitives

**Files:**
- Create: `editorial_desk/chronicle_identity.py`
- Test: `tests/test_chronicle_identity.py`

**Interfaces:**
- Produces `IdentityRegistry`, `resolve_dynasty_franchise(...)`, `resolve_redraft_manager(...)`, alias/tenure records.

- [ ] **Step 1: Write failing dynasty rename/ownership tests**

```python
def test_dynasty_history_follows_franchise_across_name_and_owner_change():
    registry = IdentityRegistry.empty()
    first = registry.register_dynasty_season(
        league_key="demo", season="2025", roster_id=3, owner_id="u1", team_name="Old Name"
    )
    second = registry.register_dynasty_season(
        league_key="demo", season="2026", roster_id=3, owner_id="u2", team_name="New Name",
        previous_season_key=first.franchise_key,
    )
    assert first.franchise_key == second.franchise_key
    assert registry.aliases(first.franchise_key) == [
        ("2025", "Old Name"), ("2026", "New Name")
    ]
    assert registry.manager_tenures(first.franchise_key)[0].owner_id == "u1"
    assert registry.manager_tenures(first.franchise_key)[1].owner_id == "u2"
```

- [ ] **Step 2: Write failing redraft identity test**

Assert same stable owner ID under two annual team names resolves to one manager key while unrelated managers remain distinct.

- [ ] **Step 3: Run and verify failure**

Run: `python -m pytest tests/test_chronicle_identity.py -q`

- [ ] **Step 4: Implement registry dataclasses and JSON serialization**

Keep franchise registry and manager registry separate. Allow manual override records to supersede auto-mapping without modifying underlying source events.

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_chronicle_identity.py -q`

- [ ] **Step 6: Commit**

```bash
git add editorial_desk/chronicle_identity.py tests/test_chronicle_identity.py
git commit -m "feat: add Chronicle identity registry"
```

---

### Task 2: Traverse Sleeper renewal chains

**Files:**
- Modify: `editorial_desk/sleeper.py`
- Create: `editorial_desk/chronicle_backfill.py`
- Test: `tests/test_chronicle_backfill.py`

**Interfaces:**
- Produces `discover_seasons(client, current_league_id) -> list[SeasonRef]` ordered oldest -> newest.

- [ ] **Step 1: Write fixture test for `previous_league_id` traversal**

Fixture chain: 2024 -> 2025 -> 2026. Assert discovery returns all three once and stops on null/missing previous ID.

- [ ] **Step 2: Add cycle-protection test**

A malformed chain that points backward in a loop must raise `BackfillError` rather than loop forever.

- [ ] **Step 3: Implement renewal traversal using existing `league()` endpoint**

No new write APIs. Preserve season metadata from each returned league object.

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest tests/test_chronicle_backfill.py -q`

```bash
git add editorial_desk/sleeper.py editorial_desk/chronicle_backfill.py tests/test_chronicle_backfill.py
git commit -m "feat: discover historical Sleeper seasons"
```

---

### Task 3: Normalize historical matchups, drafts, transactions, and picks

**Files:**
- Modify: `editorial_desk/chronicle_backfill.py`
- Create fixtures under `tests/fixtures/chronicle_history/`
- Test: `tests/test_chronicle_backfill.py`

**Interfaces:**
- Produces `backfill_season(...) -> BackfillSeasonResult(events, identity_updates, warnings)`.

- [ ] **Step 1: Add fixtures for a regular season + playoffs + trade + rookie draft + traded pick**

Fixtures must include stable transaction IDs and explicit playoff bracket records.

- [ ] **Step 2: Write failing normalization tests**

Assert:

```python
assert any(e.event_type == "MATCHUP_FINAL" for e in result.events)
assert any(e.event_type == "TRADE" for e in result.events)
assert all(e.provenance in {"source_exact", "reconstructed_from_sleeper"} for e in result.events)
assert not any(e.event_type == "PLAYER_STATUS_CHANGE" for e in result.events)
```

- [ ] **Step 3: Implement historical fetch loop**

Fetch users/rosters, Weeks 1-18 matchups and transactions, drafts/picks/traded picks, winner/loser brackets when available. Missing optional historical endpoints become warnings, not fabricated events.

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest tests/test_chronicle_backfill.py -q`

```bash
git add editorial_desk/chronicle_backfill.py tests/test_chronicle_backfill.py tests/fixtures/chronicle_history
git commit -m "feat: backfill historical Sleeper evidence"
```

---

### Task 4: Materialize living historical indexes

**Files:**
- Create: `editorial_desk/chronicle_materialize.py`
- Test: `tests/test_chronicle_materialize.py`

**Interfaces:**
- Produces `materialize_league(events, registry) -> MaterializedLeagueHistory` and writers for `matchups.json`, `records.json`, `seasons.json`, `transactions.json`, `franchises.json`/`managers.json`.

- [ ] **Step 1: Write failing all-time update test**

```python
def test_new_live_result_updates_backfilled_all_time_record():
    history = materialize_league(backfilled_events + [new_live_win], registry)
    series = history.head_to_head[("franchise_a", "franchise_b")]
    assert (series.wins_a, series.wins_b, series.ties) == (14, 1, 1)
```

- [ ] **Step 2: Add streak reset and playoff-separation tests**

Regular-season and playoff meetings both count toward all-time series but retain separate competition labels. Current streak extends/resets from chronological results.

- [ ] **Step 3: Implement materializers from event evidence only**

Never read a previous materialized total as source truth. Rebuild from full relevant ledger slice + registry.

- [ ] **Step 4: Add incomplete-coverage metadata**

Materialized history must include `coverage_start_season`, `coverage_complete`, and warning text when a renewal chain or endpoint is incomplete.

- [ ] **Step 5: Run tests and commit**

Run: `python -m pytest tests/test_chronicle_materialize.py -q`

```bash
git add editorial_desk/chronicle_materialize.py tests/test_chronicle_materialize.py
git commit -m "feat: materialize living Chronicle history"
```

---

### Task 5: Record live-observation coverage boundaries

**Files:**
- Modify: `editorial_desk/chronicle_store.py`
- Modify: `editorial_desk/chronicle_collect.py`
- Test: `tests/test_chronicle_store.py`
- Test: `tests/test_chronicle_collect.py`

**Interfaces:**
- `coverage/live_observation.json` stores first successful observation timestamp for health, practice, lineup, and projection-change sources per league/global source as appropriate.

- [ ] **Step 1: Write failing first-observation test**

Assert first successful health collection creates marker; later runs do not move the start date forward.

- [ ] **Step 2: Implement monotonic coverage start markers**

A source failure before first success creates no false coverage start. Once set, marker is immutable except explicit maintenance migration.

- [ ] **Step 3: Run tests and commit**

Run: `python -m pytest tests/test_chronicle_store.py tests/test_chronicle_collect.py -q`

```bash
git add editorial_desk/chronicle_store.py editorial_desk/chronicle_collect.py tests/test_chronicle_store.py tests/test_chronicle_collect.py
git commit -m "feat: track Chronicle live observation coverage"
```

---

### Task 6: Add backfill/materialization CLI commands

**Files:**
- Modify: `editorial_desk/cli.py`
- Create: `tests/test_chronicle_backfill_cli.py`
- Modify: `README.md`

**Interfaces:**

```text
python -m editorial_desk chronicle-backfill --config ... --chronicle-root ...
python -m editorial_desk chronicle-materialize --chronicle-root ...
```

- [ ] **Step 1: Add failing parser/orchestration tests**

Assert `chronicle-backfill` iterates all configured leagues, including publication-disabled ones, and invokes backfill oldest-to-newest.

- [ ] **Step 2: Implement command**

Before writing events, backfill must load registry; after appending events/identity updates, invoke materialization. Re-running command must produce zero added events and identical derived JSON.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_chronicle_backfill_cli.py tests/test_chronicle_backfill.py tests/test_chronicle_materialize.py -q`

- [ ] **Step 4: Document manual bootstrap and correction workflow**

Document registry override file locations and rebuild command.

- [ ] **Step 5: Commit**

```bash
git add editorial_desk/cli.py tests/test_chronicle_backfill_cli.py README.md
git commit -m "feat: add Chronicle backfill and rebuild commands"
```

---

### Task 7: Multi-season end-to-end history fixture

**Files:**
- Create: `tests/test_chronicle_history_e2e.py`
- Expand: `tests/fixtures/chronicle_history/`

- [ ] **Step 1: Build synthetic history fixture**

Include:

- dynasty franchise rename
- dynasty manager change
- redraft manager/team-name continuity
- trade
- waiver claim
- playoff meeting
- future-pick trade
- annual renewal
- one new live matchup result

- [ ] **Step 2: Write end-to-end assertions**

Assert stable identities, alias lists, manager tenure, all-time H2H update, playoff separation, transaction season retention, and no fabricated historical health events.

- [ ] **Step 3: Run test**

Run: `python -m pytest tests/test_chronicle_history_e2e.py -q`

- [ ] **Step 4: Commit**

```bash
git add tests/test_chronicle_history_e2e.py tests/fixtures/chronicle_history
git commit -m "test: verify multi-season Chronicle continuity"
```

---

### Task 8: Phase 2 regression gate

- [ ] **Step 1: Run complete suite**

Run: `python -m pytest -q`

- [ ] **Step 2: Run backfill twice against fixtures and diff output**

Expected: second run adds zero events and produces byte-identical derived history.

- [ ] **Step 3: Verify history indexes never depend on stale prior totals**

Code review: materializer inputs are ledger + registry only.

- [ ] **Step 4: Commit any regression fixes only if needed**

```bash
git add -A
git commit -m "test: close Chronicle backfill regressions"
```
