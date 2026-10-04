# Ironbound NFL Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add flagship-only NFL usage/game-script intelligence plus the corrected weekly magazine award evidence before the next Tuesday dossier rerun.

**Architecture:** Keep Sleeper as the authoritative fantasy-score/roster source. Extend the existing shared nflverse collection with full-week play-by-play and game-level snap counts, then derive compact flagship-only usage/story signals in a focused enrichment module. The existing `metrics.py` remains the owner of fantasy-league awards, while the new NFL module owns NFL usage and game-script analysis.

**Tech Stack:** Python 3.12, requests, csv/gzip standard library parsing, pytest, GitHub Actions.

**Spec:** `docs/ironbound-nfl-enrichment-design.md`

## Global Constraints

- Only `tier: flagship` leagues receive deep NFL enrichment.
- Sleeper final fantasy scores remain authoritative.
- Divisional MVP nominees must be STARTED players only; the top of the four is flagged gold foil; no card image is generated.
- Rookie of the Week must include `STARTED`, `BENCH`, or `TAXI` weekly status.
- Benchwarmer of the Week excludes taxi and reserve players.
- Free Agent of the Week means highest-scoring unrostered NFL player when complete NFL weekly stats are available.
- nflverse participation/FTN charting is not required in-season.
- Missing optional NFL sources must degrade gracefully and never block the Sleeper dossier.

---

### Task 1: Correct Sleeper-style max-points and weekly magazine features

**Files:**
- Modify: `editorial_desk/metrics.py`
- Modify: `tests/test_metrics.py`

**Interfaces:**
- Consumes: existing Sleeper snapshot fields `matchups`, `rosters`, `players`, `league.metadata`, and complete `nfl_context.player_stats`.
- Produces: `weekly_features` with `divisional_mvp_nominees`, `top_scorers_by_position`, `benchwarmer_of_the_week`, `rookie_of_the_week`, and `free_agent_of_the_week`.

- [ ] **Step 1: Write failing tests**

Add tests that prove: taxi players are included in legal max-points calculation; divisional MVPs only come from submitted starters; rookie status resolves STARTED/BENCH/TAXI; free-agent winner comes from complete nflverse stats but excludes rostered players.

```python
def test_lineup_efficiency_includes_taxi_in_sleeper_max_points():
    data = snapshot()
    data["rosters"][0]["taxi"] = ["rb2"]
    dossier = build_weekly_dossier(data)
    row = next(r for r in dossier["lineup_efficiency"] if r["roster_id"] == 1)
    assert row["optimal_points"] == 116
    assert row["efficiency"] == round(101 / 116, 4)


def test_weekly_features_keep_mvp_started_only_and_mark_gold_foil():
    dossier = build_weekly_dossier(snapshot())
    nominees = dossier["weekly_features"]["divisional_mvp_nominees"]
    assert {row["division_name"] for row in nominees} == {"Forge", "Anvil"}
    assert all(row["status"] == "STARTED" for row in nominees)
    assert sum(bool(row["gold_foil"]) for row in nominees) == 1


def test_rookie_of_week_reports_taxi_status():
    data = snapshot()
    data["players"]["rb2"].update({"years_exp": 0})
    data["rosters"][0]["taxi"] = ["rb2"]
    dossier = build_weekly_dossier(data)
    assert dossier["weekly_features"]["rookie_of_the_week"]["player"] == "Runner Two"
    assert dossier["weekly_features"]["rookie_of_the_week"]["status"] == "TAXI"


def test_free_agent_of_week_uses_complete_nfl_player_stats():
    data = snapshot()
    data["nfl_context"] = {
        "player_stats": {
            "status": "available",
            "records": [
                {"player_id": "fa1", "player_display_name": "Free Agent Star", "position": "RB", "fantasy_points_ppr": 28.0},
                {"player_id": "g1", "player_display_name": "Rostered Star", "position": "WR", "fantasy_points_ppr": 35.0},
            ],
        }
    }
    data["players"]["wr1"].update({"gsis_id": "g1"})
    dossier = build_weekly_dossier(data)
    assert dossier["weekly_features"]["free_agent_of_the_week"]["player"] == "Free Agent Star"
```

- [ ] **Step 2: Run the new tests and verify RED**

Run the targeted metrics tests. Expected: failures because taxi is currently excluded from max points and `weekly_features` does not exist.

- [ ] **Step 3: Implement the minimal metrics changes**

In `_lineup_efficiency`, exclude only reserve/IR players from max-points eligibility, not taxi. Add focused helpers `_divisional_mvp_nominees`, `_top_scorers_by_position`, `_rookie_of_week`, and `_free_agent_of_week`; expose them under `weekly_features` while preserving existing awards for compatibility.

- [ ] **Step 4: Run tests and verify GREEN**

Run targeted metrics tests, then the full existing metrics module tests.

- [ ] **Step 5: Commit**

Commit message: `feat: add weekly magazine feature evidence`

---

### Task 2: Collect nflverse snap counts and analysis-grade play-by-play

**Files:**
- Modify: `editorial_desk/nflverse.py`
- Modify: `editorial_desk/collector.py`
- Modify: `tests/test_nflverse.py`
- Modify: `tests/test_collector.py`

**Interfaces:**
- Produces `NFLVerseClient.snap_counts(season, week)` and `NFLVerseClient.play_by_play(season, week)`.
- `snap_counts` rows include `game_id`, `pfr_player_id`, `player`, `position`, `team`, `offense_snaps`, and `offense_pct`.
- `play_by_play` rows are filtered to the requested regular-season week and keep only fields needed for opportunity/game-script calculations.

- [ ] **Step 1: Write failing nflverse tests**

```python
def test_snap_counts_parse_game_level_offensive_usage():
    rows = "game_id,pfr_player_id,player,position,team,offense_snaps,offense_pct\n2026_01_NO_ATL,EttiTr00,Travis Etienne,RB,NO,34,0.52\n"
    client = NFLVerseClient(session=Session(rows.encode()))
    result = client.snap_counts("2026", 1)
    assert result[0]["offense_snaps"] == 34
    assert result[0]["offense_pct"] == 0.52


def test_play_by_play_keeps_usage_fields_for_requested_week():
    # gzip CSV fixture containing one Week 1 rush and one Week 2 rush
    result = client.play_by_play("2026", 1)
    assert result == [{...expected Week 1 usage fields...}]
```

- [ ] **Step 2: Verify RED**

Expected: `NFLVerseClient` has no `snap_counts` or `play_by_play` methods.

- [ ] **Step 3: Implement source readers**

Use nflverse release URLs:

```python
SNAP_COUNTS_URL = "https://github.com/nflverse/nflverse-data/releases/download/snap_counts/snap_counts_{season}.csv"
PLAY_BY_PLAY_URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.csv.gz"
```

Parse only the fields required by the enrichment module. Extend `_collect_nfl_week_context` and `_trim_nfl_context` so only flagship leagues retain the large `play_by_play` and `snap_counts` payloads; newspaper leagues continue receiving the lighter schedule/player-stat/late-play context.

- [ ] **Step 4: Verify GREEN**

Run nflverse and collector tests.

- [ ] **Step 5: Commit**

Commit message: `feat: collect flagship nfl usage sources`

---

### Task 3: Derive flagship NFL usage and story signals

**Files:**
- Create: `editorial_desk/nfl_enrichment.py`
- Create: `tests/test_nfl_enrichment.py`
- Modify: `editorial_desk/metrics.py`

**Interfaces:**
- Produces `build_nfl_game_intelligence(snapshot: dict[str, Any]) -> dict[str, Any] | None`.
- Returns `None` for non-flagship leagues.
- Flagship output contains `source_status`, `players`, and `story_signals`.

- [ ] **Step 1: Write failing unit tests**

Tests cover a synthetic backfield with a 52/48 snap split; a player with most reconstructed output in Q4; inside-10 touch imbalance; and a non-flagship snapshot returning `None`.

```python
def test_backfield_split_signal_requires_near_even_rb_snaps():
    intelligence = build_nfl_game_intelligence(flagship_snapshot())
    split = next(s for s in intelligence["story_signals"] if s["type"] == "BACKFIELD_SPLIT")
    assert split["players"][0]["snap_share"] == 0.52
    assert split["players"][1]["snap_share"] == 0.48


def test_non_flagship_skips_deep_nfl_enrichment():
    data = flagship_snapshot()
    data["editorial"]["tier"] = "newspaper"
    assert build_nfl_game_intelligence(data) is None
```

- [ ] **Step 2: Verify RED**

Expected: module/function does not exist.

- [ ] **Step 3: Implement minimal enrichment**

Join Sleeper players to nflverse stats by GSIS ID and snap counts by normalized player/team name when no stable PFR crosswalk is already present in the snapshot. Derive carries, targets, receptions, team opportunity shares, red-zone/inside-10/inside-5 touches, quarter usage, and team offensive touchdowns from play-by-play. Emit conservative `BACKFIELD_SPLIT`, `LATE_SURGE`, `HIGH_VALUE_TOUCH_SHIFT`, `MISSED_WINDFALL`, `VOLUME_WITHOUT_RESULTS`, `EFFICIENCY_SPIKE`, and `COMEBACK_ENGINE` candidates only when source evidence is sufficient.

- [ ] **Step 4: Verify GREEN**

Run enrichment tests plus metrics tests.

- [ ] **Step 5: Commit**

Commit message: `feat: add Ironbound NFL game intelligence`

---

### Task 4: Render commissioner-review sections

**Files:**
- Modify: `editorial_desk/render.py`
- Modify: `tests/test_metrics.py`

**Interfaces:**
- Consumes `weekly_features` and `nfl_game_intelligence` from dossier JSON.
- Produces human-readable Markdown sections `Weekly Magazine Features` and flagship-only `Ironbound NFL Game Intelligence`.

- [ ] **Step 1: Write failing rendering assertions**

Assert the Markdown contains divisional nominee/gold-foil labels, rookie STARTED/BENCH/TAXI status, free-agent feature, top-position scorers, and flagship story-signal headings.

- [ ] **Step 2: Verify RED**

Expected: headings absent.

- [ ] **Step 3: Implement minimal rendering**

Add compact evidence-first tables/bullets. Do not write magazine prose or generate images.

- [ ] **Step 4: Verify GREEN**

Run render/metrics tests.

- [ ] **Step 5: Commit**

Commit message: `feat: render weekly feature and game intelligence review`

---

### Task 5: Verification and Tuesday-run readiness

**Files:**
- Modify only if verification exposes a defect.

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest -q`
Expected: all tests pass.

- [ ] **Step 2: Validate example configuration**

Run: `cp config/leagues.example.json config/leagues.json && python -m editorial_desk validate-config --config config/leagues.json`
Expected: configuration valid.

- [ ] **Step 3: Run a manual Week 1 collection in GitHub Actions**

Use the existing `workflow_dispatch` collection path on the feature branch if available; otherwise verify with unit/integration tests and leave the live collection for the user's existing Tuesday workflow after merge.

- [ ] **Step 4: Inspect the generated flagship dossier**

Confirm the Ironbound/Unbound dossier exposes the new weekly features and NFL intelligence while newspaper-tier dossiers omit the deep enrichment.

- [ ] **Step 5: Final commit/review**

Confirm the branch contains no temporary test workflow or debugging artifact before merge.
