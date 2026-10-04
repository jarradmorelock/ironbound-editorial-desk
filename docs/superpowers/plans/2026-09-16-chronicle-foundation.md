# Chronicle Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the permanent `chronicle-data` branch, deterministic Event Ledger records, lightweight live collection, atomic/idempotent storage, source freshness/run manifests, and serialized Chronicle writer workflows without changing publication behavior.

**Architecture:** Chronicle collection is intentionally separate from the existing full editorial collector. One lightweight pulse fetches the global Sleeper player directory once, records cross-league player-status changes once, then fetches only the minimum per-league state needed for transactions, lineups, reserve state, and optional finalized matchups. A filesystem store writes an append-only ledger to a separately checked-out orphan `chronicle-data` branch using staged atomic replacement.

**Tech Stack:** Python 3.12, dataclasses, hashlib/json/pathlib/tempfile/os, requests, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-16-editorial-desk-v2-final-design.md`

## Global Constraints

- Sleeper remains read-only.
- `chronicle-data` contains generated Chronicle state and is never force-pushed by normal automation.
- Daily/pulse collection must not invoke flagship full-season, Dynasty Daddy, nflverse play-by-play, or other expensive editorial enrichment.
- Global NFL/player status events are recorded once in the cross-league stream, not once per fantasy league.
- League-specific reactions such as transactions, reserve moves, and lineup changes remain league events.
- Event IDs are deterministic and retries are idempotent.
- Observation timestamps do not create duplicate event IDs on retry.
- Source failure is freshness metadata, never a factual state transition.
- Ongoing matchups are not written as `MATCHUP_FINAL`; Tuesday/finalization explicitly authorizes final matchup events.
- Writes stage and validate before replacing persistent files.
- Current publication output is unchanged in this phase.

---

## File map

**Create**
- `editorial_desk/chronicle_events.py` — event model and semantic deterministic IDs.
- `editorial_desk/chronicle_store.py` — ledger/current-state/manifests/coverage storage with atomic writes.
- `editorial_desk/chronicle_collect.py` — lightweight global + per-league pulse collection and normalization.
- `tests/test_chronicle_events.py`
- `tests/test_chronicle_store.py`
- `tests/test_chronicle_collect.py`
- `tests/test_chronicle_cli.py`
- `.github/workflows/editorial-desk-chronicle.yml`

**Modify**
- `editorial_desk/cli.py`
- `editorial_desk/config.py`
- `tests/test_config.py`
- `README.md`

---

### Task 1: Bootstrap an orphan `chronicle-data` branch

**Files:**
- Modify: `README.md`
- No production Python change.

**Interfaces:**
- One-time repository operation creating an orphan branch with no application-code dependency.

- [ ] **Step 1: Verify branch absence before bootstrap**

Run:

```bash
git ls-remote --heads origin chronicle-data
```

Expected for first bootstrap: no matching ref.

- [ ] **Step 2: Create the orphan branch in an isolated worktree**

```bash
git worktree add --detach ../editorial-chronicle-data main
cd ../editorial-chronicle-data
git switch --orphan chronicle-data
git rm -rf .
printf '%s\n' '# Editorial Chronicle Data' > README.md
mkdir -p registry leagues cross_league coverage manifests diagnostics
touch registry/.gitkeep leagues/.gitkeep cross_league/.gitkeep coverage/.gitkeep manifests/.gitkeep diagnostics/.gitkeep
git add README.md registry leagues cross_league coverage manifests diagnostics
git commit -m "chore: initialize Chronicle data branch"
git push origin chronicle-data
```

Do not reuse this branch to execute application code.

- [ ] **Step 3: Document branch purpose and recovery rule**

README must state that application code comes from `main`, Chronicle state comes from `chronicle-data`, and normal automation never force-pushes either.

- [ ] **Step 4: Commit README documentation on the feature branch**

```bash
git add README.md
git commit -m "docs: document Chronicle data branch"
```

---

### Task 2: Define semantic deterministic Chronicle events

**Files:**
- Create: `editorial_desk/chronicle_events.py`
- Test: `tests/test_chronicle_events.py`

**Interfaces:**
- `ChronicleEvent`
- `event_id_for(identity: dict[str, Any]) -> str`
- `make_event(...) -> ChronicleEvent`
- `ChronicleEvent.to_dict() -> dict[str, Any]`

- [ ] **Step 1: Write failing canonical-ID tests**

```python
from editorial_desk.chronicle_events import event_id_for, make_event


def test_event_id_is_stable_across_dict_order():
    a = {"event_type": "TRADE", "source_ref": "tx-1", "entities": {"b": 2, "a": 1}}
    b = {"entities": {"a": 1, "b": 2}, "source_ref": "tx-1", "event_type": "TRADE"}
    assert event_id_for(a) == event_id_for(b)


def test_retry_observation_time_does_not_change_status_event_id():
    common = dict(
        event_type="PLAYER_STATUS_CHANGE", source="sleeper_players",
        source_ref="player:1234:status", league_key=None, season="2026", week=2,
        provenance="observed_live", entities={"player_id": "1234"},
        before={"status": "Questionable"}, after={"status": "Out"},
        observed_before="2026-09-16T17:05:00+00:00",
    )
    first = make_event(**common, observed_at="2026-09-16T21:04:00+00:00", observed_after="2026-09-16T21:04:00+00:00")
    retry = make_event(**common, observed_at="2026-09-16T21:06:00+00:00", observed_after="2026-09-16T21:06:00+00:00")
    assert first.event_id == retry.event_id
```

The semantic identity of a polled transition includes the prior-observation anchor (`observed_before`) plus before/after state, but excludes retry-dependent `observed_at`/`observed_after`.

- [ ] **Step 2: Run and verify failure**

Run: `python -m pytest tests/test_chronicle_events.py -q`

- [ ] **Step 3: Implement event model**

```python
@dataclass(frozen=True)
class ChronicleEvent:
    event_id: str
    schema_version: int
    event_type: str
    league_key: str | None
    season: str
    week: int | None
    occurred_at: str | None
    observed_at: str
    observed_before: str | None
    observed_after: str | None
    source: str
    source_ref: str
    provenance: str
    entities: dict[str, Any]
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    evidence: dict[str, Any]
    cross_league_key: str | None = None
    correction_of: str | None = None
```

`make_event()` builds the hash identity from stable semantic fields. For source-exact records, `source_ref` + source event identity anchors the hash. For polled transitions, identity includes `observed_before` but not retry-dependent observation completion time.

- [ ] **Step 4: Add correction-event serialization test**

Assert `correction_of` survives round-trip serialization and does not mutate the corrected event.

- [ ] **Step 5: Run tests and commit**

```bash
python -m pytest tests/test_chronicle_events.py -q
git add editorial_desk/chronicle_events.py tests/test_chronicle_events.py
git commit -m "feat: add deterministic Chronicle event model"
```

---

### Task 3: Add atomic append-only Chronicle store

**Files:**
- Create: `editorial_desk/chronicle_store.py`
- Test: `tests/test_chronicle_store.py`

**Interfaces:**
- `ChronicleStore(root: Path)`
- `append_events(events: Iterable[ChronicleEvent]) -> AppendResult`
- `read_events(league_key: str | None, season: str) -> list[dict[str, Any]]`
- `read_current_state(scope: str) -> dict[str, Any]`
- `write_current_state(scope: str, state: dict[str, Any]) -> None`
- `write_manifest(run_id: str, manifest: dict[str, Any]) -> Path`
- `read_coverage() -> dict[str, Any]`
- `write_coverage(value: dict[str, Any]) -> None`

- [ ] **Step 1: Write failing idempotency test**

Append the same event twice and assert first result `added == 1`, second `added == 0`, ledger length remains one.

- [ ] **Step 2: Write failing atomicity test**

Monkeypatch the final replace operation to raise. Assert the pre-existing ledger bytes remain unchanged.

- [ ] **Step 3: Implement canonical JSONL merge + atomic replacement**

Merge by `event_id`, preserve one record per ID, sort deterministically, write sibling temp file, flush/fsync, then `Path.replace()`.

- [ ] **Step 4: Implement current-state, manifest, and coverage JSON helpers**

Current observation state is diagnostic/live-comparison state, not historical source truth. Store it under `diagnostics/current_state/` so later retention policy can distinguish it from permanent ledger/history.

- [ ] **Step 5: Run tests and commit**

```bash
python -m pytest tests/test_chronicle_store.py -q
git add editorial_desk/chronicle_store.py tests/test_chronicle_store.py
git commit -m "feat: add atomic Chronicle filesystem store"
```

---

### Task 4: Build a truly lightweight pulse collector

**Files:**
- Create: `editorial_desk/chronicle_collect.py`
- Test: `tests/test_chronicle_collect.py`

**Interfaces:**
- `collect_pulse(leagues, client, store, week, observed_at, finalize_matchups=False) -> RunManifest`
- Private `collect_global_player_state(...)`
- Private `collect_league_pulse(...)`

**Minimum source calls per pulse:**
- once globally: `nfl_state()`, `players()`
- per league: `league()`, `users()` only if identity metadata is needed, `rosters()`, `matchups(week)`, `transactions(week)`, `traded_picks()` only when change detection requires it
- no full-season matchup loop
- no all-week transaction loop
- no drafts/brackets
- no rankings source
- no nflverse deep enrichment

- [ ] **Step 1: Write failing source-call budget test**

Use a fake client recording method calls. Assert pulse never calls `drafts`, `winners_bracket`, `losers_bracket`, `projections`, or any ranking/nflverse client.

- [ ] **Step 2: Write cross-league status deduplication test**

Two leagues roster the same player. A Questionable -> Out change produces exactly one cross-league `PLAYER_STATUS_CHANGE` event with `league_key is None`, while each league may separately produce reserve/lineup/transaction events.

- [ ] **Step 3: Write source-failure test**

If global player directory refresh fails, preserve previous current-state health data as stale, create no Healthy transitions, and record `player_health="stale"`.

- [ ] **Step 4: Write ongoing-vs-final matchup test**

With `finalize_matchups=False`, score changes create observation/current-state updates but no `MATCHUP_FINAL`. With `finalize_matchups=True` for a completed period, one deterministic final event is emitted per matchup.

- [ ] **Step 5: Implement global normalizers**

Global player-state comparison produces cross-league NFL status events and writes `diagnostics/current_state/global_players.json`.

- [ ] **Step 6: Implement league normalizers**

Normalize:

```python
_normalize_transactions(...)
_normalize_reserve_changes(...)
_normalize_lineup_changes(...)
_normalize_matchup_finals(...)
```

Sleeper transaction `transaction_id` anchors source-exact event identity.

- [ ] **Step 7: Run tests and commit**

```bash
python -m pytest tests/test_chronicle_collect.py -q
git add editorial_desk/chronicle_collect.py tests/test_chronicle_collect.py
git commit -m "feat: add lightweight Chronicle pulse collector"
```

---

### Task 5: Add Chronicle CLI commands and partial-failure manifests

**Files:**
- Modify: `editorial_desk/cli.py`
- Modify: `editorial_desk/config.py`
- Modify: `tests/test_config.py`
- Create: `tests/test_chronicle_cli.py`

**Interfaces:**

```text
python -m editorial_desk chronicle-collect \
  --config config/leagues.json \
  --week 2 \
  --chronicle-root ../chronicle-data \
  [--finalize-matchups]
```

`RunManifest` records run timestamp, requested week, attempted/succeeded/failed leagues, global/per-league source freshness, event added/skipped counts, warnings/errors, and input/output Chronicle revisions when caller supplies them.

- [ ] **Step 1: Write parser tests**

Assert `--finalize-matchups` defaults false and only Tuesday/completed-period orchestration enables it.

- [ ] **Step 2: Verify data-only leagues remain Chronicle eligible**

Existing `load_leagues()` must continue returning enabled publication-disabled leagues.

- [ ] **Step 3: Write partial-failure test**

One fake league raises `requests.RequestException`; another succeeds. Assert successful events persist and manifest isolates the failure.

- [ ] **Step 4: Implement CLI orchestration around `collect_pulse`**

Do not call `collector.collect_league()` or `enriched_collector.collect_all()` from this command.

- [ ] **Step 5: Run focused regression tests**

```bash
python -m pytest tests/test_chronicle_cli.py tests/test_config.py tests/test_collector.py -q
```

- [ ] **Step 6: Commit**

```bash
git add editorial_desk/cli.py editorial_desk/config.py tests/test_chronicle_cli.py tests/test_config.py
git commit -m "feat: add Chronicle collection CLI"
```

---

### Task 6: Add source freshness and first-observation coverage markers

**Files:**
- Modify: `editorial_desk/chronicle_collect.py`
- Modify: `editorial_desk/chronicle_store.py`
- Test: `tests/test_chronicle_collect.py`
- Test: `tests/test_chronicle_store.py`

**Interfaces:**
- Freshness values: `fresh`, `stale`, `unavailable`.
- `coverage/live_observation.json` first-success markers for global player health and per-league lineup/reserve observation.

- [ ] **Step 1: Write first-success marker tests**

Failed first health fetch creates no coverage start. First successful fetch sets marker. Later success never moves marker forward.

- [ ] **Step 2: Implement monotonic coverage updates**

Coverage start can change only through explicit future migration/maintenance code, not ordinary collection.

- [ ] **Step 3: Run tests and commit**

```bash
python -m pytest tests/test_chronicle_collect.py tests/test_chronicle_store.py -q
git add editorial_desk/chronicle_collect.py editorial_desk/chronicle_store.py tests/test_chronicle_collect.py tests/test_chronicle_store.py
git commit -m "feat: track Chronicle freshness and live coverage"
```

---

### Task 7: Add serialized daily/pulse workflow

**Files:**
- Create: `.github/workflows/editorial-desk-chronicle.yml`
- Modify: `README.md`

**Interfaces:**
- One global writer concurrency group: `editorial-chronicle-writer`.
- Code checkout from `main`; separate data checkout from `chronicle-data`.

**Exact in-season schedule (America/New_York):**
- daily baseline: 06:17 every day
- additional Wednesday-Sunday pulses: 12:17, 17:17, and 21:17

- [ ] **Step 1: Add workflow permissions/concurrency**

```yaml
permissions:
  contents: write

concurrency:
  group: editorial-chronicle-writer
  cancel-in-progress: false
```

- [ ] **Step 2: Add exact scheduled triggers and manual dispatch**

Use the schedule above. Scheduled jobs determine current active NFL week from `nfl_state`; they do not use `--finalize-matchups`.

- [ ] **Step 3: Check out application and data separately**

`actions/checkout` path `app` for `main`; path `chronicle` for `chronicle-data`. Execute Python only from `app`.

- [ ] **Step 4: Run full tests before mutation**

Run `python -m pytest -q` before `chronicle-collect`.

- [ ] **Step 5: Commit/push only changed Chronicle files**

If `git status --porcelain` is empty, no commit. If push is rejected, refetch data branch, rerun collection against new head, and retry normal push. Never force-push.

- [ ] **Step 6: Document workflow and schedule**

Document baseline vs pulse and emphasize that full Tuesday editorial enrichment remains in the separate delivery workflow.

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/editorial-desk-chronicle.yml README.md
git commit -m "ci: add serialized Chronicle pulse workflow"
```

---

### Task 8: Phase 1 verification gate

- [ ] **Step 1: Run complete suite**

Run: `python -m pytest -q`

- [ ] **Step 2: Verify retry idempotency**

Run the same fixture pulse twice. Expected second run: zero new events and no changed permanent ledger bytes.

- [ ] **Step 3: Verify source-call budget**

Pulse tests must prove no full flagship/deep enrichment methods are called.

- [ ] **Step 4: Verify Git safety**

Search workflow/code for `push --force`, destructive resets of `chronicle-data`, or branch deletion. Expected: none.

- [ ] **Step 5: Verify publication regression**

Existing collector/review/email tests remain green and current Tuesday publication files remain unchanged by Phase 1.

- [ ] **Step 6: Commit verification fixes only if needed**

```bash
git add -A
git commit -m "test: close Chronicle foundation regressions"
```
