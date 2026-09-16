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
- Event Ledger records are append-only, deterministic, idempotent, correction-aware, and schema-versioned.
- Dynasty history follows franchise identity; redraft history follows manager identity.
- Ambiguous dynasty continuity is surfaced for manual override instead of guessed.
- Backfill seeds the same living Chronicle that future weeks continue to update.
- Volunteer Voice has no divisions; Saturday Standard has East/West divisions and first-class IDP.
- The Stampede feature name is exactly `What a Way to Make a Living`; retired Heavy Lifting labels must not reappear.
- Only Ironbound Weekly and Unbound Weekly have `story_desk: true`.
- Official magazine Power Rankings stay external; Editorial Desk must not manufacture substitutes.
- Every newspaper feature reports `ready`, `ready_no_items`, or `unavailable`.
- Source failure cannot create false state transitions.
- The first Tuesday of each month attaches a validated Chronicle archive to the normal Tuesday email.
- Major Chronicle-affecting maintenance requires a successfully created, validated, and SMTP-accepted pre-change archive.
- Existing published PDFs are not regenerated.

---

## Execution order

1. `docs/superpowers/plans/2026-09-16-chronicle-foundation.md`
2. `docs/superpowers/plans/2026-09-16-chronicle-backfill-identity.md`
3. `docs/superpowers/plans/2026-09-16-publication-feature-contracts-rev2.md`
4. `docs/superpowers/plans/2026-09-16-story-desk-workflows-backups.md`

Do not start a later phase until the prior phase's full test suite is green and its reviewer gate is satisfied.

## Cross-phase acceptance gates

- [ ] Phase 1 proves semantic deterministic event IDs, global status deduplication, lightweight source-call budget, idempotent atomic writes, source freshness, and serialized data-branch writes.
- [ ] Phase 2 proves renewal-chain backfill, conservative stable identity, alias/manager-tenure preservation, correction handling, coverage boundaries, and continuously updated all-time history.
- [ ] Phase 3 proves locked weekly and preseason newspaper contracts, exact thematic mappings, readiness/dependency semantics, Decision Desk separation, game-window reconstruction, IDP, and Stampede workload data.
- [ ] Phase 4 proves every approved Story Desk candidate family and scope guardrail, Event Ledger-driven Wednesday deltas, monthly archive attachment, pre-change backup gating, 30-day diagnostic retention, and end-to-end integration.
- [ ] Final repository-wide `python -m pytest -q` passes.
- [ ] Final scheduled/manual workflow smoke run is read-only against Sleeper and writes only Chronicle/editorial repository state.
