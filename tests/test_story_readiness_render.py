from editorial_desk.story_artifacts import _render_story_desk


def test_story_desk_markdown_renders_commissioner_request_buckets():
    packet = {
        "publication_key": "ironbound_weekly",
        "status": "available",
        "candidates": [],
        "external_inputs": {
            "official_power_rankings": False,
            "war": False,
        },
        "publication_readiness": {
            "ready_for_final_publication": False,
            "required_before_publication": [
                {
                    "input": "official_power_rankings",
                    "request": "Supply this week's official Power Rankings.",
                    "reason": "The final flagship magazine requires the official ranking section.",
                }
            ],
            "optional_enrichment": [
                {
                    "input": "war",
                    "request": "Supply a WAR export if you want roster-value context.",
                    "reason": "A current story could use dynasty-value context.",
                }
            ],
            "commissioner_judgment": [
                {
                    "candidate_type": "rivalry_history",
                    "request": "Approve the rivalry framing or add commissioner context.",
                }
            ],
            "visuals_to_source_or_approve": [
                {
                    "candidate_type": "rivalry_history",
                    "request": "Source or approve a rivalry matchup image.",
                }
            ],
            "no_action_needed": [
                {
                    "input": "nflverse_snap_counts",
                    "request": "Snap-count context is already available.",
                }
            ],
        },
    }

    markdown = _render_story_desk(packet)

    assert "## Publication Readiness / Commissioner Requests" in markdown
    assert "Final publication ready: **NO**" in markdown
    assert "### Required Before Publication" in markdown
    assert "official Power Rankings" in markdown
    assert "### Optional Enrichment" in markdown
    assert "WAR export" in markdown
    assert "### Commissioner / Editorial Judgment" in markdown
    assert "rivalry framing" in markdown
    assert "### Visuals to Source or Approve" in markdown
    assert "rivalry matchup image" in markdown
    assert "### No Action Needed" in markdown
    assert "Snap-count context is already available" in markdown
