import copy
import json

import pytest

from editorial_desk.emailer import build_dossier_email
from editorial_desk.metrics import build_weekly_dossier
from editorial_desk.publication_packets import build_publication_packet
from editorial_desk.publication_render import render_publication_packet
from editorial_desk.review import build_editorial_review
from test_delivery_contract_boundary import _publication, _snapshot


def test_volunteer_rule_sanitizes_all_payloads_even_with_stale_division_contract():
    profile = _publication('volunteer_voice', ['official_table', 'lead_inputs', 'division_metrics', 'divisional_started_mvps'])
    snapshot = _snapshot(profile)
    before = copy.deepcopy(snapshot)
    dossier = build_editorial_review(snapshot)
    packet = build_publication_packet(snapshot, dossier, profile, 'weekly')
    for value in (dossier, packet):
        encoded = json.dumps(value)
        assert 'division_id' not in encoded
        assert 'division_name' not in encoded
        assert 'Holler' not in encoded
        assert 'Mountain' not in encoded
    assert not dossier.get('divisions')
    assert not any(row['feature'] in {'division_metrics', 'divisional_started_mvps'} for row in packet['departments'])
    assert snapshot == before
    assert snapshot['rosters'][0]['settings']['division'] == 1


def test_volunteer_rule_works_without_loaded_profile():
    snapshot = _snapshot(_publication('volunteer_voice', ['official_table']))
    snapshot['editorial']['publication_profile'] = None
    snapshot['editorial']['league_key'] = 'rocky_top_rumble'
    assert 'division_id' not in json.dumps(build_weekly_dossier(snapshot))


def test_other_publications_keep_division_standings():
    profile = _publication('saturday_standard', ['official_table', 'division_metrics'])
    snapshot = _snapshot(profile)
    packet = build_publication_packet(snapshot, build_weekly_dossier(snapshot), profile, 'weekly')
    assert 'division_name' in json.dumps(packet)
    assert 'Holler' in json.dumps(packet)


def test_newspaper_packet_is_plain_english_with_named_departments():
    profile = _publication('volunteer_voice', ['weekly_results', 'official_table'])
    snapshot = _snapshot(profile)
    packet = build_publication_packet(snapshot, build_weekly_dossier(snapshot), profile, 'weekly')
    text = render_publication_packet(packet)
    assert text.index("## EDITOR'S BRIEF") < text.index('## COMMISSIONER REQUESTS') < text.index('## weekly_results')
    assert 'Alpha' in text and 'Beta' in text
    assert '20.00' in text
    assert '```json' not in text and '"roster_id"' not in text
    requests = text.split('## COMMISSIONER REQUESTS')[1].split('\n## ')[0]
    assert 'Power Rankings' not in requests
    assert 'No unresolved human inputs' in requests


@pytest.mark.parametrize('key', ['ironbound_weekly', 'unbound_weekly'])
def test_email_consolidates_readiness_and_named_stories_without_raw_evidence(tmp_path, key):
    directory = tmp_path / '2026' / 'week-01' / key
    directory.mkdir(parents=True)
    dossier = {'season': '2026', 'week': 1, 'league': {'publication': key, 'league_key': key, 'tier': 'flagship'}, 'scoreboard': [{'teams': [{'team': 'Alpha', 'points': 120}, {'team': 'Beta', 'points': 110}], 'margin': 10}]}
    story = {'publication_key': key, 'publication_readiness': {'ready_for_final_publication': False, 'required_before_publication': [{'request': 'Supply official Power Rankings.'}], 'no_action_needed': [{'request': 'Snap counts already supplied.'}]}, 'candidates': [{'candidate_type': 'rivalry_history', 'display_subjects': ['Alpha', 'Beta'], 'facts': [{'statement': 'Alpha has won three recorded meetings.', 'provenance': 'chronicle_derived'}], 'entities': {'identities': ['franchise_123', 'franchise_456']}, 'cautions': ['Earlier seasons have incomplete coverage.']}]}
    for name, value in [('dossier', dossier), ('story_desk', story)]:
        (directory / f'{name}.json').write_text(json.dumps(value))
        (directory / f'{name}.md').write_text('RAW EVIDENCE SENTINEL')
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    message = build_dossier_email(tmp_path, 1, 'a@example.com', 'b@example.com')
    parts = list(message.iter_attachments())
    assert len(parts) == 1
    text = parts[0].get_content()
    assert text.index("## EDITOR'S BRIEF") < text.index('## COMMISSIONER REQUESTS') < text.index('## STORY DESK')
    assert 'Supply official Power Rankings.' in text
    assert 'Snap counts already supplied.' in text
    assert 'Alpha has won three recorded meetings.' in text
    assert 'Rivalry History — Alpha / Beta' in text
    assert 'Earlier seasons have incomplete coverage.' in text
    assert 'RAW EVIDENCE SENTINEL' not in text
    assert 'franchise_123' not in text and 'chronicle_derived' not in text
    assert {p.name: p.read_bytes() for p in directory.iterdir()} == before


def test_story_artifacts_resolve_rosters_players_and_chronicle_aliases(tmp_path, monkeypatch):
    from editorial_desk.story_artifacts import write_story_desk_artifacts
    from test_story_artifacts import _publication as magazine
    from editorial_desk import story_artifacts
    root = tmp_path / 'chronicle'
    (root / 'registry').mkdir(parents=True)
    (root / 'registry' / 'identity.json').write_text(json.dumps({'aliases': {'franchise_old': [{'season': '2025', 'name': 'Old Guard'}]}}))
    monkeypatch.setattr(story_artifacts, 'build_story_desk', lambda *a, **k: {'publication_key': 'ironbound_weekly', 'candidates': [{'candidate_type': 'trade_afterlife', 'entities': {'player_id': 'p1', 'roster_id': 1, 'identity': 'franchise_old'}, 'facts': [{'statement': 'The player scored 20 points.'}]}]})
    snapshot = _snapshot(_publication('volunteer_voice', []))
    write_story_desk_artifacts(tmp_path / 'issue', snapshot, {}, magazine(), chronicle_root=root)
    candidate = json.loads((tmp_path / 'issue' / 'story_desk.json').read_text())['candidates'][0]
    assert set(candidate['display_subjects']) == {'Player One', 'Alpha', 'Old Guard'}
    assert candidate['entities']['player_id'] == 'p1'


def test_brief_is_bounded_and_newspaper_requests_exclude_machine_failures():
    from editorial_desk.reading_packet import render_reading_packet
    packet = {'publication': 'Paper', 'departments': [{'display_name': 'Health', 'status': 'unavailable', 'reason': 'NFL service unavailable'}], 'commissioner_requests': [{'request': 'Confirm the rivalry nickname.', 'resolved': False}, {'request': 'Already supplied quote', 'resolved': True}]}
    dossier = {'scoreboard': [{'teams': [{'team': f'Team {i}', 'points': i}, {'team': 'Opponent', 'points': 1}]} for i in range(1000)]}
    text = render_reading_packet(dossier, packet=packet)
    brief = text.split("## EDITOR'S BRIEF")[1].split('## COMMISSIONER REQUESTS')[0]
    assert len(brief.split()) <= 1200
    requests = text.split('## COMMISSIONER REQUESTS')[1].split('\n## ')[0]
    assert 'Confirm the rivalry nickname.' in requests
    assert 'Already supplied quote' not in requests
    assert 'NFL service unavailable' not in requests


def test_direct_publication_writer_sanitizes_stale_nested_payload_without_mutation(tmp_path):
    from editorial_desk.publication_render import write_publication_packet
    packet = {'publication_key': 'volunteer_voice', 'publication': 'The Volunteer Voice', 'departments': [{'feature': 'official_table', 'display_name': 'Official Table', 'data': [{'team': 'Alpha', 'wins': 1, 'division_id': 1, 'division_name': 'Holler', 'nested': {'division_id': 1, 'division_name': 'Holler'}}]}]}
    before = copy.deepcopy(packet)
    write_publication_packet(tmp_path, packet)
    assert 'division_id' not in (tmp_path / 'publication_packet.json').read_text()
    assert 'Holler' not in (tmp_path / 'publication_packet.json').read_text()
    assert packet == before


def test_flagship_brief_includes_verified_game_day_and_health_context():
    from editorial_desk.reading_packet import render_reading_packet
    dossier = {'league': {'tier': 'flagship'}, 'game_timing': {'monday': {'lead_changes': [{'final_winner': 'Alpha', 'final_loser': 'Beta', 'final_margin': 2.5}]}}, 'roster_health': {'status': 'available', 'players': [{'player': 'Player One', 'team': 'Alpha', 'injury_status': 'Out'}]}}
    text = render_reading_packet(dossier)
    brief = text.split('## COMMISSIONER REQUESTS')[0]
    assert 'Monday' in brief and 'Alpha' in brief and '2.50' in brief
    assert 'Player One' in brief and 'Out' in brief


def test_department_prose_preserves_decisions_divisions_and_game_window_provenance():
    from editorial_desk.reading_packet import fact_lines
    flip = {'team': 'Alpha', 'started_player': 'Starter', 'started_points': 5, 'bench_player': 'Reserve', 'bench_points': 20, 'point_swing': 15, 'would_flip_result': True}
    text = ' '.join(fact_lines([flip]))
    assert 'Reserve' in text and 'Starter' in text and '15.00' in text and 'changed the result' in text
    division = {'division_name': 'Holler', 'teams': [{'team': 'Alpha', 'points': 20}, {'team': 'Beta', 'points': 10}], 'average_points': 15, 'head_to_head_record': {'wins': 1, 'losses': 1, 'ties': 0}}
    text = ' '.join(fact_lines([division]))
    assert 'Holler' in text and '15.00' in text
    assert 'finished ahead' not in text
    window = {'team': 'Alpha', 'opponent': 'Beta', 'window': 'Monday', 'pre_window_score': 80, 'opponent_pre_window_score': 90, 'final_score': 110, 'opponent_final_score': 100, 'provenance': 'reconstructed'}
    text = ' '.join(fact_lines([window]))
    assert 'Monday' in text and '110.00' in text and 'reconstructed' in text


def test_story_prose_preserves_incomplete_coverage_warning():
    from editorial_desk.reading_packet import render_reading_packet
    story = {'candidates': [{'candidate_type': 'rivalry_history', 'display_subjects': ['Alpha', 'Beta'], 'facts': [{'statement': 'Three recorded meetings.', 'coverage_complete': False}]}]}
    text = render_reading_packet({}, story=story)
    assert 'Historical coverage is incomplete' in text


def test_story_display_facts_resolve_roster_references_but_keep_original_evidence(tmp_path):
    from editorial_desk.story_artifacts import _with_display_subjects
    from editorial_desk.chronicle_queries import ChronicleQueries
    snapshot = _snapshot(_publication('volunteer_voice', []))
    original = {'candidates': [{'entities': {'roster_id': 1}, 'facts': [{'statement': 'Roster 1 carries six receivers.'}]}]}
    result = _with_display_subjects(original, snapshot, ChronicleQueries(tmp_path))
    candidate = result['candidates'][0]
    assert candidate['display_facts'][0]['statement'] == 'Alpha carries six receivers.'
    assert candidate['facts'] == original['candidates'][0]['facts']


def test_enriched_collection_writes_same_reading_packet_as_email(tmp_path, monkeypatch):
    from editorial_desk import enriched_collector
    from test_delivery_contract_boundary import _league, DivisionTaggedSleeperClient
    from test_nfl_context_collection import FakeNFLVerse
    profile = _publication('volunteer_voice', ['weekly_results', 'official_table'])
    snapshot = _snapshot(profile)
    directory = tmp_path / '2026' / 'week-01' / 'demo'
    directory.mkdir(parents=True)
    snapshot_path = directory / 'snapshot.json'
    snapshot_path.write_text(json.dumps(snapshot))
    monkeypatch.setattr(enriched_collector, 'collect_base', lambda *a, **k: [snapshot_path])
    class Client(DivisionTaggedSleeperClient):
        def players(self):
            return snapshot['players']
        def drafts(self, league_id):
            return []
    generated = enriched_collector.collect_all([_league(profile.key)], 1, tmp_path, client=Client(), publications={profile.key: profile}, nflverse_client=FakeNFLVerse())
    reading_path = directory / 'reading_packet.md'
    assert reading_path in generated
    text = reading_path.read_text()
    email = build_dossier_email(tmp_path, 1, 'a@example.com', 'b@example.com')
    assert list(email.iter_attachments())[0].get_content().strip() == text.strip()
    assert 'Holler' not in text and 'division_id' not in text
    assert json.loads(snapshot_path.read_text())['rosters'][0]['settings']['division'] == 1


def test_health_summary_keeps_ir_and_practice_alert_reasons():
    from editorial_desk.reading_packet import fact_lines
    text = ' '.join(fact_lines([{'player': 'Player One', 'team': 'Alpha', 'status': 'Active', 'on_ir': True, 'practice_participation': 'Did Not Participate'}]))
    assert 'IR/RESERVE' in text
    assert 'Did Not Participate' in text
