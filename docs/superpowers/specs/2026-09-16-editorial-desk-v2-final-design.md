# Editorial Desk v2 — Final Architecture and Publication Design

Date: 2026-09-16
Status: Final design for editor review
Repository: `jarradmorelock/ironbound-editorial-desk`

This is the authoritative consolidated design for Editorial Desk v2. It supersedes, where wording conflicts, the earlier design checkpoint, weekly newspaper contract companion, amendment, and intermediate consolidated draft on this branch.

No implementation should begin until the editor approves this document and a detailed implementation plan is written.

---

## 1. Mission

Editorial Desk v2 should function as a durable fantasy-football newsroom system.

It must:

- preserve league history across seasons
- continue updating all-time records as new games occur
- capture meaningful in-season changes as events
- support evidence-backed historical and rivalry reporting
- produce consistent publication-ready packets for the weekly newspapers
- provide a richer editorial Story Desk for Ironbound Weekly and Unbound Weekly only
- preserve each publication's visual/editorial identity without duplicating factual calculations
- fail safely when sources break
- protect permanent history from race conditions and accidental corruption
- maintain independent email backups in addition to Git history
- give the human editors evidence, not false certainty

Core principle:

> The software remembers facts and connects potentially related facts. The editors decide what those facts mean and how the story should be told.

The system may report supported event sequence. It must not infer motive merely because one event followed another.

---

## 2. Architectural layers

Editorial Desk v2 has five major layers:

1. **Universal factual spine**
2. **Chronicle**
3. **Event Ledger**
4. **Publication Feature Contracts**
5. **Magazine Story Desk**, available only to Ironbound Weekly and Unbound Weekly

The intended flow is:

```text
upstream sources
  -> normalized collection
  -> Event Ledger + Chronicle
  -> common derived features
  -> publication feature contract
  -> publication-ready packet
  -> human editorial writing/design
```

For Ironbound Weekly and Unbound Weekly:

```text
Chronicle + Event Ledger + common features + optional external editorial inputs
  -> Magazine Story Desk
  -> evidence-rich candidate stories
  -> human editorial selection
  -> 20-30 page magazine
```

The current collector, enrichment, review, health, rendering, Tuesday workflow, Wednesday supplement, and publication configuration should be extended rather than discarded.

---

## 3. Persistent storage branch

Permanent generated history lives on a dedicated branch in the same repository:

`chronicle-data`

Application code remains on `main`.

Scheduled jobs execute code from `main` and read/write `chronicle-data` separately.

Benefits:

- generated history does not clutter development commits
- Git supplies an audit trail
- history survives Actions cache/artifact expiration
- no new hosted database is required
- prior revisions remain recoverable

Normal automation must never force-push `chronicle-data`.

---

## 4. Chronicle data layout

Persistent data uses:

- append-only JSONL event streams as factual audit trail
- compact JSON derived indexes as rebuildable materialized views
- stable identity registries
- run and backup manifests

Illustrative layout:

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

  coverage/
    live_observation.json

  manifests/
    ...
```

The ledger is primary evidence. Derived history is rebuildable.

If an identity mapping changes, the registry is corrected and the derived history is regenerated rather than manually editing many historical totals.

---

## 5. Minimum event record shape

Each normalized event should contain enough information to be independently understood and traced.

Minimum conceptual fields:

```text
event_id
schema_version
event_type
league_key            # null for cross-league NFL-only events when appropriate
season
week                   # null where not meaningful
occurred_at            # source-exact time when available
observed_at            # collector observation time
observed_before        # optional interval bound
observed_after         # optional interval bound
source
source_ref
provenance             # source_exact / reconstructed_from_sleeper / observed_live
entities                # players, franchises, managers, picks, etc.
before                  # optional state
 after                  # optional state
evidence                 # source facts used to normalize the event
cross_league_key         # optional correlation key
correction_of            # optional superseding/correction reference
```

Exact serialization may evolve during implementation, but these semantics must remain available.

Every event gets a deterministic ID so reruns cannot create duplicate factual events.

---

## 6. Idempotency

Repeated collection must be safe.

The same source event fetched multiple times must still produce one ledger event.

This includes:

- finalized matchups
- trades
- waiver claims
- free-agent additions
- drops
- player-status changes
- reserve/IR changes
- lineup changes
- draft events
- traded-pick events

A workflow retry after partial failure must not duplicate already-preserved facts.

---

## 7. Stable identity model

### Dynasty

Dynasty history follows the **franchise**, not the current team name or current manager.

Each dynasty franchise has a stable internal `franchise_key` surviving:

- team-name changes
- annual Sleeper league renewals
- manager display-name changes
- ordinary ownership transfers unless the commissioner explicitly declares a new franchise

Manager tenure is stored separately so the system can answer both franchise-history and manager-era questions.

### Redraft

Redraft history follows **stable manager identity within that league**.

This supports all-time manager-vs-manager records even when annual team names and rosters change.

### Registry corrections

Each season maps Sleeper roster/owner IDs to stable internal keys.

Co-managers, orphan teams, ownership ambiguity, and unusual transitions must be manually correctable without rewriting source matchup evidence.

---

## 8. Which leagues receive Chronicle history

Every configured tracked league is eligible for durable Chronicle history, including publication-disabled/data-only leagues.

A publication-disabled league can contribute history and cross-league factual context without receiving a publication packet or Story Desk output.

---

## 9. Historical backfill

The initial bootstrap walks each configured league backward through Sleeper's renewal chain as far as Sleeper can reliably reconstruct it.

Backfill is **not** a frozen historical appendix. It seeds the permanent Chronicle.

Future games and seasons append to the same source history.

Example:

```text
backfilled rivalry record: 13-1-1
new current-season win:   +1 win
new all-time record:       14-1-1
```

There must not be a stale manually maintained `historical_record` number.

### Backfillable facts

When available:

- league settings/scoring
- owner IDs
- roster/franchise mappings
- historical aliases
- regular-season matchups
- playoff matchups/brackets
- season records
- final placement/championships
- drafts
- transactions
- traded future picks
- divisions where the league actually used them

### Ephemeral facts that cannot be invented

Do not reconstruct unsupported historical state such as:

- exact old Questionable -> Out change moments
- old practice participation never collected
- old projection swings never preserved
- historical Sunday lineup transitions not available from source
- unstored commissioner/editorial knowledge

These become trustworthy only from the start of live observation.

### Provenance

Facts should distinguish:

- `source_exact`
- `reconstructed_from_sleeper`
- `observed_live`

### Live-coverage markers

The Chronicle must record when live observation begins for sources such as:

- health/status polling
- practice data
- intraweek lineup observation
- projection-change monitoring

This prevents the absence of an older event from being misread as proof that no event occurred.

### Alias preservation

Old team/manager names remain time-bounded aliases. Current names do not overwrite historical wording.

### Rebuildability

All-time records, streaks, rivalry totals, scoring records, and similar indexes are derived from underlying events and can be regenerated.

---

## 10. Event Ledger scope

Initial event families include:

- `MATCHUP_FINAL`
- `TRADE`
- `WAIVER_ADD`
- `FREE_AGENT_ADD`
- `DROP`
- `PLAYER_STATUS_CHANGE`
- `IR_RESERVE_CHANGE`
- `PRACTICE_STATUS_CHANGE` for magazine-level health enrichment
- `LINEUP_CHANGE`
- materially significant `PROJECTION_CHANGE` when configured
- `RECORD_SET`
- draft events
- traded-pick events

NFL/player events and league-specific fantasy events remain separate.

Example:

- NFL player becomes Out -> cross-league player event
- fantasy franchise acquires a replacement -> league event

The system may correlate those records without duplicating the NFL event into every league ledger.

---

## 11. Timestamp semantics and causation

Source-exact timestamps and observed intervals are different kinds of evidence.

Sleeper transactions may carry exact event timestamps.

Polled status changes usually do not. They use observation bounds such as:

```text
observed_before: 13:05 Questionable
observed_after:  17:04 Out
```

A 17:08 acquisition can be described as occurring after the first observed Out state.

The system must not state that the injury **caused** the acquisition unless independent evidence supports that conclusion.

---

## 12. Collection cadence

### Daily baseline

One lightweight morning collection every day during the season.

### Wednesday-Sunday pulse

Three lightweight passes per day Wednesday through Sunday.

Priority inputs:

- Sleeper league state
- transactions
- lineups
- player status
- IR/reserve state

Do not rerun all expensive enrichment on every pulse.

### Tuesday full build

Tuesday remains the primary editorial compilation.

Sequence:

1. final factual collection pass
2. validate and commit Chronicle changes
3. pin one Chronicle revision for the editorial run
4. derive common features
5. apply newspaper contracts
6. build Ironbound/Unbound Story Desks
7. generate Tuesday files
8. send normal Tuesday email
9. on first Tuesday of month, attach Chronicle archive

### Wednesday supplement

Compare Tuesday baseline with Event Ledger/current state and surface genuinely new developments without duplicating the full Tuesday report.

---

## 13. Universal factual spine

All publications consume normalized common facts.

The system should expose, where applicable:

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

Paper themes do not create separate contradictory calculations.

---

## 14. Feature Contract dependency strength

Each publication feature can declare dependencies as:

- **required**: fundamental data without which the feature cannot be truthfully produced
- **preferred**: materially improves the feature but may degrade gracefully if missing
- **optional**: enriches output but has no effect on readiness if absent

Examples:

- Sleeper matchup results may be required for a scoreboard
- deeper injury metadata may be preferred for a health section
- externally supplied dynasty market values may be preferred/optional depending on department

Missing preferred or optional enrichment must not kill an otherwise valid paper.

Fundamental missing facts should be surfaced clearly rather than silently replaced.

---

## 15. Newspaper readiness states

Each required newspaper department reports one of:

- `ready`
- `ready_no_items`
- `unavailable`

Examples:

- health source succeeds, no injuries -> `ready_no_items`
- health source fails -> `unavailable`
- health source succeeds with flagged players -> `ready`

A quiet week is not a failure.

---

## 16. Issue phases

Publication contracts are phase-aware.

Supported phases:

- weekly regular season
- preseason/draft
- postseason/offseason

A preseason department must not become a mandatory weekly feature simply because it exists in the same publication.

---

## 17. Shared metric definitions

### Lineup efficiency

Submitted points divided by optimal legal active-lineup points.

Taxi and IR/reserve players are excluded when they are not legally startable.

### Result-flipping lineup decision

A legal alternative start that changes the matchup winner.

Preserve:

- actual starter
- legal bench alternative
- points for both
- point swing
- hypothetical final
- whether result flips

### Manager of the Week

Not simply highest score or highest efficiency.

Use the established evidence-based manager-decision methodology. Themed presentation may differ by publication.

### Bad Beat

Strong losing performance based primarily on scoring and matchup context, with median context where relevant.

### Escape Artist

Win achieved despite weak scoring context, especially below-median scoring in median leagues.

### Rookie of the Week

Strongest rookie fantasy performance with started/benched status explicitly recorded.

### Free Agent of the Week

Consider genuinely unrostered/free-agent players rather than rostered players merely absent from the week's matchup.

### Waiver impact

Preserve transaction type, FAAB, production, lineup status, and result relevance when measurable.

### Historical claims

Every historical claim comes from Chronicle evidence. If historical coverage is incomplete, say so rather than treating available coverage as truly all-time.

---

# WEEKLY NEWSPAPER CONTRACTS

## 18. The Ballad Crier

Editorial identity: medical / hospital-rounds framing.

### Weekly departments

- Lead / weekly diagnosis
- Week Cardiogram / scoreboard
- Final Monitor
- Weekly Rounds / lineup autopsy
- Official Standings
- Rankings Wire
- Rounds Report
- Position Leaders
- Waiver Star
- Ward Report
- Record Watch
- Next Card

### Lead material

Surface:

- closest finish
- largest comeback
- high score
- largest margin
- late-window/Monday reversal
- meaningful health-related swing when supported

### Week Cardiogram

Include all scores, matchups, weekly median when applicable, above/below-median result, and H2H/median record impact.

### Final Monitor

Compact final scorecard with winner, loser, and score.

### Weekly Rounds

First-class result-flipping start/sit analysis. Show all legal single substitutions that would have flipped a result.

### Official Standings

Official record, points, efficiency, ordering/seeding rules.

### Rankings Wire

Forward-looking data-power projection and movement, distinct from standings.

### Rounds Report

Support:

- Manager of the Week
- Bad Beat
- Escape Artist
- Benchwarmer
- Rookie of the Week
- Free Agent of the Week

### Position Leaders

Support league positions including QB/RB/WR/TE and DEF/DST when applicable. Identify started vs benched.

### Waiver Star

Player, team, transaction type, FAAB, production, result relevance.

### Ward Report

IR/reserve, Out/Doubtful/Questionable, meaningful status labels, per-team health counts, largest ward, changes since prior collection.

### Next Card

Next matchups with current standing/record and projection context.

### Preseason/draft departments

Preserve support for:

- Draft Desk
- Opening Card / Game of the Week and undercard factual material
- Crier Lean inputs, while the lean itself remains human/editorial judgment
- Keeper Heist
- Ward Report
- Full Draft Board
- ADP Draft Profile
- Value Board
- Reach Watch
- Streamers' Pact

Existing published papers are not regenerated.

---

## 19. The Stampede

Editorial identity: 9-to-5 / workweek / Dolly Parton framing.

### Weekly departments

- scoreboard and median result where applicable
- standings movement
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

This is the official recurring workload/stat-line department.

Retired names:

- `The Week's Heavy Lifting`
- `Heavy Lifting`

They must not be used in future implementation/output.

Underlying NFL stat support should include:

- rushing attempts
- rushing yards
- rushing TDs
- receiving volume
- receiving yards
- receiving TDs
- passing volume
- passing yards
- passing TDs where editorially useful

The feature highlights real-world football work/production rather than merely sorting fantasy points.

### Preseason/draft departments

Preserve support for:

- Rankings Wire / The 9 to 5 power poll
- First Shift
- Value Board
- Paper Favorite
- Stampede Board
- Draft Night / Market Report
- I Will Always Love You reach watch
- Bargain Store
- Coat of Many Colors positional power rankings
- Old Flames keeper value
- Little Engine That Could youth/rookie/value context
- Week 1 optimized forecast
- Mystery Mine Health Board
- Season Predictions
- Preseason Truth

---

## 20. The Volunteer Voice

Editorial identity: Tennessee / Rocky Top / family rivalry.

**Rocky Top Rumble has no divisions.**

No Volunteer Voice code may assume division membership.

### Weekly departments

- Lead Story / weekly aftermath
- Official Table
- weekly median and second result
- Rankings Wire
- Decision Desk / The Call That Won the Week
- league-wide MVP / Mountain MVP treatment
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

Separate from generic efficiency.

Preserve:

- winning manager
- starter
- plausible alternative
- projection relationship
- actual scoring relationship
- point swing
- victory margin
- evidence that decision materially affected the result

### MVP treatment

No divisional MVPs.

If gold-foil treatment is used, it goes to the single highest-scoring qualifying **STARTED** player league-wide.

The Editorial Desk identifies the player; card graphics are produced separately.

### Explicitly prohibited Volunteer Voice requirements

- divisions
- divisional MVPs
- Division Pulse
- division scoring averages
- division H2H records
- divisional standings

### Special league awareness

Respect Rocky Top's league-median scoring and established seeding/postseason rules.

### Preseason departments

Preserve support for:

- Rankings Wire
- First Read
- The Pack Is Tighter Than It Looks
- Rocky Top Board
- Commissioner's Warning factual inputs
- Preseason Superlatives including Lineup to Chase, Built to Last, and Upset Engine
- Preseason Scouting Report team capsules with value, projected PPG, starter ranks, core, and watch items

---

## 21. The Saturday Standard

Editorial identity: SEC college-football framing.

The SEC Dynasty league **does have East and West divisions**.

Divisions, offense, and IDP are all first-class publication structure.

### Weekly departments

- Saturday Scoreboard
- Opening Statement
- Monday Night Theft / late-window factual material
- Saturday Ledger
- East and West Division Pulse
- East and West Power Polls
- Lineup Efficiency
- Portal Film Room
- Portal Commitments
- Saturday Honors
- offensive/IDP Position Board
- Saturday Desk
- Dynasty Market Board
- Transfer Portal Dispatch
- Recruiting Desk
- recruiting/future-pick ledger
- next-week slate

### Saturday Ledger

Support high score, low score, largest margin, closest finish, Bad Beat, Escape Artist, and division edge.

### Divisions

Support:

- East/West identity
- average division scoring
- division H2H records
- divisional standings/poll context
- East MVP
- West MVP
- gold-foil designation for higher-scoring divisional MVP

Each divisional MVP is the highest-scoring **STARTED** player in that division.

Card art remains outside Editorial Desk.

### IDP

Do not collapse this league into offense-only analysis.

Support configured defensive positions, including relevant subsets of:

- LB
- DL
- DE
- DT
- DB
- CB
- NT

IDP scoring, lineup decisions, rookies, and roster strength are first-class.

### Portal Film Room

Use shared result-flipping lineup calculation.

### Portal Commitments

Player, acquiring program, FAAB, production, result relevance.

### Dynasty Market Board

Use authoritative dynasty market values when available. Label source. Do not fabricate values if unavailable.

### Transfer Portal Dispatch

Trades, waiver/free-agent movement, players/picks exchanged, timestamps.

### Recruiting Desk

Rookie draft board, offensive/IDP rookies, immediate-impact context, class totals, first IDP selection, factual class superlatives.

### Future-pick ledger

Year, round, current owner, original owner where available.

### Preseason/draft departments

Preserve support for:

- Committee Poll
- Depth Chart Wire with full-roster projected PPG split offense/defense
- East/West division power order
- First Read
- West Is Different
- Selection Committee: East favorite, West favorite, offensive standard, defensive standard, best starting unit, top recruiting class
- Divisional Board
- Transfer Portal Dispatch
- East/West Power Poll
- PI based on optimal lineup, full roster, and dynasty/recruiting context
- Recruiting Edition
- Full Recruiting Board rounds 1-3
- Recruiting Class Standings
- Recruiting Desk

---

## 22. The Hollywood Beat

Editorial identity: film/studio/box-office framing.

The prior `publication standard pending` concept is obsolete.

### Weekly departments

- Box Office
- Marquee / Official Standings
- Top Billing / First Cut lead material
- Hollywood Board
- Monday Night / Late Show
- For Your Consideration
- Cutting Room Floor
- Studio Efficiency
- Casting Call
- Production Delays
- Dailies / Backlot Reports
- This Week's Bill

### Box Office / Marquee

Final scores, winner/loser, median result where used, records, points, ordering.

### Hollywood Board

Support factual candidates for:

- Top Billing
- Scene Stealer
- Plot Twist
- Bad Beat

### Monday Night / Late Show

Support score entering final game window, players remaining, late-game scoring, projection delta when available, final result/margin.

### For Your Consideration

Support:

- Scene Stealer
- Best Supporting Act
- Manager of the Week
- Bench MVP
- Rookie of the Week
- Free Agent Watch
- position leaders

### Cutting Room Floor

Use shared result-flipping decision calculation.

### Studio Efficiency

Submitted points, optimal legal points, efficiency, unused points.

### Casting Call

Waiver/free-agent additions, FAAB, production, result relevance.

### Production Delays

Health/status plus IR/reserve and recent change where available.

### Dailies / Backlot Reports

Deterministic briefs on significant trades, roster construction, reserve problems, or meaningful league-wide changes. Not a magazine Story Desk.

### This Week's Bill

Next matchups, record context, optional Double Feature when deterministic criteria support one, Chronicle history as supporting color.

### Preseason/dynasty departments

Preserve support for:

- Opening Credits / Backlot Opens
- Top Billing / First Read
- Critics' Poll
- Hollywood Board
- Dailies
- Meet the Cast team capsules
- Development Slate
- Casting Call rookie first round
- Development Rights / future firsts
- Cutting Room Floor future-pick scarcity
- Studio Deals / major trades
- Production Delays / reserves
- This Week's Bill

Hollywood Beat does **not** receive the Magazine Story Desk.

---

## 23. Publication consistency objective

The contracts exist to make every paper reliably itself.

A themed name changes presentation, not the metric.

Examples:

```text
lineup_flip_candidates
  -> Ballad Crier: Weekly Rounds
  -> Saturday Standard: Portal Film Room
  -> Hollywood Beat: Cutting Room Floor

waiver_impact
  -> Ballad: Waiver Star
  -> Saturday: Portal Commitments
  -> Hollywood: Casting Call
```

The editors should not have to rediscover recurring departments or manually reconstruct standard calculations each week.

---

## 24. Universal game-window context

Monday-night and late-window storytelling is a universal factual capability.

Where supported, preserve enough timing/stat data to derive:

- score entering Monday/final window
- players remaining
- points scored in the window
- final score
- final margin

This supports the newspapers without requiring Story Desk logic.

The system must distinguish reconstructed context from exact preserved live snapshots.

---

## 25. Health boundary

Every publication receives:

- general player status
- Sleeper IR/reserve state

Ironbound Weekly and Unbound Weekly additionally receive deeper context when available:

- practice participation
- injury start date
- depth-chart information

Healthy roster = valid no-item result, not unavailable data.

---

# MAGAZINE EDITORIAL MODEL

## 26. Ironbound Weekly and Unbound Weekly

These are editorially driven magazines rather than fixed newspaper templates.

They receive a factual backbone so important league information cannot disappear, including:

- results/standings
- major movement
- significant transactions
- health
- Record Watch
- divisional state
- MVP/award candidates
- next matchups

But the code must not impose a fixed 20-30 page table of contents.

The editors construct each issue from the strongest stories, analysis, data, graphics, and recurring factual material.

---

## 27. Story Desk scope

The Story Candidate Engine is enabled only for:

- Ironbound Weekly
- Unbound Weekly

It is disabled for:

- Ballad Crier
- Stampede
- Volunteer Voice
- Saturday Standard
- Hollywood Beat

Use an explicit publication capability such as `story_desk: true`; do not infer this from dynasty format or generic flagship tier.

---

## 28. Story Desk philosophy

The Story Desk is generous.

A normal Tuesday should surface approximately 12-20 viable ideas when sufficient evidence exists.

It should not decide the magazine.

The human editors determine which candidates become:

- cover features
- major articles
- departments
- sidebars
- graphics
- briefs
- unused ideas

Candidates are editorial work products, not primary Chronicle truth.

They may be retained as Tuesday JSON/Markdown artifacts for audit/review, but source facts remain in Chronicle/Event Ledger.

---

## 29. Story candidate families

Initial families include:

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
- David-vs-Goliath when authoritative rankings are supplied

Extensible as new useful patterns are identified.

---

## 30. Story candidate payload

Each candidate should include:

- candidate type
- objective trigger reasons
- evidence IDs
- relevant timestamps/provenance
- historical context
- affected franchises/managers/players
- evidence strength
- optional signal score based on measurable rarity/significance
- caution about unsupported causation
- suggested editorial angles
- headline concepts
- potential graphics/tables
- estimated article depth

Possible depth classes:

- cover feature: ~4-6 pages
- major feature: ~2-4 pages
- department/analysis: ~1-2 pages
- sidebar/graphic: ~half to one page
- brief: a few paragraphs

The depth classification is an editorial planning aid, not an automatic layout rule.

---

## 31. Story signal inputs

Objective significance signals may include:

- rarity
- historical depth
- timing proximity
- number of affected leagues
- scoring/margin magnitude
- playoff relevance
- transaction cost
- signal convergence across multiple factual sources

A signal score helps prioritize review. It does not establish causation or final editorial importance.

---

## 32. Magazine voice

Ironbound and Unbound share factual infrastructure but not voice.

Ironbound headline language may draw from:

- forging
- metal
- fire
- Crown
- architecture
- pressure

Unbound may draw from:

- chains
- links
- tension
- weak links
- breaking points
- Crown

Evidence beneath the headlines remains neutral.

---

## 33. Power Rankings and WAR

Power Rankings are a **required final section** in every regular-season Ironbound Weekly and Unbound Weekly magazine.

They are produced by the existing separate rankings workflow and emailed to the editor.

Editorial Desk must not:

- duplicate that ranking workflow
- create a competing official ranking
- substitute another internal metric when the official packet is absent

The rankings are manually incorporated during magazine building.

WAR is optional external editorial enrichment unless separately automated in the future.

### Story Desk use of external inputs

When supplied, rankings/WAR may support:

- David vs Goliath
- giant-killing upset
- ranking/record divergence
- over/underperformance
- roster dependency

If official rankings are absent, Story Desk must not call a team `No. 1`, `No. 15`, etc. using a substitute ranking.

The Tuesday magazine packet should state which external editorial inputs were available.

---

# FAILURE, RETENTION, AND RECOVERY

## 34. Failure philosophy

Fail locally, preserve good facts, and make incompleteness obvious.

A failure in one league or one source must not erase successful facts from others.

---

## 35. Source freshness states

Each upstream source can be:

- `fresh`
- `stale`
- `unavailable`

`stale` means prior valid data exists but current refresh failed.

Source failure must never be interpreted as a factual transition.

Example: temporary absence of health metadata must not create Questionable -> Healthy.

---

## 36. Run manifest

Every collection run records:

- run timestamp
- source freshness
- leagues attempted
- league successes/failures
- event counts created
- duplicate/skipped counts
- warnings/errors
- materialization result
- Chronicle input revision
- Chronicle output revision when changed

---

## 37. Atomic writes

Chronicle changes are staged and validated before commit.

A crash during materialization must leave the prior valid Chronicle intact.

Retries are safe because events are idempotent.

---

## 38. Corrections

- identity mapping error -> fix registry, rebuild derived history
- genuine source fact correction -> explicit correction/superseding event where needed

Do not silently rewrite factual audit history when a correction record is appropriate.

---

## 39. Retention classes

### Permanent

- Event Ledger
- Chronicle indexes/history
- registries
- run manifests
- schema/correction metadata

### About 30 days of diagnostic data

- recent raw/reduced Sleeper snapshots
- health/status observations
- normalized collection snapshots useful for troubleshooting

### Ephemeral

- temporary caches
- staging trees
- render scratch data
- temporary downloads

The repository must not accumulate years of giant redundant raw snapshots.

---

## 40. Concurrency

All workflows that can modify `chronicle-data` share one serialized writer concurrency group.

Reads may occur concurrently. Writes may not race.

Write sequence:

```text
1. checkout main code
2. fetch latest chronicle-data
3. collect facts
4. stage changes
5. validate
6. refresh chronicle-data before commit
7. reconcile newer state if necessary
8. rematerialize from combined ledger
9. commit only if changed
10. push without force
```

If a non-fast-forward conflict appears, refetch/rebuild/retry. Never normal-force-push.

Where practical, one successful logical collection run should produce one data-branch commit.

---

## 41. Schema evolution

Every event has `schema_version`.

Prefer:

- preserving old ledger records
- teaching materializers/migrations to read older versions
- rebuilding derived indexes into the latest schema

Do not rewrite the entire ledger merely because a new schema exists.

---

## 42. Stable Chronicle revision for editorial build

Tuesday may update Chronicle during its final factual pass.

After that commit, the editorial build pins one exact Chronicle SHA for the rest of the run.

The dossier cannot change underneath itself.

---

## 43. Monthly Chronicle archive

On the **first Tuesday of every month**, the normal Tuesday Editorial Desk email to the normal weekly-report destination includes:

- the usual weekly report/files
- one validated Chronicle backup archive attachment

No separate monthly email is required.

Suggested name:

`editorial-chronicle-backup-YYYY-MM-DD.zip`

### Archive contents

Enough permanent state to restore the newsroom:

- registries
- league event ledgers
- derived history/indexes
- cross-league NFL/player events
- relevant manifests
- backup manifest

### Backup manifest

Include:

- creation timestamp
- exact `chronicle-data` SHA
- schema version(s)
- leagues included
- seasons included
- event counts
- file checksums
- validation result

### Retry behavior

A successful first-Tuesday send must not send duplicate monthly archives on a workflow retry.

If the original send failed, retry may attempt the archive again.

---

## 44. Pre-major-change safety archive

Before any major Chronicle-affecting maintenance, create and successfully email a fresh archive to the same normal weekly-report destination.

Major operations include:

- event-schema migrations
- registry restructuring
- identity-logic changes
- historical backfill/re-backfill
- bulk corrections
- storage-layout changes
- recreating `chronicle-data`
- materializer changes capable of materially rewriting derived history

Normal append-only collection does not require a pre-change archive.

Maintenance sequence:

```text
1. validate current Chronicle
2. create backup archive
3. email backup
4. confirm send succeeded
5. run major maintenance
6. validate resulting Chronicle
7. retain backup regardless of outcome
```

If backup creation or send fails, the major operation stops.

---

# TESTING AND VERIFICATION

## 45. Event correctness/idempotency tests

Test:

- deterministic event IDs
- repeated source fetches produce no duplicates
- repeated matchup final imports produce no duplicates
- repeated transaction imports produce no duplicates
- status transitions normalize correctly
- reserve transitions normalize correctly

Derived-history examples:

```text
13-1-1 + win = 14-1-1
```

and streaks extend/reset correctly.

---

## 46. Identity continuity tests

Fixtures cover:

- dynasty franchise rename
- dynasty manager change
- annual Sleeper renewal
- redraft manager returning under new team name
- manager leaving/rejoining
- ambiguous ownership fixed via registry override

Assertions:

- dynasty history follows franchise
- redraft history follows manager
- dynasty manager tenure remains separately queryable

---

## 47. Historical backfill tests

Multi-season fixtures verify:

- each matchup imports once
- drafts/transactions preserve season
- aliases persist
- playoff vs regular-season meetings remain distinct
- second backfill run is idempotent
- new current result updates all-time record
- missing history stays unknown
- historical health transitions are not fabricated
- exact historical transaction timestamps survive when source provides them
- live-observation coverage marker begins only when collector actually starts observing

---

## 48. Timing/correlation tests

Fixture example:

```text
13:05 Questionable observed
17:04 Out observed
17:08 acquisition
```

Assert:

- supported temporal order is preserved
- no exact status-change minute is invented
- no unsupported causal claim is generated

Cross-league tests show one NFL event correlating with league-specific reactions across multiple leagues.

---

## 49. Story Desk scope tests

Enabled:

- Ironbound Weekly
- Unbound Weekly

Disabled:

- Ballad Crier
- Stampede
- Volunteer Voice
- Saturday Standard
- Hollywood Beat

Common factual events may appear in every league packet while Story Desk candidates are generated only for the two magazines.

---

## 50. Newspaper contract tests

Use fixture-driven tests per publication.

Shared lineup-flip fixture must render as:

```text
Ballad Crier      -> Weekly Rounds
Saturday Standard -> Portal Film Room
Hollywood Beat    -> Cutting Room Floor
```

with one shared underlying calculation.

### Volunteer Voice regression

Assert:

- no division logic
- no divisional MVP requirement
- no Division Pulse
- league-wide MVP
- median-scoring support
- Decision Desk support

### Saturday Standard regression

Assert:

- East/West divisions
- East MVP
- West MVP
- gold-foil comparison
- IDP position leaders

### Stampede regression

Assert:

- exact feature name `What a Way to Make a Living`
- retired Heavy Lifting labels do not appear
- real NFL workload/stat inputs are present

---

## 51. Readiness tests

Verify `ready`, `ready_no_items`, and `unavailable` are semantically distinct.

Examples:

```text
health success + zero flags -> ready_no_items
health source failure       -> unavailable
health success + Q players  -> ready
```

Apply similar tests to lineup flips, waiver impact, Record Watch, and other departments.

---

## 52. Game-window reconstruction tests

Fixture: team trails entering Monday/final NFL window and wins because of remaining player.

Verify reconstruction of:

- pre-window score
- remaining players
- late-game production
- final score
- final margin

Must work without Story Desk.

---

## 53. Story Desk factual guardrail tests

Do not test subjective headline quality.

Do test:

- candidate evidence IDs exist
- historical claims match Chronicle
- rivalry records are exact
- unsupported causation is not asserted
- official ranking references appear only when official input is supplied
- WAR claims appear only when WAR exists
- missing official rankings never become fake internal `No. 1` labels
- depth/signal metadata does not alter source facts

---

## 54. Failure/recovery tests

Simulate:

- one league fails while others succeed
- transactions succeed while health fails
- stale health
- malformed event
- failed materialization
- duplicate scheduled run
- interrupted write
- non-fast-forward conflict

Assert:

- good facts survive
- failed source/league is flagged
- no false events are generated
- previous valid Chronicle stays intact
- rerun completes without duplication

---

## 55. Backup tests

Monthly archive:

- created only on first Tuesday
- attached to normal Tuesday email
- sent to normal weekly-report destination
- required Chronicle files present
- manifest SHA matches exact data-branch revision
- checksums validate
- successful retry does not duplicate archive send
- failed first send permits retry

Pre-major-change:

```text
backup succeeds -> maintenance may proceed
backup fails    -> maintenance stops
```

---

## 56. End-to-end fixture

Maintain at least one synthetic multi-season fixture containing:

- franchise rename
- manager change
- trade
- waiver claim
- injury/status event
- upset
- lineup flip
- playoff meeting
- future-pick trade
- annual renewal

Exercise:

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

## 57. CI bands

### Fast

Unit tests on every push.

### Full

Fixture + integration tests on pull requests and `main`.

### Live smoke

Read-only smoke tests against real upstream APIs on scheduled/manual workflows.

External API availability must not make normal unit/local testing fail.

---

## 58. Implementation completion standard

Editorial Desk v2 is not complete unless testing proves:

- backfill continuity into future seasons
- continuously updated all-time history
- idempotent event collection
- stable identity behavior
- accurate provenance/time semantics
- publication contract integrity
- correct Volunteer Voice no-division behavior
- correct Saturday Standard East/West behavior
- correct Stampede feature naming and NFL workload data
- Story Desk only for Ironbound/Unbound
- no fake causation
- graceful source degradation
- atomic writes
- serialized writers
- recoverable Chronicle
- first-Tuesday backup attachment
- pre-major-change backup gate
- end-to-end packet generation

---

## 59. Locked decisions

The following are locked unless explicitly changed by the editor:

- durable Chronicle history for every tracked league
- publication-disabled tracked leagues may still have Chronicle history
- historical backfill seeds the same living Chronicle used by future seasons
- all-time numbers are derived and continuously updated, not static backfill fields
- dynasty history follows franchise identity
- redraft history follows manager identity
- manager tenure remains separately available for dynasty
- `chronicle-data` stores permanent generated history
- ledger is append-only, idempotent, versioned, and auditable
- derived history is rebuildable
- live-observation coverage is explicit
- daily morning collection
- three Wednesday-Sunday pulse collections per day
- Tuesday full build
- Wednesday delta supplement
- one normalized factual spine feeds every publication
- newspaper publications use explicit issue-phase Feature Contracts
- dependencies can be required/preferred/optional
- readiness distinguishes valid-empty from unavailable
- game-window context is universal
- health/status + Sleeper IR/reserve is universal
- deeper health enrichment belongs to Ironbound/Unbound
- Ballad Crier retains its established departments and preseason/draft support
- Stampede's workload feature is **What a Way to Make a Living**
- Volunteer Voice has **no divisions**
- Volunteer Voice MVP is league-wide, not divisional
- Saturday Standard has **East and West divisions**
- Saturday Standard treats IDP as first-class
- Hollywood Beat has a complete established weekly contract
- only Ironbound Weekly and Unbound Weekly receive Magazine Story Desk
- Story Desk aims for a generous evidence-rich candidate pool rather than deciding the issue
- Story candidates are not source-of-truth history
- Ironbound and Unbound retain separate editorial voices
- Power Rankings are mandatory in final regular-season magazines but remain externally generated
- WAR remains optional external enrichment
- Editorial Desk never substitutes a fake official ranking
- source failures cannot become false state transitions
- Chronicle writes are staged/validated/atomic
- all Chronicle writers are serialized
- normal automation never force-pushes data branch
- approximately 30 days of diagnostics are retained
- first Tuesday of every month attaches a validated Chronicle archive to the normal Tuesday email
- major Chronicle-affecting maintenance requires a successfully sent pre-change archive
- human editors retain final authority over causation, interpretation, story choice, prose, graphics, and layout

---

## 60. Implementation boundary

This specification defines required behavior and architecture, not every future class/function name.

The implementation plan should map these requirements onto the current repository with minimal unnecessary refactoring, reuse existing working modules where sensible, and introduce new modules only where they create clear responsibility boundaries.

Implementation should likely be phased so permanent history/storage, publication contracts, and Story Desk can be verified independently while still converging on the complete system.

No code implementation begins before editor approval of this spec and completion of the implementation plan.