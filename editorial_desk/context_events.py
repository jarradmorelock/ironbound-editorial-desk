"""Index collected beat evidence for reuse; never collect or reinterpret news."""
from collections import defaultdict


def build_context_events(beat_report, games):
    indices = {key: defaultdict(set) for key in ('by_player', 'by_roster', 'by_game', 'by_module')}
    events = {}
    for item in (beat_report or {}).get('items') or []:
        event_id = str(item.get('event_id') or '')
        if not event_id:
            continue
        events[event_id] = dict(item)
        rosters, names = set(), set()
        for player in item.get('league_players') or []:
            pid = player.get('sleeper_player_id')
            rid = player.get('roster_id')
            if pid:
                indices['by_player'][str(pid)].add(event_id)
            if rid is not None:
                rosters.add(str(rid))
                indices['by_roster'][str(rid)].add(event_id)
            if player.get('fantasy_team'):
                names.add(player['fantasy_team'])
        for game in games:
            game_rosters = {str(rid) for rid in game.get('roster_ids') or []}
            game_rosters.update(str(t['roster_id']) for t in game.get('teams') or [] if t.get('roster_id') is not None)
            game_names = {t.get('team') for t in game.get('teams') or []}
            if rosters & game_rosters or names & game_names:
                indices['by_game'][str(game.get('matchup_id'))].add(event_id)
                for module in ('LEAD_FEATURE', 'GAME_REPORTS', 'SECONDARY_FEATURE'):
                    indices['by_module'][module].add(event_id)
        lanes = item.get('editorial_lanes') or {}
        if lanes.get('health_context'):
            indices['by_module']['ROSTER_HEALTH'].add(event_id)
        if lanes.get('usage_context'):
            indices['by_module']['USAGE_DESK'].add(event_id)
        if lanes.get('preview_context') or lanes.get('health_context'):
            for module in ('FULL_SLATE', 'PRESSURE_POINTS'):
                indices['by_module'][module].add(event_id)
        if any(lanes.get(key) for key in ('health_context', 'usage_context', 'since_we_last_printed')):
            indices['by_module']['MARKET_DESK'].add(event_id)
    return {
        'policy': 'Reuse attributed evidence across relevant stories; chronology alone does not establish causation.',
        'items': [events[key] for key in sorted(events)],
        **{kind: {key: sorted(ids) for key, ids in sorted(index.items())} for kind, index in indices.items()},
    }
