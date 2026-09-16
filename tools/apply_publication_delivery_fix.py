from pathlib import Path


def replace(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Expected patch target not found in {path}: {old[:80]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


replace(
    "editorial_desk/collector.py",
    '''                "editorial_priorities": list(publication.editorial_priorities),
            }
''',
    '''                "editorial_priorities": list(publication.editorial_priorities),
                "weekly_features": [
                    contract.feature for contract in publication.contracts_for("weekly")
                ],
            }
''',
)

replace(
    "editorial_desk/metrics.py",
    '''    division_summary = _division_summary(
        snapshot, matchup_rows, scoreboard, league_median, teams
    )
''',
    '''    editorial = snapshot.get("editorial") or {}
    profile = editorial.get("publication_profile") or {}
    weekly_features = set(profile.get("weekly_features") or [])
    division_summary = (
        _division_summary(snapshot, matchup_rows, scoreboard, league_median, teams)
        if editorial.get("tier") == "flagship" or "division_metrics" in weekly_features
        else []
    )
''',
)

replace(
    "editorial_desk/weekly_features.py",
    '''    dossier["weekly_features"] = {
        "lineup_efficiency_top_three": lineup[:3],
        "divisional_mvp_nominees": _divisional_mvp_nominees(snapshot),
        "top_scorers_by_position": _top_scorers_by_position(snapshot),
        "benchwarmer_of_the_week": _benchwarmer_of_week(snapshot),
        "rookie_of_the_week": _rookie_of_week(snapshot),
        "free_agent_of_the_week": _free_agent_of_week(snapshot),
    }
''',
    '''    features = {
        "lineup_efficiency_top_three": lineup[:3],
        "top_scorers_by_position": _top_scorers_by_position(snapshot),
        "benchwarmer_of_the_week": _benchwarmer_of_week(snapshot),
        "rookie_of_the_week": _rookie_of_week(snapshot),
        "free_agent_of_the_week": _free_agent_of_week(snapshot),
    }
    editorial = snapshot.get("editorial") or {}
    profile = editorial.get("publication_profile") or {}
    weekly_contract_features = set(profile.get("weekly_features") or [])
    if (
        editorial.get("tier") == "flagship"
        or "divisional_started_mvps" in weekly_contract_features
    ):
        features["divisional_mvp_nominees"] = _divisional_mvp_nominees(snapshot)
    dossier["weekly_features"] = features
''',
)

replace(
    "editorial_desk/review.py",
    '''    nominees = features.get("divisional_mvp_nominees") or []
    lines.append("### Divisional MVP Nominations")
    if not nominees:
        lines.append("- No divisional nominees available")
    for row in nominees:
        foil = " — **GOLD FOIL**" if row.get("gold_foil") else ""
        lines.append(
            f"- {row.get('division_name')}: {row.get('player')} "
            f"({row.get('position') or '?'}) — {row.get('team')} — "
            f"{_points(row.get('points'))} — {row.get('status', 'STARTED')}{foil}"
        )
    lines.append("- Card images are generated separately after commissioner review.")
''',
    '''    if "divisional_mvp_nominees" in features:
        nominees = features.get("divisional_mvp_nominees") or []
        lines.append("### Divisional MVP Nominations")
        if not nominees:
            lines.append("- No divisional nominees available")
        for row in nominees:
            foil = " — **GOLD FOIL**" if row.get("gold_foil") else ""
            lines.append(
                f"- {row.get('division_name')}: {row.get('player')} "
                f"({row.get('position') or '?'}) — {row.get('team')} — "
                f"{_points(row.get('points'))} — {row.get('status', 'STARTED')}{foil}"
            )
        lines.append("- Card images are generated separately after commissioner review.")
''',
)

replace(
    "editorial_desk/emailer.py",
    '''    packets: list[tuple[Path, dict[str, Any]]] = []
''',
    '''    packets: list[tuple[list[tuple[Path, str]], dict[str, Any]]] = []
''',
)

replace(
    "editorial_desk/emailer.py",
    '''        packets.append((markdown_path, dossier))
        seasons.add(str(dossier.get("season") or "unknown"))
''',
    '''        publication_packet = markdown_path.parent / "publication_packet.md"
        primary_path = publication_packet if publication_packet.is_file() else markdown_path
        delivery_paths: list[tuple[Path, str]] = [(primary_path, "")]
        story_desk = markdown_path.parent / "story_desk.md"
        if story_desk.is_file():
            delivery_paths.append((story_desk, "-story-desk"))
        packets.append((delivery_paths, dossier))
        seasons.add(str(dossier.get("season") or "unknown"))
''',
)

replace(
    "editorial_desk/emailer.py",
    '''    for markdown_path, dossier in packets:
        league = dossier.get("league") or {}
        league_key = str(league.get("league_key") or markdown_path.parent.name)
        filename = f"{league_key}-week-{week:02d}.md"
        message.add_attachment(
            markdown_path.read_text(encoding="utf-8"),
            subtype="markdown",
            filename=filename,
        )
''',
    '''    for delivery_paths, dossier in packets:
        league = dossier.get("league") or {}
        fallback_directory = delivery_paths[0][0].parent.name
        league_key = str(league.get("league_key") or fallback_directory)
        for markdown_path, suffix in delivery_paths:
            filename = f"{league_key}-week-{week:02d}{suffix}.md"
            message.add_attachment(
                markdown_path.read_text(encoding="utf-8"),
                subtype="markdown",
                filename=filename,
            )
''',
)

print("Publication delivery patch applied")
