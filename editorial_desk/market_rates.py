"""Optional adapter for supplied, source-attributed Sleeper platform percentages.

No undocumented endpoint is a production dependency. A separately verified
provider can deposit this file; failures are always nonblocking.
"""
from datetime import datetime, timezone
import json
import math
from pathlib import Path


def timestamp(value):
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamp must include timezone')
    return parsed


def load_market_rates(path: Path | None, *, as_of: str | None = None) -> dict:
    unavailable = {'status': 'UNAVAILABLE', 'required': False, 'players': {}, 'scope': 'Sleeper-wide'}
    if path is None:
        return unavailable
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        if data.get('scope') != 'Sleeper-wide' or not str(data.get('source_url', '')).startswith('https://'):
            raise ValueError('Platform scope and source URL are required')
        observed = timestamp(data['observed_at'])
        cutoff = timestamp(as_of) if as_of else datetime.now(timezone.utc)
        age = (cutoff - observed).total_seconds()
        if not 0 <= age <= 7 * 86400:
            raise ValueError('Rates must be observed within seven days before the issue cutoff')
        rows = data['players']
        if not isinstance(rows, dict) or not rows:
            raise ValueError('Player rates are missing')
        normalized = {}
        for pid, row in rows.items():
            values = {}
            for field in ('roster_percent', 'start_percent'):
                value = row.get(field)
                if value is None:
                    continue
                if isinstance(value, bool) or not math.isfinite(float(value)) or not 0 <= float(value) <= 100:
                    raise ValueError('Rates must be finite percentages from 0 to 100')
                values[field] = float(value)
            if not values:
                raise ValueError('Each player needs a roster or start percentage')
            normalized[str(pid)] = values
        return {**unavailable, 'status': 'EXPERIMENTAL', 'players': normalized,
                'observed_at': data['observed_at'], 'source_url': data['source_url'],
                'note': 'Optional supplied platform data; endpoint stability is not guaranteed.'}
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        return {**unavailable, 'note': str(exc)}
