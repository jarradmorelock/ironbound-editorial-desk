from __future__ import annotations

from .story_models import StoryCandidate


_GRAPHIC_IDEAS = {
    "rivalry_history": "Head-to-head series table with playoff meetings highlighted",
    "injury_shock": "Observed player-status timeline with the polling window labeled",
    "reaction_transaction": "Status-to-transaction sequence timeline with timestamps",
    "waiver_run": "Cross-league waiver/add table by league and observation time",
    "trade_afterlife": "Trade timeline beside the current-week fantasy stat line",
    "trade_market_shift": "League trade-volume timeline for the recent observation window",
    "asset_journey": "Player asset-journey transaction timeline",
    "roster_architecture": "Roster construction chart by position group",
    "dynasty_identity": "Franchise alias and manager-tenure timeline",
    "historic_upset": "Season-record comparison beside the completed matchup result",
    "scoring_record": "Record card with the exact Chronicle record event and value",
    "streak": "Head-to-head streak timeline",
    "repeated_close_losses": "Close-loss margin chart across recorded matchups",
    "former_player_matchup": "Trade-route diagram connecting current and former roster",
    "playoff_rematch": "Prior playoff result box beside the current matchup",
    "lineup_catastrophe": "Actual-versus-alternative lineup swing table",
    "division_pressure": "Division gap table using supplied division metrics",
    "cross_league_shock": "Cross-league event timeline keyed to the shared NFL player",
    "david_vs_goliath": "Official Power Ranking gap beside the completed matchup",
}


def present_story_candidate(
    candidate: StoryCandidate, publication_key: str
) -> StoryCandidate:
    """Apply publication voice and evidence-breadth presentation without changing truth."""
    graphics = _graphic_ideas(candidate)
    return StoryCandidate.build(
        candidate_type=candidate.candidate_type,
        evidence_refs=candidate.evidence_refs,
        title_concepts=_title_concepts(candidate.candidate_type, publication_key),
        trigger_reasons=candidate.trigger_reasons,
        facts=candidate.facts,
        historical_context=candidate.historical_context,
        entities=candidate.entities,
        evidence_strength=candidate.evidence_strength,
        signal_score=candidate.signal_score,
        signal_components=candidate.signal_components,
        cautions=candidate.cautions,
        editorial_angles=candidate.editorial_angles,
        graphic_ideas=graphics,
        depth_class=_depth_class(candidate, bool(graphics)),
    )


def _title_concepts(candidate_type: str, publication_key: str) -> tuple[str, ...]:
    base = candidate_type.replace("_", " ").title()
    if publication_key == "unbound_weekly":
        return (
            f"Links Under Tension: {base}",
            f"Where the Chain Bends: {base}",
        )
    return (
        f"Under Pressure: {base}",
        f"Forged in the Week: {base}",
    )


def _graphic_ideas(candidate: StoryCandidate) -> tuple[str, ...]:
    idea = _GRAPHIC_IDEAS.get(candidate.candidate_type)
    if not idea or not candidate.evidence_refs:
        return ()
    return (idea,)


def _depth_class(candidate: StoryCandidate, has_graphic: bool) -> str:
    breadth = len(candidate.evidence_refs)
    score = float(candidate.signal_score)
    if score >= 15 and breadth >= 3:
        return "cover_4_6_pages"
    if score >= 11 or breadth >= 4:
        return "major_2_4_pages"
    if score >= 8 or breadth >= 2:
        return "analysis_1_2_pages"
    if has_graphic:
        return "sidebar_graphic"
    return "brief"
