# Ironbound NFL Enrichment Design

## Purpose

Add a second, deeper NFL evidence layer for **Ironbound Weekly** and **Unbound Weekly** without increasing the scope or runtime burden of the other publication dossiers.

The editorial desk remains a read-only research pipeline. It does not write finished magazine copy, generate trading-card images, or post to Discord.

## Publication split

All publication-enabled leagues continue to receive the existing Sleeper-driven matchup, standings, lineup, transaction, projection, and weekly-award evidence.

Only leagues configured with `tier: flagship` receive the deeper NFL usage and game-script layer described below. Today those are Ironbound Weekly and Unbound Weekly.

## Weekly editorial features

The research dossier must expose these deterministic weekly features for commissioner review:

- **Divisional MVP nominations:** one player per named division, selected only from players who were actually in a submitted starting lineup. Bench and taxi players are never eligible. The highest-scoring divisional nominee is flagged `gold_foil: true`. The editorial desk does not generate card images.
- **Top scorers by position:** magazine evidence independent from trading-card nominations.
- **Benchwarmer of the Week:** highest-scoring player whose status for the reviewed week was BENCH.
- **Rookie of the Week:** highest-scoring rookie on a fantasy roster, with explicit weekly roster status of `STARTED`, `BENCH`, or `TAXI`.
- **Free Agent of the Week:** highest-scoring NFL player who was unrostered in the fantasy league at the end of the reviewed week, when a complete weekly NFL player-stat source is available.

## Sleeper max-points reconciliation

Sleeper fantasy-football Max PF includes taxi players. The desk's lineup-efficiency calculation must therefore evaluate every player in the weekly matchup player pool, including taxi players, when constructing the legal maximum lineup. This keeps the desk's weekly `MAX` and efficiency values aligned with Sleeper's Weekly Report.

Submitted lineup points still come only from submitted starters. Taxi status still matters for Rookie of the Week and other editorial labels; it simply does not exclude a player from Sleeper-style max-points calculation.

## Flagship NFL source layer

The shared NFL collection runs once per NFL week and is reused by both flagship leagues.

### Required open sources

- nflverse weekly player stats
- nflverse play-by-play
- nflverse game schedule
- nflverse/PFR game-level snap counts
- nflverse player-ID crosswalk so PFR snap-count IDs can be joined to GSIS/Sleeper-linked players

A missing optional NFL source must not stop the Sleeper dossier. The source status and missing evidence must be explicit.

### Optional future exact-route source

Exact weekly routes are not required for the first implementation. If a `PFF_API_KEY` is later supplied, a PFF Pro adapter is the preferred automation path because PFF exposes route/snap data through a documented API suitable for CI. The base workflow must not scrape Fantasy Life, FTN, or another website to obtain routes.

## Player usage summaries

For NFL players relevant to a flagship league, derive compact weekly evidence:

- offensive snaps and snap percentage
- carries, targets, receptions and total opportunities
- team carry share and target share
- red-zone opportunities
- inside-10 opportunities
- inside-5 opportunities
- quarter-by-quarter carries and targets
- fantasy production by quarter when play-by-play supports the league's scoring categories
- team offensive touchdown environment
- backfield teammate comparison

Sleeper remains authoritative for the final fantasy score. Reconstructed play-by-play scoring is contextual evidence and must identify itself as reconstructed. If reconstructed totals materially disagree with Sleeper, the dossier should show the source mismatch rather than silently treating the reconstruction as authoritative.

## Editorial story signals

The enrichment layer should emit evidence-first candidate flags, not prose conclusions. Each flag contains a type, player/team identifiers, supporting numbers, and a short factual explanation.

Initial signal types:

- `LATE_SURGE`: a large share of reconstructed fantasy production occurred in Q4/OT.
- `BACKFIELD_SPLIT`: two same-team RBs had near-even offensive snap shares.
- `HIGH_VALUE_TOUCH_SHIFT`: a teammate captured materially more inside-10/inside-5 work than a relevant RB despite comparable overall opportunity.
- `MISSED_WINDFALL`: an NFL offense created a high-touchdown/high-scoring environment while a relevant fantasy player captured little of the scoring or premium opportunity.
- `VOLUME_WITHOUT_RESULTS`: heavy opportunity produced a low fantasy return.
- `EFFICIENCY_SPIKE`: a large fantasy result came on unusually little opportunity.
- `COMEBACK_ENGINE`: a player produced a large share of his output in a fourth-quarter/OT comeback game script.

Signal thresholds should be conservative so the research file remains a useful shortlist rather than a dump of every player-week.

## Route participation and offseason charting

Weekly route participation is an optional enhancement, not a blocker for the in-season layer. Snap share, targets, carries, and play-by-play high-value usage cover the immediate editorial need.

Richer charting such as routes, play action, screens, RPOs, designed reads, quarterback location, formations, and related tendency data should be retained as a future source for long-form offseason analysis. Planned offseason issues are:

1. postseason wrap-up
2. rookie preview
3. preseason preview

## Output placement

The human-readable flagship dossier gains two review sections:

1. `Weekly Magazine Features`
2. `Ironbound NFL Game Intelligence`

The machine-readable dossier receives matching structured objects so later magazine-building work can select, reject, or expand candidate stories without re-collecting data.
