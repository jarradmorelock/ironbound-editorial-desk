# Flagship Research Contract v0.6 Implementation Plan

> **Execution:** Use test-driven development. Keep source systems authoritative and make Editorial Desk an assembler.

**Goal:** Make Ironbound Weekly and Unbound Weekly consume the same flagship research contract, with Power Rankings v3 inputs, a deterministic Roster & Market desk, reusable beat/news context, and a shared 22-page editorial spine.

**Architecture:** Power Rankings remains authoritative for ranking components, movement, schedule strength, playoff forecast, weekly simulated lines/totals, and rendered ranking assets. Forum Feed Poster remains authoritative for accepted Draft Sharks/RotoWire news. Editorial Desk maps and combines those sources with Sleeper, Chronicle, nflverse, and league history without recalculating upstream models.

## Task 1: Consume Power Rankings handoff v3
- Extend ExternalEditorialInputs with ranking components, remaining-schedule strength, and weekly matchup forecast.
- Preserve legacy schema v2 compatibility.
- Expose components to Power Board prose.
- Expose authoritative schedule-strength and Full Slate blocks.
- Validate v3 fields when a v3 handoff is supplied.

## Task 2: Build deterministic Roster & Market research
- Aggregate league transactions, repeated asset movement, roster architecture, and lineup churn.
- Map beat/news events into health, transaction, lineup-decision, usage, and preview context.
- Preserve injury/news timelines and source attribution.
- Add cross-league Ironbound Network add/drop counts from all collected league snapshots.
- Represent Sleeper-wide ownership/start-rate enrichment as an explicit optional provider state until a stable source is verified.

## Task 3: Lock the shared flagship spine
- Encode the same canonical 22-page module order for Ironbound and Unbound.
- Allow publication-specific display names only.
- Standardize Honors/Rookie Watch and running efficiency requirements.
- Keep Divisional MVP/Card Shop outside the magazine contract.

## Task 4: Encode analyst-style writing guidance
- Stats support a thesis rather than reproduce a chart in prose.
- Distinguish result from process, role from efficiency, and expectation from outcome.
- Surface uncertainty and actionable consequence.
- Allow the same verified context event to inform multiple departments.

## Verification
- Add focused tests before implementation.
- Run the full Editorial Desk regression suite.
- Merge only after CI is green.
