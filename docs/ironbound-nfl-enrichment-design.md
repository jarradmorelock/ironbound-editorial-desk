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
- **Rookie of the Week:** highest-scoring rookie on a fantasy roster, with explicit weekly roster status of `STARTED`, `BENCH`, or `TAXI`. Taxi rookies remain eligible for this award even though taxi points are excluded from lineup efficiency.
- **Free Agent of the Week:** highest-scoring NFL player who was unrostered in the fantasy league at the end of the reviewed week, when a complete weekly NFL player-stat source is available.

## Editorial lineup MAX policy

The desk's `MAX` and lineup-efficiency values answer a commissioner/editorial question: **what was the best legal active lineup the manager could actually have submitted?**

Taxi and reserve/IR players are therefore excluded from the candidate pool. This is intentional even if Sleeper's own Max PF accounting includes taxi production. Submitted lineup points still come only from submitted starters.

Taxi status remains meaningful elsewhere in the dossier. In particular, a rookie may win Rookie of the Week while on taxi, but his points do not improve a manager's editorial lineup MAX or efficiency score.

## Flagship NFL source layer

The shared NFL collection runs once per NFL week and is reused by both flagship leagues.

### Required open sources

- nflverse weekly player stats
- nflverse play-by-play
- nflverse game schedule
- nflverse/PFR game-level snap counts
- player identity reconciliation using GSIS IDs when available and name + NFL team + position fallback when Sleeper's current player directory lacks GSIS IDs

A missing optional NFL source must not stop the Sleeper dossier. The source status and missing evidence must be explicit.

### Dynasty Daddy WAR / League Format layer

Dynasty Daddy is a strong complementary source because it answers a different question from nflverse. nflverse describes **how usage and game script happened**; Dynasty Daddy WAR/WoRP describes **how valuable that production is relative to replacement in a specific league format**.

Useful Dynasty Daddy evidence includes:

- Wins over Replacement Player / WAR by position and player
- positional WAR tiers and replacement cliffs
- quality starts and spike-week classifications
- fantasy opportunities and points per opportunity
- historical started/rostered percentages
- Captured WAR (`cWAR`) when available to the user's Dynasty Daddy Club account; cWAR weights production by historical start confidence so bench explosions do not receive the same roster-construction credit as confidently started production
- league-infused values for comparing market price with format-specific utility
- waiver/trade-market activity where available

A direct 2026 probe of the hosted `/api/v1/league/format` endpoint confirmed that the endpoint exists but now requires a Dynasty Daddy API key. The desk must therefore treat automated WAR/cWAR ingestion as **credential-gated**. Do not scrape an authenticated Dynasty Daddy page or reuse browser cookies in GitHub Actions. If Dynasty Daddy provides an API key for the user's paid account, store it only as a repository secret and add a documented API adapter.

Until authenticated access is configured, the current open Dynasty Daddy daily player-value feed remains usable, while WAR/cWAR is a planned optional enrichment rather than a required dependency.

### Exact weekly route participation

PFF is not part of the planned pipeline because its required paid tier is not economical for this project.

Exact weekly routes are therefore optional, not a blocker. Dynasty Daddy's League Format tooling has historically exposed advanced opportunity fields including routes and target-route-share, making it the first source to investigate once authenticated API access is available. We must verify that those fields are current for the 2026 season before depending on them. The base workflow must not scrape Fantasy Life, FTN, Dynasty Daddy, or another authenticated website to obtain routes.

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
- `EFFICIENCY_SPIKE`: a skill-position player produced a large fantasy result on unusually little opportunity.
- `COMEBACK_ENGINE`: a player produced a large share of his output in a fourth-quarter/OT comeback game script.

Once authenticated Dynasty Daddy WAR/cWAR is available, additional useful candidate signals include market value versus replacement value, positional scarcity/league-breaker status, roster WAR concentration, and players whose cWAR materially differs from raw WAR because managers could not confidently capture their production in starting lineups.

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
