from pathlib import Path

from editorial_desk.config import load_publications


PUBLICATIONS = load_publications(Path("config/publications.json"))


def _weekly(key):
    return PUBLICATIONS[key].contracts_for("weekly")


def _preseason(key):
    return PUBLICATIONS[key].contracts_for("preseason")


def _names(contracts):
    return [row.display_name for row in contracts]


def _features(contracts):
    return [row.feature for row in contracts]


def test_ballad_weekly_contract_is_locked():
    assert _names(_weekly("ballad_crier")) == [
        "Week Cardiogram",
        "Final Monitor",
        "Weekly Rounds",
        "Official Standings",
        "Rankings Wire",
        "Rounds Report",
        "Position Leaders",
        "Waiver Star",
        "Ward Report",
        "Record Watch",
        "Next Card",
    ]
    assert "lineup_flip_candidates" in _features(_weekly("ballad_crier"))


def test_stampede_weekly_contract_uses_exact_workload_department_name():
    contracts = _weekly("the_stampede")
    by_feature = {row.feature: row.display_name for row in contracts}
    assert by_feature["workload_stat_lines"] == "What a Way to Make a Living"
    text = " ".join(_names(contracts) + list(PUBLICATIONS["the_stampede"].recurring_sections))
    assert "Heavy Lifting" not in text
    assert "Week's Heavy Lifting" not in text


def test_volunteer_weekly_contract_has_no_division_assumptions():
    contracts = _weekly("volunteer_voice")
    assert _names(contracts) == [
        "Lead Story / Weekly Aftermath",
        "Official Table",
        "Median Result",
        "Rankings Wire",
        "Decision Desk / The Call That Won the Week",
        "Mountain MVP",
        "Manager of the Week",
        "Benchwarmer",
        "Rookie of the Week",
        "Free Agent of the Week",
        "Efficiency Board",
        "Bad Beat",
        "Escape Artist",
        "Waiver Star",
        "Bench Blast",
        "Record Watch",
        "Next-Week Scouting",
    ]
    combined = " ".join(_features(contracts) + _names(contracts)).casefold()
    assert "division" not in combined
    assert "divisional" not in combined
    assert "league_wide_started_mvp" in _features(contracts)
    assert "divisional_started_mvps" not in _features(contracts)


def test_saturday_weekly_contract_retains_divisions_idp_and_recruiting():
    contracts = _weekly("saturday_standard")
    features = _features(contracts)
    names = _names(contracts)
    assert "division_metrics" in features
    assert "divisional_started_mvps" in features
    assert "idp_position_metrics" in features
    assert "East and West Division Pulse" in names
    assert "East and West Power Polls" in names
    assert "Portal Film Room" in names
    assert "Portal Commitments" in names
    assert "Position Board" in names
    assert "Dynasty Market Board" in names
    assert "Transfer Portal Dispatch" in names
    assert "Recruiting Desk" in names
    assert "Recruiting / Future Pick Ledger" in names


def test_hollywood_weekly_contract_is_complete_not_placeholder():
    assert _names(_weekly("hollywood_beat")) == [
        "Box Office",
        "Marquee / Official Standings",
        "Top Billing / First Cut",
        "Hollywood Board",
        "Monday Night / Late Show",
        "For Your Consideration",
        "Cutting Room Floor",
        "Studio Efficiency",
        "Casting Call",
        "Production Delays",
        "Dailies / Backlot Reports",
        "This Week's Bill",
    ]
    all_text = " ".join(
        _names(_weekly("hollywood_beat"))
        + list(PUBLICATIONS["hollywood_beat"].recurring_sections)
        + list(PUBLICATIONS["hollywood_beat"].editorial_priorities)
    ).casefold()
    assert "publication standard pending" not in all_text


def test_preseason_contracts_remain_phase_specific_and_locked():
    assert _names(_preseason("ballad_crier")) == [
        "Draft Desk",
        "Opening Card",
        "Keeper Heist",
        "Ward Report",
        "Full Draft Board",
        "ADP Draft Profile",
        "Value Board",
        "Reach Watch",
        "Streamers' Pact",
    ]
    assert _names(_preseason("the_stampede")) == [
        "Rankings Wire",
        "First Shift",
        "Value Board",
        "Paper Favorite",
        "Stampede Board",
        "Market Report",
        "I Will Always Love You",
        "Bargain Store",
        "Coat of Many Colors",
        "Old Flames",
        "Little Engine That Could",
        "Mystery Mine",
        "Season Predictions",
        "Preseason Truth",
    ]
    assert _names(_preseason("volunteer_voice")) == [
        "Rankings Wire",
        "First Read",
        "The Pack Is Tighter Than It Looks",
        "Rocky Top Board",
        "Commissioner's Warning",
        "Preseason Superlatives",
        "Scouting Report",
    ]
    volunteer_preseason = " ".join(
        _features(_preseason("volunteer_voice")) + _names(_preseason("volunteer_voice"))
    ).casefold()
    assert "division" not in volunteer_preseason
    assert _names(_preseason("saturday_standard")) == [
        "Committee Poll",
        "Depth Chart Wire",
        "East/West Division Order",
        "First Read",
        "West Is Different",
        "Selection Committee",
        "Divisional Board",
        "Transfer Portal Dispatch",
        "East/West Power Poll",
        "PI",
        "Recruiting Edition",
        "Full Recruiting Board",
        "Recruiting Class Standings",
        "Recruiting Desk",
    ]
    assert _names(_preseason("hollywood_beat")) == [
        "Opening Credits / Backlot Opens",
        "Top Billing / First Read",
        "Critics' Poll",
        "Hollywood Board",
        "Dailies",
        "Meet the Cast",
        "Development Slate",
        "Casting Call",
        "Development Rights",
        "Cutting Room Floor",
        "Studio Deals",
        "Production Delays",
        "This Week's Bill",
    ]


def test_story_desk_capability_is_confined_to_ironbound_siblings():
    enabled = {key for key, publication in PUBLICATIONS.items() if publication.story_desk}
    assert enabled == {"ironbound_weekly", "unbound_weekly"}
