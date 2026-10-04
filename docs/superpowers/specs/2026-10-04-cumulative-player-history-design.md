# Cumulative Player and Rookie History Contract

## Status

Approved design; implementation pending written-spec review.

## Problem

The Week 3 publication-complete packet has complete team and matchup coverage, but its cumulative player and rookie boards are blocked because fifteen current-roster players have no player-week row for an eligible week. The current resolver treats an absent player-score row as missing evidence. The board builder then correctly refuses to present a complete total rather than silently treating the gap as zero. The rookie season board reuses the same completeness result, so it is blocked by the shared history gap rather than by a separate rookie calculation failure.

The existing transaction exemption is insufficient as the authoritative membership model. It depends on the current roster snapshot and a particular historical transaction shape, while the required question is whether the player was rostered, not yet acquired, or otherwise eligible for each completed week.

## Goals

1. Produce deterministic season-to-date player totals through the issue week.
2. Preserve a traceable fact for every player-week that contributes to, or is explicitly excluded from, a total.
3. Distinguish an observed score, an evidenced zero, a player not yet acquired, and an unresolved gap.
4. Make rookie season leaders use the same score ledger while retaining independent draft-status and pick provenance.
5. Keep the local manuscript builder fully offline: no builder-stage Sleeper, Chronicle, NFL, or web lookups.
6. Make `PUBLICATION READY` mean that the cumulative rows can be reproduced from packet evidence alone.

## Non-goals

- Do not infer a zero from a missing row.
- Do not relax readiness to allow unknown player-weeks.
- Do not change fantasy scoring rules or editorial ranking choices.
- Do not merge PR #32 as part of this work.

## Canonical player-week fact

The canonical evidence layer will expose one normalized fact per `(league, season, week, roster, player)` when the source can establish roster membership or an explicit exclusion. The fact will retain the existing evidence ID convention and add explicit state:

```json
{
  "evidence_id": "player-week:2026:2:11:11256",
  "league_key": "ironbound_sixteen",
  "season": "2026",
  "week": 2,
  "roster_id": 11,
  "player_id": "11256",
  "points": 0.0,
  "score_status": "CERTIFIED_ZERO",
  "membership_status": "ROSTERED",
  "authority": "sleeper_matchups",
  "source_refs": ["..."],
  "reason": "Player appears in the finalized weekly roster and no points entry is present."
}
```

Allowed score states are `OBSERVED`, `CERTIFIED_ZERO`, and `UNKNOWN`. Allowed membership states are `ROSTERED`, `NOT_YET_ACQUIRED`, `NOT_ROSTERED`, and `UNKNOWN`. `UNKNOWN` is never eligible for a cumulative total.

The collector and Chronicle materializer must preserve player IDs from finalized weekly matchup rosters even when `players_points` omits a zero scorer. If a weekly roster is not available, a transaction alone may establish `NOT_YET_ACQUIRED` only when its timing and destination roster are unambiguous; otherwise the fact remains unresolved.

## Resolution and aggregation

The canonical resolver will:

1. Prefer exact finalized Sleeper player-week rows.
2. Use Chronicle finalized player-week events to fill absent Sleeper values and to corroborate exact values.
3. Emit `CERTIFIED_ZERO` only when the finalized weekly roster explicitly includes the player and the authoritative source establishes no points.
4. Apply as-of-week roster membership and transaction timing before deciding whether a missing row is excluded or blocking.
5. Mark contradictory authoritative values `MANUAL_VERIFY` and block dependent boards.

The player board computes:

```text
season_total(player) = sum(points for eligible weeks where score_status is OBSERVED or CERTIFIED_ZERO)
```

`NOT_YET_ACQUIRED` and `NOT_ROSTERED` weeks are excluded from the sum. `UNKNOWN`, `MANUAL_VERIFY`, missing eligible weeks, or ambiguous membership keep the board unavailable. A player may change fantasy rosters; the total remains keyed by NFL player and the displayed team label comes from the current issue snapshot, while each contributing roster and source remains in evidence.

The rookie board consumes the same resolved totals and independently requires verified rookie status plus draft provenance. A missing rookie draft field cannot be repaired by a score row.

## Readiness contract

`PLAYER_SEASON_BOARD_NOT_READY` and `ROOKIE_SEASON_BOARD_NOT_READY` remain blocking codes when unresolved eligible player-weeks exist. The packet will expose coverage counts and unresolved fact identifiers so the gap report names the evidence problem directly. A board marked `READY` must contain the requested positional rows, per-row through-week coverage, and evidence references sufficient for an offline builder to reproduce the totals.

## Historical backfill

Before the Week 3 rerun, backfill finalized player-week facts for Weeks 1–3 from the retained Sleeper historical matchup inputs and Chronicle where available. The backfill must be idempotent and must not rewrite live league state. It should record explicit zero facts and as-of acquisition exclusions, then be consumed by the preview workflow through the normal canonical evidence path.

## Validation

Add tests for:

- an omitted `players_points` entry with explicit weekly roster membership becoming `CERTIFIED_ZERO`;
- a player acquired after a completed week being `NOT_YET_ACQUIRED` rather than a blocker;
- an absent roster-membership row remaining `UNKNOWN` and blocking publication;
- conflicting Sleeper and Chronicle scores blocking publication;
- cumulative totals across roster changes;
- rookie totals using the shared score ledger but independent draft provenance;
- packet readiness and offline rendering from the resulting evidence only.

The acceptance check is the Week 3 preview packet: both season boards must be `READY`, every cumulative row must have complete evidence through Week 3, and the local manuscript builder must reproduce the corresponding magazine facts without additional research.
