# Story Desk, Workflows, and Backups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the Ironbound/Unbound Magazine Story Desk, Event Ledger-driven Wednesday deltas, first-Tuesday Chronicle backup attachment, pre-major-change safety backups, diagnostic retention cleanup, and final end-to-end workflow orchestration.

**Architecture:** Story Desk consumes only normalized features, Chronicle queries, Event Ledger evidence, and explicitly supplied external editorial inputs. Backup/archive code is separate from editorial logic and produces a validated restore archive before email. The existing Tuesday/Wednesday workflow becomes Chronicle-aware while the lightweight writer workflow remains responsible for routine state capture.

**Tech Stack:** Python 3.12, dataclasses/json/pathlib/zipfile/hashlib, existing SMTP emailer, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-16-editorial-desk-v2-final-design.md`

## Global Constraints

- Story Desk is enabled only for Ironbound Weekly and Unbound Weekly.
- Story candidates are evidence packages, not source-of-truth history.
- The system never asserts unsupported causation.
- Official Power Rankings are external; internal metrics cannot masquerade as official ranks.
- WAR is optional external enrichment.
- Wednesday supplements report only genuinely new post-Tuesday evidence.
- First Tuesday monthly archive is attached to the normal Tuesday email, not sent separately.
- Major Chronicle-affecting maintenance stops if pre-change backup cannot be created and emailed.
- Diagnostic snapshots are retained for approximately 30 days; permanent ledger/history is never pruned by diagnostic cleanup.

---

## File map

**Create**
- `editorial_desk/story_models.py` — story candidate/evidence models.
- `editorial_desk/story_desk.py` — candidate generation, signal scoring, editorial cautions.
- `editorial_desk/chronicle_queries.py` — read-only historical/event query helpers for editorial consumers.
- `editorial_desk/external_inputs.py` — optional official Power Rankings/WAR input validation.
- `editorial_desk/chronicle_backup.py` — validated ZIP archive + checksums/manifest.
- `editorial_desk/retention.py` — diagnostic snapshot pruning only.
- `tests/test_story_desk.py`
- `tests/test_chronicle_queries.py`
- `tests/test_external_inputs.py`
- `tests/test_chronicle_backup.py`
- `tests/test_retention.py`
- `tests/test_editorial_v2_e2e.py`

**Modify**
- `editorial_desk/review.py`
- `editorial_desk/enriched_collector.py`
- `editorial_desk/supplement.py`
- `editorial_desk/emailer.py`
- `editorial_desk/cli.py`
- `.github/workflows/editorial-desk-dry-run.yml`
- `.github/workflows/editorial-desk-chronicle.yml` if final concurrency harmonization is needed
- `README.md`
- corresponding existing tests

---

### Task 1: Add read-only Chronicle query API

**Files:**
- Create: `editorial_desk/chronicle_queries.py`
- Test: `tests/test_chronicle_queries.py`

**Interfaces:**
- `ChronicleQueries(root: Path)`
- `head_to_head(league_key, left_key, right_key) -> dict[str, Any] | None`
- `current_streak(...) -> dict[str, Any] | None`
- `season_records(league_key, season) -> dict[str, Any]`
- `recent_events(league_key, since, event_types=None) -> list[dict[str, Any]]`
- `player_events(player_id, since=None) -> list[dict[str, Any]]`
- `transactions_for_entity(...) -> list[dict[str, Any]]`

- [ ] **Step 1: Write failing historical-query tests**

Use Phase 2 materialized fixture and assert H2H, playoff meetings, streak, and incomplete-coverage metadata return exactly what Chronicle stores.

- [ ] **Step 2: Implement query layer without recomputing source history ad hoc**

Queries read materialized indexes for summary answers and ledger for event detail. Return coverage metadata with every historical summary.

- [ ] **Step 3: Run tests and commit**

Run: `python -m pytest tests/test_chronicle_queries.py -q`

```bash
git add editorial_desk/chronicle_queries.py tests/test_chronicle_queries.py
git commit -m "feat: add read-only Chronicle editorial queries"
```

---

### Task 2: Define Story Desk candidate model

**Files:**
- Create: `editorial_desk/story_models.py`
- Test: `tests/test_story_desk.py`

**Interfaces:**
- `StoryEvidenceRef(event_id, source, description)`
- `StoryCandidate(candidate_id, candidate_type, title_concepts, trigger_reasons, evidence_refs, facts, historical_context, entities, evidence_strength, signal_score, cautions, editorial_angles, graphic_ideas, depth_class)`

- [ ] **Step 1: Write candidate serialization test**

Assert candidate JSON contains no free-standing factual claim without either evidence reference or a derived-fact provenance key.

- [ ] **Step 2: Implement immutable models and deterministic candidate ID**

Candidate ID is stable for the same candidate type + core entity/event evidence, so rerunning Tuesday does not reshuffle identities unnecessarily.

- [ ] **Step 3: Run tests and commit**

Run: `python -m pytest tests/test_story_desk.py -q`

```bash
git add editorial_desk/story_models.py tests/test_story_desk.py
git commit -m "feat: define Magazine Story Desk candidate model"
```

---

### Task 3: Add optional external editorial input loader

**Files:**
- Create: `editorial_desk/external_inputs.py`
- Test: `tests/test_external_inputs.py`

**Interfaces:**
- `load_external_inputs(path: Path | None, publication_key: str) -> ExternalEditorialInputs`
- Fields: `official_power_rankings`, `war`, `notes`, `source_metadata`.

- [ ] **Step 1: Write missing-input test**

`None` or nonexistent optional path returns an empty validated input object, not an error.

- [ ] **Step 2: Write official-rank validation test**

A supplied ranking file must identify itself as official external input and provide unique integer ranks. Invalid duplicates raise `ExternalInputError`.

Example accepted JSON:

```json
{
  "publication_key": "ironbound_weekly",
  "official_power_rankings": [
    {"franchise_key": "scenic_city", "rank": 1},
    {"franchise_key": "mormonts", "rank": 15}
  ],
  "war": [],
  "source_metadata": {"label": "Ironbound Power Rankings", "week": 7}
}
```

- [ ] **Step 3: Implement loader**

Do not fetch the other ranking workflow automatically. This is an explicit optional bridge for editor-supplied material.

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest tests/test_external_inputs.py -q`

```bash
git add editorial_desk/external_inputs.py tests/test_external_inputs.py
git commit -m "feat: accept optional official editorial inputs"
```

---

### Task 4: Implement core Story Desk candidate rules

**Files:**
- Create: `editorial_desk/story_desk.py`
- Test: `tests/test_story_desk.py`

**Interfaces:**
- `build_story_desk(publication_key, snapshot, dossier, chronicle, external_inputs) -> dict[str, Any]`
- Internal candidate producers each return `list[StoryCandidate]`.

- [ ] **Step 1: Add failing scope test**

```python
assert build_story_desk("ironbound_weekly", ...)["status"] == "available"
assert build_story_desk("unbound_weekly", ...)["status"] == "available"
assert build_story_desk("ballad_crier", ...)["status"] == "disabled"
```

- [ ] **Step 2: Add historical/rivalry candidate test**

Fixture with deep H2H imbalance and current matchup produces `rivalry_history` candidate whose historical fact exactly matches Chronicle query and includes coverage metadata.

- [ ] **Step 3: Add injury/reaction timing test**

Fixture with observed status interval plus exact later acquisition may generate `reaction_transaction`; caution must say temporal sequence is supported but motive is not established.

- [ ] **Step 4: Add trade-afterlife/asset-journey test**

A player/pick appearing across draft + multiple transaction events produces evidence refs to each underlying event.

- [ ] **Step 5: Add division-pressure, streak, scoring-record, lineup-catastrophe, playoff-rematch tests**

Each candidate must be generated only when objective thresholds/conditions are met and contain neutral facts.

- [ ] **Step 6: Implement initial candidate producers**

Create focused functions:

```python
_rivalry_candidates(...)
_status_reaction_candidates(...)
_trade_afterlife_candidates(...)
_asset_journey_candidates(...)
_roster_architecture_candidates(...)
_dynasty_timeline_candidates(...)
_upset_and_record_candidates(...)
_streak_candidates(...)
_playoff_rematch_candidates(...)
_lineup_catastrophe_candidates(...)
_division_pressure_candidates(...)
_cross_league_shock_candidates(...)
```

- [ ] **Step 7: Implement signal score**

Score only measurable components: rarity, historical depth, timing proximity, affected-league count, magnitude, playoff relevance, transaction cost, signal convergence. Preserve component breakdown so score is auditable.

- [ ] **Step 8: Implement candidate ranking and generous cap**

Sort descending by signal score/evidence strength, then deterministic candidate ID. Return up to 20 candidates, but do not pad to a minimum or invent weak stories merely to reach 12.

- [ ] **Step 9: Run tests and commit**

Run: `python -m pytest tests/test_story_desk.py -q`

```bash
git add editorial_desk/story_desk.py tests/test_story_desk.py
git commit -m "feat: generate evidence-backed magazine story candidates"
```

---

### Task 5: Add ranking/WAR story guardrails and magazine voice suggestions

**Files:**
- Modify: `editorial_desk/story_desk.py`
- Test: `tests/test_story_desk.py`

- [ ] **Step 1: Write David-vs-Goliath guardrail test**

Without official external rankings, no candidate may include `No. 1`, `No. 15`, `power_rank`, or ranking-disparity trigger based on internal substitutes.

With validated official rankings, ranking-disparity candidate may be produced.

- [ ] **Step 2: Write WAR guardrail test**

WAR-dependent facts appear only when `external_inputs.war` is nonempty and validated.

- [ ] **Step 3: Add publication-specific headline concept templates**

Ironbound concepts may use forge/metal/Crown/pressure language; Unbound concepts may use chain/link/tension/break language. Headline concepts must not alter factual evidence.

- [ ] **Step 4: Add depth and graphic suggestion mapping**

Depth classification is based on evidence breadth, not prose length. Suggested graphics reference available data such as score trajectory, trade chain, rivalry timeline, division table, or player workload chart.

- [ ] **Step 5: Run tests and commit**

Run: `python -m pytest tests/test_story_desk.py -q`

```bash
git add editorial_desk/story_desk.py tests/test_story_desk.py
git commit -m "feat: add magazine story editorial guardrails"
```

---

### Task 6: Write Story Desk artifacts during Tuesday collection

**Files:**
- Modify: `editorial_desk/enriched_collector.py`
- Modify: `editorial_desk/review.py`
- Modify: `editorial_desk/cli.py`
- Test: `tests/test_story_desk.py`

**Interfaces:**
- For story-desk-enabled publications write:
  - `story_desk.json`
  - `story_desk.md`
- Optional CLI argument: `--external-inputs-dir PATH` for manual/editor-supplied inputs. Absence is valid.

- [ ] **Step 1: Write failing artifact test**

Ironbound/Unbound fixture directories receive Story Desk files; newspapers do not.

- [ ] **Step 2: Implement Story Desk rendering**

Markdown sections per candidate:

```text
headline concepts
type / signal score / evidence strength
why it triggered
facts
historical context
editorial caution
possible angles
possible graphics
depth class
evidence IDs
```

- [ ] **Step 3: Expose external input availability in magazine packet**

Record `power_rankings: supplied/not_supplied`, `war: supplied/not_supplied`.

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest tests/test_story_desk.py tests/test_collector.py -q`

```bash
git add editorial_desk/enriched_collector.py editorial_desk/review.py editorial_desk/cli.py tests/test_story_desk.py
git commit -m "feat: write magazine Story Desk packets"
```

---

### Task 7: Make Wednesday supplement Event Ledger-aware

**Files:**
- Modify: `editorial_desk/supplement.py`
- Test: existing `tests/test_supplement.py` if present; otherwise create `tests/test_supplement_events.py`.

**Interfaces:**
- `generate_supplements(..., chronicle_root: Path | None = None, baseline_time: str | None = None)`
- Uses Event Ledger events after Tuesday pinned baseline in addition to dossier comparison.

- [ ] **Step 1: Write failing new-event test**

A health event or transaction that appears after Tuesday baseline must produce a supplement even if a broad dossier section would otherwise compare equal.

- [ ] **Step 2: Write no-duplicate test**

Events already represented in Tuesday packet/baseline must not reappear Wednesday.

- [ ] **Step 3: Implement event-to-supplement evidence rendering**

Include event type, supported timestamp semantics, affected entities, and source reference. For health transitions, preserve observed window rather than invent exact time.

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest tests/test_supplement*.py -q`

```bash
git add editorial_desk/supplement.py tests/test_supplement*.py
git commit -m "feat: drive Wednesday updates from Event Ledger deltas"
```

---

### Task 8: Build validated Chronicle backup archives

**Files:**
- Create: `editorial_desk/chronicle_backup.py`
- Test: `tests/test_chronicle_backup.py`

**Interfaces:**
- `build_chronicle_backup(chronicle_root: Path, output_path: Path, chronicle_sha: str, created_at: datetime) -> BackupResult`
- ZIP includes permanent Chronicle state plus `BACKUP_MANIFEST.json`.

- [ ] **Step 1: Write failing archive-content test**

Fixture root contains registry/events/history/coverage/manifests. Assert ZIP contains them and excludes diagnostic temp/cache directories.

- [ ] **Step 2: Write checksum/SHA validation test**

Manifest must contain exact supplied Chronicle SHA and SHA-256 checksum for every archived file.

- [ ] **Step 3: Implement deterministic archive builder**

Sort paths, write JSON manifest with creation time, schema versions, league/season/event counts, validation result, checksums.

- [ ] **Step 4: Implement `validate_backup(path) -> BackupValidation`**

Recompute checksums and fail closed on mismatch/missing required state.

- [ ] **Step 5: Run tests and commit**

Run: `python -m pytest tests/test_chronicle_backup.py -q`

```bash
git add editorial_desk/chronicle_backup.py tests/test_chronicle_backup.py
git commit -m "feat: create validated Chronicle backups"
```

---

### Task 9: Attach monthly backup to normal Tuesday email

**Files:**
- Modify: `editorial_desk/emailer.py`
- Modify: `editorial_desk/cli.py`
- Modify: `tests/test_emailer.py`
- Modify/Create: `tests/test_chronicle_backup.py`

**Interfaces:**
- `build_dossier_email(..., extra_attachments: tuple[Path, ...] = ())`
- `send_dossier_email(..., extra_attachments=())`
- CLI detects first Tuesday and supplies backup attachment if validated.

- [ ] **Step 1: Write first-Tuesday date helper test**

```python
assert is_first_tuesday(date(2026, 9, 1)) is True
assert is_first_tuesday(date(2026, 9, 8)) is False
```

- [ ] **Step 2: Write email attachment test**

Normal dossier attachments remain; monthly ZIP is one additional attachment with exact backup filename.

- [ ] **Step 3: Add duplicate-send marker behavior**

Store monthly send receipt in Chronicle manifests keyed by `YYYY-MM`. A retry after successful send must not attach/send the archive again; failed send creates no success receipt.

- [ ] **Step 4: Implement and run tests**

Run: `python -m pytest tests/test_emailer.py tests/test_chronicle_backup.py -q`

- [ ] **Step 5: Commit**

```bash
git add editorial_desk/emailer.py editorial_desk/cli.py tests/test_emailer.py tests/test_chronicle_backup.py
git commit -m "feat: attach monthly Chronicle backup to Tuesday email"
```

---

### Task 10: Add mandatory pre-major-change backup gate

**Files:**
- Modify: `editorial_desk/cli.py`
- Modify: `editorial_desk/chronicle_backup.py`
- Create: `tests/test_chronicle_maintenance_gate.py`

**Interfaces:**
- `python -m editorial_desk chronicle-maintenance-backup --chronicle-root ... --output ... --send`
- `require_prechange_backup(operation, ...) -> BackupReceipt` used by destructive/migratory commands.

- [ ] **Step 1: Write backup-failure gate test**

Simulated email failure must prevent maintenance callback from executing.

- [ ] **Step 2: Write success gate test**

Validated archive + successful email produces receipt containing SHA, sent timestamp, archive checksum, operation label.

- [ ] **Step 3: Integrate gate with `chronicle-backfill --rebuild`/future migration entry points**

Ordinary append collection does not invoke gate. Re-backfill, registry restructuring, bulk correction, storage migration, and materializer rewrite modes do.

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest tests/test_chronicle_maintenance_gate.py -q`

```bash
git add editorial_desk/cli.py editorial_desk/chronicle_backup.py tests/test_chronicle_maintenance_gate.py
git commit -m "feat: gate major Chronicle changes on backup"
```

---

### Task 11: Add 30-day diagnostic retention cleanup

**Files:**
- Create: `editorial_desk/retention.py`
- Test: `tests/test_retention.py`
- Modify: `editorial_desk/cli.py`

**Interfaces:**
- `prune_diagnostics(root: Path, now: datetime, retention_days: int = 30) -> PruneResult`

- [ ] **Step 1: Write failing prune test**

Create diagnostic files at ages 31 and 29 days plus permanent ledger/history files. Assert only old diagnostic file is deleted.

- [ ] **Step 2: Implement allowlist-based pruning**

Only paths under explicitly diagnostic directories are eligible. `events/`, `history/`, `registry/`, `coverage/`, backup receipts, and permanent manifests are never deleted by this function.

- [ ] **Step 3: Add CLI `chronicle-prune-diagnostics`**

Scheduled workflow may invoke after successful Chronicle write.

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest tests/test_retention.py -q`

```bash
git add editorial_desk/retention.py editorial_desk/cli.py tests/test_retention.py
git commit -m "feat: prune only expired Chronicle diagnostics"
```

---

### Task 12: Upgrade Tuesday/Wednesday workflow orchestration

**Files:**
- Modify: `.github/workflows/editorial-desk-dry-run.yml`
- Modify: `.github/workflows/editorial-desk-chronicle.yml`
- Modify: `README.md`

- [ ] **Step 1: Give Tuesday workflow Chronicle checkout/write permissions**

Use the same `editorial-chronicle-writer` concurrency group with `cancel-in-progress: false` for any job that mutates `chronicle-data`.

- [ ] **Step 2: Tuesday sequence**

Workflow order must be:

```text
tests
-> checkout/fetch chronicle-data
-> final chronicle-collect
-> materialize
-> commit/push Chronicle if changed
-> capture exact Chronicle SHA
-> run full editorial collect against that pinned data revision
-> build Story Desk + newspaper packets
-> if first Tuesday build validated backup
-> email normal packet (+ archive when due)
-> save Tuesday baseline
```

- [ ] **Step 3: Wednesday sequence**

Use Event Ledger since Tuesday baseline; do not send duplicate full packet when baseline unavailable.

- [ ] **Step 4: Add diagnostic prune only after successful data commit**

Do not prune before archive/validation steps.

- [ ] **Step 5: Document manual external inputs**

README should show how to supply official Power Rankings/WAR JSON for a manual Story Desk build without implying that the other rankings workflow is now owned by Editorial Desk.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/editorial-desk-dry-run.yml .github/workflows/editorial-desk-chronicle.yml README.md
git commit -m "ci: integrate Chronicle with editorial delivery"
```

---

### Task 13: Full end-to-end v2 fixture

**Files:**
- Create: `tests/test_editorial_v2_e2e.py`
- Reuse/extend: `tests/fixtures/chronicle_history/`

- [ ] **Step 1: Build fixture scenario**

Include:

- historical renewal chain
- franchise rename
- manager transfer
- current live status event
- later waiver/trade reaction
- lineup flip
- playoff rematch history
- future-pick transaction
- newspaper leagues including Volunteer/SEC distinctions
- optional official rankings input for one magazine

- [ ] **Step 2: Exercise complete flow**

```text
backfill
-> materialize
-> live collect
-> current materialize
-> build publication packets
-> build Story Desk
-> generate Wednesday delta
-> build monthly archive
-> build Tuesday email
```

- [ ] **Step 3: Assert critical boundaries**

Verify:

- all-time records update from backfill + live result
- no duplicate events on rerun
- Volunteer Voice has no division output
- Saturday Standard has East/West + IDP
- Stampede exact feature name
- only Ironbound/Unbound get Story Desk
- official rank language only appears when supplied
- health sequence is temporal, not causal
- backup manifest/checksums valid

- [ ] **Step 4: Run test and commit**

Run: `python -m pytest tests/test_editorial_v2_e2e.py -q`

```bash
git add tests/test_editorial_v2_e2e.py tests/fixtures/chronicle_history
git commit -m "test: verify Editorial Desk v2 end to end"
```

---

### Task 14: Final repository verification

- [ ] **Step 1: Run complete suite**

Run: `python -m pytest -q`

Expected: PASS with no skipped critical v2 regression tests.

- [ ] **Step 2: Run configuration validation**

Run:

```bash
cp config/leagues.example.json /tmp/editorial-leagues.json
python -m editorial_desk validate-config --config /tmp/editorial-leagues.json --publications config/publications.json
```

Expected: valid configuration; Story Desk capability is explicit in publication config.

- [ ] **Step 3: Search for forbidden regressions**

Run:

```bash
grep -R "Week's Heavy Lifting" config editorial_desk --exclude-dir=.git || true
grep -R "publication standard pending" config editorial_desk --exclude-dir=.git || true
grep -R "push --force" .github editorial_desk --exclude-dir=.git || true
```

Expected: no production matches.

- [ ] **Step 4: Verify backup archive against fixture Chronicle**

Run backup build + validator; expected checksum/manifest PASS.

- [ ] **Step 5: Perform read-only live smoke collection**

Use manual workflow or local configured read-only collection. Confirm no Sleeper mutation endpoints exist or are invoked.

- [ ] **Step 6: Commit verification-only fixes if needed**

```bash
git add -A
git commit -m "test: complete Editorial Desk v2 verification"
```

Only create this commit if verification required fixes.
