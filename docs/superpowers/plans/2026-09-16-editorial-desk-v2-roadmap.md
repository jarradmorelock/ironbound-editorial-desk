# Editorial Desk v2 Implementation Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement these plans task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the approved Editorial Desk v2 architecture in four independently testable phases without mixing storage, identity, publication-contract, and Story Desk risks into one change set.

**Architecture:** Phase 1 establishes the orphan `chronicle-data` branch, deterministic Event Ledger, lightweight live collection, and safe serialized writes. Phase 2 adds conservative cross-season identity, historical backfill, corrections, and living materialized history. Phase 3 turns normalized facts into locked weekly/preseason newspaper packets. Phase 4 adds the Ironbound/Unbound Story Desk, Chronicle-aware Wednesday deltas, monthly/pre-change backups, retention, and final workflow integration.

**Tech Stack:** Python 3.12 in GitHub Actions, standard library dataclasses/json/pathlib/zipfile/hashlib/zoneinfo, requests, pytest, GitHub Actions, Git-backed `chronicle-data` branch.

**Spec:** `docs/superpowers/specs/2026-09-16-editorial-desk-v2-final-design.md`

## Global Constraints

- All Sleeper interaction remains read-only.
- Permanent generated history lives on an orphan `chronicle-data` branch; normal automation never force-pushes it.
- Daily/pulse Chronicle collection is lightweight and does not invoke full flagship/editorial enrichment.
- Global NFL/player status events are recorded once and correlated with league-specific reactions.
- Global health/status observation is limited to players relevant to tracked leagues, using the union of currently rostered/current-matchup player IDs and any other explicitly tracked entity IDs needed by the Event Ledger; do not create noisy status history for the entire Sleeper universe.
- Event Ledger records are append-only, deterministic, idempotent, correction-aware, and schema-versioned.
- Dynasty history follows franchise identity; redraft history follows manager identity.
- Ambiguous dynasty continuity is surfaced for manual override instead of guessed.
- Backfill seeds the same living Chronicle that future weeks continue to update.
- Tuesday deep flagship collection, when the upstream data exists, also normalizes `PRACTICE_STATUS_CHANGE` and configured materially significant `PROJECTION_CHANGE` events with the same timestamp/provenance safeguards as other events.
- Materialization recognizes genuinely new league/scoring records and can emit deterministic `RECORD_SET` events keyed to the underlying result/evidence; reruns cannot duplicate them.
- Volunteer Voice has no divisions; Saturday Standard has East/West divisions and first-class IDP.
- The Stampede feature name is exactly `What a Way to Make a Living`; retired Heavy Lifting labels must not reappear.
- Only Ironbound Weekly and Unbound Weekly have `story_desk: true`.
- Official magazine Power Rankings stay external; Editorial Desk must not manufacture substitutes.
- Every newspaper feature reports `ready`, `ready_no_items`, or `unavailable`.
- Source failure cannot create false state transitions.
- The first Tuesday of each month attaches a validated Chronicle archive to the normal Tuesday email.
- Initial construction/backfill of an empty Chronicle does not require a pre-change archive because no prior Chronicle exists to preserve; once durable history exists, re-backfill or other major Chronicle-affecting maintenance requires a successfully created, validated, and SMTP-accepted pre-change archive.
- Existing published PDFs are not regenerated.

---

## Execution order

1. `docs/superpowers/plans/2026-09-16-chronicle-foundation.md`
2. `docs/superpowers/plans/2026-09-16-chronicle-backfill-identity.md`
3. `docs/superpowers/plans/2026-09-16-publication-feature-contracts-rev2.md`
4. `docs/superpowers/plans/2026-09-16-story-desk-workflows-backups.md`

Do not start a later phase until the prior phase's full test suite is green and its reviewer gate is satisfied.

## Mandatory cross-phase implementation checks

These checks are part of the plans even where the implementation naturally spans two phases:

- [ ] Phase 1 pulse collector first gathers current roster/current-matchup relevance across configured leagues, then compares the global Sleeper player feed only for the relevant player-ID union before writing cross-league status transitions.
- [ ] Phase 2 materializer includes deterministic record detection and `RECORD_SET` event generation, followed by one rematerialization pass so the ledger and record indexes agree.
- [ ] Phase 4 Tuesday deep-collection integration compares prior observed flagship practice/projection state to current data and appends `PRACTICE_STATUS_CHANGE` and threshold-qualified `PROJECTION_CHANGE` events when those sources are available.
- [ ] Practice/projection source failure creates freshness degradation only and never a false transition.
- [ ] Projection-change thresholds/configuration are explicit and tested; a missing/disabled threshold means no `PROJECTION_CHANGE` event, not an arbitrary default editorial claim.
- [ ] Cross-league player event IDs remain global while league reaction events retain their own league keys and evidence links.
- [ ] Initial bootstrap is exempt from the pre-change backup gate only while no durable Chronicle history exists; every later destructive/rebuilding mode is gated.

## Cross-phase acceptance gates

- [ ] Phase 1 proves semantic deterministic event IDs, relevant-player global status deduplication, lightweight source-call budget, idempotent atomic writes, source freshness, and serialized data-branch writes.
- [ ] Phase 2 proves renewal-chain backfill, conservative stable identity, alias/manager-tenure preservation, correction handling, record-event generation, coverage boundaries, and continuously updated all-time history.
- [ ] Phase 3 proves locked weekly and preseason newspaper contracts, exact thematic mappings, readiness/dependency semantics, Decision Desk separation, game-window reconstruction, IDP, and Stampede workload data.
- [ ] Phase 4 proves every approved Story Desk candidate family and scope guardrail, practice/projection event capture, Event Ledger-driven Wednesday deltas, monthly archive attachment, pre-change backup gating, 30-day diagnostic retention, and end-to-end integration.
- [ ] Final repository-wide `python -m pytest -q` passes.
- [ ] Final scheduled/manual workflow smoke run is read-only against Sleeper and writes only Chronicle/editorial repository state.
