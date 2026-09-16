from __future__ import annotations

from .chronicle_backfill import MaterializeRunResult
from .chronicle_identity import IdentityError
from .chronicle_materialize import materialize_league


def run_materialize_partial(store) -> MaterializeRunResult:
    """Materialize every safely mapped league without blocking on identity gaps.

    Scheduled editorial delivery uses this mode so a cold or partially backfilled
    Chronicle can still preserve new ledger facts and publish weekly packets. A
    strict manual materialization remains available for identity repair work.
    """
    registry = store.read_identity_registry()
    backfill_coverage = store.read_backfill_coverage()
    failed: list[str] = []
    unresolved: list[object] = []
    record_added = 0
    league_keys = tuple(sorted(set(store.league_keys()) | set(registry.league_keys())))

    for league_key in league_keys:
        ambiguities = registry.unresolved_for_league(league_key)
        if ambiguities:
            failed.append(league_key)
            unresolved.extend(ambiguities)
            continue

        events = store.read_all_league_events(league_key)
        if not events:
            continue
        try:
            history = materialize_league(
                events,
                registry,
                coverage_warnings=(
                    (backfill_coverage.get(league_key) or {}).get("warnings") or ()
                ),
            )
        except IdentityError:
            # The Event Ledger remains authoritative and untouched. Once backfill
            # or a commissioner override supplies the mapping, a later rebuild can
            # materialize the exact same events into all-time history.
            failed.append(league_key)
            continue

        record_result = store.append_events(history.record_events)
        record_added += record_result.added
        store.write_materialized_history(history)

    return MaterializeRunResult(
        failed_leagues=tuple(sorted(set(failed))),
        unresolved_ambiguities=tuple(unresolved),
        record_events_added=record_added,
    )
