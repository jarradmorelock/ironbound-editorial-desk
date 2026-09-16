# Publication Feature Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the existing generic weekly dossier into publication-ready newspaper packets with locked department contracts, shared metric definitions, readiness states, exact Volunteer Voice/SEC/Stampede rules, and universal game-window context.

**Architecture:** Shared computations remain normalized in focused feature modules. `config/publications.json` declares publication capabilities and phase-aware department contracts. A packet builder maps normalized features into each paper's established department names, attaches readiness metadata, and renders publication-specific Markdown without recomputing the same metric differently for each paper.

**Tech Stack:** Python 3.12, dataclasses/json, existing `metrics.py`, `weekly_features.py`, `health.py`, `nfl_enrichment.py`, `render.py`, pytest.

**Spec:** `docs/superpowers/specs/2026-09-16-editorial-desk-v2-final-design.md`

## Global Constraints

- The five weekly newspapers are contract-driven.
- Shared facts are computed once and themed at the publication layer.
- Readiness values are exactly `ready`, `ready_no_items`, or `unavailable`.
- Volunteer Voice has no divisions and no divisional MVP logic.
- Saturday Standard retains East/West divisions and first-class IDP.
- The Stampede feature name is exactly `What a Way to Make a Living`.
- Hollywood Beat is no longer `publication standard pending`.
- Existing published PDFs are not regenerated.
- Magazine Story Desk behavior is out of scope for this phase.

---

## File map

**Create**
- `editorial_desk/feature_models.py` — readiness/result dataclasses and dependency semantics.
- `editorial_desk/feature_producers.py` — shared deterministic calculations that do not belong in monolithic `metrics.py`.
- `editorial_desk/publication_contracts.py` — parse/validate phase-aware feature contracts.
- `editorial_desk/publication_packets.py` — build themed newspaper packet from normalized dossier/features.
- `editorial_desk/publication_render.py` — render packet Markdown by department order and labels.
- `tests/test_feature_models.py`
- `tests/test_feature_producers.py`
- `tests/test_publication_contracts.py`
- `tests/test_publication_packets.py`
- `tests/test_publication_regressions.py`
- `tests/test_game_window_features.py`

**Modify**
- `config/publications.json`
- `editorial_desk/config.py`
- `editorial_desk/weekly_features.py`
- `editorial_desk/review.py`
- `editorial_desk/enriched_collector.py`
- `editorial_desk/nfl_enrichment.py` only where shared game-window/stat inputs need exposing
- `tests/test_config.py`
- existing weekly feature/health/review tests as needed

---

### Task 1: Add feature readiness and dependency models

**Files:**
- Create: `editorial_desk/feature_models.py`
- Test: `tests/test_feature_models.py`

**Interfaces:**
- Produces `FeatureReadiness`, `FeatureResult`, `FeatureDependency`, `DependencyStrength`.

- [ ] **Step 1: Write failing enum/dataclass tests**

```python
from editorial_desk.feature_models import FeatureResult


def test_feature_result_distinguishes_empty_from_unavailable():
    empty = FeatureResult.ready_no_items("ward_report")
    unavailable = FeatureResult.unavailable("ward_report", "health source failed")
    assert empty.status == "ready_no_items"
    assert unavailable.status == "unavailable"
    assert unavailable.reason == "health source failed"
```

- [ ] **Step 2: Run failing test**

Run: `python -m pytest tests/test_feature_models.py -q`

- [ ] **Step 3: Implement immutable models**

```python
from dataclasses import dataclass
from typing import Any, Literal

Readiness = Literal["ready", "ready_no_items", "unavailable"]
Strength = Literal["required", "preferred", "optional"]

@dataclass(frozen=True)
class FeatureDependency:
    source: str
    strength: Strength

@dataclass(frozen=True)
class FeatureResult:
    feature: str
    status: Readiness
    data: Any = None
    reason: str | None = None
    freshness: dict[str, str] | None = None
```

Provide classmethods `ready`, `ready_no_items`, `unavailable`.

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest tests/test_feature_models.py -q`

```bash
git add editorial_desk/feature_models.py tests/test_feature_models.py
git commit -m "feat: add publication feature readiness model"
```

---

### Task 2: Extend publication configuration schema

**Files:**
- Modify: `editorial_desk/config.py`
- Modify: `config/publications.json`
- Modify: `tests/test_config.py`
- Create: `tests/test_publication_contracts.py`

**Interfaces:**
- `PublicationConfig` gains `capabilities: dict[str, bool]` and `feature_contracts: dict[str, tuple[FeatureContractConfig, ...]]`.
- `FeatureContractConfig` fields: `feature`, `display_name`, `dependencies`, `required`.

- [ ] **Step 1: Write failing config tests**

Assert:

```python
assert publications["ironbound_weekly"].capabilities["story_desk"] is True
assert publications["unbound_weekly"].capabilities["story_desk"] is True
assert publications["hollywood_beat"].capabilities["story_desk"] is False
assert "weekly" in publications["ballad_crier"].feature_contracts
```

- [ ] **Step 2: Add schema parser/validation**

Reject unknown dependency strength, duplicate feature IDs within a phase, and missing display names.

- [ ] **Step 3: Rewrite `config/publications.json` with authoritative contracts**

Use explicit `capabilities`:

```json
"capabilities": {"story_desk": false, "chronicle": true}
```

For each newspaper add `feature_contracts.weekly`, `feature_contracts.preseason`, and where useful `feature_contracts.offseason` entries matching the approved spec.

Required exact corrections:

- Volunteer Voice: no `division_pulse`, no `divisional_mvp`
- Saturday Standard: includes `division_pulse`, `divisional_mvp`, `idp_position_leaders`
- Stampede: display name `What a Way to Make a Living`
- Hollywood Beat: full weekly contract, no placeholder text

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_config.py tests/test_publication_contracts.py -q`

- [ ] **Step 5: Commit**

```bash
git add editorial_desk/config.py config/publications.json tests/test_config.py tests/test_publication_contracts.py
git commit -m "feat: encode publication feature contracts"
```

---

### Task 3: Extract shared result-flip and decision-swing calculations

**Files:**
- Create: `editorial_desk/feature_producers.py`
- Modify: `editorial_desk/weekly_features.py`
- Test: `tests/test_feature_producers.py`
- Modify: `tests/test_manager_award.py`

**Interfaces:**
- Produces:
  - `result_flipping_decisions(snapshot, dossier) -> list[dict[str, Any]]`
  - `manager_decision_evidence(snapshot, dossier) -> list[dict[str, Any]]`
  - `league_wide_started_mvp(snapshot) -> dict[str, Any] | None`
  - `divisional_started_mvps(snapshot) -> list[dict[str, Any]]`

- [ ] **Step 1: Write shared lineup-flip fixture test**

```python
flips = result_flipping_decisions(snapshot, dossier)
assert flips[0]["started_player_id"] == "starter"
assert flips[0]["bench_player_id"] == "bench"
assert flips[0]["result_flips"] is True
```

- [ ] **Step 2: Add Volunteer Voice league-wide MVP test**

Assert highest-scoring STARTED player wins, regardless of nonexistent division metadata.

- [ ] **Step 3: Add Saturday Standard divisional MVP test**

Assert one started MVP per East/West division and gold foil on the higher score.

- [ ] **Step 4: Implement by moving reusable logic out of `weekly_features.py`**

Do not change Manager of the Week scoring method except to call the shared evidence producer.

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_feature_producers.py tests/test_manager_award.py -q`

- [ ] **Step 6: Commit**

```bash
git add editorial_desk/feature_producers.py editorial_desk/weekly_features.py tests/test_feature_producers.py tests/test_manager_award.py
git commit -m "refactor: centralize weekly feature calculations"
```

---

### Task 4: Add shared waiver impact, record watch, and position leader producers

**Files:**
- Modify: `editorial_desk/feature_producers.py`
- Test: `tests/test_feature_producers.py`

**Interfaces:**
- Produces:
  - `waiver_impact(snapshot, dossier) -> list[dict[str, Any]]`
  - `record_watch(dossier, chronicle_history) -> dict[str, Any]`
  - `position_leaders(snapshot) -> dict[str, dict[str, Any]]`
  - `bench_blast(snapshot) -> dict[str, Any] | None`

- [ ] **Step 1: Add failing waiver-impact test**

Assert player, transaction type, FAAB, started/bench status, fantasy points, and victory-margin relevance are preserved.

- [ ] **Step 2: Add position leader test including IDP**

Fixture includes QB/RB/WR/TE/LB/DB. Assert all configured positions can be surfaced and started/bench status remains attached.

- [ ] **Step 3: Implement producers**

Reuse existing `_rostered_player_weeks` and transaction evidence patterns where possible rather than duplicating scoring calculations.

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest tests/test_feature_producers.py -q`

```bash
git add editorial_desk/feature_producers.py tests/test_feature_producers.py
git commit -m "feat: add shared waiver record and position features"
```

---

### Task 5: Add Stampede NFL workload feature producer

**Files:**
- Modify: `editorial_desk/feature_producers.py`
- Test: `tests/test_feature_producers.py`
- Modify: `editorial_desk/enriched_collector.py` if needed to preserve fields already present in nflverse stats.

**Interfaces:**
- Produces `workload_leaders(snapshot) -> FeatureResult` for feature ID `workload_stat_lines`.

- [ ] **Step 1: Write failing stat-line test**

Fixture must include real NFL fields:

```python
{
  "player_id": "rb1",
  "carries": 26,
  "rushing_yards": 142,
  "rushing_tds": 2,
  "receptions": 4,
  "receiving_yards": 31
}
```

Assert returned rows preserve workload categories and are not merely ordered by fantasy points.

- [ ] **Step 2: Implement workload categories**

Return separate ranked facts for rushing workload, passing production, and receiving volume/production so editors can choose the most compelling weekly work.

- [ ] **Step 3: Assert exact display label lives only in contract layer**

Producer feature ID stays neutral (`workload_stat_lines`); Stampede contract renders `What a Way to Make a Living`.

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest tests/test_feature_producers.py -q`

```bash
git add editorial_desk/feature_producers.py editorial_desk/enriched_collector.py tests/test_feature_producers.py
git commit -m "feat: add NFL workload feature data"
```

---

### Task 6: Add universal game-window reconstruction feature

**Files:**
- Modify: `editorial_desk/feature_producers.py`
- Modify: `editorial_desk/nfl_enrichment.py` if required
- Create: `tests/test_game_window_features.py`

**Interfaces:**
- Produces `game_window_context(snapshot, dossier) -> FeatureResult` with per-matchup `pre_window_score`, `remaining_players`, `window_points`, `final_score`, `final_margin`, `provenance`.

- [ ] **Step 1: Write Monday comeback fixture test**

Assert team trailing before Monday wins after one remaining starter scores enough points.

- [ ] **Step 2: Add reconstructed-vs-observed provenance test**

If pre-window state is reconstructed from final score minus Monday-player production, mark `provenance="reconstructed"`; if Chronicle contains a preserved live snapshot, mark `provenance="observed_live"`.

- [ ] **Step 3: Implement feature without Story Desk dependency**

Use NFL schedule weekday/game start plus player stat lines and fantasy scoring context already available in snapshot/dossier.

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest tests/test_game_window_features.py -q`

```bash
git add editorial_desk/feature_producers.py editorial_desk/nfl_enrichment.py tests/test_game_window_features.py
git commit -m "feat: add universal late-game reconstruction"
```

---

### Task 7: Build publication packet compiler

**Files:**
- Create: `editorial_desk/publication_contracts.py`
- Create: `editorial_desk/publication_packets.py`
- Test: `tests/test_publication_packets.py`

**Interfaces:**
- `build_publication_packet(snapshot, dossier, publication_config, phase, chronicle_history=None) -> dict[str, Any]`
- Packet keys: `publication`, `phase`, `departments`, `readiness`, `source_freshness`, `generated_at`.

- [ ] **Step 1: Write failing packet readiness test**

Ballad Ward Report with successful empty health returns department status `ready_no_items`; simulated health failure returns `unavailable` with reason.

- [ ] **Step 2: Write mapping test**

One normalized `lineup_flip_candidates` result maps to:

- Ballad `Weekly Rounds`
- Saturday `Portal Film Room`
- Hollywood `Cutting Room Floor`

without changing underlying data payload.

- [ ] **Step 3: Implement dependency evaluator**

Required source missing -> `unavailable`; preferred source missing -> keep feature if minimum facts exist and add degradation note; optional source missing -> no readiness penalty.

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest tests/test_publication_packets.py -q`

```bash
git add editorial_desk/publication_contracts.py editorial_desk/publication_packets.py tests/test_publication_packets.py
git commit -m "feat: build publication-ready feature packets"
```

---

### Task 8: Add publication-specific rendering

**Files:**
- Create: `editorial_desk/publication_render.py`
- Modify: `editorial_desk/review.py`
- Modify: `editorial_desk/enriched_collector.py`
- Test: `tests/test_publication_packets.py`

**Interfaces:**
- `render_publication_packet(packet) -> str`
- Existing `dossier.json` remains available; newspaper output adds `publication_packet.json` and `publication_packet.md`.

- [ ] **Step 1: Write rendering test for department order and readiness banner**

Assert contract order is preserved and unavailable departments visibly include reason.

- [ ] **Step 2: Implement renderer**

Do not hard-code publication-specific calculations in renderer. It reads display names and data already selected by packet builder.

- [ ] **Step 3: Update enriched collector**

After `build_editorial_review`, for `tier == "newspaper"`, build and write packet JSON/Markdown alongside current dossier files.

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest tests/test_publication_packets.py tests/test_health_reporting.py -q`

```bash
git add editorial_desk/publication_render.py editorial_desk/review.py editorial_desk/enriched_collector.py tests/test_publication_packets.py
git commit -m "feat: render themed newspaper feature packets"
```

---

### Task 9: Lock publication-specific regressions

**Files:**
- Create: `tests/test_publication_regressions.py`

- [ ] **Step 1: Volunteer Voice regression test**

Assert packet contains no department whose feature ID/display name references divisions; league-wide MVP uses highest-scoring started player.

- [ ] **Step 2: Saturday Standard regression test**

Assert East/West pulse/polls/MVPs and IDP position board are present.

- [ ] **Step 3: Stampede regression test**

Assert output contains `What a Way to Make a Living` and contains neither `Heavy Lifting` nor `The Week's Heavy Lifting`.

- [ ] **Step 4: Hollywood Beat regression test**

Assert weekly packet includes Box Office, Marquee, Hollywood Board, Late Show, For Your Consideration, Cutting Room Floor, Studio Efficiency, Casting Call, Production Delays, and This Week's Bill.

- [ ] **Step 5: Ballad Crier regression test**

Assert Cardiogram, Final Monitor, Weekly Rounds, Rankings Wire, Rounds Report, Ward Report, Waiver Star, Record Watch, and Next Card.

- [ ] **Step 6: Run tests and commit**

Run: `python -m pytest tests/test_publication_regressions.py -q`

```bash
git add tests/test_publication_regressions.py
git commit -m "test: lock weekly newspaper contracts"
```

---

### Task 10: Phase-aware preseason/offseason contract tests

**Files:**
- Modify: `tests/test_publication_contracts.py`
- Modify: `tests/test_publication_packets.py`

- [ ] **Step 1: Test preseason departments are available only in preseason phase**

For example, Ballad `Keeper Heist` and Saturday `Recruiting Board` should not become required in `weekly` phase.

- [ ] **Step 2: Test external/preferred inputs degrade gracefully**

Missing Dynasty Daddy market values may mark Dynasty Market Board degraded/unavailable per contract without breaking Saturday scoreboard/efficiency departments.

- [ ] **Step 3: Run tests and commit**

Run: `python -m pytest tests/test_publication_contracts.py tests/test_publication_packets.py -q`

```bash
git add tests/test_publication_contracts.py tests/test_publication_packets.py
git commit -m "test: verify phase-aware publication contracts"
```

---

### Task 11: Phase 3 regression gate

- [ ] **Step 1: Run complete suite**

Run: `python -m pytest -q`

- [ ] **Step 2: Generate fixture packets for all five newspapers**

Inspect JSON and Markdown to verify no missing locked department and no cross-publication label leakage.

- [ ] **Step 3: Search retired/wrong labels**

Run:

```bash
grep -R "Week's Heavy Lifting\|Division Pulse" config editorial_desk tests --exclude-dir=.git
```

Expected: `Week's Heavy Lifting` only in explicit negative regression test/spec comments; `Division Pulse` never associated with Volunteer Voice and remains valid for Saturday Standard.

- [ ] **Step 4: Commit any regression fixes only if needed**

```bash
git add -A
git commit -m "test: close publication contract regressions"
```
