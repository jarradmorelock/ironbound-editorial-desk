# Flagship Research Contract v0.6 Implementation Plan

**Goal:** Make Ironbound Weekly and Unbound Weekly share one deterministic flagship research spine while consuming authoritative model outputs from Power Rankings and combining roster health, transactions, lineup churn, roster construction, and beat-news context into a reusable Roster & Market research layer.

## Constraints
- Power Rankings owns rank components, movement, remaining-schedule strength, playoff odds, weekly matchup simulations, and chart assets.
- Editorial Desk consumes those outputs and never recomputes them.
- Beat/news events are contextual evidence reused by game, health, market, and preview modules, not a standalone magazine department.
- Sleeper-wide roster/start percentages are optional/experimental until a verified provider exists; missing them must not block publication.
- Ironbound and Unbound share the same 22-page canonical module spine; display names may differ.
- NFL draft capital remains research metadata but is not a required print column.
- Divisional MVP Card Shop remains separate.

## Tasks
1. Extend external ranking handoff parser for v3 component, schedule-strength, and weekly forecast fields.
2. Add deterministic Roster & Market research from full Sleeper transaction/schedule history, starter churn, roster architecture, network add counts, current health, and beat-event timelines.
3. Add model-owned forward forecast and schedule-strength sections to flagship packet and Power Board writer inputs.
4. Add reusable context-event index across game/health/market/preview lanes.
5. Standardize shared honors and 22-page flagship spine with brand-specific display names.
6. Add analytical editorial guidance: statistics support a thesis; distinguish process/result, role/efficiency, expectation/reality, sustainability, uncertainty, and consequence.
7. Regression-test both flagship contracts and preserve existing publication behavior.
