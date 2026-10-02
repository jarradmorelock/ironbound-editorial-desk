# Publication-Complete Packet and Offline Builder Design

**Date:** 2026-10-02  
**Project:** Ironbound Editorial Desk  
**Status:** Design for review  
**Primary acceptance fixture:** `ironbound weekly 2026.04 week 03.pptx`

## 1. Purpose

The Editorial Desk must produce a research package that is complete enough for a disconnected local manuscript builder to write every non-personal factual section of a publication without performing additional research.

The target workflow is:

1. Editorial Desk collects, reconciles, calculates, and validates all factual evidence.
2. Editorial Desk emits a **Publication-Complete Packet**.
3. A local editorial model uses only that packet, or deterministic derivatives of it, to plan and draft the issue.
4. The commissioner edits and approves the manuscript and adds the intentionally personal **From the Ironbound Desk** column.
5. A local PowerPoint publisher uses only the approved manuscript, approved page plan, publication template, and packaged assets to build an editable slide deck.
6. The commissioner performs final image/design polish and exports the publication.

After the Publication-Complete Packet is emitted, neither the manuscript builder nor the slide builder may call Sleeper, nflverse, Chronicle, GitHub, web search, a screenshot, a prior issue, or another research source.

## 2. Acceptance criterion

A packet is publication-complete only when:

> A disconnected manuscript builder can produce every non-personal factual page of the issue without additional retrieval, research, calculation, screenshots, or human-supplied facts.

The finished Week 3 Ironbound magazine is the first gold-standard acceptance case. The pipeline is not considered flagship-ready until its research output can support the factual contents of that issue without the supplemental lookups that were required during manual production.

The personal `FROM_THE_IRONBOUND_DESK` page is intentionally excluded from this criterion. The publisher must reserve and render that page when approved user copy is supplied, but no automated system should invent its content.

## 3. Problem statement

The current pipeline already collects substantial useful evidence, but the boundary between "research" and "writing" is incomplete.

Examples exposed by the Week 3 production process include:

- historical Sleeper matchup and player-score data existed in the snapshot but was not always consumed by cumulative boards;
- complete trade terms and draft-pick provenance required direct transaction review after the packet was produced;
- retained historical projections had to be re-queried to verify projection-based honors;
- division and cross-division season summaries required a separate historical calculation;
- roster-health copy required later supplemental evidence;
- some downstream code preferred prior dossier or Chronicle history even when authoritative Sleeper history was already present;
- missing projections for fringe players could incorrectly disable whole award families;
- source notes sometimes depended on screenshots or manual reconciliation rather than one canonical evidence object.

The solution is not to give the local writer more tools. The solution is to finish the newsroom work upstream.

## 4. Design principles

### 4.1 Research ends at the packet boundary

Anything that can change a factual claim belongs upstream of the Publication-Complete Packet.

The local writer may:

- select story emphasis;
- choose among verified candidates;
- write headlines, decks, body copy, captions, and callouts;
- explain verified evidence;
- recommend cover or feature treatment;
- recommend one rotating award from the qualified candidate set, subject to commissioner selection.

The local writer may not:

- fetch new facts;
- calculate season totals;
- reconstruct standings or records;
- decode raw Sleeper transactions;
- recalculate rankings;
- infer missing health or news facts;
- replace an unavailable fact with an assumed one;
- create award eligibility.

### 4.2 One canonical factual answer

Downstream departments should not independently decide whether to trust Sleeper, Chronicle, prior dossiers, or a current snapshot.

A normalization/reconciliation layer must produce one canonical factual object with provenance.

### 4.3 Raw evidence remains available, but writers consume normalized answers

The existing snapshot, dossier, Story Desk, ranking handoff, Chronicle, beat ledger, and nflverse data remain useful research artifacts.

The Publication-Complete Packet is a derived publication contract. It should retain evidence references and compact supporting evidence, not duplicate every raw record.

### 4.4 No page-count lock

The packet must not encode a permanent 22-, 24-, 25-, or 26-page magazine requirement.

The issue plan supplies a page/module plan. The normal flagship structure may evolve or expand. Research completeness is defined by required departments and selected story assignments, not by a fixed number of pages.

### 4.5 Ranking outputs remain authoritative

The Ironbound Power Rankings system remains the authority for:

- official Power Rank;
- prior rank and movement;
- Power Board components supplied by that system;
- playoff forecasts;
- division forecasts when supplied;
- remaining schedule strength;
- weekly matchup forecasts;
- supplied ranking/playoff graphics.

Editorial Desk may normalize and package those values but must not recompute them.

## 5. Architecture

The pipeline becomes:

```text
existing collectors
    |
    +-- Sleeper
    +-- nflverse
    +-- Chronicle
    +-- beat/news ledger
    +-- Power Rankings handoff
    +-- optional verified enrichments
    |
    v
raw/enriched research artifacts
    |
    v
Canonical Evidence Resolver
    |
    v
Department Research Builders
    |
    v
Publication-Complete Packet
    |
    +--> Readiness Validator
    |
    +--> compact editorial_brief.json
             |
             v
        local Issue Editor
             |
             v
         issue_plan.json
             |
             v
      section assignments
             |
             v
       manuscript_draft.json
             |
        human edit/approve
             |
     + From the Ironbound Desk
             |
             v
      manuscript_approved.json
             |
             v
      procedural PPTX publisher
```

The Publication-Complete Packet is the factual source of truth for all builder stages.

## 6. New component: Canonical Evidence Resolver

The resolver receives research from existing sources and emits normalized evidence records.

A canonical record contains:

```json
{
  "evidence_id": "player-week:2026:3:12345",
  "fact_type": "PLAYER_FANTASY_WEEK",
  "league_key": "ironbound_sixteen",
  "season": "2026",
  "week": 3,
  "entities": {
    "player_id": "12345",
    "roster_id": 7
  },
  "value": {
    "points": 22.5,
    "started": true
  },
  "authority": "sleeper_matchups",
  "provenance": "source_exact",
  "observed_at": "...",
  "source_refs": ["..."],
  "status": "VERIFIED"
}
```

### 6.1 Conflict policy

The resolver must never silently pick between contradictory authoritative values.

If two sources disagree materially:

- preserve both source refs;
- mark the canonical fact `MANUAL_VERIFY`;
- identify the conflicting values;
- block any required department that depends on the unresolved fact.

### 6.2 Source preference examples

These are factual authority rules, not fallback permission to invent data.

**League matchup result / submitted lineup / fantasy player score**
1. Sleeper historical matchup endpoint for the exact league/week.
2. Matching Chronicle finalized event.
3. Prior finalized Editorial Desk artifact.
4. Conflict -> `MANUAL_VERIFY`.

**League transaction**
1. Sleeper transaction endpoint for the relevant transaction leg/week.
2. Chronicle normalized transaction history.
3. Normalize players, FAAB, roster movement, and draft-pick provenance into one transaction object.

**Historical projection**
1. Sleeper retained same-season/week projection resource.
2. Apply the league's scoring settings deterministically.
3. Preserve source season/week and retrieval provenance.

**Power ranking / playoff / schedule-strength values**
1. Current authoritative Ironbound Power Rankings handoff only.
2. Do not recalculate in Editorial Desk.

**NFL stat line / usage**
1. Existing nflverse sources and deterministic scoring/usage transforms.
2. If required player mapping fails, mark that row unavailable rather than substituting fantasy points as NFL statistics.

**Health**
1. Latest verified health/injury source available at the configured issue cutoff.
2. Preserve observed time and source status.
3. A packet is not required to contain information that did not yet exist at the cutoff; it is required to contain the latest verified information available at that cutoff.

## 7. New artifact: publication_complete_packet.json

The packet is a publication-facing factual contract.

Top-level shape:

```text
publication_complete_packet
├── schema_version
├── contract_version
├── publication
├── issue_identity
├── information_cutoff
├── source_manifest
├── readiness
├── evidence_index
├── game_dossiers
├── feature_evidence
├── usage_desk
├── roster_health
├── transaction_desk
├── manager_honors
├── player_honors
├── rookie_watch
├── division_report
├── power_board
├── playoff_forecast
├── power_rankings
├── week_ahead
├── sources_and_model_notes
└── publication_assets
```

The packet may reference evidence IDs in `evidence_index` rather than repeat the same evidence in every department.

## 8. Department contracts

### 8.1 Game dossiers

Each completed league matchup must provide:

- matchup ID;
- teams and roster IDs;
- final score and margin;
- winner/loser;
- submitted starters and bench;
- player fantasy points;
- retained same-week player projections where available;
- actual NFL stat lines for editorially relevant starters;
- usage context;
- timing/late-game context when available;
- verified division status;
- entering records;
- entering Power Rank;
- relevant accepted beat/news context;
- relevant transaction/health context;
- evidence IDs.

Flagship validation requires all eight completed matchups.

### 8.2 Feature evidence

Feature candidates are evidence bundles, not prose.

A candidate may be a matchup, transaction-driven story, health-driven story, standings/division story, or another deterministic Story Desk candidate.

Each candidate contains:

- candidate ID;
- candidate type;
- involved teams/players;
- verified facts;
- related game IDs;
- related transaction IDs;
- relevant health/news events;
- ranking/forecast context;
- historical context;
- cautions;
- evidence IDs.

The Issue Editor may select "none" when no candidate warrants feature treatment.

### 8.3 Usage Desk

Must contain writer-ready, normalized rows for meaningful workload signals, including when available:

- carries;
- targets;
- receptions;
- snap share;
- carry share;
- target share;
- red-zone opportunities;
- inside-10 and inside-5 opportunities;
- backfield split context;
- meaningful week-over-week workload changes;
- source status.

The writer should not calculate shares from raw rows.

### 8.4 Roster Health

For every materially relevant rostered player, provide:

- Sleeper designation;
- roster placement, including IR/reserve;
- injury/body part when available;
- practice participation/status when available;
- relevant accepted news events;
- observed time;
- source status;
- fantasy team;
- evidence IDs.

The packet uses an explicit `information_cutoff`. If formal Wednesday/Thursday practice data does not yet exist, the latest verified status at cutoff is sufficient. A later scheduled research refresh may produce a newer publication-complete packet, but a builder must never supplement an already-issued packet itself.

### 8.5 Transaction Desk

Each normalized completed transaction in the reporting window must include:

- transaction ID;
- transaction type;
- completion time;
- all participating rosters/teams;
- every player added/dropped;
- every draft pick transferred;
- original pick owner when determinable;
- FAAB amount when applicable;
- transaction week/leg;
- immediate post-transaction starting status;
- reviewed-week fantasy result for acquired players when applicable;
- longer historical relationship needed by awards such as Cut by Your Own Blade;
- evidence IDs.

A writer should never need to inspect the Sleeper transaction payload directly.

### 8.6 Manager Honors

The packet must contain:

- Manager of the Week and supporting facts;
- Most Efficient Manager;
- High Score;
- Low Score;
- Bad Beat;
- Escape Artist;
- season efficiency board;
- season scoring board;
- all qualified rotating-award candidates;
- manual-review rotating candidates;
- per-award audit;
- commissioner-selection-required flag.

Projection-based awards use retained same-week Sleeper projections and candidate-specific eligibility. A missing projection for an unrelated fringe player must not disable an otherwise evaluable award.

### 8.7 Player Honors

Must contain:

- Overall Player of the Week;
- distinct QB/RB/WR/TE weekly winners;
- Benchwarmer;
- Free Agent of the Week when supported;
- actual NFL stat lines;
- fantasy points;
- fantasy team;
- season-to-date player totals by position;
- ranking/ordering already calculated.

Weekly and season boards are deterministic research outputs, not writer calculations.

### 8.8 Rookie Watch

Must contain:

- weekly Top 5 rookies;
- fantasy team;
- started/bench/taxi status;
- actual NFL stat line;
- fantasy points;
- fantasy rookie-draft pick and provenance;
- Rookie of the Week / breakout candidate;
- Top Rookie Starter;
- Rookie Disappointment candidates with supporting evidence;
- season-to-date rookie position leaders.

Editorial selection may remain for contextual awards such as Rookie Disappointment, but the candidate evidence must already be present.

### 8.9 Division Report

Must contain deterministic season-through-week values:

- division membership;
- each team's overall record;
- each team's divisional/internal record;
- cross-division record;
- division pooled internal record;
- division cross-division record;
- cumulative points;
- team-game count;
- division scoring average;
- division forecast when supplied;
- remaining schedule strength;
- evidence IDs.

No division summary may depend on the writer manually querying Weeks 1-N.

### 8.10 Power Board, Playoff Forecast, and Power Rankings

Package the authoritative ranking handoff and supplied assets unchanged.

The packet provides writer-ready rows and the immutable supplied image assets.

### 8.11 Week Ahead

Must contain all upcoming league matchups plus:

- teams;
- projected-optimal legal line;
- projected total;
- model source;
- current health caveats available at cutoff;
- relevant schedule-strength/division implications;
- evidence IDs.

The writer does not construct projected lineups.

### 8.12 Sources and Model Notes

Generated from the source manifest and evidence actually used.

Must distinguish:

- measured league/NFL facts;
- model estimates;
- supplied ranking assets;
- time-sensitive health information;
- experimental optional enrichments.

## 9. Source manifest

The packet must expose source health explicitly.

Example:

```json
{
  "sleeper": {
    "matchups": {"status": "READY", "weeks": [1, 2, 3]},
    "transactions": {"status": "READY", "weeks": [1, 2, 3]},
    "projections": {"status": "READY", "season": "2026", "week": 3}
  },
  "nflverse": {
    "player_stats": {"status": "READY"},
    "snap_counts": {"status": "READY"},
    "play_by_play": {"status": "READY"}
  },
  "rankings": {"status": "READY", "authority": "Ironbound_power_ranks"},
  "beat_news": {"status": "PARTIAL", "coverage_start": "..."},
  "health": {"status": "READY", "observed_at": "..."}
}
```

An optional or experimental source may be unavailable without blocking publication unless a selected department explicitly depends on it.

## 10. Publication readiness

`readiness` becomes the hard gate for local builders.

Example:

```json
{
  "publication_ready": false,
  "status": "BLOCKED",
  "blocking_gaps": [
    {
      "section": "transaction_desk",
      "code": "UNRESOLVED_PICK_PROVENANCE",
      "detail": "Transaction ... contains a draft pick whose original owner is unresolved."
    }
  ],
  "warnings": [],
  "optional_gaps": []
}
```

### 10.1 Blocking flagship requirements

At minimum, flagship publication requires:

- eight completed matchup dossiers;
- verified submitted lineups and final team/player scoring;
- exact historical weeks needed for entering records and cumulative calculations;
- complete normalized reporting-window transactions;
- required projection evidence for any projection-based claim or award candidate;
- current health snapshot as of the issue cutoff;
- complete static honors;
- deterministic season player and team boards;
- rookie draft/season context required by Rookie Watch;
- division calculations;
- current ranking/playoff/schedule-strength handoff;
- all upcoming matchup forecast rows required by the issue;
- required supplied ranking assets.

### 10.2 Warnings versus blockers

A warning does not prevent writing if the publication can state the limitation honestly.

Examples:

- beat-news ledger coverage began after the start of the reporting week;
- optional Sleeper-wide market percentage enrichment unavailable;
- a non-feature player's nflverse usage row failed to map.

A blocker means a required recurring department cannot be factually produced from the packet.

## 11. Health and time-sensitive refresh policy

Publication completeness is relative to an explicit information cutoff.

The production workflow may run more than once:

- Tuesday research run after results/rankings are available;
- optional later scheduled refresh to capture newer health/news information;
- the final packet used for manuscript generation is immutable.

The local builder never performs the refresh.

If the commissioner wants newer information after a manuscript has been generated, the correct process is:

1. rerun Editorial Desk;
2. issue a new packet with a new `brief_id` / packet ID;
3. regenerate or selectively refresh the affected manuscript sections.

This preserves provenance.

## 12. Relationship to editorial_brief.json

The Publication-Complete Packet is the verified factual superset.

A deterministic compiler creates a smaller `editorial_brief.json` for the local Issue Editor. The brief should normally target roughly 8k-12k tokens and contain:

- issue identity/readiness;
- page framework;
- style guidance;
- condensed story candidates;
- all eight matchup summaries;
- noteworthy usage/health/market signals;
- honors and rotating-award candidates;
- rankings/playoff context;
- upcoming slate;
- evidence IDs.

The brief may omit low-priority raw details because section assignments can retrieve those details deterministically from the Publication-Complete Packet.

No local model is allowed to fetch missing details externally.

## 13. Issue plan and human checkpoint

The local Issue Editor returns `issue_plan.json`, containing editorial choices only:

- lead feature candidate;
- secondary feature candidate;
- feature matchup allocation;
- cover subject/direction;
- section emphasis;
- rotating award recommendation;
- expansion recommendation.

It references packet/brief IDs and does not duplicate or change facts.

The commissioner may override feature selections and chooses one or no rotating award.

## 14. Section assignments and manuscript

After issue-plan approval, a deterministic assignment compiler emits small job-specific JSON files.

Each assignment contains:

- issue/packet ID;
- page/module role;
- selected angle;
- word/character budget;
- only relevant verified evidence;
- allowed evidence IDs;
- warnings/cautions.

Each writer returns structured manuscript JSON with:

- headline;
- deck;
- body blocks;
- callouts;
- table/card copy;
- art direction;
- evidence IDs;
- warnings.

Validators reject:

- unknown evidence IDs;
- unsupported numeric claims;
- wrong teams/players;
- length violations severe enough to break layout;
- missing required fields.

## 15. Continuity pass

A final local continuity pass may inspect:

- approved issue plan;
- condensed completed section manuscripts.

It may propose prose-level edits for:

- repeated phrases;
- duplicated framing;
- headline collisions;
- missing transitions;
- contradictory editorial emphasis.

It may not introduce new factual claims or evidence.

Any accepted replacement must retain the original evidence IDs.

## 16. Approved manuscript contract

The human-approved artifact becomes `manuscript_approved.json`.

It contains:

- the approved issue/page plan;
- all approved section copy;
- commissioner-selected rotating award;
- approved captions/callouts/tables;
- art directions;
- publication asset references;
- manual `from_the_ironbound_desk` copy when supplied.

The approved manuscript is the only prose source for the PowerPoint publisher.

## 17. PowerPoint publisher boundary

The PPTX publisher receives only:

- `manuscript_approved.json`;
- static publication template/layout definitions;
- packaged publication assets;
- approved/user-supplied art and photos.

It may:

- create native editable text boxes;
- create native shapes, rules, cards, badges, tables, and decorative objects;
- place approved raster art/photos;
- place authoritative ranking/playoff graphics unchanged;
- enforce typography/spacing templates;
- flag overflow.

It may not:

- rewrite copy;
- research facts;
- change numbers;
- calculate rankings;
- choose awards;
- silently shrink unreadable text to make overflow disappear.

Each slide remains a portrait 8.5x11 magazine page unless the publication template itself changes.

## 18. Offline acceptance testing

The key regression test is an offline reproduction test.

### 18.1 Week 3 flagship fixture

Create a compact checked-in acceptance manifest derived from the finished Week 3 Ironbound issue.

The test does not need to store the entire user magazine in the repository. It records the factual capabilities the packet must support, such as:

- all eight results and feature evidence;
- complete normalized Buckaneers trade terms and other major trades;
- Week 3 retained projections used by No Fear;
- cumulative manager/team boards;
- cumulative player positional boards;
- rookie weekly and season boards;
- true division/cross-division records and scoring;
- full Week 4 slate/model rows;
- health/news fields required by the health page;
- source/model notes.

### 18.2 Network prohibition

The manuscript-generation integration test runs with network access disabled or with all research clients replaced by fail-fast stubs.

If manuscript generation attempts to call Sleeper, nflverse, Chronicle, web search, GitHub, or another external source, the test fails.

### 18.3 Deterministic packet tests

Tests must cover:

- source conflict handling;
- historical Sleeper fallback/authority;
- transaction normalization and pick provenance;
- candidate-specific projection readiness;
- entering-record calculation;
- player season totals;
- rookie season totals;
- division calculations;
- readiness blockers;
- optional-source warnings;
- packet/brief evidence-ID integrity.

## 19. Newspapers

The same boundary applies to newspapers:

> publication packet -> offline manuscript -> human approval -> PPTX.

Newspapers may use a smaller department set and lighter enrichment than the two flagship magazines, but their manuscript builders receive publication-complete factual packets too.

Implementation should first prove the contract with Ironbound Week 3, then apply the generic envelope/readiness machinery to Unbound and the newspaper profiles.

This avoids weakening the flagship acceptance case while keeping one common publishing architecture.

## 20. Migration strategy

### Phase 1: Canonical historical league facts

Implement canonical objects for:

- historical matchups;
- submitted starters;
- player fantasy scores;
- entering records;
- cumulative team scoring;
- cumulative player scoring;
- division records/scoring.

Use Sleeper history already captured in the flagship snapshot before adding redundant new collection.

### Phase 2: Transactions and projection-dependent honors

Normalize:

- complete transactions;
- pick provenance;
- recent acquisition impact;
- retained same-week projections;
- candidate-specific award qualification.

### Phase 3: Health/news and source manifest

Unify:

- current roster health;
- injury/practice observations;
- accepted beat/news context;
- source freshness/status;
- explicit information cutoff.

### Phase 4: Publication-Complete Packet and hard validator

Build the new artifact from the normalized research.

Do not declare `publication_ready=true` until all required flagship departments pass.

### Phase 5: Week 3 offline acceptance case

Recreate the required factual capability of the finished Week 3 issue using only the packet.

Close any remaining research gaps upstream.

### Phase 6: Local editorial contracts

Implement:

- editorial brief;
- issue plan;
- assignment compiler;
- structured manuscript;
- continuity validator.

### Phase 7: PPTX publisher

Only after the offline manuscript path is proven, connect the approved manuscript to the editable PowerPoint production templates.

## 21. Non-goals for this implementation cycle

This design does not require:

- choosing the final local LLM;
- tuning llama.cpp;
- creating cover art;
- redesigning the magazine;
- locking the page count;
- replacing the Power Rankings engine;
- moving Chronicle responsibilities into Editorial Desk;
- adding Manager of the Year;
- automating the personal From the Ironbound Desk column.

## 22. Definition of done

The flagship research architecture is ready for local publishing when all of the following are true:

1. Week 3 Ironbound can generate a Publication-Complete Packet with no unresolved required research gaps except limitations that genuinely did not exist by the configured cutoff.
2. Every factual element needed for the non-personal Week 3 magazine departments is present or deterministically derivable inside that packet.
3. The local manuscript builder can run with research/network clients disabled.
4. The manuscript builder performs no factual calculations beyond formatting already-normalized values.
5. The commissioner can edit/approve the manuscript and insert From the Ironbound Desk.
6. The PowerPoint publisher can build the issue from the approved manuscript and packaged assets without research access.
7. The same contract can be applied to Unbound, then to newspaper profiles with smaller required-department sets.

That is the boundary the project should optimize for going forward.
