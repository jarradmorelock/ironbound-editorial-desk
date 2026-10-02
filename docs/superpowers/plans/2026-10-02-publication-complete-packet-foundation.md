# Publication-Complete Packet Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the deterministic Publication-Complete Packet, readiness gate, and Week 3 offline acceptance case so a later local manuscript builder can write the flagship issue without further research.

**Architecture:** Keep the existing collector, Chronicle, flagship research packet, beat/news handoff, and ranking handoff intact. Add a canonical evidence layer that reconciles historical league facts and transactions, then compile a publication-facing packet whose required departments are validated before downstream use. Prove the boundary with a checked-in Week 3 Ironbound acceptance fixture and a network-free integration test.

**Tech Stack:** Python 3.11+, pytest, existing requests-based Sleeper/nflverse clients, existing Chronicle JSONL/materialized query layer, JSON artifacts.

**Spec:** `docs/superpowers/specs/2026-10-02-publication-complete-packet-design.md`

## Global Constraints

- After `publication_complete_packet.json` is emitted, downstream manuscript and slide builders may not call Sleeper, nflverse, Chronicle, GitHub, web search, screenshots, prior magazines, or any other research source.
- The finished Week 3 Ironbound magazine is the first flagship acceptance case.
- `FROM_THE_IRONBOUND_DESK` remains intentionally manual and is excluded from publication-readiness requirements.
- Do not lock the magazine to a permanent 22-, 24-, 25-, or 26-page count.
- Ironbound Power Rankings remains authoritative for rank, movement, supplied model outputs, and supplied ranking/playoff graphics; Editorial Desk must not recompute them.
- Sleeper historical matchups are authoritative for league results, submitted lineups, and fantasy player scores for the exact league/week; Chronicle and prior finalized artifacts are corroborating/fallback sources.
- Sleeper retained same-season/week projections are valid historical projection evidence and are scored with the league's Sleeper scoring settings.
- Required-source conflicts must produce `MANUAL_VERIFY`/blocking evidence, never silent source selection.
- Optional enrichment failures must be warnings unless a required selected department explicitly depends on them.
- Preserve existing flagship research artifacts for compatibility; the new packet is additive.
- Use TDD for every task and run the entire pytest suite before branch completion.

## Review Focus

1. **Historical-source disagreement:** when Sleeper and Chronicle disagree on the same finalized player/team value, the resolver must block that fact instead of silently preferring one; Task 1 adds this conflict test.
2. **Incomplete early-week coverage:** when one historical week or roster is missing, cumulative boards and entering-record evidence must be incomplete/blocking rather than presented as full-season totals; Task 1 tests this.
3. **Sparse projection rows:** one unrelated fringe player with no scoreable projection must not disable projection-based awards that have all evidence they actually require; Task 3 tests candidate-specific readiness.
4. **Multi-leg trades and pick provenance:** transactions crossing Sleeper transaction-week legs must preserve every player/pick and original/previous/current pick owner when Sleeper supplies it; Task 2 tests this.
5. **Time-sensitive health cutoff:** health evidence observed after the packet cutoff must not leak into the packet, while the latest verified observation at/before cutoff must remain usable; Task 4 tests this.

---

### Task 1: Canonical Historical League Evidence

**Files:**
- Create: `editorial_desk/canonical_evidence.py`
- Modify: `editorial_desk/flagship_research.py`
- Test: `tests/test_canonical_evidence.py`
- Modify test: `tests/test_week2_completeness_fixes.py`

**Interfaces:**
- Consumes: enriched `snapshot: dict[str, Any]`, optional `ChronicleQueries`.
- Produces: `build_canonical_league_evidence(snapshot: dict[str, Any], chronicle: ChronicleQueries | None = None) -> dict[str, Any]`.
- Produces evidence keys: `historical_matchups`, `player_weeks`, `entering_records`, `team_season_totals`, `player_season_totals`, `division_summary`, `evidence_index`, `conflicts`, `coverage`.
- Produces stable IDs through `evidence_id(kind: str, season: str, week: int | None, *parts: object) -> str`.
- Later tasks consume this object without re-reading Sleeper/Chronicle.

- [ ] **Step 1: Write failing tests for historical Sleeper evidence and conflict handling**

Create `tests/test_canonical_evidence.py` with focused tests:

```python
def test_sleeper_schedule_history_builds_entering_records_and_player_totals():
    result = build_canonical_league_evidence(snapshot_with_weeks_1_to_3(), None)
    assert result["coverage"]["weeks"] == [1, 2, 3]
    assert result["entering_records"]["3"]["1"] == {"wins": 2, "losses": 0, "ties": 0}
    assert result["player_season_totals"]["p1"]["points"] == 63.5
    assert result["player_season_totals"]["p1"]["through_week"] == 3

def test_missing_historical_roster_blocks_full_season_totals():
    result = build_canonical_league_evidence(snapshot_missing_one_week_two_roster(), None)
    assert result["coverage"]["status"] == "PARTIAL"
    assert "week 2" in result["coverage"]["reason"].lower()
    assert result["player_season_totals_status"] == "UNAVAILABLE"

def test_sleeper_chronicle_conflict_is_manual_verify():
    result = build_canonical_league_evidence(
        snapshot_with_final(week=1, roster_id=1, points=100.0),
        ChronicleWithMatchupFinal(points=99.0),
    )
    assert result["conflicts"][0]["status"] == "MANUAL_VERIFY"
    assert result["coverage"]["status"] == "MANUAL_VERIFY"
```

Extend `tests/test_week2_completeness_fixes.py` so the season team/player board path can consume historical Sleeper schedule rows when Chronicle is absent.

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```bash
pytest tests/test_canonical_evidence.py tests/test_week2_completeness_fixes.py -q
```

Expected: new canonical-evidence tests fail because the module/functions do not yet exist, while existing unrelated tests remain green.

- [ ] **Step 3: Implement `canonical_evidence.py` and route flagship cumulative boards through it**

Implement:

```python
def evidence_id(kind: str, season: str, week: int | None, *parts: object) -> str: ...

def build_canonical_league_evidence(
    snapshot: dict[str, Any],
    chronicle: ChronicleQueries | None = None,
) -> dict[str, Any]: ...
```

Required behavior:

- Read current and prior completed weeks from `snapshot["flagship_sleeper"]["schedule"]["weeks"]`; include the current `snapshot["matchups"]` as authoritative current-week rows.
- Build one canonical roster-week record per team and one canonical player-week record per rostered player using Sleeper `players_points` / `players_points_custom`.
- Use Chronicle finalized matchup/player events only to corroborate or fill genuinely absent Sleeper historical rows.
- Record a conflict when both authoritative sources exist for the same roster/player-week and materially disagree.
- Compute entering records for every reviewed week from canonical prior-week results.
- Compute cumulative team/player totals only when coverage is complete through the reviewed week.
- Compute division membership and pooled internal/cross-division W-L, total PF, team-game count, and scoring average using roster division settings plus league metadata.
- Return explicit status/reason fields instead of treating partial history as full history.

Modify `flagship_research.py` to use this canonical evidence for season team score and player boards rather than requiring Chronicle-only historical player events.

- [ ] **Step 4: Run canonical and flagship regression tests**

Run:

```bash
pytest tests/test_canonical_evidence.py tests/test_week2_completeness_fixes.py tests/test_flagship_research*.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add editorial_desk/canonical_evidence.py editorial_desk/flagship_research.py tests/test_canonical_evidence.py tests/test_week2_completeness_fixes.py
git commit -m "feat: add canonical historical league evidence"
```

---

### Task 2: Normalize Complete Transactions and Draft-Pick Provenance

**Files:**
- Create: `editorial_desk/transaction_evidence.py`
- Modify: `editorial_desk/roster_market.py`
- Test: `tests/test_transaction_evidence.py`
- Modify test: `tests/test_roster_market.py`

**Interfaces:**
- Consumes: `snapshot: dict[str, Any]`, optional `ChronicleQueries`.
- Produces: `build_transaction_evidence(snapshot: dict[str, Any], chronicle: ChronicleQueries | None = None) -> dict[str, Any]`.
- Produces normalized `transactions: list[dict[str, Any]]` with `transaction_id`, `week`, `type`, `completed_at`, `teams`, `players`, `draft_picks`, `faab`, `evidence_ids`.
- Produces `pick_provenance_status` and `coverage`.
- `roster_market.py` may consume the normalized records instead of independently decoding the same Sleeper payloads.

- [ ] **Step 1: Write failing transaction tests**

Create tests that cover:

```python
def test_trade_normalization_preserves_every_player_and_pick():
    result = build_transaction_evidence(snapshot_with_buckaneers_trade(), None)
    trade = result["transactions"][0]
    assert {p["player"] for p in trade["players"]["received_by"]["The Buckaneers"]} == {
        "Drake London", "Germie Bernard"
    }
    pick = trade["draft_picks"][0]
    assert pick["season"] == "2027"
    assert pick["round"] == 1
    assert pick["original_team"] == "The Buckaneers"

def test_pick_provenance_keeps_original_previous_and_new_owner():
    pick = build_transaction_evidence(snapshot_with_retraded_pick(), None)["transactions"][0]["draft_picks"][0]
    assert pick["original_roster_id"] == 10
    assert pick["previous_owner_roster_id"] == 2
    assert pick["new_owner_roster_id"] == 4

def test_transactions_across_sleeper_week_legs_are_not_dropped():
    result = build_transaction_evidence(snapshot_with_week2_and_week3_trade_legs(), None)
    assert {row["transaction_id"] for row in result["transactions"]} == {"tx-week2", "tx-week3"}
```

Extend `tests/test_roster_market.py` to assert the Transaction Desk uses the normalized object and retains FAAB plus complete trade compensation.

- [ ] **Step 2: Run transaction tests and verify RED**

Run:

```bash
pytest tests/test_transaction_evidence.py tests/test_roster_market.py -q
```

Expected: FAIL because `transaction_evidence.py` does not exist.

- [ ] **Step 3: Implement transaction normalization**

Implement:

```python
def build_transaction_evidence(
    snapshot: dict[str, Any],
    chronicle: ChronicleQueries | None = None,
) -> dict[str, Any]: ...
```

Rules:

- Read every completed transaction through the reviewed week from `flagship_sleeper.transactions.weeks`; fall back to current snapshot transactions only when the flagship history block is absent.
- Dedupe by `transaction_id`.
- Resolve team/player names from snapshot users/rosters/player directory.
- Preserve raw Sleeper draft-pick fields required for provenance, including original roster ID and previous/new owner IDs when supplied.
- Map those roster IDs to team labels without inventing unknown owners.
- Normalize FAAB from `settings.waiver_bid` or `settings.amount`.
- Preserve Chronicle event IDs only as additional provenance, not as a replacement for exact Sleeper transaction terms.
- Mark unresolved pick provenance as a per-transaction warning; only the publication readiness layer decides whether that warning blocks a required Transaction Desk claim.

Refactor `roster_market.py` to consume the normalized transaction evidence for current-week transaction rows and repeated-movement counts where practical, avoiding a second incompatible decoder.

- [ ] **Step 4: Run transaction and market tests**

Run:

```bash
pytest tests/test_transaction_evidence.py tests/test_roster_market.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add editorial_desk/transaction_evidence.py editorial_desk/roster_market.py tests/test_transaction_evidence.py tests/test_roster_market.py
git commit -m "feat: normalize publication transaction evidence"
```

---

### Task 3: Make Honors Evidence Candidate-Specific and Historical-Record Complete

**Files:**
- Modify: `editorial_desk/honors.py`
- Modify: `editorial_desk/flagship_research.py`
- Test: `tests/test_honors_registry.py`
- Test: `tests/test_historical_projection_awards.py`
- Test: `tests/test_canonical_evidence.py`

**Interfaces:**
- Consumes: existing `research_honors(...)` inputs plus canonical historical evidence through helper calls.
- Preserves public `research_honors(snapshot, dossier, external, history=(), chronicle=None)` signature unless an optional keyword is required for clean integration.
- Produces the existing honors object, but availability becomes candidate/matchup-specific rather than league-global.

- [ ] **Step 1: Add failing honors regressions**

Add tests:

```python
def test_unprojected_fringe_bench_player_does_not_disable_iron_balls():
    result = research_honors(snapshot_with_valid_decision_and_unrelated_unprojected_player(), dossier(), external())
    assert result["award_availability"]["IRON_BALLS"]["status"] == "AVAILABLE"
    assert any(row["candidate_type"] == "IRON_BALLS" for row in result["rotating_award_candidates"])

def test_no_fear_uses_complete_actual_submitted_starter_projection_only():
    result = research_honors(snapshot_with_all_starter_projections(), dossier(), external())
    candidate = next(row for row in result["rotating_award_candidates"] if row["candidate_type"] == "NO_FEAR")
    assert candidate["evidence"]["projected_deficit"] >= 15.0

def test_bad_beat_and_escape_artist_use_sleeper_historical_entering_records():
    packet = build_flagship_research_packet_for_week3_without_prior_dossiers()
    assert packet["weekly_honors"]["bad_beat"]["entering_record"] == {"wins": 2, "losses": 0, "ties": 0}
    assert packet["weekly_honors"]["escape_artist"]["entering_record"] is not None
```

- [ ] **Step 2: Run honors tests and verify RED**

Run:

```bash
pytest tests/test_honors_registry.py tests/test_historical_projection_awards.py -q
```

Expected: at least the sparse-projection and entering-record tests fail on current behavior.

- [ ] **Step 3: Implement candidate-specific projection readiness and canonical entering records**

In `honors.py`:

- remove the global requirement that every active rostered player have a scoreable projection before projection-based awards can evaluate;
- evaluate Iron Balls/Bone Head/Mad Blacksmith only when the specific starter/alternative pair has both projection and actual-score evidence;
- evaluate Goosed/Tempered only for starters with their own verified projection;
- evaluate Full Forge only when every starter on that one roster has a verified projection;
- evaluate No Fear only when all actual submitted starters for both teams in that matchup have verified projections;
- return `PARTIAL`/candidate-level reasons when some teams cannot be evaluated, while still emitting qualified candidates from evaluable teams.

In `flagship_research.py`:

- derive Bad Beat/Escape Artist entering records from canonical historical evidence/Sleeper schedule when prior dossier history is absent;
- preserve the non-overlap rule between Bad Beat and Escape Artist.

Do not change any award threshold.

- [ ] **Step 4: Run honors and flagship packet tests**

Run:

```bash
pytest tests/test_honors_registry.py tests/test_historical_projection_awards.py tests/test_flagship_research*.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add editorial_desk/honors.py editorial_desk/flagship_research.py tests/test_honors_registry.py tests/test_historical_projection_awards.py
git commit -m "fix: evaluate honors from complete candidate evidence"
```

---

### Task 4: Build Source Manifest and Cutoff-Safe Health Evidence

**Files:**
- Create: `editorial_desk/publication_sources.py`
- Modify: `editorial_desk/enriched_collector.py`
- Test: `tests/test_publication_sources.py`
- Modify test: `tests/test_roster_market.py`

**Interfaces:**
- Produces: `build_source_manifest(snapshot: dict[str, Any], dossier: dict[str, Any], external: ExternalEditorialInputs, *, beat_report: dict[str, Any] | None, publication_assets: dict[str, Any] | None, information_cutoff: str | None = None) -> dict[str, Any]`.
- Produces: `health_evidence(snapshot: dict[str, Any], dossier: dict[str, Any], beat_report: dict[str, Any] | None, information_cutoff: str | None) -> dict[str, Any]`.
- Later packet builder consumes both objects.

- [ ] **Step 1: Write failing source/cutoff tests**

Create tests:

```python
def test_source_manifest_reports_exact_sleeper_history_projection_and_ranking_status():
    manifest = build_source_manifest(snapshot(), dossier(), external_ready(), beat_report=beat(), publication_assets=assets())
    assert manifest["sleeper"]["matchups"]["weeks"] == [1, 2, 3]
    assert manifest["sleeper"]["projections"]["week"] == 3
    assert manifest["rankings"]["status"] == "READY"

def test_health_evidence_excludes_observation_after_cutoff():
    result = health_evidence(snapshot(), dossier_with_health(), beat_with_before_and_after_events(), "2026-09-30T18:00:00+00:00")
    assert [row["event_id"] for row in result["news_events"]] == ["before-cutoff"]

def test_partial_beat_history_is_warning_not_health_fact_invention():
    manifest = build_source_manifest(...beat_report=partial_beat_report()...)
    assert manifest["beat_news"]["status"] == "PARTIAL"
    assert manifest["beat_news"]["blocking"] is False
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
pytest tests/test_publication_sources.py -q
```

Expected: FAIL because the source-manifest module does not exist.

- [ ] **Step 3: Implement source manifest and cutoff-safe health evidence**

Implement the interfaces above.

Requirements:

- `information_cutoff` defaults to the dossier/packet information timestamp when not explicitly passed.
- Report exact Sleeper schedule/transaction/projection coverage already present in the snapshot.
- Report nflverse source statuses from `snapshot["nfl_context"]`.
- Report ranking handoff availability, schema version, ranking week/results-through-week metadata, and supplied asset readiness without recalculating values.
- Preserve beat-news coverage start and partial status.
- Build health rows from the latest verified status at/before cutoff; never include later news/status observations.
- Keep time-sensitive/source-limited notes in structured warnings.

Wire `enriched_collector.py` to build these objects once per flagship publication for use by Task 5.

- [ ] **Step 4: Run source/health tests**

Run:

```bash
pytest tests/test_publication_sources.py tests/test_roster_market.py tests/test_beat_news.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add editorial_desk/publication_sources.py editorial_desk/enriched_collector.py tests/test_publication_sources.py tests/test_roster_market.py
git commit -m "feat: add publication source and cutoff evidence"
```

---

### Task 5: Compile and Validate the Publication-Complete Packet

**Files:**
- Create: `editorial_desk/publication_complete.py`
- Modify: `editorial_desk/enriched_collector.py`
- Test: `tests/test_publication_complete.py`
- Modify: `tests/test_reading_packets.py`

**Interfaces:**
- Produces: `build_publication_complete_packet(snapshot: dict[str, Any], dossier: dict[str, Any], flagship_packet: dict[str, Any], external: ExternalEditorialInputs, *, canonical_evidence: dict[str, Any], transaction_evidence: dict[str, Any], source_manifest: dict[str, Any], health: dict[str, Any], publication_assets: dict[str, Any] | None = None) -> dict[str, Any]`.
- Produces: `validate_publication_complete_packet(packet: dict[str, Any]) -> dict[str, Any]`.
- Produces: `write_publication_complete_packet(directory: Path, packet: dict[str, Any]) -> tuple[Path, ...]`.
- File output: `publication_complete_packet.json` and compact `publication_complete_packet.md`.
- Contract version: `publication-complete-v1`.

- [ ] **Step 1: Write failing packet/readiness tests**

Create tests for exact top-level contract:

```python
def test_complete_flagship_packet_contains_writer_ready_departments():
    packet = build_complete_fixture_packet()
    assert packet["contract_version"] == "publication-complete-v1"
    assert set(packet) >= {
        "issue_identity", "source_manifest", "readiness", "evidence_index",
        "game_dossiers", "feature_evidence", "usage_desk", "roster_health",
        "transaction_desk", "manager_honors", "player_honors", "rookie_watch",
        "division_report", "power_board", "playoff_forecast", "power_rankings",
        "week_ahead", "sources_and_model_notes", "publication_assets"
    }

def test_missing_required_transaction_fact_blocks_publication():
    packet = build_packet_with_unresolved_required_pick_provenance()
    assert packet["readiness"]["publication_ready"] is False
    assert packet["readiness"]["status"] == "BLOCKED"
    assert any(gap["section"] == "transaction_desk" for gap in packet["readiness"]["blocking_gaps"])

def test_optional_market_enrichment_does_not_block_publication():
    packet = build_packet_with_optional_sleeper_market_unavailable()
    assert packet["readiness"]["publication_ready"] is True
    assert any(gap["section"] == "optional_market" for gap in packet["readiness"]["optional_gaps"])

def test_packet_does_not_require_fixed_page_count():
    packet = build_complete_fixture_packet()
    assert "required_page_count" not in packet["readiness"]
```

- [ ] **Step 2: Run packet tests and verify RED**

Run:

```bash
pytest tests/test_publication_complete.py -q
```

Expected: FAIL because the packet module does not exist.

- [ ] **Step 3: Implement packet compiler, evidence index, and readiness validator**

Build the packet from already-normalized inputs.

Department rules:

- `game_dossiers`: all eight reviewed-week matchups plus normalized historical/entering context and evidence IDs.
- `feature_evidence`: existing Story Desk/cover candidates plus related verified transaction/health/ranking/history facts, never prose.
- `usage_desk`: reuse writer-ready normalized usage rows from flagship research.
- `roster_health`: cutoff-safe Task 4 object.
- `transaction_desk`: Task 2 normalized transactions, plus immediate reviewed-week performance/start status for acquired players when deterministically available.
- `manager_honors`: static honors, season boards, all rotating qualified/manual-review candidates, award audit, and `commissioner_selection_required=true`.
- `player_honors`: weekly distinct winners, benchwarmer/free agent, NFL stat lines, season positional boards.
- `rookie_watch`: weekly Top 5, draft provenance, weekly award candidates, season position leaders.
- `division_report`: canonical Task 1 values plus supplied division forecast/SOS rows where available.
- `power_board`, `playoff_forecast`, `power_rankings`: pass authoritative handoff data/assets through unchanged.
- `week_ahead`: all next-week matchups plus supplied projected-optimal model rows and health caveats available at cutoff.
- `sources_and_model_notes`: structured distinctions among measured facts, models, time-sensitive health, partial beat coverage, and experimental optional data.

Readiness rules:

- require exactly eight completed flagship matchups for the 16-team flagship profile;
- require complete reviewed-week submitted lineup/player-score evidence;
- require complete prior weeks needed for entering records and cumulative boards;
- require complete normalized reporting-window transactions used by the Transaction Desk;
- require current health object at the stated cutoff;
- require static honors and deterministic season boards;
- require rookie draft/season context used by Rookie Watch;
- require division calculations;
- require current rankings/playoff/SOS handoff and required ranking assets;
- require all eight next-week matchup forecast rows when the issue contains a Full Slate department;
- classify genuinely optional enrichments as warnings/optional gaps.

`write_publication_complete_packet` writes JSON plus a compact human-readable readiness/source summary. Do not duplicate the full manuscript-like flagship research Markdown.

Wire `enriched_collector.py` so every flagship run emits the new files next to `flagship_research_packet.json`.

- [ ] **Step 4: Run packet and collector tests**

Run:

```bash
pytest tests/test_publication_complete.py tests/test_reading_packets.py tests/test_flagship_research.py tests/test_ranking_asset_handoff.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add editorial_desk/publication_complete.py editorial_desk/enriched_collector.py tests/test_publication_complete.py tests/test_reading_packets.py
git commit -m "feat: emit publication-complete flagship packet"
```

---

### Task 6: Add Week 3 Ironbound Gold-Standard Acceptance Fixture

**Files:**
- Create: `tests/fixtures/ironbound_week3_publication_input.json`
- Create: `tests/fixtures/ironbound_week3_publication_acceptance.json`
- Create: `tests/test_ironbound_week3_publication_acceptance.py`
- Modify: `docs/superpowers/specs/2026-10-02-publication-complete-packet-design.md` only if implementation reveals an ambiguity that must be clarified before the test can be written.

**Interfaces:**
- The input fixture is a compact, deterministic extraction of the Week 3 workflow evidence required for the acceptance claims; it must not depend on the user's PPTX file at test runtime.
- The acceptance manifest records the factual capabilities expected from the finished Week 3 issue.
- Test consumes only local fixture JSON and production packet-building functions.

- [ ] **Step 1: Create the acceptance manifest and failing integration test**

The acceptance manifest must pin at least these Week 3 capabilities/facts from the finished issue:

```json
{
  "season": "2026",
  "week": 3,
  "required_matchups": 8,
  "manager_honors": {
    "bad_beat_team": "Martian Targaryen",
    "escape_artist_team": "Granite Mountain Drakes",
    "no_fear_team": "The Mad Hatters FC",
    "no_fear_min_projected_deficit": 15.0
  },
  "player_honors": {
    "overall": "Jahmyr Gibbs",
    "benchwarmer": "Geno Smith"
  },
  "season_team_points_top_three": [
    "Martian Targaryen",
    "Madtown Coyotes",
    "Frozen Tundraners"
  ],
  "division_averages": {
    "Forge": 112.3608,
    "Hammer": 107.1367,
    "Anvil": 101.78,
    "Crucible": 98.7117
  },
  "week_ahead_matchups": 8
}
```

Also include acceptance checks that the normalized transaction evidence contains the Buckaneers/Chicken and Buckaneers/San Carlos trade compensation described in the finished issue, including transferred picks and pick provenance when supplied by the source fixture.

Write:

```python
def test_week3_gold_standard_is_publication_ready_without_external_research():
    packet = build_week3_packet_from_local_fixture()
    assert packet["readiness"]["publication_ready"] is True
    assert len(packet["game_dossiers"]) == 8
    assert acceptance_matches(packet, load_acceptance_manifest())
```

- [ ] **Step 2: Run the Week 3 acceptance test and verify RED**

Run:

```bash
pytest tests/test_ironbound_week3_publication_acceptance.py -q
```

Expected: FAIL on whichever factual department is not yet supplied completely by Tasks 1-5. Treat those failures as upstream research-contract defects, not reasons to weaken the acceptance manifest.

- [ ] **Step 3: Close only the upstream gaps exposed by the fixture**

Modify the owning modules from Tasks 1-5 as necessary.

Rules:

- do not add web/API calls to the test or downstream packet consumer;
- do not hard-code Week 3 answers into production code;
- fix the generic evidence normalization/calculation that caused each missing capability;
- if the source fixture genuinely lacks an evidence field that production already collects, add that field to the compact local input fixture;
- if production does not collect a required recurring fact, add the collection to the existing upstream collector, not the packet writer.

- [ ] **Step 4: Run Week 3 acceptance plus all related department tests**

Run:

```bash
pytest   tests/test_ironbound_week3_publication_acceptance.py   tests/test_canonical_evidence.py   tests/test_transaction_evidence.py   tests/test_honors_registry.py   tests/test_publication_sources.py   tests/test_publication_complete.py -q
```

Expected: PASS and `publication_ready == true` for the Week 3 gold-standard fixture.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/ironbound_week3_publication_input.json tests/fixtures/ironbound_week3_publication_acceptance.json tests/test_ironbound_week3_publication_acceptance.py editorial_desk
git commit -m "test: prove week 3 publication-complete research"
```

---

### Task 7: Enforce the Offline Boundary and Integrate Production Output

**Files:**
- Create: `tests/test_publication_offline_boundary.py`
- Modify: `editorial_desk/enriched_collector.py`
- Modify: `editorial_desk/reading_packet.py`
- Modify: `README.md`
- Modify: `.github/workflows/editorial-desk-dry-run.yml`
- Test: `tests/test_workflow_integration.py`

**Interfaces:**
- No new research interface.
- Production workflow must package and deliver `publication_complete_packet.json` with the flagship dossier artifacts.
- The local-builder boundary is represented by a test consumer that receives a packet object/path only and has no research clients.

- [ ] **Step 1: Write failing offline/workflow tests**

Create an offline test that patches/fails all known research entry points and then performs packet-to-consumer validation:

```python
def test_publication_packet_consumer_requires_no_research_clients(monkeypatch, week3_packet):
    monkeypatch.setattr(SleeperClient, "get_json", fail_if_called)
    monkeypatch.setattr(NFLVerseClient, "player_stats", fail_if_called)
    monkeypatch.setattr(ChronicleQueries, "league_events", fail_if_called)

    summary = validate_offline_consumability(week3_packet)

    assert summary["research_calls"] == 0
    assert summary["required_departments_ready"] is True
```

Extend `tests/test_workflow_integration.py`:

```python
def test_tuesday_delivery_packages_publication_complete_packet():
    text = _text(WEEKLY)
    assert "publication_complete_packet.json" in text
```

- [ ] **Step 2: Run boundary/workflow tests and verify RED**

Run:

```bash
pytest tests/test_publication_offline_boundary.py tests/test_workflow_integration.py -q
```

Expected: FAIL until packaging and the local-only validation helper exist.

- [ ] **Step 3: Implement the offline-consumability validator and production packaging**

Add to `publication_complete.py`:

```python
def validate_offline_consumability(packet: dict[str, Any]) -> dict[str, Any]: ...
```

This validator inspects only the supplied packet and must not accept any client objects.

Update:

- `enriched_collector.py` generated-path list so new packet files are included in artifacts;
- `reading_packet.py` to point editors/builders to `publication_complete_packet.json` as the factual source of truth while retaining current reading packet compatibility;
- Tuesday workflow artifact/email packaging so the publication-complete packet is included in the delivered flagship package;
- README to document the boundary: research finishes before local writing begins.

Do not make a partial Week 3 beat-news coverage warning fail the entire production run unless a required factual department actually lacks evidence.

- [ ] **Step 4: Run full verification**

Run:

```bash
pytest -q
python -m compileall editorial_desk
```

Expected:

- full pytest suite PASS;
- compileall exits 0;
- Week 3 gold-standard fixture reports `publication_ready=true`;
- no offline-consumer test performs a research call.

- [ ] **Step 5: Commit**

```bash
git add editorial_desk/publication_complete.py editorial_desk/enriched_collector.py editorial_desk/reading_packet.py tests/test_publication_offline_boundary.py tests/test_workflow_integration.py .github/workflows/editorial-desk-dry-run.yml README.md
git commit -m "feat: enforce publication-complete offline boundary"
```

---

## Branch Completion Verification

After all seven tasks:

1. Run `pytest -q`.
2. Run `python -m compileall editorial_desk`.
3. Generate a Week 3 publication-complete packet from the checked-in fixture and save the test output/log showing `publication_ready=true`.
4. Review the generated `publication_complete_packet.json` manually for:
   - eight matchups;
   - complete Week 1-3 cumulative facts;
   - complete normalized major trades/picks;
   - honors candidates and audit;
   - season player/rookie boards;
   - division report;
   - eight Week 4 forecast rows;
   - source manifest and cutoff;
   - no fixed-page-count requirement.
5. Request fresh whole-branch code review before merge.
6. Merge only after CI is green and review findings are resolved.

## Follow-on Plans

Do **not** implement these in this plan:

1. **Local Editorial Manuscript Pipeline**
   - `editorial_brief.json`
   - `issue_plan.json`
   - commissioner editorial checkpoint
   - section assignment JSON
   - structured manuscript
   - continuity pass
   - `manuscript_approved.json`

2. **Procedural PowerPoint Publisher**
   - Press Runbook
   - portrait editable PowerPoint templates
   - page-plan driven layout
   - native objects and overflow preflight
   - placement of authoritative ranking assets unchanged

Those plans begin only after this plan proves the factual offline boundary.
