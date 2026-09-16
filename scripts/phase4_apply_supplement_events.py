from pathlib import Path

path = Path("editorial_desk/supplement.py")
text = path.read_text(encoding="utf-8")

import_anchor = "from typing import Any, Callable\n"
if "from .chronicle_queries import ChronicleQueries" not in text:
    text = text.replace(
        import_anchor,
        import_anchor + "\nfrom .chronicle_queries import ChronicleQueries\n",
        1,
    )

old_signature = '''def generate_supplements(\n    baseline_root: Path,\n    current_root: Path,\n    output_root: Path,\n    week: int,\n) -> list[Path]:\n'''
new_signature = '''def generate_supplements(\n    baseline_root: Path,\n    current_root: Path,\n    output_root: Path,\n    week: int,\n    chronicle_root: Path | None = None,\n    baseline_time: str | None = None,\n) -> list[Path]:\n'''
if old_signature in text:
    text = text.replace(old_signature, new_signature, 1)
elif "chronicle_root: Path | None = None" not in text:
    raise SystemExit("generate_supplements signature anchor missing")

old_lines = '''        baseline = _read_json(baseline_path)\n        current = _read_json(current_path)\n        lines = _supplement_lines(baseline, current)\n        if not lines:\n'''
new_lines = '''        baseline = _read_json(baseline_path)\n        current = _read_json(current_path)\n        lines = _supplement_lines(baseline, current)\n        if chronicle_root is not None:\n            since = baseline_time or baseline.get("information_current_through")\n            if since:\n                league_key = relative.parent.name\n                events = ChronicleQueries(Path(chronicle_root)).recent_events(\n                    league_key, str(since)\n                )\n                season = str(current.get("season") or "")\n                events = [\n                    event\n                    for event in events\n                    if (event.get("week") is None or int(event.get("week")) == int(week))\n                    and (not season or str(event.get("season") or "") == season)\n                ]\n                lines.extend(_ledger_event_lines(events))\n        if not lines:\n'''
if old_lines in text:
    text = text.replace(old_lines, new_lines, 1)
elif "lines.extend(_ledger_event_lines(events))" not in text:
    raise SystemExit("supplement line-generation anchor missing")

helper_anchor = '''def _read_json(path: Path) -> dict[str, Any]:\n    return json.loads(path.read_text(encoding="utf-8"))\n'''
helpers = '''def _ledger_event_lines(events: list[dict[str, Any]]) -> list[str]:\n    if not events:\n        return []\n    lines = ["## Event Ledger Updates", ""]\n    for event in sorted(\n        events,\n        key=lambda row: (str(row.get("observed_at") or ""), str(row.get("event_id") or "")),\n    ):\n        event_type = str(event.get("event_type") or "EVENT").replace("_", " ")\n        details = [_event_time_text(event)]\n        entities = _event_entities_text(event.get("entities") or {})\n        if entities:\n            details.append(entities)\n        transition = _event_transition_text(event.get("before"), event.get("after"))\n        if transition:\n            details.append(transition)\n        source_ref = str(event.get("source_ref") or "").strip()\n        source = str(event.get("source") or "").strip()\n        if source_ref or source:\n            source_text = source_ref or source\n            if source_ref and source:\n                source_text += f" ({source})"\n            details.append(f"source {source_text}")\n        event_id = str(event.get("event_id") or "").strip()\n        if event_id:\n            details.append(f"event {event_id}")\n        lines.append(f"- {event_type} — " + "; ".join(part for part in details if part))\n    lines.append("")\n    return lines\n\n\ndef _event_time_text(event: dict[str, Any]) -> str:\n    before = event.get("observed_before")\n    after = event.get("observed_after")\n    occurred = event.get("occurred_at")\n    if before and after:\n        return f"observed between {before} and {after}"\n    if occurred:\n        return f"occurred at {occurred}"\n    observed = event.get("observed_at")\n    return f"observed at {observed}" if observed else "observation time unavailable"\n\n\ndef _event_entities_text(entities: dict[str, Any]) -> str:\n    pairs = []\n    for key in sorted(entities):\n        value = entities.get(key)\n        if value in (None, "", [], {}):\n            continue\n        if isinstance(value, (dict, list, tuple)):\n            rendered = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))\n        else:\n            rendered = str(value)\n        pairs.append(f"{key}={rendered}")\n    return ", ".join(pairs)\n\n\ndef _event_transition_text(before: Any, after: Any) -> str:\n    if not isinstance(before, dict) and not isinstance(after, dict):\n        return ""\n    before = before if isinstance(before, dict) else {}\n    after = after if isinstance(after, dict) else {}\n    keys = sorted(set(before) | set(after))\n    changes = []\n    for key in keys:\n        old = before.get(key)\n        new = after.get(key)\n        if old == new:\n            continue\n        changes.append(f"{key}={old} → {key}={new}")\n    return ", ".join(changes)\n\n\n'''
if "def _ledger_event_lines(" not in text:
    if helper_anchor not in text:
        raise SystemExit("read-json helper anchor missing")
    text = text.replace(helper_anchor, helpers + helper_anchor, 1)

path.write_text(text, encoding="utf-8")
