# Editorial Desk v2 Implementation Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement these plans task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the approved Editorial Desk v2 architecture in four independently testable phases without mixing storage, identity, publication-contract, and Story Desk risks into one change set.

**Architecture:** The work is intentionally decomposed. Phase 1 establishes durable Chronicle/Event Ledger storage and safe collection. Phase 2 adds multi-season identity/backfill/materialization. Phase 3 turns normalized facts into locked newspaper feature packets. Phase 4 adds the Ironbound/Unbound Story Desk, Wednesday Event Ledger integration, monthly/pre-change backups, and final workflow orchestration.

**Tech Stack:** Python 3.12 in GitHub Actions, standard library dataclasses/json/pathlib/zipfile/hashlib, requests, pytest, GitHub Actions, Git-backed `chronicle-data` branch.

**Spec:** `docs/superpowers/specs/2026-09-16-editorial-desk-v2-final-design.md`

## Global Constraints

- All Sleeper interaction remains read-only.
- Permanent generated history lives on `chronicle-data`; normal automation never force-pushes it.
- Event Ledger records are append-only, deterministic, idempotent, and schema-versioned.
- Dynasty history follows franchise identity; redraft history follows manager identity.
- Backfill seeds the same living Chronicle that future weeks continue to update.
- Volunteer Voice has no divisions; Saturday Standard has East/West divisions and first-class IDP.
- The Stampede feature name is exactly `What a Way to Make a Living`; retired Heavy Lifting labels must not reappear.
- Only Ironbound Weekly and Unbound Weekly have `story_desk: true`.
- Official magazine Power Rankings stay external; Editorial Desk must not manufacture substitutes.
- Every newspaper feature reports `ready`, `ready_no_items`, or `unavailable`.
- Source failure cannot create false state transitions.
- The first Tuesday of each month attaches a validated Chronicle archive to the normal Tuesday email.
- Major Chronicle-affecting maintenance requires a successfully sent pre-change archive.
- Existing published PDFs are not regenerated.

---

## Execution order

1. `docs/superpowers/plans/2026-09-16-chronicle-foundation.md`
2. `docs/superpowers/plans/2026-09-16-chronicle-backfill-identity.md`
3. `docs/superpowers/plans/2026-09-16-publication-feature-contracts.md`
4. `docs/superpowers/plans/2026-09-16-story-desk-workflows-backups.md`

Do not start a later phase until the prior phase's full test suite is green and its reviewer gate is satisfied.

## Cross-phase acceptance gates

- [ ] Phase 1 proves deterministic event IDs, idempotent writes, atomic staging, source freshness, and a serialized data-branch workflow.
- [ ] Phase 2 proves renewal-chain backfill, stable identity, alias preservation, live-coverage boundaries, and continuously updated all-time materialized history.
- [ ] Phase 3 proves every weekly newspaper contract, exact thematic mappings, readiness semantics, game-window reconstruction, and regression constraints.
- [ ] Phase 4 proves Story Desk scope/guardrails, Event Ledger-driven Wednesday deltas, monthly archive attachment, pre-change backup gating, and end-to-end integration.
- [ ] Final repository-wide `python -m pytest -q` passes.
- [ ] Final scheduled/manual workflow smoke run is read-only against Sleeper and writes only Chronicle/editorial repository state.
