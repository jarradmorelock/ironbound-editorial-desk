# Editorial Desk v2 — Chronicle, Event Ledger, Publication Contracts, and Magazine Story Desk

Date: 2026-09-16
Status: Final design for user review
Repository: `jarradmorelock/ironbound-editorial-desk`

This document is the authoritative consolidated design for the next major evolution of the Editorial Desk. It supersedes the earlier design checkpoint, weekly newspaper contract companion, and amendment documents on this branch where any wording conflicts.

The implementation plan must follow this document unless the editor explicitly approves a later design change.

---

## 1. Goal

The Editorial Desk should become a durable fantasy-football newsroom system rather than a weekly stat dump.

It must:

- preserve long-term league history across seasons
- record meaningful in-season events as they occur
- support reliable historical claims and rivalry records
- produce coherent, publication-specific weekly packets for the newspapers
- provide a richer Story Desk only for Ironbound Weekly and Unbound Weekly
- preserve each publication's distinct identity while sharing the same underlying factual calculations
- fail safely when an upstream source breaks
- remain recoverable through Git history and independent email backups
- provide enough evidence that the human editors can make final editorial decisions with confidence

The core editorial principle is:

> The software remembers facts and connects potentially related facts. The editors decide what those facts mean and how the story should be told.

The software may report supported temporal sequence. It must not infer motive merely because one event followed another.

---

## 2. High-level architecture

Editorial Desk v2 has five major layers:

1. **Universal factual spine**
2. **Chronicle**
3. **Event Ledger**
4. **Publication Feature Contracts**
5. **Magazine Story Desk**, enabled only for Ironbound Weekly and Unbound Weekly

The existing collector, review, health, rendering, Tuesday workflow, Wednesday supplement, and publication configuration remain foundations. The new design extends them rather than replacing them wholesale.

The intended flow is:

```text
upstream sources
  -> normalized factual collection
  -> Event Ledger + Chronicle
  -> common derived metrics/features
  -> publication feature contract
  -> publication-ready weekly packet
  -> human editorial writing/design
```

For Ironbound Weekly and Unbound Weekly, the flow additionally includes:

```text
Chronicle + Event Ledger + common features + optional external editorial inputs
  -> Magazine Story Desk
  -> evidence-rich candidate stories
  -> human editorial selection
  -> 20-30 page magazine
```

---

## 3. Permanent storage model

Permanent generated history will live on a dedicated branch in the same repository:

`chronicle-data`

The normal application code remains on `main`.

Scheduled jobs run code from `main` and read/write the data branch separately.

### Why a dedicated branch

This keeps generated data out of normal development history while preserving:

- Git auditability
- recovery from prior revisions
- no dependency on a new hosted database
- no dependency on Actions cache or artifact retention
- durable storage inside the existing repository

Normal automation must never force-push `chronicle-data`.

---

## 4. Chronicle and Event Ledger layout

The persistent data model uses:

- append-only JSONL event streams as the factual audit trail
- compact JSON history/index files as rebuildable materialized views
- small registries for stable identity mapping

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

  manifests/
    ...
```

The ledger is the primary factual record. Derived indexes are disposable and rebuildable.

If a franchise mapping is corrected later, the system should rebuild derived history from the ledger and corrected registry instead of manually editing many totals.

---

## 5. Event identity and idempotency

Every normalized event must receive a deterministic event ID derived from stable source identity and event content.

Repeated collection must not create duplicate events.

Examples that must remain idempotent:

- finalized matchups
- trades
- waiver claims
- free-agent additions
- drops
- player-status transitions
- reserve/IR transitions
- lineup changes
- draft events
- traded-pick events

A rerun after a workflow failure should be safe by design.

---

## 6. Stable league, franchise, and manager identity

### Dynasty leagues

Dynasty history follows the **franchise slot**, not the current display name or current manager.

Each dynasty franchise receives a stable internal `franchise_key` that persists across:

- team-name changes
- annual Sleeper renewals
- manager display-name changes
- ordinary ownership transfers unless the commissioner explicitly declares a new franchise

Manager tenure is recorded separately so the Chronicle can distinguish franchise history from manager-era history.

### Redraft leagues

Redraft history follows **stable manager identity within that league**, because rosters are recreated each season and team names are not durable franchise identities.

The Chronicle should therefore support all-time manager-vs-manager records across different annual team names.

### Registry corrections

Each season maps Sleeper `roster_id` and `owner_id` to stable internal identity keys.

Ambiguous ownership changes, co-managers, orphaned teams, and other edge cases must be manually correctable in the registry without rewriting source matchup history.

---

## 7. Historical backfill

The bootstrap process should walk each configured league backward through Sleeper's renewal chain as far as Sleeper can reliably reconstruct it.

Backfill is not a static appendix. It **seeds the permanent Chronicle**.

New seasons and new finalized events append to the same history, and all derived all-time indexes continue to update.

Example:

```text
backfilled all-time series: 13-1-1
new current-season win:     +1 win
materialized all-time:      14-1-1
```

There must not be a stale hand-maintained `historical_record` field that stops changing after backfill.

### Backfillable facts

When available, backfill should import:

- league settings and scoring
- owner/manager IDs
- roster/franchise mappings
- team-name aliases
- regular-season matchups
- playoff matchups/brackets
- records and final placement
- draft results
- transactions
- traded future picks
- division membership where the league actually used divisions
- championships and season finishes when reconstructable

### Facts that cannot be honestly backfilled

The system must not invent ephemeral state that was never observed.

Examples:

- exact historical moment a player changed from Questionable to Out
- old practice-participation changes never collected
- old projection swings
- exact historical Sunday lineup-state transitions that Sleeper no longer exposes
- commissioner knowledge that was never stored

These become trustworthy only from the start of live event collection.

### Provenance classes

Stored facts should retain provenance such as:

- `source_exact`
- `reconstructed_from_sleeper`
- `observed_live`

This distinction is available to later editorial logic.

### Alias preservation

Old team names and manager display names remain historical aliases with time ranges. They are not overwritten by current names.

### Rebuildability

Historical totals, streaks, rivalry records, scoring records, and similar indexes are regenerated from source events and registries. They are not treated as primary truth.

---

## 8. Event Ledger scope

The Event Ledger records meaningful state changes instead of only weekly end states.

Initial event families include:

- `MATCHUP_FINAL`
- `TRADE`
- `WAIVER_ADD`
- `FREE_AGENT_ADD`
- `DROP`
- `PLAYER_STATUS_CHANGE`
- `IR_RESERVE_CHANGE`
- `PRACTICE_STATUS_CHANGE` for deeper flagship collection
- `LINEUP_CHANGE`
- materially significant `PROJECTION_CHANGE` where configured
- `RECORD_SET`
- draft and future-pick events where relevant

League events and NFL/player events are separate streams.

An NFL player's health change is a cross-league player event. A fantasy acquisition is a league-specific event. The system correlates them without duplicating the same NFL event in every league ledger.

---

## 9. Time semantics and causation guardrails

Sleeper transactions may have exact source timestamps.

Health/status changes discovered through polling have observation-window semantics rather than fabricated exact change times.

Example:

```text
PLAYER_STATUS_CHANGE
player: Example Player
from: Questionable
to: Out
observed_before: 2026-09-16T13:05:00-04:00
observed_after: 2026-09-16T17:04:00-04:00
```

A later acquisition might have an exact timestamp:

```text
TRADE
occurred_at: 2026-09-16T17:08:23-04:00
```

The system may safely say the trade occurred after the first observed OUT state. It must not claim the manager made the trade because of that status unless independent evidence supports the causal statement.

---

## 10. Collection cadence

### Daily baseline

Run one lightweight collection every morning during the season.

### Active-week pulse

Run three lightweight passes per day from Wednesday through Sunday.

These passes prioritize:

- Sleeper league state
- transactions
- lineups
- player health/status
- reserve/IR state

They should not rerun every expensive enrichment source.

### Tuesday full compilation

Tuesday remains the primary editorial build.

It should:

- perform a final factual collection pass
- commit Chronicle changes first
- read one stable Chronicle revision for the rest of that editorial run
- build common derived features
- apply publication contracts
- build Magazine Story Desk candidates for Ironbound/Unbound only
- create the normal Tuesday reports/dossiers
- send the normal Tuesday email

### Wednesday supplement

The Wednesday supplement reads the Event Ledger and Tuesday baseline and reports genuinely new developments rather than resending the full dossier.

---

## 11. Universal factual spine

All publications consume normalized facts from a shared data layer.

The shared factual spine should support, as applicable:

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

The collector computes factual concepts, not themed department names.

For example, `lineup_flip_candidates` is calculated once and may render as:

- Ballad Crier: Weekly Rounds
- Saturday Standard: Portal Film Room
- Hollywood Beat: Cutting Room Floor

---

## 12. Publication Feature Contracts

The five weekly newspapers are contract-driven:

- The Ballad Crier
- The Stampede
- The Volunteer Voice
- The Saturday Standard
- The Hollywood Beat

The contracts are based on the actual established papers and are implementation requirements, not suggestions.

Contracts are issue-phase aware:

- weekly regular season
- preseason/draft
- offseason/postseason

A preseason-only feature must not become mandatory every Tuesday during the regular season.

---

## 13. Newspaper readiness states

Every required newspaper department must report one of:

- `ready`
- `ready_no_items`
- `unavailable`

Examples:

- healthy roster with no injuries -> `ready_no_items`
- health source failure -> `unavailable`
- three current Questionable players -> `ready`

A quiet week is not a source failure.

The compiler must never silently omit a required department because no qualifying event occurred.

---

## 14. Shared newspaper metric definitions

### Lineup efficiency

Submitted points divided by optimal legal active-lineup points.

Players who are not legally startable because they are on taxi or reserve/IR are excluded from the editorial optimal lineup.

### Result-flipping lineup decision

A legal alternative lineup substitution that changes the matchup winner.

The packet must preserve:

- actual starter
- alternative bench player
- actual points for both
- point swing
- hypothetical final
- whether the result flips

### Manager of the Week

Manager of the Week is not simply the highest score or highest efficiency.

It uses evidence-based manager-decision logic. Each publication may frame the honor differently, but the underlying calculation must remain coherent.

### Bad Beat

Strong losing performance based primarily on points and matchup context, with median context where applicable.

### Escape Artist

A win despite weak scoring context, especially below-median scoring in a median league.

### Rookie of the Week

Strongest rookie fantasy performance, with explicit started/benched status.

### Free Agent of the Week

Should consider genuinely unrostered/free-agent players rather than merely rostered players who did not appear in the current matchup.

### Waiver impact

Must preserve transaction type, FAAB, player production, lineup status, and result relevance when measurable.

### Historical facts

Every historical claim must be generated from Chronicle evidence. Incomplete historical coverage must be labeled rather than silently treated as true all-time coverage.

---

## 15. The Ballad Crier contract

Editorial identity: medical / hospital-rounds framing.

### Weekly requirements

- Lead / weekly diagnosis material
- Week Cardiogram / scoreboard
- Final Monitor
- Weekly Rounds / lineup autopsy
- Official Standings
- Rankings Wire
- Rounds Report / weekly honors
- Position Leaders
- Waiver Star
- Ward Report
- Record Watch
- Next Card

### Lead material must surface

- closest finish
- largest comeback
- highest score
- largest margin
- late-game/Monday reversal
- important health-driven swing when supported

### Cardiogram

Must include:

- every team score
- matchup pairings
- H2H result
- weekly median where applicable
- above/below-median result
- record impact

### Weekly Rounds

Must include all legal bench-to-starter substitutions that would have flipped results, not merely generic efficiency.

### Standings

Must include official record, points, efficiency, and ordering/seeding logic.

### Rankings Wire

Must remain distinct from standings and support forward-looking data-power context and movement.

### Rounds Report

Must support:

- Manager of the Week
- Bad Beat
- Escape Artist
- Benchwarmer
- Rookie of the Week
- Free Agent of the Week

### Position Leaders

Support league positions including at least QB/RB/WR/TE and DEF/DST when used, with started/benched status.

### Waiver Star

Preserve player, acquiring team, transaction type, FAAB, production, and result relevance.

### Ward Report

Must include general health/status plus Sleeper IR/reserve, per-team health counts, largest ward, and status changes where available.

Deep flagship injury enrichment is not required.

### Preseason/draft support

- Draft Desk
- Keeper Heist / keeper value
- reach/value analysis
- full draft-board context
- market-event / news-driven ADP context
- Streamers' Pact where relevant

Existing published papers are not regenerated retroactively.

---

## 16. The Stampede contract

Editorial identity: 9-to-5 / workweek / Dolly Parton framing.

### Weekly requirements

- scoreboard and median result where applicable
- standings and power movement
- lineup efficiency
- Manager of the Week
- Bad Beat
- Escape Artist
- Bench MVP / result-flipping decision
- waiver/transaction desk
- **What a Way to Make a Living**
- Health Board / Mystery Mine
- Record Watch
- Next Shift

### What a Way to Make a Living

This is the official name of the Stampede's recurring real-football workload/stat-line feature.

The old names `The Week's Heavy Lifting` and `Heavy Lifting` are retired and must not appear in implementation.

The underlying collector must preserve real football production such as:

- rushing attempts
- rushing yards
- rushing touchdowns
- receiving volume
- receiving yards
- receiving touchdowns
- passing volume
- passing yards
- passing touchdowns where editorially useful

The purpose is to highlight substantial real-world football workload and production, not merely repeat fantasy-points leaders.

### Preseason/draft support

- Rankings Wire
- First Shift
- Value Board
- Paper Favorite
- Stampede Board
- reach-watch material
- I Will Always Love You
- Bargain Store
- Coat of Many Colors
- Old Flames
- Little Engine That Could
- Mystery Mine / Health Board
- season predictions when simulation data exists

---

## 17. The Volunteer Voice contract

Editorial identity: Tennessee / Rocky Top / family-rivalry framing.

**Rocky Top Rumble has no divisions. Volunteer Voice logic must never assume divisions exist.**

### Weekly requirements

- Lead Story / weekly aftermath
- Official Table
- league-median line and second result
- Rankings Wire
- Decision Desk / The Call That Won the Week
- league-wide MVP / top individual performance
- Manager of the Week
- Benchwarmer
- Rookie of the Week
- Free Agent of the Week
- Efficiency Board
- Bad Beat
- Escape Artist
- Waiver Star
- Bench Blast
- Record Watch
- next-week scouting report

### Decision Desk

Must remain distinct from generic efficiency and preserve:

- winning manager
- actual starter
- plausible alternative
- projection relationship
- actual scoring relationship
- point swing
- final victory margin
- evidence that the decision materially affected the result

### MVP treatment

Volunteer Voice has no divisional MVPs.

If a gold-foil treatment is used, it represents the single highest-scoring qualifying started player league-wide.

Trading-card images remain outside the Editorial Desk.

### Explicitly prohibited Volunteer Voice assumptions

- divisional MVP nominees
- Division Pulse
- division averages
- division H2H records
- divisional standings

Any prior paper section that used division language is not a future implementation requirement.

### League-specific awareness

The contract must remain aware of Rocky Top's league-median scoring and established postseason/seeding rules when relevant.

---

## 18. The Saturday Standard contract

Editorial identity: SEC college-football framing.

The SEC Dynasty league **does use East and West divisions**, and divisions are first-class publication structure.

Offense and IDP are equally important first-class data.

### Weekly requirements

- Saturday Scoreboard
- Opening Statement/game-feature material
- East and West Division Pulse
- East and West Power Polls
- Lineup Efficiency
- Portal Film Room
- Portal Commitments
- Saturday Honors
- offensive and IDP Position Board
- Saturday Desk
- Dynasty Market Board
- Transfer Portal Dispatch
- Recruiting Desk
- future-pick/recruiting ledger
- next-week slate

### Divisional requirements

Must support:

- East and West division identity
- division scoring averages
- division H2H records
- divisional standings/poll context
- East MVP
- West MVP
- gold-foil designation for the higher-scoring divisional MVP

Divisional MVP candidates are the highest-scoring **STARTED** player in each division.

Card art remains outside the Editorial Desk.

### IDP requirements

The Position Board and analysis must support defensive positions as configured, including relevant subsets of:

- LB
- DL
- DE
- DT
- DB
- CB
- NT

IDP lineup decisions, IDP rookie analysis, and defensive roster strength must not be dropped during refactoring.

### Dynasty/market/recruiting requirements

Must support:

- dynasty market values when an authoritative source is available
- source labeling and graceful degradation when unavailable
- trades and waiver/free-agent movement
- future picks by year/round/original owner where available
- rookie draft board
- recruiting-class totals and immediate-impact context
- offensive and IDP rookie positions

---

## 19. The Hollywood Beat contract

Editorial identity: film-industry / studio / box-office framing.

The earlier "publication standard pending" state is obsolete.

### Weekly requirements

- Box Office
- Marquee / Official Standings
- Top Billing / First Cut lead material
- Hollywood Board factual slots
- Monday Night / Late Show timeline context
- For Your Consideration honors
- Cutting Room Floor
- Studio Efficiency
- Casting Call
- Production Delays
- Dailies / Backlot Reports
- This Week's Bill

### Box Office / Marquee

Support final scores, winners/losers, median result where used, records, points, and current ordering.

### Hollywood Board

Must support factual candidates for at least:

- Top Billing
- Scene Stealer
- Plot Twist
- Bad Beat

### Late Show

Must support:

- score entering final game window
- players remaining
- late-game production
- projection delta when available
- final score/margin

### For Your Consideration

Must support:

- Scene Stealer
- Best Supporting Act
- Manager of the Week
- Bench MVP
- Rookie of the Week
- Free Agent Watch
- position leaders

### Cutting Room Floor

Uses the shared result-flipping lineup-decision calculation.

### Casting Call

Uses waiver/free-agent additions, FAAB, production, and result relevance.

### Production Delays

Uses general health/status plus reserve/IR state.

### Dynasty/preseason support

- Critics' Poll inputs
- Meet the Cast roster capsules
- rookie Casting Call
- Development Rights / future picks
- Studio Deals / major trades
- roster timeline context
- dynasty market context

Hollywood Beat does **not** receive the Magazine Story Desk.

---

## 20. Universal NFL game-timeline context

Monday-night and late-window storytelling is not exclusive to the magazines.

The universal data layer should preserve enough NFL timing/stat context to deterministically reconstruct, where supported:

- score entering Monday/final window
- players remaining
- points added in the late window
- final score
- final margin

This supports Ballad Crier, Saturday Standard, Hollywood Beat, and any other paper that uses late-game swings.

The implementation must distinguish exact preserved snapshots from reconstructed game-window context.

---

## 21. Health-reporting boundary

All publication tiers receive:

- general player health/status
- Sleeper IR/reserve state

Ironbound Weekly and Unbound Weekly additionally receive deeper health context when available, such as:

- practice participation
- injury start date
- depth-chart context

A healthy roster is not `unavailable`. It is a valid no-flags result.

`unavailable` is reserved for genuine upstream data failure.

---

## 22. Ironbound Weekly and Unbound Weekly editorial model

Ironbound Weekly and Unbound Weekly are editorially driven magazines rather than rigid newspaper templates.

They receive a small mandatory factual backbone, including:

- results/standings
- important movement
- significant transactions
- health
- Record Watch
- relevant divisional state
- MVP/award candidates
- next matchups

However, the system must not encode a fixed 20-30 page table of contents.

The editors assemble each issue from the best available stories, analysis, graphics, and recurring factual sections.

---

## 23. Magazine Story Desk scope

The Story Candidate Engine is enabled **only** for:

- Ironbound Weekly
- Unbound Weekly

It is disabled for:

- Ballad Crier
- Stampede
- Volunteer Voice
- Saturday Standard
- Hollywood Beat

This scope must be explicit in configuration, ideally as a capability such as `story_desk: true`, rather than inferred merely from dynasty format or generic tier.

---

## 24. Story Desk behavior

The Story Desk should be generous rather than overly selective.

A normal Tuesday packet should aim to surface roughly 12-20 viable ideas when enough events exist.

The engine does **not** decide the final magazine.

The editors decide which ideas become:

- cover features
- major articles
- departments
- sidebars
- graphics
- briefs
- nothing at all

### Candidate families

Initial candidate families include:

- rivalry/history
- injury shock
- reaction transaction
- waiver run
- trade afterlife
- trade-market shift
- asset journey
- roster architecture
- dynasty identity / two timelines
- historic upset
- scoring record
- franchise/manager streak
- repeated close losses
- former-player matchup
- playoff rematch
- lineup catastrophe
- division-state pressure
- cross-league NFL shock
- David-vs-Goliath when authoritative ranking context is supplied

The family list is extensible.

---

## 25. Story candidate payload

Each candidate should carry:

- candidate type
- objective trigger reasons
- evidence facts
- referenced ledger/history IDs
- relevant timestamps and provenance
- historical context
- affected franchises/managers/players
- evidence strength
- caution about unsupported causation where relevant
- suggested editorial angles
- possible headline concepts
- possible charts/graphics/tables
- estimated article depth

Suggested depth classes:

- cover feature: about 4-6 pages
- major feature: about 2-4 pages
- department/analysis: about 1-2 pages
- sidebar/graphic: about half to one page
- brief: a few paragraphs

These are planning aids, not automatic layout decisions.

---

## 26. Magazine voice

Ironbound Weekly and Unbound Weekly share infrastructure but retain separate editorial identities.

Ironbound headline suggestions may use established language around:

- forging
- metal
- fire
- Crown
- architecture
- pressure

Unbound suggestions may use established language around:

- chains
- links
- tension
- weak links
- breaking points
- Crown

Underlying evidence remains neutral.

---

## 27. External Power Rankings and WAR

Power Rankings are a **non-negotiable final magazine section** for every regular-season Ironbound Weekly and Unbound Weekly issue.

However, the authoritative Power Rankings are produced by the existing separate workflow and emailed to the editor.

Editorial Desk v2 must not:

- replace that workflow
- independently calculate an alternate official ranking
- silently substitute a different internal metric

The magazine is assembled with the external ranking packet manually supplied.

WAR is likewise treated as optional external editorial enrichment unless a separate future project changes that responsibility.

### Story Desk usage

When official Power Rankings or WAR are supplied, the Story Desk may use them as supporting evidence for stories such as:

- David vs. Goliath
- giant-killing upset
- ranking/record divergence
- overperformance or underperformance
- player/roster dependency

If official ranking input is absent, the Story Desk must not call a team "No. 1" or "No. 15" using a substitute metric.

The packet should identify which external editorial inputs were available for the build.

---

## 28. Failure and recovery model

The system should **fail locally, preserve good facts, and make incompleteness obvious**.

One broken league or source must not destroy successful data from other leagues/sources.

### Source freshness states

Each source should be represented as:

- `fresh`
- `stale`
- `unavailable`

`stale` means prior valid data exists but the current refresh failed.

### No false transitions from missing data

A source failure must never be interpreted as a factual change.

Example:

If health metadata disappears temporarily, the system must not generate `Questionable -> Healthy`. It marks health stale instead.

### Run manifest

Every collection run should record:

- run timestamp
- source freshness
- leagues attempted
- successful/failed leagues
- events created
- duplicate/skipped events
- materialization status
- warnings/errors
- Chronicle revision used/produced

### Atomic write behavior

Chronicle writes should be staged, validated, then committed.

A crash halfway through materialization must leave the prior valid Chronicle intact.

### Retry safety

Because event IDs are deterministic, rerunning after failure must not duplicate already-recorded facts.

### Corrections

- identity errors -> registry correction + rebuild
- genuine source-fact correction -> explicit correction/superseding event when needed

The audit trail should be preserved rather than silently rewriting source history.

---

## 29. Data retention

Data falls into three retention classes.

### Permanent

- Event Ledger
- Chronicle history/indexes
- identity registries
- run manifests
- schema/correction records

### Recent diagnostic retention

Keep approximately 30 days of:

- raw/recent Sleeper snapshots
- health/status observations
- normalized collection snapshots useful for debugging

The exact cleanup implementation may vary, but the retention target is about 30 days.

### Ephemeral

Delete after the workflow run:

- temporary caches
- staging trees
- rendering scratch files
- temporary downloads

The repository should not become a warehouse of giant raw snapshots.

---

## 30. Concurrency and Chronicle write safety

All workflows capable of modifying `chronicle-data` must share one serialized writer concurrency group.

Reads may be concurrent. Writes may not race.

The write flow should be:

```text
1. checkout main code
2. fetch latest chronicle-data
3. collect new facts
4. stage changes
5. validate events/indexes
6. refresh chronicle-data before commit
7. reconcile newer branch state if necessary
8. materialize from the combined ledger
9. commit only if content changed
10. push without force
```

If a non-fast-forward conflict occurs, the job should refetch/rebuild/retry rather than overwrite newer data.

Where practical, one successful logical collection run should map to one data-branch commit.

Commit metadata should make operational diagnosis easy, for example recording week, event counts, warnings, and run time.

---

## 31. Schema evolution

Every event carries a `schema_version`.

The preferred model is:

- preserve old ledger records
- teach materializers/migrations how to read old versions
- rebuild derived indexes into the latest schema

Avoid wholesale rewriting of historical ledger files merely because a new schema version exists.

---

## 32. Stable Chronicle snapshot during editorial builds

Tuesday publication assembly should not read a moving target.

The Tuesday workflow may perform a final collection pass, commit it, then pin the rest of the editorial build to that exact Chronicle revision.

The dossier must not change underneath itself during generation.

---

## 33. Monthly email archive

On the **first Tuesday of every month**, the normal Tuesday Editorial Desk email should include the usual weekly files **plus a validated Chronicle backup archive as an additional attachment**.

No separate monthly email is required.

Suggested filename:

`editorial-chronicle-backup-YYYY-MM-DD.zip`

### Archive contents

The backup should include enough permanent state to restore the newsroom, including:

- registries
- league event ledgers
- derived history/indexes
- cross-league player events
- relevant manifests
- backup manifest

### Backup manifest

The archive should record:

- archive creation timestamp
- exact `chronicle-data` commit SHA
- schema version(s)
- leagues included
- seasons included
- event counts
- file checksums
- validation result

### Retry behavior

If the first-Tuesday workflow retries, it should avoid sending duplicate monthly archives when the original monthly archive/send already succeeded.

If the original send failed, retry should attempt to send it.

---

## 34. Pre-major-change backups

Before any major Chronicle-affecting maintenance operation, create and successfully send a fresh safety archive before the operation proceeds.

Major changes include:

- event-schema migration
- registry restructuring
- franchise/manager identity-logic changes
- historical backfill/re-backfill
- bulk correction jobs
- storage-layout changes
- replacing/recreating `chronicle-data`
- materializer changes capable of substantially rewriting derived history

Normal append-only collection does not require a pre-change backup.

For major maintenance, the sequence is:

```text
1. validate current Chronicle
2. create backup archive
3. email backup
4. confirm successful send
5. only then run major migration/maintenance
6. validate resulting Chronicle
7. retain backup regardless of outcome
```

Failure to produce/send the pre-change backup is a hard stop for that maintenance operation.

---

## 35. Testing strategy — event correctness

Unit tests must prove:

- deterministic event IDs
- repeated collection creates no duplicates
- repeated final matchup imports create no duplicates
- repeated transaction imports create no duplicates
- status transitions normalize correctly
- reserve transitions normalize correctly

Derived history tests must prove continuous updating, for example:

```text
13-1-1 + win = 14-1-1
```

and winning streaks reset/extend correctly.

---

## 36. Testing strategy — identity continuity

Fixtures must cover:

- dynasty franchise rename
- dynasty manager change
- annual Sleeper league renewal
- redraft manager returning under a new team name
- manager leaving/rejoining
- ambiguous roster ownership corrected via registry override

Assertions must prove:

- dynasty history follows franchise identity
- redraft history follows manager identity
- manager tenure remains separately queryable in dynasty

---

## 37. Testing strategy — historical backfill

Backfill fixtures should span multiple seasons and verify:

- each matchup imports once
- drafts/transactions preserve season context
- aliases are preserved
- playoff meetings are distinguishable from regular-season meetings
- second backfill run makes no duplicate changes
- a new live result updates the same all-time record
- missing historical fields remain unknown rather than invented
- historical ephemeral health transitions do not magically appear
- exact historical transaction timestamps are preserved when the source provides them

---

## 38. Testing strategy — event timing and correlation

Fixtures should test observation windows such as:

```text
13:05 Questionable observed
17:04 Out observed
17:08 acquisition
```

Assertions should verify that supported event order is reported without inventing an exact status-change minute or causal motive.

Cross-league tests should show that one NFL player event can correlate with league-specific reactions in multiple leagues.

---

## 39. Testing strategy — Story Desk scope

Regression tests must prove Story Desk is enabled only for:

- Ironbound Weekly
- Unbound Weekly

and disabled for:

- Ballad Crier
- Stampede
- Volunteer Voice
- Saturday Standard
- Hollywood Beat

A common event may affect every league's factual packet while producing Story Desk candidates only in the two magazines.

---

## 40. Testing strategy — newspaper contracts

Each newspaper gets fixture-driven contract tests.

A shared lineup-flip fixture should prove the same normalized fact renders as:

- Ballad Crier -> Weekly Rounds
- Saturday Standard -> Portal Film Room
- Hollywood Beat -> Cutting Room Floor

The underlying calculation must remain identical.

### Corrected contract regression tests

Volunteer Voice:

- no division logic
- no divisional MVP requirement
- no Division Pulse
- league-wide MVP
- median-scoring logic
- Decision Desk

Saturday Standard:

- East/West divisions exist
- East MVP
- West MVP
- gold-foil comparison
- IDP position leaders

Stampede:

- department name is `What a Way to Make a Living`
- retired Heavy Lifting names do not appear
- real NFL workload/stat inputs are available

---

## 41. Testing strategy — readiness states

Tests must distinguish:

- `ready`
- `ready_no_items`
- `unavailable`

Examples:

- health source succeeds and roster healthy -> `ready_no_items`
- health source fails -> `unavailable`
- health source succeeds with flagged players -> `ready`

Equivalent behavior should be tested for lineup flips, waiver impact, Record Watch, and other recurring features.

---

## 42. Testing strategy — game-window reconstruction

A fixture should include a matchup where one team trails entering Monday/final window and wins because of a remaining player.

The packet should reconstruct:

- pre-window score
- players remaining
- late-game production
- final score
- final margin

This functionality must work without the Magazine Story Desk.

---

## 43. Testing strategy — Story Desk factual guardrails

Do not unit-test whether a headline is aesthetically good.

Do test that:

- candidate evidence references valid ledger/history IDs
- rivalry records match Chronicle values
- historical claims match stored evidence
- unsupported causation is not asserted
- official Power Ranking references appear only when official ranking input is supplied
- WAR-derived claims appear only when WAR input exists
- candidate depth classification does not change source facts
- absent official rankings never trigger fake "No. 1" labels from substitute metrics

---

## 44. Testing strategy — failure and recovery

Simulate:

- one league failing while others succeed
- transactions succeeding while health fails
- stale health state
- malformed event input
- failed materialization
- duplicate scheduled run
- interrupted Chronicle write
- non-fast-forward branch update

Assertions:

- valid league/source data survives
- failed components are flagged
- no false transition events are generated
- previous valid Chronicle remains intact
- rerun succeeds without duplication

---

## 45. Testing strategy — backup behavior

Monthly backup tests must verify:

- archive created only on first Tuesday of the month
- archive is attached to the normal Tuesday email
- required Chronicle state is present
- manifest contains exact `chronicle-data` SHA
- checksums validate
- successful retry does not send duplicate monthly backup
- failed original send permits retry

Pre-major-change tests must verify:

```text
backup succeeds -> migration may proceed
backup fails    -> migration stops
```

---

## 46. End-to-end fixture

Maintain at least one synthetic multi-season fixture league/history containing:

- franchise rename
- manager change
- trade
- waiver claim
- injury/status event
- upset
- lineup flip
- playoff meeting
- future-pick trade
- new-season renewal

The integration test should exercise:

```text
historical backfill
-> Chronicle build
-> live event append
-> derived indexes
-> newspaper packets
-> Magazine Story Desk
-> Wednesday supplement
-> monthly archive
```

---

## 47. CI bands

### Fast

Run unit tests on every push.

### Full

Run fixture and integration tests on pull requests and `main`.

### Live smoke

Run read-only smoke validation against real upstream APIs on scheduled/manual workflows.

Live external availability should not become a requirement for normal local/unit test success.

---

## 48. Operational success standard

Implementation is not considered complete unless it proves:

- historical continuity
- continuously updating all-time history
- idempotent event capture
- stable identity mapping
- publication-contract integrity
- Story Desk scope boundaries
- correct newspaper distinctions
- correct Volunteer Voice no-division behavior
- correct Saturday Standard East/West behavior
- correct Stampede `What a Way to Make a Living` naming/data
- graceful source degradation
- atomic Chronicle writes
- concurrency safety
- monthly independent backups
- pre-major-change backups
- recoverability

---

## 49. Locked decisions summary

The following decisions are approved and must not be weakened during implementation without explicit editorial approval:

- every tracked league receives durable Chronicle history
- historical backfill seeds the permanent Chronicle and continues updating forever
- dynasty history follows franchise identity
- redraft history follows manager identity
- generated permanent history lives on `chronicle-data`
- the Event Ledger is append-only and idempotent
- derived history is rebuildable
- source provenance and time uncertainty are explicit
- lightweight daily collection runs in season
- three Wednesday-Sunday pulse collections run daily
- Tuesday remains the full editorial build
- Wednesday remains the supplement/delta pass
- all newspapers consume one normalized factual spine
- newspaper publications are governed by explicit Feature Contracts
- readiness distinguishes valid-empty from unavailable
- game-window/Monday context is a universal capability
- health/status + IR/reserve is universal
- deeper health enrichment remains magazine-only
- Ballad Crier retains its established recurring departments
- Stampede retains its established workweek identity and `What a Way to Make a Living`
- Volunteer Voice has **no divisions**
- Volunteer Voice MVP treatment is league-wide
- Saturday Standard retains **East and West divisions**
- Saturday Standard treats IDP as first-class
- Hollywood Beat has a complete established weekly contract
- only Ironbound Weekly and Unbound Weekly receive the Magazine Story Desk
- Story Desk should provide a generous pool of evidence-rich ideas rather than deciding the issue
- Ironbound and Unbound keep distinct editorial voices
- official magazine Power Rankings remain externally generated and mandatory in final regular-season magazines
- WAR remains optional external enrichment
- Editorial Desk never substitutes fake official rankings when the external ranking packet is missing
- source failures do not become false factual transitions
- writes to Chronicle are staged and atomic
- all Chronicle writers are serialized
- no normal automation force-pushes `chronicle-data`
- about 30 days of diagnostic snapshots are retained
- the first Tuesday of each month attaches a validated Chronicle archive to the normal Tuesday email
- major Chronicle-affecting maintenance requires a successfully sent pre-change backup
- testing must cover continuity, idempotency, identity, contracts, failure recovery, backups, and end-to-end behavior
- human editors retain final authority over causation, interpretation, story selection, prose, graphics, and layout

---

## 50. Implementation boundary

This design defines behavior and architecture. It intentionally does not prescribe every filename/class/function in advance.

The implementation plan should map these requirements onto the current repository structure with minimal unnecessary refactoring, preserve existing working workflows where possible, and introduce new modules only where they create clear responsibility boundaries.

No implementation should begin until this consolidated design is approved by the editor and a detailed implementation plan has been written.