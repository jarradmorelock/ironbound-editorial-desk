# Editorial Chronicle, Event Ledger, and Publication Architecture

Date: 2026-09-16
Status: Approved design checkpoint
Repository: `jarradmorelock/ironbound-editorial-desk`

## Purpose

The Editorial Desk is evolving from a weekly fantasy-football data collector into a durable newsroom system. The code should remember facts, preserve history, detect meaningful changes, and prepare publication-specific evidence. Human editors retain control over interpretation, causation, story selection, prose, graphics, and final magazine layout.

This checkpoint records the design decisions approved before implementation. It intentionally does not yet define the final historical backfill procedure, failure-recovery policy, or complete test plan. Those are the next design section and must be approved before implementation begins.

## Core editorial principle

The software remembers facts and connects potentially related facts. The editors decide what those facts mean and how the story should be told.

The system must not infer motive merely from timing. It may report that an injury status changed before a trade or waiver move and that the events were close in time. Strong causal language requires independent evidence or explicit commissioner/editorial knowledge.

## Architecture overview

The system will have five conceptual layers:

1. Universal data spine
2. Chronicle
3. Event Ledger
4. Publication Feature Contracts
5. Magazine Story Desk for Ironbound Weekly and Unbound Weekly only

The existing weekly collector, publication mappings, review rendering, health reporting, and Tuesday/Wednesday delivery remain useful foundations. The new architecture should extend them rather than replace them wholesale.

## Permanent storage

Permanent generated history will live on a dedicated branch in the existing repository, named `chronicle-data`.

The normal code branch remains `main`. Scheduled jobs run code from `main` and read/write the data branch separately.

Reasons for this choice:

- generated history does not clutter the development branch
- the archive survives GitHub Actions cache and artifact expiration
- no new hosted database or paid service is required
- every committed history change has an audit trail
- historical state can be recovered or rebuilt from repository history

The system should commit to `chronicle-data` only when meaningful stored data changes.

## Storage model

The permanent archive uses append-only JSONL event files plus rebuildable JSON history indexes.

Illustrative structure:

```text
chronicle-data/
  registry/
    franchises.json
    managers.json

  leagues/
    ironbound_sixteen/
      events/
        2026.jsonl
        2027.jsonl
      history/
        franchises.json
        matchups.json
        records.json
        seasons.json
        transactions.json

    rocky_top_rumble/
      events/
        2026.jsonl
      history/
        managers.json
        matchups.json
        records.json
        seasons.json

  cross_league/
    nfl_player_events/
      2026.jsonl
```

The JSONL ledger is the factual audit trail. Derived JSON history files are query-oriented indexes and may be rebuilt from the ledger and registry.

If a franchise mapping error is discovered later, the registry should be corrected and derived history rebuilt rather than manually rewriting many historical totals.

Every stored event must have a deterministic identity so repeated collection is idempotent and cannot create duplicate trades, matchup finals, or status-change events.

## Raw snapshot retention

Large raw snapshots are not permanent history by default.

The system should retain recent raw snapshots long enough for debugging and short-term reconstruction, while compact normalized events and finalized historical facts remain permanent.

This prevents the repository from accumulating large redundant daily snapshots across many seasons.

## League and franchise identity

History is universal across all tracked leagues, including redraft leagues.

### Dynasty leagues

Dynasty history follows the franchise slot, not the current manager name or current team name.

Each dynasty franchise receives a stable internal `franchise_key` that survives:

- team-name changes
- manager-display-name changes
- annual Sleeper league renewals
- ordinary ownership changes unless the commissioner explicitly declares a new franchise

Manager tenure is preserved as a separate historical layer so the system can distinguish franchise history from a particular manager era.

### Redraft leagues

Redraft history follows stable manager identity within that league because the roster itself is recreated each year and team names can change frequently.

The archive should support statements such as an all-time manager-vs-manager record across multiple team names.

### Registry mapping

Each season maps Sleeper roster IDs and owner IDs to stable internal franchise or manager keys. Ambiguous ownership changes, co-managers, orphaned teams, and other edge cases must be manually correctable in a small registry without rewriting underlying matchup evidence.

## Cross-season continuity

Sleeper renewal chains and historical weekly matchups should be used to connect seasons where available.

The Chronicle should retain, when recoverable:

- matchup results
- all-time head-to-head records
- playoff meetings
- winning and losing streaks
- scoring records
- season finishes
- championships
- division membership
- draft history
- trade history
- future-pick history
- manager tenure

Historical uncertainty must remain explicit. The system must not invent missing seasons, missing events, or missing ownership mappings.

## Chronicle editorial policy

All tracked leagues receive historical memory.

Ironbound Weekly and Unbound Weekly may use history as a primary feature-story trigger. A matchup record, rivalry, long-running trade consequence, franchise era, or old playoff result may itself justify a major feature.

The newspaper publications also receive historical facts, but history alone normally appears as supporting color inside Record Watch, a matchup capsule, a themed department, or another established section unless current events make the history independently significant.

## Event Ledger

The Event Ledger records meaningful changes instead of preserving only weekly end states.

Event families include, at minimum:

- `MATCHUP_FINAL`
- `TRADE`
- `WAIVER_ADD`
- `FREE_AGENT_ADD`
- `DROP`
- `PLAYER_STATUS_CHANGE`
- `IR_RESERVE_CHANGE`
- `PRACTICE_STATUS_CHANGE` when collected for flagship leagues
- `LINEUP_CHANGE`
- `PROJECTION_CHANGE` when the change is materially large enough to preserve
- `RECORD_SET`
- draft and future-pick events where relevant

League events and NFL/player events are separate streams.

For example, Brock Bowers changing health status is an NFL/player event. A Buckaneers trade for Hunter Henry is an Ironbound league event. The Story Desk may correlate them without storing duplicate copies of the same NFL event in every league.

## Time semantics

Transaction timestamps supplied by Sleeper can be stored as source event times.

Health/status changes discovered by periodic polling must preserve observation uncertainty. The system should store the previous observation time and the first new observation time rather than fabricate an exact moment of change when the upstream source does not provide one.

Example:

```text
PLAYER_STATUS_CHANGE
player: Brock Bowers
from: Questionable
to: Out
observed_before: 2026-09-16T13:05:00-04:00
observed_after: 2026-09-16T17:04:00-04:00
```

A trade may have an exact timestamp:

```text
TRADE
occurred_at: 2026-09-16T17:08:23-04:00
franchise: buckaneers
acquired: Hunter Henry
```

The editorial system may safely describe event order supported by these timestamps, but it must preserve the difference between exact source timestamps and observed intervals.

## Collection cadence

The data desk runs more frequently than the full editorial compiler.

### Daily baseline

Run one lightweight collection every morning during the season.

### Active-week pulse

Run three lightweight passes per day from Wednesday through Sunday.

These passes prioritize Sleeper and current health/status inputs. They do not rerun every expensive or deep enrichment source.

### Tuesday compilation

Tuesday remains the full editorial build. It reads the Chronicle and the current week's Event Ledger, gathers the normal weekly facts, applies publication contracts, and for Ironbound/Unbound builds the Magazine Story Desk.

### Wednesday supplement

The Wednesday supplement remains, but it can now read the Event Ledger as well as compare current state with Tuesday's packet. It should surface genuinely new information without sending a duplicate full dossier.

## Universal data spine

All publication tiers share a normalized factual layer. It should expose reusable facts rather than paper-specific department names.

The factual spine should include, as applicable:

```text
weekly_results
league_median
standings
ranking_inputs
ranking_movement
lineup_efficiency
lineup_flip_candidates
manager_decision_evidence
player_position_leaders
bench_leaders
rookie_of_week
free_agent_of_week
waiver_impact
transactions
health_status
division_metrics
record_watch
historical_matchups
next_matchups

draft_results
draft_adp_value
keeper_costs
roster_age
positional_strength

future_picks
rookie_draft
dynasty_market_values
idp_position_metrics
offense_defense_splits

nfl_game_timeline_context
player_stat_lines
```

The collector should know factual concepts such as `lineup_flip_candidates` or `waiver_impact`, not themed labels such as "Cutting Room Floor" or "Ward Report."

## Publication Feature Contracts

The newspaper publications are contract-driven.

Each publication profile should declare which factual outputs its recurring sections require. The contract is derived from the actual preseason and Week 1 papers, not only from historical configuration labels.

Contracts should be issue-phase aware so preseason/draft features are not treated as mandatory every regular-season week.

Supported phases should include, as appropriate:

- weekly
- preseason/draft
- offseason

A publication readiness check should verify that required weekly facts are present. If a required upstream source genuinely fails, the packet should explicitly report the missing dependency instead of silently omitting a department.

### The Ballad Crier

Weekly contract should support:

- scores and median line
- standings
- forward-looking Rankings Wire
- lineup efficiency
- result-flipping start/sit analysis / weekly lineup autopsy
- Manager of the Week
- Bad Beat
- Escape Artist
- Benchwarmer
- Rookie of the Week
- Free Agent of the Week
- position leaders
- Waiver Star with cost and result relevance
- health/IR Ward Report
- Record Watch
- next matchup card

Preseason/draft support should include:

- keeper value
- draft reach/value
- draft board context
- Streamers' Pact / rostered-defense state where relevant

### The Stampede

Weekly contract should support:

- scores and league median where applicable
- standings movement
- lineup efficiency
- Manager of the Week
- Bad Beat
- Escape Artist
- Bench MVP / result-flipping decision
- waiver and transaction context
- health board
- Record Watch
- next matchup preview
- The Week's Heavy Lifting using real player-stat categories for standout rushing and passing/receiving performances

Preseason/draft support should include:

- consensus/power inputs
- roster age/depth
- positional strength
- keeper value
- draft reach and bargains
- season simulation

### The Volunteer Voice

Weekly contract should support:

- scores and league median
- official standings/table
- Record Watch
- Decision Desk / Call That Won the Week
- rankings movement
- Manager of the Week
- divisional MVPs including gold-foil designation
- lineup efficiency
- division pulse
- Bad Beat
- Escape Artist
- Waiver Star
- Bench Blast
- Rookie of the Week
- Free Agent of the Week
- next-week scouting context

The decision-swing calculation must remain separate from generic lineup efficiency.

### The Saturday Standard

Weekly and dynasty contract should support:

- offense and IDP analysis as first-class data
- East/West polls and movement
- division averages and records
- lineup efficiency
- Portal Film Room result-flipping decisions
- waiver and FAAB commitments
- divisional MVPs
- full position board including IDP positions
- Dynasty Market Board
- rookie/recruiting draft
- recruiting class strength
- traded picks and future-pick ledger
- transfer/trade activity
- next-week slate

### The Hollywood Beat

The earlier configuration placeholder that its weekly publication standard was pending is obsolete. The preseason and Week 1 issues establish a real recurring contract.

Weekly contract should support:

- Box Office scores and league median
- Marquee standings
- Hollywood Board factual inputs
- Monday-night and other NFL game-timeline context
- weekly awards
- Cutting Room Floor lineup-flip analysis
- Studio Efficiency
- Casting Call waiver additions and FAAB
- health/reserve Production Delays
- next week's bill

Dynasty/preseason support should include:

- rookie draft
- future rights / future picks
- major trades
- roster timeline context
- dynasty market context

Hollywood Beat does not receive the Magazine Story Desk.

## Shared calculation, distinct presentation

The same normalized calculation may feed different themed departments.

Examples:

- `lineup_flip_candidates` -> Ballad Crier "Weekly Rounds" / Saturday Standard "Portal Film Room" / Hollywood Beat "Cutting Room Floor"
- `waiver_impact` -> Ballad "Waiver Star" / Saturday "Portal Commitments" / Hollywood "Casting Call"
- health facts -> Ballad "Ward Report" / Stampede "Health Board" / Hollywood "Production Delays"

This keeps calculations coherent and comparable while allowing each publication to maintain its own voice and visual identity.

## Publication-ready feature packets

The Tuesday output for newspaper publications should be a structured feature packet, not merely a research dump.

The packet should organize already-calculated facts into the publication's recurring departments, with clear availability/readiness status.

A readiness block may report, for example:

```text
PUBLICATION READINESS
✓ scoreboard
✓ standings
✓ rankings movement
✓ lineup efficiency
✓ flip decisions
✓ weekly honors
✓ waiver impact
✓ health
✓ record watch
✓ next matchups
```

If health data genuinely fails upstream, the contract should show that the health department is incomplete rather than silently dropping it.

## Game-timeline context

Game timing is universal factual material, not exclusive to the flagship Story Desk.

The collector should preserve enough NFL game/timing context to support deterministic descriptions such as:

- entered Monday down by X
- Player Y scored Z on Monday
- the matchup flipped during the final game window
- the final margin became N

This is required because Ballad Crier, Hollywood Beat, and Saturday Standard already use Monday-night swings as important weekly material.

## Ironbound Weekly and Unbound Weekly editorial model

Ironbound Weekly and Unbound Weekly are newsroom-driven rather than rigidly department-driven.

They still receive a small mandatory factual backbone so core league information is never lost, including current results/standings, major movement, significant transactions, health, Record Watch, divisional state, MVP/award candidates, and next matchups.

However, the system must not encode a fixed 20-30 page table of contents for every issue.

The final magazines are expected to be approximately 20-30 pages and are assembled editorially from story packages, supporting analysis, graphics, and recurring factual material.

## Magazine Story Desk scope

The Story Candidate Engine exists only for:

- `ironbound_weekly`
- `unbound_weekly`

It does not run for the other newspaper publications, even when those leagues are dynasty leagues.

The Story Desk should be generous. A normal Tuesday output should aim to surface approximately 12-20 viable ideas rather than prematurely deciding that only a handful of developments matter.

The editors choose which ideas become articles, sidebars, graphics, or nothing at all.

## Story candidate families

Initial candidate families should include, when supported by evidence:

- rivalry/history
- injury shock
- reaction transaction
- waiver run
- trade afterlife
- trade market shift
- asset journey
- roster architecture
- dynasty identity / two timelines
- historic upset
- scoring record
- franchise or manager streak
- repeated close losses
- former-player matchup
- playoff rematch
- lineup catastrophe
- division state / pressure
- cross-league NFL shock
- David-vs-Goliath when authoritative ranking context is supplied

The engine should remain extensible as editors identify useful recurring patterns.

## Story candidate payload

Each candidate should carry more than a headline.

A candidate should include:

- candidate type
- objective trigger reasons
- evidence/facts
- relevant timestamps
- historical context
- affected franchises/managers/players
- confidence in factual linkage
- editorial cautions about unsupported causation
- suggested editorial angles
- possible headline concepts
- possible graphics/tables
- estimated article depth

Suggested depth classes may include:

- cover feature: approximately 4-6 pages
- major feature: approximately 2-4 pages
- department/analysis: approximately 1-2 pages
- sidebar/graphic: approximately half to one page
- brief: a few paragraphs

These are editorial planning signals, not automatic layout decisions.

## Magazine voice

Ironbound Weekly and Unbound Weekly share infrastructure but are editorial siblings, not clones.

Ironbound headline suggestions may use its established language of forging, metal, Crown, architecture, fire, pressure, and divisions.

Unbound headline suggestions may use its established language of chains, links, tension, weak links, breaking points, and the Crown.

The factual evidence package remains neutral beneath those voice-specific headline suggestions.

## Power Rankings and WAR

Power Rankings are a non-negotiable section in every regular-season Ironbound Weekly and Unbound Weekly magazine.

The authoritative Power Rankings are produced by a separate existing workflow and emailed to the commissioner/editor. This Editorial Desk must not duplicate, replace, or independently calculate those rankings.

The magazine build may manually incorporate the authoritative ranking packet.

WAR is also treated as external/manual editorial enrichment unless a separate future project explicitly changes that responsibility.

The Story Desk may use Power Rankings or WAR as supporting evidence only when those external inputs are explicitly supplied.

If the official ranking input is absent, the Story Desk must not call a team "No. 1," "No. 15," or similar based on a substitute metric. It may still describe an upset or mismatch using records, scoring, projections, dynasty value, or other available evidence.

External inputs may support story types such as:

- David vs. Goliath
- giant-killing upset
- ranking/record divergence
- overperformance or underperformance
- roster dependency based on WAR

The magazine packet should identify which external editorial inputs were available for that build.

## Health reporting boundary

The existing health-reporting correction remains part of this architecture.

All publication tiers receive general Sleeper health/status and IR/reserve reporting.

Only Ironbound Weekly and Unbound Weekly receive expanded health context such as practice participation, injury start date, and depth-chart detail when available.

A healthy roster must be represented as having no health flags, not as health data unavailable.

"Unavailable" is reserved for genuine upstream metadata failure.

## What this checkpoint does not yet specify

The following are intentionally deferred to the next design section rather than guessed here:

- exact historical backfill execution sequence and migration safety
- exact data-branch write/merge mechanics under concurrent scheduled runs
- retry and partial-failure behavior for each upstream source
- archive corruption/rebuild recovery procedures
- exact retention duration for recent raw snapshots
- full test matrix, fixtures, and CI strategy
- implementation order and task breakdown

Those items must be designed and approved before coding begins.

## Locked decisions summary

The following decisions are considered approved and should not be changed during implementation without explicit editorial approval:

- permanent history for every tracked league
- deeper history-driven editorial use in Ironbound/Unbound
- dedicated `chronicle-data` branch
- append-only JSONL ledger plus rebuildable JSON indexes
- stable dynasty franchise identity and redraft manager identity
- lightweight daily collection plus three daily Wednesday-Sunday pulses
- Tuesday full compilation
- Event Ledger with explicit timestamp uncertainty
- universal normalized factual spine
- issue-phase-aware Publication Feature Contracts
- publication-ready deterministic packets for newspaper publications
- Hollywood Beat now has an established contract
- game-timeline context is universal
- Story Candidate Engine only for Ironbound Weekly and Unbound Weekly
- approximately 12-20 candidate ideas is preferred over aggressive filtering
- candidates include evidence, editorial cautions, graphics ideas, and article-depth suggestions
- Ironbound and Unbound retain distinct editorial voices
- official Power Rankings remain external and mandatory in the final magazines
- WAR remains optional external editorial enrichment
- the Editorial Desk must not fabricate or substitute missing official Power Rankings
- editors retain final control over causation, story selection, prose, and magazine layout
