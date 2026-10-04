# Publication Feature Contracts Revised Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build publication-ready weekly and preseason newspaper packets from one shared factual layer, with locked paper-specific departments and readiness semantics.

**Architecture:** Neutral feature producers compute facts once. Publication configuration maps feature IDs to themed department labels and phase rules. Packet compilation evaluates required/preferred/optional inputs and rendering only presents already-computed facts.

**Tech Stack:** Python 3.12, dataclasses/json, current metrics/weekly_features/health/nflverse modules, pytest.

**Spec:** `docs/superpowers/specs/2026-09-16-editorial-desk-v2-final-design.md`

## Global Constraints

- Readiness values: `ready`, `ready_no_items`, `unavailable`.
- Dependency strengths: `required`, `preferred`, `optional`.
- Volunteer Voice has no divisions and uses one league-wide started-player MVP.
- Saturday Standard retains East/West divisions and first-class IDP.
- The Stampede department name is exactly `What a Way to Make a Living`.
- Hollywood Beat has a complete established contract.
- Preseason/draft features are phase-aware and do not become mandatory weekly features.
- Story Desk is not implemented in this phase.

---

### Task 1: Add readiness/dependency models

**Files:** Create `editorial_desk/feature_models.py`, `tests/test_feature_models.py`.

**Interfaces:**

```python
Readiness = Literal["ready", "ready_no_items", "unavailable"]
Strength = Literal["required", "preferred", "optional"]

@dataclass(frozen=True)
class FeatureResult:
    feature: str
    status: Readiness
    data: Any = None
    reason: str | None = None
    freshness: dict[str, str] | None = None
    degraded: bool = False
```

- [ ] Write tests distinguishing valid empty data from unavailable source data.
- [ ] Implement `ready`, `ready_no_items`, and `unavailable` constructors.
- [ ] Run `python -m pytest tests/test_feature_models.py -q` and commit `feat: add feature readiness model`.

---

### Task 2: Encode phase-aware publication contracts

**Files:** Modify `editorial_desk/config.py`, `config/publications.json`, `tests/test_config.py`; create `tests/test_publication_contracts.py`.

**Interfaces:**

```python
@dataclass(frozen=True)
class FeatureContractConfig:
    feature: str
    display_name: str
    required_in_phase: bool
    dependencies: tuple[FeatureDependencyConfig, ...]
```

- [ ] Add failing tests for explicit `story_desk` capability flags and weekly/preseason/offseason contract parsing.
- [ ] Add regression assertions: Volunteer has no division feature IDs; Saturday has division + IDP IDs; Stampede maps `workload_stat_lines` to `What a Way to Make a Living`; Hollywood has real weekly departments.
- [ ] Implement parser validation for duplicate feature IDs, invalid dependency strength, and missing display names.
- [ ] Rewrite `config/publications.json` from the approved spec, removing obsolete Volunteer division and Stampede Heavy Lifting wording.
- [ ] Run `python -m pytest tests/test_config.py tests/test_publication_contracts.py -q` and commit `feat: encode publication feature contracts`.

---

### Task 3: Centralize weekly shared producers

**Files:** Create `editorial_desk/feature_producers.py`; modify `editorial_desk/weekly_features.py`; create `tests/test_feature_producers.py`; update `tests/test_manager_award.py`.

**Required interfaces:**

```python
result_flipping_decisions(snapshot, dossier)
winning_decision_swings(snapshot, dossier)
league_wide_started_mvp(snapshot)
divisional_started_mvps(snapshot)
position_leaders(snapshot)
bench_leader(snapshot)
waiver_impact(snapshot, dossier)
record_watch(dossier, chronicle_history)
bench_blast(snapshot)
```

- [ ] Test a legal bench swap that changes a matchup result.
- [ ] Test Volunteer `winning_decision_swings` independently from efficiency ranking.
- [ ] Test Volunteer league-wide started-player MVP with no division dependency.
- [ ] Test Saturday East/West started-player MVPs and gold designation.
- [ ] Test IDP leaders alongside offensive positions.
- [ ] Test waiver impact preserves transaction type, FAAB, lineup status, points, and margin relevance.
- [ ] Test Record Watch carries Chronicle coverage warnings when history is incomplete.
- [ ] Refactor current logic into shared producers without changing the established Manager of the Week formula.
- [ ] Run `python -m pytest tests/test_feature_producers.py tests/test_manager_award.py -q` and commit `refactor: centralize weekly feature calculations`.

---

### Task 4: Implement Stampede NFL workload data

**Files:** Modify `editorial_desk/feature_producers.py` and, only if necessary, `editorial_desk/enriched_collector.py`; extend `tests/test_feature_producers.py`.

**Interface:** `workload_stat_lines(snapshot) -> FeatureResult`.

- [ ] Create fixture stats containing carries, rushing yards/TDs, receptions/receiving yards/TDs, pass attempts/yards/TDs.
- [ ] Assert category leaders are based on real NFL workload/production, not just fantasy-point order.
- [ ] Keep the neutral feature ID `workload_stat_lines`; the publication contract supplies the display name.
- [ ] Run tests and commit `feat: add NFL workload feature data`.

---

### Task 5: Implement universal late-game reconstruction

**Files:** Modify `editorial_desk/feature_producers.py`, `editorial_desk/nfl_enrichment.py`; create `tests/test_game_window_features.py`.

**Interface:** `game_window_context(snapshot, dossier, chronicle_events=None) -> FeatureResult`.

- [ ] Test a team trailing before Monday that wins after a remaining starter scores.
- [ ] Test provenance: Chronicle live snapshot => `observed_live`; computed final-minus-window scoring => `reconstructed`.
- [ ] Preserve pre-window score, remaining players, window points, final score, and final margin.
- [ ] Run `python -m pytest tests/test_game_window_features.py -q` and commit `feat: add universal game-window reconstruction`.

---

### Task 6: Implement normalized preseason/draft producers

**Files:** Modify `editorial_desk/feature_producers.py`; create `tests/test_preseason_features.py`.

**Required interfaces:**

```python
draft_results(snapshot)
draft_adp_value(snapshot)
keeper_value(snapshot)
roster_age(snapshot)
positional_strength(snapshot)
future_pick_ledger(snapshot)
rookie_draft(snapshot)
recruiting_class(snapshot)
dynasty_market(snapshot)
offense_defense_splits(snapshot)
streaming_roster_state(snapshot)
```

- [ ] Test Sleeper-native features as `ready` when source data is present.
- [ ] Test externally dependent features as unavailable/degraded when authoritative source data is absent; never fabricate values.
- [ ] Test Saturday offense/defense split includes IDP as first-class data.
- [ ] Keep subjective labels such as matchup leans or editorial superlatives outside neutral producers unless the contract defines a deterministic rule.
- [ ] Run `python -m pytest tests/test_preseason_features.py -q` and commit `feat: add preseason and draft feature data`.

---

### Task 7: Build packet compiler with dependency evaluation

**Files:** Create `editorial_desk/publication_contracts.py`, `editorial_desk/publication_packets.py`, `tests/test_publication_packets.py`.

**Interface:**

```python
build_publication_packet(
    snapshot,
    dossier,
    publication_config,
    phase,
    chronicle_history=None,
    chronicle_events=None,
) -> dict[str, Any]
```

- [ ] Test health success with zero flags => `ready_no_items`; health source failure => `unavailable`.
- [ ] Test one shared lineup-flip payload maps unchanged to Ballad `Weekly Rounds`, Saturday `Portal Film Room`, Hollywood `Cutting Room Floor`.
- [ ] Implement dependency evaluation: missing required => unavailable; missing preferred => degraded when minimum facts remain; missing optional => no readiness penalty.
- [ ] Implement phase filtering so preseason-only departments are not required weekly.
- [ ] Run `python -m pytest tests/test_publication_packets.py -q` and commit `feat: build publication-ready packets`.

---

### Task 8: Render and write newspaper packets

**Files:** Create `editorial_desk/publication_render.py`; modify `editorial_desk/review.py`, `editorial_desk/enriched_collector.py`; extend `tests/test_publication_packets.py`.

- [ ] Test contract department order and visible unavailable reasons.
- [ ] Implement renderer with no scoring/award calculations.
- [ ] For newspaper publications write `publication_packet.json` and `publication_packet.md` beside existing dossier files.
- [ ] Run `python -m pytest tests/test_publication_packets.py tests/test_health_reporting.py -q` and commit `feat: render themed newspaper packets`.

---

### Task 9: Lock weekly publication regressions

**Files:** Create `tests/test_publication_regressions.py`.

- [ ] Ballad: assert Cardiogram, Final Monitor, Weekly Rounds, Standings, Rankings Wire, Rounds Report, Position Leaders, Waiver Star, Ward Report, Record Watch, Next Card.
- [ ] Volunteer: assert median result, Official Table, Rankings Wire, Decision Desk, league-wide MVP, Efficiency Board, notebook facts, Record Watch, next-week scouting; assert no division output.
- [ ] Saturday: assert East/West pulse/polls/MVPs, IDP Position Board, Portal Film Room/Commitments, Dynasty Market, Transfer Portal, Recruiting/future picks.
- [ ] Stampede: assert exact `What a Way to Make a Living`, real NFL workload data, and no retired Heavy Lifting label in production output.
- [ ] Hollywood: assert Box Office, Marquee, Hollywood Board, Late Show, For Your Consideration, Cutting Room Floor, Studio Efficiency, Casting Call, Production Delays, This Week’s Bill.
- [ ] Run `python -m pytest tests/test_publication_regressions.py -q` and commit `test: lock weekly newspaper contracts`.

---

### Task 10: Lock preseason/draft regressions

**Files:** Extend `tests/test_publication_contracts.py`, `tests/test_publication_packets.py`, `tests/test_preseason_features.py`.

- [ ] Ballad preseason: Draft Desk, Opening Card inputs, Keeper Heist, Ward Report, Draft Board, ADP profile, Value/Reach, Streamers’ Pact; matchup lean remains editorial.
- [ ] Stampede preseason: Rankings Wire, First Shift, Value Board, Paper Favorite inputs, Stampede Board, Market Report, I Will Always Love You, Bargain Store, Coat of Many Colors, Old Flames, Little Engine That Could, Mystery Mine, Season Prediction inputs, Preseason Truth support.
- [ ] Volunteer preseason: Rankings Wire, First Read facts, Pack Is Tighter Than It Looks inputs, Rocky Top Board, Commissioner’s Warning inputs, superlative inputs, scouting capsules; no division assumptions.
- [ ] Saturday preseason: Committee Poll, Depth Chart Wire offense/defense split, East/West order, Selection Committee inputs, Divisional Board, Transfer Portal, PI inputs, Recruiting Board/Class Standings/Desk.
- [ ] Hollywood preseason: Opening Credits, Top Billing/First Read inputs, Critics’ Poll, Hollywood Board, Dailies, Meet the Cast inputs, Development Slate, rookie Casting Call, Development Rights, future-pick scarcity, Studio Deals, Production Delays, This Week’s Bill.
- [ ] Compile a weekly packet with no preseason inputs and assert it remains valid.
- [ ] Run the three phase test files and commit `test: lock phase-aware newspaper contracts`.

---

### Task 11: Phase 3 verification gate

- [ ] Run `python -m pytest -q`.
- [ ] Generate fixture JSON/Markdown packets for all five newspapers and inspect for missing locked departments or cross-publication label leakage.
- [ ] Run `grep -R "Week's Heavy Lifting\|publication standard pending" config editorial_desk --exclude-dir=.git || true`; expect no production matches.
- [ ] Verify Volunteer packet/config contains no division feature and Saturday retains division structures.
- [ ] Code-review that renderers/contracts do not recalculate lineup efficiency, result flips, or waiver impact.
- [ ] Commit verification fixes only if needed with `test: close publication contract regressions`.
