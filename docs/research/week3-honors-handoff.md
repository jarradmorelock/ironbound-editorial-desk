# Week 3 honors research update

Suggested PR title: **Update weekly honors and deterministic manager award research**

The research packet now supplies the five-component Manager of the Week, distinct Overall/QB/RB/WR/TE started-player honors, all static franchise honors, and a deterministic rotating-manager candidate registry. It preserves Top-3 season boards, Rookie Watch Top 5, NFL stat-line enrichment, and the existing 22-page spine. No local-AI runtime, PPTX publisher, ranking calculation, ranking graphic, or workflow schedule changes are included.

## Manager selection

All managers are scored internally on a 0–1 scale: result 25%, lineup efficiency 25%, team-scoring all-play percentile 20%, entering record/consistency 15%, opponent quality 15%. Record/consistency is the equal-weight mean of prior head-to-head winning percentage and prior weekly all-play percentile. Opponent quality is `(league_size - previous_rank) / (league_size - 1)`. The authoritative handoff supplies `previous_rank`; a mismatched results/ranking week is rejected. Missing context uses a neutral component with explicit data warnings; postweek roster records and current ranks are never substituted. Ties in total score resolve by actual lineup points, efficiency, then roster ID.

Only winners can receive the automatic honor. An exceptional-loss review flag requires a loss by at most 1 point, at least 98% lineup efficiency, top-quarter weekly scoring, and a top-quarter entering-ranked opponent. It never replaces the winning manager. Magazine output contains supporting facts, not component scores.

## Frozen-projection limitation for this run

Inspected current `main` at `00b0a81` and Chronicle data at `e8e52f2` (September 29, 2026 pulse). The collector calls the Sleeper projections endpoint during research collection and stores season/week/player data, but not a pregame capture timestamp or verified freeze. Chronicle contains no frozen-projection snapshot artifact. These sources cannot establish a genuine Week 3 pregame projection.

Consequently **Iron Balls, Mad Blacksmith, Bone Head, Left on the Anvil, Goosed, Tempered, Full Forge, No Fear, and Against All Odds remain unavailable for Week 3 unless a verified pregame capture is supplied**. Left on the Anvil needs projections to rule out a single Bone Head explanation. Giant Killer can still qualify using authoritative entering ranks.

The explicit accepted snapshot field is `frozen_pregame_projections`, containing matching `season` and `week`, an identifiable `source`, timezone-aware `captured_at` and `first_kickoff_at` with capture strictly before kickoff, numeric `player_points` keyed by player ID, and frozen pregame `matchup_points` keyed by roster ID. All active roster player projections are required for the player-dependent rules. No current or postgame projection fallback is used. This change does not invent or backfill such a capture, or add a new capture scheduler.

## Other limits and conventions

- All qualified rotating candidates are returned. `selected_rotating_award` stays null; an editor chooses one or none.
- Mad Blacksmith replaces Iron Balls only for two distinct starter/alternative decisions whose combined alternative lineup is also legal. Against All Odds replaces No Fear and Giant Killer for the same upset. Bone Head suppresses Left on the Anvil. A free or $0 pickup receives `FOUND_STEEL` on Scrapheap Savior.
- “Recent” acquisition means the completed fantasy week. Completed transaction IDs are deduplicated. Prior drops and trades use the full-season Sleeper transaction history plus Chronicle evidence where available. Incomplete historical coverage is explicit.
- Reforged requires the immediately prior week's loss followed by a win and at least 40 additional team points.
- FAAB Furnace provides **MANUAL_REVIEW** evidence for positive spend with at most 1 immediate fantasy point. There is no invented substantial-spend cutoff and no automatic qualified award.
- The Spoiler remains **UNSUPPORTED** until deterministic elimination and counterfactual playoff/seeding evidence exists. Old Score Settled and Revenge of the Forge are not registry awards.
- Optional award gaps appear in the packet's availability section and validation `award_warnings`; they do not make otherwise complete core research fail. Required research and handoff checks retain their existing behavior.
- Season boards merge durable history with current-week evidence, deduplicate team/week rows, and exclude future weeks.

## Production and local delivery

The Tuesday 9:17 PM Eastern run and Wednesday 5:17 AM backup are unchanged. It is safe to let the scheduled research collection execute after the branch is merged, subject to the existing live-source checks. This does **not** certify that every external source will be available or that projection-dependent awards can be published. Their unavailable status is expected and explicit.

The user will push this local branch. No remote push, PR, or merge is performed by this task. Push the branch and open a PR to `main`; merely pushing does not update the scheduled production code.

## Validation

- Python 3.12 full suite: **393 passed** (baseline: 352).
- Focused coverage includes every supported registry rule, threshold boundaries, overlap upgrades/suppression, FLEX rearrangements and combined legal decisions, projection provenance/missing-data gates, entering `previous_rank`, team-name handoffs, exceptional losses, distinct player honors, stat-line enrichment, Top-3 history merging, and absent versus empty transaction history.
- Independent review findings were fixed and regression-tested. Whitespace checks pass. The run schedule, ranking engine, ranking PNGs, and page spine are unchanged.
