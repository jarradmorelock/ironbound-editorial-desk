import json
from editorial_desk.ranking_history import apply_newspaper_ranking_history, prior_newspaper_ranking
from editorial_desk.publication_packets import _ranking_wire


def dossier(week=4):
    return {'week': week, 'season': '2026', 'rankings': {
        'data_power_ranking': {'status': 'calculated', 'rows': [
            {'roster_id': 1, 'team': 'A', 'rank': 2}, {'roster_id': 2, 'team': 'B', 'rank': 1}]} }}


def prior():
    return {'season': '2026', 'week': 3, 'rows': [
        {'roster_id': 1, 'team': 'A', 'rank': 1}, {'roster_id': 2, 'team': 'B', 'rank': 2}]}


def test_newspaper_compares_current_research_ranking_with_prior_issue():
    d = dossier()
    apply_newspaper_ranking_history(d, prior())
    wire = _ranking_wire(d)
    assert wire.status == 'ready'
    assert wire.data[0]['movement'] == -1
    assert 'Week 3' in wire.reason


def test_missing_current_ranking_carries_prior_without_claiming_new_movement():
    d = dossier()
    d['rankings']['data_power_ranking']['rows'] = []
    apply_newspaper_ranking_history(d, prior())
    wire = _ranking_wire(d)
    assert wire.status == 'ready'
    assert [r['rank'] for r in wire.data] == [1, 2]
    assert all(r['movement'] is None for r in wire.data)
    assert 'carried forward from Week 3' in wire.reason


def test_missing_or_partial_prior_does_not_pass_movement_readiness():
    for baseline in [None, {'week': 3, 'rows': prior()['rows'][:1]}, {**prior(), 'week': 4}]:
        d = dossier()
        apply_newspaper_ranking_history(d, baseline)
        assert _ranking_wire(d).status == 'unavailable'


def test_first_week_can_establish_baseline_without_prior():
    d = dossier(1)
    apply_newspaper_ranking_history(d, None)
    assert _ranking_wire(d).status == 'ready'


def test_prior_dossier_is_bound_to_league_season_and_earlier_week(tmp_path):
    p = tmp_path/'2026'/'week-03'/'league-a'/'dossier.json'
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(dossier(3)))
    found = prior_newspaper_ranking(tmp_path, 'league-a', '2026', 4)
    assert found['week'] == 3
    assert prior_newspaper_ranking(tmp_path, 'league-b', '2026', 4) is None
    assert prior_newspaper_ranking(tmp_path, 'league-a', '2025', 4) is None
    assert prior_newspaper_ranking(tmp_path, 'league-a', '2026', 3) is None


def test_legacy_dynasty_rows_preserve_the_order_printed_in_the_prior_issue(tmp_path):
    d = dossier(3)
    for row in d['rankings']['data_power_ranking']['rows']:
        del row['rank']
    p = tmp_path/'2026'/'week-03'/'league-a'/'dossier.json'
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(d))
    found = prior_newspaper_ranking(tmp_path, 'league-a', '2026', 4)
    assert [r['rank'] for r in found['rows']] == [1, 2]
    d['week'] = 4
    apply_newspaper_ranking_history(d, found)
    assert [r['rank'] for r in d['rankings']['data_power_ranking']['rows']] == [1, 2]


def test_dynasty_component_rows_with_failed_sources_do_not_become_new_rankings(tmp_path):
    d = dossier()
    d['rankings']['data_power_ranking']['status'] = 'awaiting_sources'
    archived = tmp_path/'2026'/'week-03'/'league-a'/'dossier.json'
    archived.parent.mkdir(parents=True)
    archived.write_text(json.dumps({**d, 'week': 3}))
    assert prior_newspaper_ranking(tmp_path, 'league-a', '2026', 4) is None
    apply_newspaper_ranking_history(d, prior())
    wire = _ranking_wire(d)
    assert d['rankings']['data_power_ranking']['ranking_status'] == 'carried_forward'
    assert [r['rank'] for r in wire.data] == [1, 2]
    assert all(r['movement'] is None for r in wire.data)
    d = dossier()
    d['rankings']['data_power_ranking']['status'] = 'awaiting_sources'
    apply_newspaper_ranking_history(d, None)
    assert _ranking_wire(d).status == 'unavailable'
    assert d['rankings']['data_power_ranking']['rows'] == []
