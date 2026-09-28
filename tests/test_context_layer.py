from editorial_desk.context_events import build_context_events


def test_one_injury_event_routes_to_all_relevant_entities_and_modules():
    event = {'event_id': 'news1', 'source_url': 'https://example.com/story',
             'tags': ['Injury'], 'editorial_lanes': {'health_context': True, 'preview_context': True},
             'league_players': [{'sleeper_player_id': 'p3', 'roster_id': 1}]}
    context = build_context_events({'items': [event, event]}, [{'matchup_id': 7, 'roster_ids': [1, 2]}])
    assert len(context['items']) == 1
    assert context['by_player']['p3'] == ['news1']
    assert context['by_roster']['1'] == ['news1']
    assert context['by_game']['7'] == ['news1']
    for module in ['ROSTER_HEALTH', 'MARKET_DESK', 'FULL_SLATE', 'PRESSURE_POINTS', 'GAME_REPORTS']:
        assert context['by_module'][module] == ['news1']
    assert context['items'][0]['source_url'] == event['source_url']
