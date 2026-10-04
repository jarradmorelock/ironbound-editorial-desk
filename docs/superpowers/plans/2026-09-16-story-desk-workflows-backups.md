# Story Desk, Workflows, and Backups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the Ironbound/Unbound Magazine Story Desk, Chronicle/Event Ledger-aware Wednesday deltas, first-Tuesday validated email backups, pre-major-change backup gating, diagnostic retention cleanup, and final Chronicle-aware editorial workflows.

**Architecture:** Story Desk consumes normalized features, Chronicle query results, Event Ledger evidence, and explicitly supplied external editorial inputs. It never owns source truth. Backup/archive logic is separate, deterministic, and validated before attachment. Tuesday pins one Chronicle revision for the editorial build; Wednesday reads events after that baseline.

**Tech Stack:** Python 3.12, dataclasses/json/pathlib/zipfile/hashlib/zoneinfo, existing SMTP emailer, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-16-editorial-desk-v2-final-design.md`

## Global Constraints

- Story Desk is enabled only for Ironbound Weekly and Unbound Weekly through explicit config capability.
- Story candidates are editorial work products, not Chronicle truth.
- Every candidate fact must point to ledger evidence or a derived Chronicle fact with provenance/coverage metadata.
- Supported temporal sequence is allowed; unsupported motive/causation is not.
- Official Power Rankings are external; internal metrics never masquerade as official ranks.
- WAR is optional external enrichment only.
- Wednesday supplements report only evidence newer than Tuesday's pinned baseline.
- First Tuesday is evaluated in `America/New_York`.
- Monthly archive attaches to the normal Tuesday email; no separate monthly email.
- Major Chronicle-affecting maintenance stops when backup creation, validation, or SMTP acceptance fails.
- Diagnostic cleanup never touches permanent ledger/history/registry/coverage or backup receipts.

---

## File map

**Create**
- `editorial_desk/chronicle_queries.py`
- `editorial_desk/story_models.py`
- `editorial_desk/story_desk.py`
- `editorial_desk/external_inputs.py`
- `editorial_desk/chronicle_backup.py`
- `editorial_desk/retention.py`
- `tests/test_chronicle_queries.py`
- `tests/test_story_desk.py`
- `tests/test_external_inputs.py`
- `tests/test_chronicle_backup.py`
- `tests/test_chronicle_maintenance_gate.py`
- `tests/test_retention.py`
- `tests/test_editorial_v2_e2e.py`

**Modify**
- `editorial_desk/review.py`
- `editorial_desk/enriched_collector.py`
- `editorial_desk/supplement.py`
- `editorial_desk/emailer.py`
- `editorial_desk/cli.py`
- `.github/workflows/editorial-desk-dry-run.yml`
- `.github/workflows/editorial-desk-chronicle.yml`
- `README.md`

---

### Task 1: Add read-only Chronicle query API

**Files:** Create `editorial_desk/chronicle_queries.py`, `tests/test_chronicle_queries.py`.

**Interfaces:**

```python
class ChronicleQueries:
    def head_to_head(self, league_key, left_key, right_key) -> dict | None: ...
    def current_streak(self, league_key, left_key, right_key) -> dict | None: ...
    def season_records(self, league_key, season) -> dict: ...
    def recent_events(self, league_key, since, event_types=None) -> list[dict]: ...
    def player_events(self, player_id, since=None) -> list[dict]: ...
    def transactions_for_entity(self, league_key, entity_key, since=None) -> list[dict]: ...
```

- [ ] Write tests proving H2H, playoff meetings, streak, and coverage metadata match materialized Chronicle exactly.
- [ ] Implement summary reads from materialized indexes and detail reads from ledger.
- [ ] Return `coverage_complete`/warnings with historical summaries.
- [ ] Run `python -m pytest tests/test_chronicle_queries.py -q` and commit `feat: add read-only Chronicle queries`.

---

### Task 2: Define Story Candidate evidence model

**Files:** Create `editorial_desk/story_models.py`; start `tests/test_story_desk.py`.

**Interfaces:**

```python
@dataclass(frozen=True)
class StoryEvidenceRef:
    evidence_id: str
    source: str
    description: str

@dataclass(frozen=True)
class StoryCandidate:
    candidate_id: str
    candidate_type: str
    title_concepts: tuple[str, ...]
    trigger_reasons: tuple[str, ...]
    evidence_refs: tuple[StoryEvidenceRef, ...]
    facts: tuple[dict, ...]
    historical_context: tuple[dict, ...]
    entities: dict
    evidence_strength: str
    signal_score: float
    signal_components: dict[str, float]
    cautions: tuple[str, ...]
    editorial_angles: tuple[str, ...]
    graphic_ideas: tuple[str, ...]
    depth_class: str
```

- [ ] Test deterministic candidate ID from type + stable core evidence IDs.
- [ ] Test serialization rejects/flags factual rows without evidence or derived-fact provenance.
- [ ] Implement immutable models and commit `feat: define Story Desk evidence model`.

---

### Task 3: Add optional official editorial-input loader

**Files:** Create `editorial_desk/external_inputs.py`, `tests/test_external_inputs.py`.

**Interface:** `load_external_inputs(path: Path | None, publication_key: str) -> ExternalEditorialInputs`.

Accepted optional JSON shape:

```json
{
  "publication_key": "ironbound_weekly",
  "official_power_rankings": [
    {"franchise_key": "scenic_city", "rank": 1},
    {"franchise_key": "mormonts", "rank": 15}
  ],
  "war": [],
  "notes": [],
  "source_metadata": {"label": "Ironbound Power Rankings", "week": 7}
}
```

- [ ] Missing path returns an empty valid object.
- [ ] Duplicate/invalid ranks raise `ExternalInputError`.
- [ ] Publication-key mismatch raises `ExternalInputError`.
- [ ] Loader performs no automatic fetch from the separate Power Rankings workflow.
- [ ] Run tests and commit `feat: accept optional official editorial inputs`.

---

### Task 4: Implement all approved Story Desk candidate families

**Files:** Create `editorial_desk/story_desk.py`; extend `tests/test_story_desk.py`.

**Interface:**

```python
build_story_desk(
    publication_key,
    snapshot,
    dossier,
    chronicle: ChronicleQueries,
    external_inputs: ExternalEditorialInputs,
) -> dict[str, Any]
```

**Required candidate families and focused producers:**

```python
_rivalry_history_candidates(...)
_injury_shock_candidates(...)
_reaction_transaction_candidates(...)
_waiver_run_candidates(...)
_trade_afterlife_candidates(...)
_trade_market_shift_candidates(...)
_asset_journey_candidates(...)
_roster_architecture_candidates(...)
_dynasty_identity_candidates(...)
_historic_upset_candidates(...)
_scoring_record_candidates(...)
_streak_candidates(...)
_repeated_close_loss_candidates(...)
_former_player_matchup_candidates(...)
_playoff_rematch_candidates(...)
_lineup_catastrophe_candidates(...)
_division_pressure_candidates(...)
_cross_league_shock_candidates(...)
_david_goliath_candidates(...)
```

- [ ] Scope test: Ironbound/Unbound => available; every newspaper => disabled.
- [ ] Rivalry test: candidate record exactly equals Chronicle value and includes coverage metadata.
- [ ] Injury-shock test: status change itself can be a candidate when magnitude/roster dependency evidence exists.
- [ ] Reaction-transaction test: observed status interval + later exact transaction produces temporal candidate with explicit no-motive caution.
- [ ] Waiver-run test: multiple league transactions for same NFL/player need a minimum count threshold and evidence list.
- [ ] Trade-afterlife/asset-journey tests: chain picks/players through draft and subsequent transactions without losing event IDs.
- [ ] Trade-market-shift test: unusual trade volume/concentration compares against current season baseline.
- [ ] Roster architecture/dynasty identity tests: compare current/future roster composition using available normalized data, not prose assumptions.
- [ ] Historic upset/scoring-record/streak/repeated-close-loss tests: objective thresholds and exact history.
- [ ] Former-player matchup test: player transaction history links current roster to former franchise and current matchup.
- [ ] Playoff-rematch test: prior playoff meeting plus current scheduled matchup.
- [ ] Lineup-catastrophe test: points-left/flip evidence exceeds objective threshold.
- [ ] Division-pressure test only for leagues with real divisions; never run this against Volunteer Voice.
- [ ] Cross-league shock test: one global NFL event linked to reactions in multiple tracked leagues.
- [ ] David-v-Goliath test only when validated official rankings are supplied.

**Signal scoring:** measurable components only: rarity, historical depth, timing proximity, affected-league count, magnitude, playoff relevance, transaction cost, signal convergence. Preserve component breakdown.

**Candidate selection:** deterministic descending signal/evidence ordering, maximum 20; never pad weak stories to hit 12.

- [ ] Run `python -m pytest tests/test_story_desk.py -q` and commit `feat: generate evidence-backed magazine stories`.

---

### Task 5: Add causation, ranking, WAR, voice, depth, and graphic guardrails

**Files:** Modify `editorial_desk/story_desk.py`, `tests/test_story_desk.py`.

- [ ] Without official rankings, assert no `No. 1`, ranking-disparity, or David-v-Goliath claim derived from substitute metrics.
- [ ] With official rankings, ranking-based candidate may be generated and cites external-input provenance.
- [ ] WAR facts appear only when validated WAR input exists.
- [ ] Every status/reaction candidate includes a caution when motive is unsupported.
- [ ] Ironbound headline concepts use forge/metal/fire/Crown/pressure vocabulary; Unbound uses chain/link/tension/break vocabulary; evidence payload remains identical in semantics.
- [ ] Depth class is based on evidence breadth: cover 4-6 pages, major 2-4, analysis 1-2, sidebar/graphic, brief.
- [ ] Graphic suggestions reference available data such as rivalry timeline, score trajectory, trade chain, division table, workload chart.
- [ ] Run tests and commit `feat: add Story Desk editorial guardrails`.

---

### Task 6: Write Tuesday Story Desk artifacts

**Files:** Modify `editorial_desk/enriched_collector.py`, `editorial_desk/review.py`, `editorial_desk/cli.py`; extend `tests/test_story_desk.py`.

**Outputs for story-desk-enabled publications:**
- `story_desk.json`
- `story_desk.md`

**Optional CLI:** `--external-inputs-dir PATH`.

- [ ] Test Ironbound/Unbound artifacts exist and newspaper artifacts do not.
- [ ] Render each candidate with headline concepts, trigger, evidence strength/score, facts, history, cautions, angles, graphics, depth, evidence IDs.
- [ ] Include external-input availability block: `power_rankings: supplied/not_supplied`, `war: supplied/not_supplied`.
- [ ] Run relevant collector/story tests and commit `feat: write magazine Story Desk packets`.

---

### Task 7: Make Wednesday supplements Event Ledger-aware

**Files:** Modify `editorial_desk/supplement.py`; create/extend `tests/test_supplement_events.py`.

**Interface:**

```python
generate_supplements(
    baseline_root,
    current_root,
    output_root,
    week,
    chronicle_root=None,
    baseline_time=None,
)
```

- [ ] New post-Tuesday transaction/status event produces supplement even when broad dossier comparison misses it.
- [ ] Event already represented by Tuesday baseline does not repeat.
- [ ] Health event rendering shows observed interval, not invented exact change time.
- [ ] New event is rendered with source reference and affected entities.
- [ ] Run tests and commit `feat: drive Wednesday updates from Event Ledger`.

---

### Task 8: Build and validate Chronicle ZIP backups

**Files:** Create `editorial_desk/chronicle_backup.py`, `tests/test_chronicle_backup.py`.

**Interfaces:**

```python
build_chronicle_backup(chronicle_root, output_path, chronicle_sha, created_at) -> BackupResult
validate_backup(path) -> BackupValidation
```

**Archive includes:** registries, league ledgers, materialized history, cross-league events, coverage, permanent manifests, `BACKUP_MANIFEST.json`.

**Manifest includes:** creation time, exact Chronicle SHA, schema versions, leagues, seasons, event counts, SHA-256 per file, validation status.

- [ ] Test diagnostic temp/cache paths are excluded.
- [ ] Test every archived checksum and exact Chronicle SHA.
- [ ] Test tampered archive fails validation.
- [ ] Test archive contains enough state to recreate the same permanent tree when extracted into an empty directory.
- [ ] Run tests and commit `feat: create validated Chronicle backups`.

---

### Task 9: Attach monthly archive to normal Tuesday email

**Files:** Modify `editorial_desk/emailer.py`, `editorial_desk/cli.py`, `tests/test_emailer.py`, `tests/test_chronicle_backup.py`.

**Interfaces:**

```python
build_dossier_email(..., extra_attachments: tuple[Path, ...] = ())
send_dossier_email(..., extra_attachments: tuple[Path, ...] = ())
is_first_tuesday(now: datetime, timezone_name="America/New_York") -> bool
```

- [ ] Test timezone-aware first Tuesday: 2026-09-01 local => true; 2026-09-08 => false.
- [ ] Test normal dossier attachments plus exactly one Chronicle ZIP when due.
- [ ] After SMTP accepts the message, write a monthly send receipt keyed by `YYYY-MM` containing Chronicle SHA, archive checksum, SMTP-accepted timestamp.
- [ ] A later workflow run with a committed success receipt skips monthly archive attachment.
- [ ] If SMTP raises before acceptance, no success receipt is written and retry remains eligible.
- [ ] Document the unavoidable edge case: SMTP acceptance followed by failure to persist the receipt can cause a duplicate retry; the archive filename/checksum and email subject make such a duplicate identifiable. Do not claim stronger exactly-once semantics than SMTP + Git can provide.
- [ ] Run tests and commit `feat: attach monthly Chronicle backup to Tuesday email`.

---

### Task 10: Gate major maintenance on a fresh emailed backup

**Files:** Modify `editorial_desk/cli.py`, `editorial_desk/chronicle_backup.py`; create `tests/test_chronicle_maintenance_gate.py`.

**Interface:** `require_prechange_backup(operation, ...) -> BackupReceipt`.

- [ ] Backup creation failure prevents maintenance callback.
- [ ] Backup validation failure prevents maintenance callback.
- [ ] SMTP failure prevents maintenance callback.
- [ ] Successful receipt records operation label, Chronicle SHA, archive checksum, sent time.
- [ ] Re-backfill, registry restructuring mode, bulk correction mode, storage migration, and materializer-rewrite maintenance entry points invoke the gate; ordinary append collection does not.
- [ ] Run tests and commit `feat: gate Chronicle maintenance on backup`.

---

### Task 11: Add 30-day diagnostic pruning

**Files:** Create `editorial_desk/retention.py`, `tests/test_retention.py`; modify `editorial_desk/cli.py`.

**Interface:** `prune_diagnostics(root, now, retention_days=30) -> PruneResult`.

- [ ] Fixture includes 31-day and 29-day diagnostic files plus permanent ledger/history/registry/coverage/backup receipt files.
- [ ] Assert only expired diagnostic file is removed.
- [ ] Implement allowlist pruning under `diagnostics/` only.
- [ ] Add `chronicle-prune-diagnostics` CLI and run tests.
- [ ] Commit `feat: prune expired Chronicle diagnostics`.

---

### Task 12: Integrate Chronicle into Tuesday/Wednesday workflows

**Files:** Modify `.github/workflows/editorial-desk-dry-run.yml`, `.github/workflows/editorial-desk-chronicle.yml`, `README.md`.

- [ ] Both workflows that write Chronicle use `concurrency.group: editorial-chronicle-writer`, `cancel-in-progress: false`.
- [ ] Tuesday order is exactly:

```text
tests
-> checkout main + chronicle-data separately
-> determine completed period
-> chronicle-collect --finalize-matchups for completed week
-> materialize
-> commit/push Chronicle if changed
-> capture exact Chronicle SHA
-> full editorial collection against pinned SHA
-> newspaper packets + Story Desk
-> if first Tuesday build/validate archive
-> normal email (+ archive when due)
-> persist monthly send receipt when SMTP accepted
-> save Tuesday baseline
```

- [ ] Wednesday uses Chronicle events after Tuesday baseline plus dossier comparison; no duplicate full packet when baseline unavailable.
- [ ] Diagnostic prune runs only after successful Chronicle mutation/validation, never before backup creation.
- [ ] README documents optional manual external-input directory without transferring ownership of Power Rankings workflow into Editorial Desk.
- [ ] Commit `ci: integrate Chronicle with editorial delivery`.

---

### Task 13: Full Editorial Desk v2 end-to-end fixture

**Files:** Create `tests/test_editorial_v2_e2e.py`; extend `tests/fixtures/chronicle_history/`.

Fixture includes: renewal chain, dynasty rename/manager change, redraft manager continuity, trade, waiver, health transition, later reaction, lineup flip, playoff rematch, future-pick trade, Volunteer no-division league, SEC divided/IDP league, optional official magazine rankings.

- [ ] Exercise `backfill -> materialize -> live pulse -> current materialize -> newspaper packets -> Story Desk -> Wednesday supplement -> monthly archive -> Tuesday email`.
- [ ] Assert all-time record updates from historical + live evidence.
- [ ] Assert rerun creates no duplicate events.
- [ ] Assert Volunteer no division output; Saturday East/West + IDP; Stampede exact feature name.
- [ ] Assert only Ironbound/Unbound get Story Desk.
- [ ] Assert official ranking language only with supplied official input.
- [ ] Assert temporal health/reaction sequence has no unsupported causal statement.
- [ ] Assert backup validation succeeds.
- [ ] Run test and commit `test: verify Editorial Desk v2 end to end`.

---

### Task 14: Final verification gate

- [ ] Run `python -m pytest -q`.
- [ ] Validate example configuration with current publication config.
- [ ] Search production files for obsolete labels: `Week's Heavy Lifting`, `publication standard pending`; expect none.
- [ ] Search workflow/code for normal `push --force`; expect none.
- [ ] Build and validate a fixture Chronicle backup.
- [ ] Perform read-only live smoke collection; verify no Sleeper mutation endpoint exists or is invoked.
- [ ] Review Story Desk output for evidence references and scope boundaries, not subjective headline quality.
- [ ] Commit verification fixes only if needed with `test: complete Editorial Desk v2 verification`.
