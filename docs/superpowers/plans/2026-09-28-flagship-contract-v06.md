# Flagship Research Contract v0.6 Implementation Plan

> Test-first implementation. Power Rankings remains the model authority; Editorial Desk assembles deterministic evidence and never redraws/recalculates model-owned outputs.

## Goal
Create one common 22-page research contract for Ironbound Weekly and Unbound Weekly, add authoritative v3 ranking/forecast inputs, and build a deterministic Roster & Market evidence module that remains useful even in quiet transaction weeks.

## Tasks
- [ ] Parse v3 ranking components, remaining-schedule strength, and weekly matchup forecast.
- [ ] Add failing contract tests for common 22-page issue manifest and standardized awards.
- [ ] Add failing tests for Roster & Market: transaction ledger, starter churn, roster architecture, health/beat context, optional Sleeper-wide market signal state.
- [ ] Implement the market evidence module and context-event reuse.
- [ ] Promote flagship contract to v0.6 and add Late-Round-inspired analytical writing rules.
- [ ] Require v3 schedule strength and full-slate forecast when a v3 handoff is supplied.
- [ ] Render the new evidence explicitly for local publishing AI.
- [ ] Run full regression suite and merge only when green.

## Boundaries
- Rankings/movement/component scores/schedule strength/matchup simulations: Ironbound_power_ranks.
- Usage/NFL stats/league transactions/roster state: Editorial Desk.
- Beat/news collection/dedupe/timeline: Ironbound-Forum-Feed-Poster.
- Divisional MVP Card Shop remains separate.
- Sleeper-wide roster/start percentages are optional provider data: READY / EXPERIMENTAL / UNAVAILABLE. Missing values never block flagship research.
