# Chronicle Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic Event Ledger records, safe local Chronicle storage/materialization primitives, lightweight live collection, run manifests, and a serialized GitHub Actions writer path without changing publication behavior yet.

**Architecture:** New focused Chronicle modules sit beside the existing collector. Existing Sleeper/NFL collection remains read-only; Chronicle normalization converts snapshots/source state into deterministic events. A filesystem store writes to a separately checked-out `chronicle-data` tree using staging and atomic replacement, while the workflow serializes all data-branch writers.

**Tech Stack:** Python 3.12, dataclasses, hashlib/json/pathlib/tempfile/shutil, requests, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-16-editorial-desk-v2-final-design.md`

## Global Constraints

- All Sleeper interaction remains read-only.
- Normal automation never force-pushes `chronicle-data`.
- Event IDs are deterministic and repeated collection is idempotent.
- Source failures are represented as freshness state, never as factual transitions.
- Exact source timestamps and observed intervals remain distinguishable.
- Chronicle writes stage and validate before replacing current files.
- Publication output must remain behaviorally unchanged in this phase.

---

## File map

**Create**
- `editorial_desk/chronicle_events.py` — event dataclass, canonical serialization, deterministic event IDs.
- `editorial_desk/chronicle_store.py` — append-only ledger merge, atomic writes, run manifests, coverage metadata.
- `editorial_desk/chronicle_collect.py` — normalize current Sleeper snapshot facts into Chronicle events and source freshness.
- `tests/test_chronicle_events.py`
- `tests/test_chronicle_store.py`
- `tests/test_chronicle_collect.py`
- `.github/workflows/editorial-desk-chronicle.yml` — daily/pulse writer workflow.

**Modify**
- `editorial_desk/cli.py` — add `chronicle-collect` command.
- `editorial_desk/config.py` — expose Chronicle eligibility for every configured league without changing publication enablement.
- `tests/test_config.py`
- `README.md` — document the data branch and safe collection commands.

---

### Task 1: Define deterministic Chronicle events

**Files:**
- Create: `editorial_desk/chronicle_events.py`
- Test: `tests/test_chronicle_events.py`

**Interfaces:**
- Produces: `ChronicleEvent`, `event_id_for(payload: dict[str, Any]) -> str`, `make_event(...) -> ChronicleEvent`, `ChronicleEvent.to_dict() -> dict[str, Any]`.
- Consumes: only standard library.

- [ ] **Step 1: Write failing event-ID and serialization tests**

```python
from editorial_desk.chronicle_events import event_id_for, make_event


def test_event_id_is_stable_across_dict_order():
    left = {"event_type": "TRADE", "source_ref": "tx-1", "entities": {"b": 2, "a": 1}}
    right = {"entities": {"a": 1, "b": 2}, "source_ref": "tx-1", "event_type": "TRADE"}
    assert event_id_for(left) == event_id_for(right)


def test_make_event_preserves_observation_window_without_fake_occurred_at():
    event = make_event(
        event_type="PLAYER_STATUS_CHANGE",
        source="sleeper_players",
        source_ref="player:1234:status",
        league_key=None,
        season="2026",
        week=2,
        provenance="observed_live",
        entities={"player_id": "1234"},
        before={"status": "Questionable"},
        after={"status": "Out"},
        observed_at="2026-09-16T21:04:00+00:00",
        observed_before="2026-09-16T17:05:00+00:00",
        observed_after="2026-09-16T21:04:00+00:00",
    )
    row = event.to_dict()
    assert row["occurred_at"] is None
    assert row["observed_before"] == "2026-09-16T17:05:00+00:00"
    assert row["observed_after"] == "2026-09-16T21:04:00+00:00"
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/test_chronicle_events.py -q`

Expected: import failure because `chronicle_events.py` does not exist.

- [ ] **Step 3: Implement canonical event model**

```python
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any

SCHEMA_VERSION = 1


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def event_id_for(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()[:24]


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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_event(*, event_type: str, source: str, source_ref: str, league_key: str | None,
               season: str, week: int | None, provenance: str, entities: dict[str, Any],
               observed_at: str, occurred_at: str | None = None,
               observed_before: str | None = None, observed_after: str | None = None,
               before: dict[str, Any] | None = None, after: dict[str, Any] | None = None,
               evidence: dict[str, Any] | None = None, cross_league_key: str | None = None,
               correction_of: str | None = None) -> ChronicleEvent:
    identity = {
        "schema_version": SCHEMA_VERSION,
        "event_type": event_type,
        "league_key": league_key,
        "season": season,
        "week": week,
        "source": source,
        "source_ref": source_ref,
        "entities": entities,
        "before": before,
        "after": after,
        "occurred_at": occurred_at,
        "observed_before": observed_before,
        "observed_after": observed_after,
    }
    return ChronicleEvent(
        event_id=event_id_for(identity), schema_version=SCHEMA_VERSION,
        event_type=event_type, league_key=league_key, season=season, week=week,
        occurred_at=occurred_at, observed_at=observed_at,
        observed_before=observed_before, observed_after=observed_after,
        source=source, source_ref=source_ref, provenance=provenance,
        entities=entities, before=before, after=after, evidence=evidence or {},
        cross_league_key=cross_league_key, correction_of=correction_of,
    )
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_chronicle_events.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add editorial_desk/chronicle_events.py tests/test_chronicle_events.py
git commit -m "feat: add deterministic Chronicle event model"
```

---

### Task 2: Add append-only Chronicle filesystem store

**Files:**
- Create: `editorial_desk/chronicle_store.py`
- Test: `tests/test_chronicle_store.py`

**Interfaces:**
- Consumes: `ChronicleEvent.to_dict()`.
- Produces: `ChronicleStore(root: Path)`, `append_events(events) -> AppendResult`, `write_manifest(manifest)`, `read_events(league_key, season)`, `write_coverage(...)`.

- [ ] **Step 1: Write failing idempotency and atomic-write tests**

```python
from pathlib import Path
from editorial_desk.chronicle_events import make_event
from editorial_desk.chronicle_store import ChronicleStore


def _event():
    return make_event(
        event_type="MATCHUP_FINAL", source="sleeper", source_ref="league:1:week:1:matchup:7",
        league_key="demo", season="2026", week=1, provenance="source_exact",
        entities={"matchup_id": 7}, observed_at="2026-09-15T12:00:00+00:00",
        evidence={"winner": 1, "loser": 2},
    )


def test_append_events_is_idempotent(tmp_path: Path):
    store = ChronicleStore(tmp_path)
    first = store.append_events([_event()])
    second = store.append_events([_event()])
    assert first.added == 1
    assert second.added == 0
    assert len(store.read_events("demo", "2026")) == 1
```

- [ ] **Step 2: Run failing test**

Run: `python -m pytest tests/test_chronicle_store.py -q`

Expected: import failure.

- [ ] **Step 3: Implement `ChronicleStore` with staging + replace**

Use line-delimited canonical JSON sorted by `event_id`, merge old/new by ID, write to a sibling temporary file, fsync, then `Path.replace()` the destination. Return a frozen `AppendResult(added: int, skipped: int, paths: tuple[Path, ...])`.

- [ ] **Step 4: Add manifest and coverage tests**

Test that `manifests/<run_id>.json` and `coverage/live_observation.json` are valid sorted JSON and survive repeated updates.

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_chronicle_store.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add editorial_desk/chronicle_store.py tests/test_chronicle_store.py
git commit -m "feat: add atomic append-only Chronicle store"
```

---

### Task 3: Normalize live Sleeper facts into events

**Files:**
- Create: `editorial_desk/chronicle_collect.py`
- Test: `tests/test_chronicle_collect.py`

**Interfaces:**
- Consumes existing snapshot dictionaries from `collector.collect_league` and previous observation state from Chronicle coverage/current-state JSON.
- Produces `normalize_snapshot(snapshot, previous_state, observed_at) -> CollectionDelta` with `events`, `current_state`, `source_freshness`.

- [ ] **Step 1: Write failing tests for matchups, transactions, IR, and health transitions**

Include tests proving:

```python
assert {event.event_type for event in delta.events} >= {"TRADE", "IR_RESERVE_CHANGE"}
assert health_event.occurred_at is None
assert health_event.observed_before == previous_timestamp
assert health_event.observed_after == current_timestamp
```

Also test that missing player-health input marks `source_freshness["player_health"] == "stale"` and creates no Healthy transition.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/test_chronicle_collect.py -q`

- [ ] **Step 3: Implement focused normalizers**

Create private functions:

```python
_normalize_matchup_finals(...)
_normalize_transactions(...)
_normalize_roster_reserve(...)
_normalize_player_status(...)
_normalize_lineups(...)
```

Transaction event IDs use Sleeper `transaction_id` in `source_ref`. Matchup finals use league/season/week/matchup identity. Health transitions compare prior observed player state to current state and never infer a transition if the source is unavailable.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_chronicle_collect.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add editorial_desk/chronicle_collect.py tests/test_chronicle_collect.py
git commit -m "feat: normalize live league state into Chronicle events"
```

---

### Task 4: Add Chronicle CLI collection command

**Files:**
- Modify: `editorial_desk/cli.py`
- Modify: `editorial_desk/config.py`
- Test: `tests/test_config.py`
- Create: `tests/test_chronicle_cli.py`

**Interfaces:**
- Produces CLI:

```text
python -m editorial_desk chronicle-collect \
  --config config/leagues.json \
  --publications config/publications.json \
  --week 2 \
  --chronicle-root ../chronicle-data
```

- [ ] **Step 1: Add failing parser test**

Assert parser accepts `chronicle-collect`, `--config`, `--publications`, `--week`, and `--chronicle-root`.

- [ ] **Step 2: Add config test proving publication-disabled leagues remain Chronicle-eligible**

Use a data-only league fixture and assert `load_leagues()` returns it even though no publication packet is generated.

- [ ] **Step 3: Run tests and verify failure**

Run: `python -m pytest tests/test_chronicle_cli.py tests/test_config.py -q`

- [ ] **Step 4: Implement command orchestration**

The command should:

```python
leagues = load_leagues(args.config)
state = sleeper.nfl_state()
for league in leagues:
    snapshot = collect_league(...)
    previous = store.read_current_state(league.key)
    delta = normalize_snapshot(snapshot, previous, observed_at)
    store.append_events(delta.events)
    store.write_current_state(league.key, delta.current_state)
store.write_manifest(...)
```

Do not generate publication dossiers in this command.

- [ ] **Step 5: Run focused and existing collector tests**

Run: `python -m pytest tests/test_chronicle_cli.py tests/test_config.py tests/test_collector.py -q`

- [ ] **Step 6: Commit**

```bash
git add editorial_desk/cli.py editorial_desk/config.py tests/test_chronicle_cli.py tests/test_config.py
git commit -m "feat: add Chronicle collection command"
```

---

### Task 5: Add run manifests and source freshness reporting

**Files:**
- Modify: `editorial_desk/chronicle_collect.py`
- Modify: `editorial_desk/chronicle_store.py`
- Test: `tests/test_chronicle_collect.py`
- Test: `tests/test_chronicle_store.py`

**Interfaces:**
- `RunManifest` fields: run timestamp, attempted leagues, success/failure per league, freshness per source, added/skipped events, warnings/errors, input/output revisions where supplied.

- [ ] **Step 1: Write failing partial-failure test**

Simulate one league throwing a `requests.RequestException` while another succeeds. Assert successful league events are retained and manifest records failure only for the broken league.

- [ ] **Step 2: Implement `RunManifest` and per-league exception isolation**

Catch source/league failures at the league boundary, not around the whole run. Preserve successful normalized events and mark failures explicitly.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_chronicle_collect.py tests/test_chronicle_store.py -q`

- [ ] **Step 4: Commit**

```bash
git add editorial_desk/chronicle_collect.py editorial_desk/chronicle_store.py tests/test_chronicle_collect.py tests/test_chronicle_store.py
git commit -m "feat: record Chronicle run freshness and partial failures"
```

---

### Task 6: Add serialized Chronicle writer workflow

**Files:**
- Create: `.github/workflows/editorial-desk-chronicle.yml`
- Modify: `README.md`

**Interfaces:**
- Scheduled lightweight morning + Wednesday-Sunday pulse runs.
- Shared concurrency group: `editorial-chronicle-writer`.
- Separate checkout paths: application repo and `chronicle-data` worktree/checkout.

- [ ] **Step 1: Add workflow with safe permissions and concurrency**

Required YAML structure:

```yaml
permissions:
  contents: write

concurrency:
  group: editorial-chronicle-writer
  cancel-in-progress: false
```

Schedule one morning baseline daily and three Wednesday-Sunday pulses. All scheduled/manual writer jobs must use the same concurrency group.

- [ ] **Step 2: Make the workflow check out `main` and `chronicle-data` separately**

Use two `actions/checkout` steps with different `path` values. Never execute application code from the data checkout.

- [ ] **Step 3: Run tests before Chronicle mutation**

The workflow must run `python -m pytest -q` before the collection/write step.

- [ ] **Step 4: Commit only changed data**

Shell logic should perform `git status --porcelain`, skip commit if empty, otherwise commit with a deterministic descriptive message and push normally. On push conflict, refetch/re-run collection rather than force-push.

- [ ] **Step 5: Document operational model in README**

Document branch purpose, manual dispatch, no Sleeper writes, and that publication delivery remains in the existing Tuesday workflow until Phase 4.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/editorial-desk-chronicle.yml README.md
git commit -m "ci: add serialized Chronicle collection workflow"
```

---

### Task 7: Phase 1 regression gate

**Files:**
- No new files unless failures require fixes.

- [ ] **Step 1: Run complete suite**

Run: `python -m pytest -q`

Expected: all existing tests plus Chronicle tests PASS.

- [ ] **Step 2: Verify publication behavior unchanged**

Run existing dossier/review/email tests and confirm no new Chronicle command changes the current `collect` output schema unless explicitly additive and backward-compatible.

- [ ] **Step 3: Review workflow diff for destructive Git operations**

Search: `git push --force`, `git reset --hard` against `chronicle-data`, and branch deletion commands. Expected: none.

- [ ] **Step 4: Commit any regression-only fixes**

```bash
git add -A
git commit -m "test: close Chronicle foundation regressions"
```

Only create this commit if fixes were needed.
