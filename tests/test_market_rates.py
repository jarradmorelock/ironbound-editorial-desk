import json
from editorial_desk.market_rates import load_market_rates


def test_missing_and_invalid_optional_rates_never_raise(tmp_path):
    assert load_market_rates(None)['status'] == 'UNAVAILABLE'
    path = tmp_path / 'rates.json'
    path.write_text('{bad')
    assert load_market_rates(path)['required'] is False
    path.write_text(json.dumps({'scope': 'Ironbound Network', 'players': {}}))
    assert load_market_rates(path)['status'] == 'UNAVAILABLE'


def test_experimental_rates_require_provenance_valid_percentages_and_freshness(tmp_path):
    path = tmp_path / 'rates.json'
    payload = {'scope': 'Sleeper-wide', 'source_url': 'https://sleeper.com/',
               'observed_at': '2026-09-20T00:00:00+00:00',
               'players': {'p3': {'roster_percent': 99, 'start_percent': 25}}}
    path.write_text(json.dumps(payload))
    result = load_market_rates(path, as_of='2026-09-21T00:00:00+00:00')
    assert result['status'] == 'EXPERIMENTAL'
    assert result['players']['p3']['start_percent'] == 25
    assert result['required'] is False
    assert load_market_rates(path, as_of='2026-09-28T00:00:00+00:00')['status'] == 'UNAVAILABLE'
    payload['players']['p3']['start_percent'] = 101
    path.write_text(json.dumps(payload))
    assert load_market_rates(path)['status'] == 'UNAVAILABLE'
