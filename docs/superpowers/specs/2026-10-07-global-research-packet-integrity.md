# Global Research Packet Integrity Design

## Purpose

Make every weekly research packet use complete Sleeper player fantasy-score history, deliver all packet files together by email, preserve usable power rankings when the separate Saturday ranking publisher has no current handoff, and carry the existing Starter Offense / IDP Board work into the same release.

The feature is complete when every configured league receives the same history and packaging behavior, cumulative player boards use Sleeper's finalized week scores with week-specific roster ownership, absent rankings are clearly carried forward from a saved issue, and the email contains one ZIP with the generated research files.

## Current behavior and problem

The weekly Chronicle collector requests Sleeper matchup data for the selected week and writes `PLAYER_FANTASY_WEEK_FINAL` events for that week when matchups are finalized. Season player boards read those events across prior weeks and merge the current week's live snapshot. If earlier weeks were never finalized into Chronicle, the board correctly reports missing history even though Sleeper's week-specific matchup endpoints still expose those scores.

The weekly workflow uploads the complete `output/primary/` directory as a GitHub artifact. The emailer instead creates per-league reading-packet Markdown attachments and separate publication-asset attachments, leaving the rest of each generated packet out of the email.

External official rankings are loaded from an optional handoff file. When no Saturday-publisher handoff exists, the editorial packet has no durable ranking source to reuse from the prior completed issue.

The existing local edits add a required Starter Offense / IDP Board to Saturday Standard: starter offensive and IDP scoring totals and the leading scorer in each group, using Sleeper matchup points. This behavior and its tests are part of the intended release.

## Design

### 1. Backfill finalized player-week scores for every league

Use Sleeper as the authoritative source for fantasy points. For each production run and every configured league, collect each completed week from Week 1 through the requested report week using the existing `matchups(league_id, week)` endpoint. Normalize each `players_points` entry into a `PLAYER_FANTASY_WEEK_FINAL` record keyed by league, season, week, roster ID, and player ID. Use the roster ID in that week's matchup response so trades and roster moves do not assign historical points to the player's current team. Preserve a legitimate zero score when Sleeper explicitly supplies it; never fill a missing player score with zero.

The catch-up must be idempotent. Re-running unchanged Sleeper data must not create duplicate records. If Sleeper later corrects a stored final, record a correction linked to the original event and have history queries return the latest valid value while retaining both source and collection-time provenance. The common collection path must apply to every configured league and every publication profile; the cumulative player and rookie boards must consume this shared history rather than league-specific exceptions.

In preview mode, retrieve the same completed-week rows for packet construction without writing Chronicle state. Production mode both uses the rows and persists them to Chronicle. A preview must remain read-only. A week is considered final only under the workflow's existing completed-week gate.

Before a cumulative board is labeled complete, validate score-row coverage for every expected player-week/roster assignment available from Sleeper. Missing or malformed rows remain explicit gaps. Do not derive fantasy points from NFL statistics or silently treat absent points as zero. Where Sleeper omits a score row, the packet names the affected week and reports the board as incomplete.

### 2. Email one ZIP of the complete research output

After the workflow creates the weekly outputs, build one deterministic archive from every generated file under `output/primary/`, preserving relative paths. This includes each league's Markdown and JSON packets, images and supporting files. Attach that archive as the single research-output attachment. Keep the email body concise and identify the season, week, included leagues, and archive filename. Do not attach per-league Markdown or publication images separately.

The ZIP is distinct from the GitHub Actions artifact: the artifact remains available for download and recovery. Existing Chronicle backup and receipt behavior remains governed by its current explicit workflow conditions and is not silently folded into the research ZIP.

### 3. Preserve and carry forward weekly ranking snapshots

Save each completed issue's resolved ranking snapshot durably in Chronicle history, keyed by league and season/week, with franchise identity, rank, ranking source, source week, and collection/publication provenance. If the current external ranking handoff exists, use it and record it as the current snapshot. If it is absent, select the most recent prior snapshot for that publication, carry its ordering forward, and mark it plainly as carried forward from its source week. Do not describe a carried ranking as a fresh Saturday update or imply new movement; movement is computed only when a new ranking source is available and can be compared with the saved prior snapshot.

If no prior ranking snapshot exists, preserve the existing missing-ranking readiness state. Never infer ranks from Discord text or a different league's ranking file.

### 4. Include the Starter Offense / IDP Board

Carry forward the existing local changes that register `offense_defense_splits` as a required Saturday Standard feature and add starter offensive points, starter IDP points, and the leading starter for each group from Sleeper matchups. Preserve the existing roster-composition counts. Keep the feature's current test coverage and add or adjust tests only if integration with the current main branch requires it.

## Data and delivery safeguards

- Historical fantasy points come from Sleeper's player-point maps using the league's configured scoring; no alternate scoring reconstruction is introduced.
- All joins use stable league, season, week, roster, and player identifiers; display names are not keys.
- One league's missing history or rankings must not be filled with another league's data.
- Preview performs no Chronicle writes. Production history writes are repeatable and auditable.
- A packet reports incomplete history when the fetched data cannot satisfy coverage checks.
- The weekly research ZIP contains every generated research output file exactly once, with relative paths retained.
- Existing user work in the original `fix/publication-reading-packets` checkout remains untouched; its four-file Starter Offense / IDP Board diff is explicitly included in the isolated implementation branch.

## Verification criteria

1. A multi-week fixture proves that each player's Sleeper score is stored against the roster that owned the player that week, including a traded player and an explicit zero score.
2. Repeating a completed-week collection does not duplicate events; a changed finalized score is recorded as a correction and queries return the corrected value.
3. A missing score row produces an incomplete-history status naming the missing week; it is not rendered as zero or a complete season total.
4. Every configured league is backfilled, and preview builds the same player history without changing Chronicle state.
5. Ranking tests cover a new external snapshot, a carried-forward prior snapshot with provenance and no claimed movement, and the no-history case.
6. Email tests inspect the archive and verify all generated league files and assets are included once; the message contains only the ZIP as its research-output attachment.
7. Saturday Standard tests verify the required Starter Offense / IDP Board remains present and contains starter offense/IDP totals and leaders.
8. The full repository test suite and workflow validation pass before the change is considered ready.

## Scope boundary

This work does not change the separate Saturday ranking publisher, alter league scoring, derive fantasy points from NFL statistics, change the editorial format of individual packet files, or merge any pull request. It changes the editorial desk's collection, persistence, fallback, and delivery behavior only.
