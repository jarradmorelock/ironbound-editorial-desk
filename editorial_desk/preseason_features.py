from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .feature_models import FeatureResult, ready, ready_no_items, unavailable

OFFENSE_POSITIONS = {"QB", "RB", "FB", "WR", "TE"}
IDP_POSITIONS = {"DL", "DE", "DT", "NT", "LB", "DB", "CB", "S"}
DEFENSE_POSITIONS = {"DEF", "DST", "D/ST"}


def draft_results(snapshot: dict[str, Any]) -> FeatureResult:
    source = _draft_context(snapshot)
    if source.get("status") != "available":
        return unavailable(
            "draft_results",
            source.get("reason") or source.get("error") or "Draft context unavailable",
        )
    players = snapshot.get("players") or {}
    rows: list[dict[str, Any]] = []
    for record in source.get("records") or []:
        draft = record.get("draft") or {}
        draft_id = str(draft.get("draft_id") or "")
        draft_name = str((draft.get("metadata") or {}).get("name") or draft_id or "Draft")
        for pick in record.get("picks") or []:
            player_id = str(pick.get("player_id") or "")
            metadata = pick.get("metadata") or {}
            player = players.get(player_id) or {}
            rows.append(
                {
                    "draft_id": draft_id,
                    "draft_name": draft_name,
                    "season": str(draft.get("season") or ""),
                    "draft_type": draft.get("type"),
                    "pick_no": _int_or_none(pick.get("pick_no")),
                    "round": _int_or_none(pick.get("round")),
                    "roster_id": _int_or_none(pick.get("roster_id")),
                    "player_id": player_id,
                    "player": _player_name(player_id, player, metadata),
                    "position": str(player.get("position") or metadata.get("position") or ""),
                    "metadata": dict(metadata),
                }
            )
    rows.sort(key=lambda row: (row.get("season") or "", row.get("pick_no") or 10**9))
    if not rows:
        return ready_no_items("draft_results", reason="Draft source contained no picks")
    return ready("draft_results", rows)


def draft_adp_value(snapshot: dict[str, Any]) -> FeatureResult:
    drafts = draft_results(snapshot)
    if drafts.status == "unavailable":
        return unavailable("draft_adp_value", drafts.reason or "Draft results unavailable")
    if drafts.status == "ready_no_items":
        return ready_no_items("draft_adp_value", reason="No draft picks to compare with ADP")

    adp_source = (snapshot.get("ranking_inputs") or {}).get("draft_adp") or {}
    adp_players = adp_source.get("players") or {}
    rows: list[dict[str, Any]] = []
    for pick in drafts.data:
        player_id = str(pick.get("player_id") or "")
        metadata = pick.get("metadata") or {}
        adp = metadata.get("adp")
        if adp is None:
            adp = (adp_players.get(player_id) or {}).get("adp")
        numeric_adp = _float_or_none(adp)
        pick_no = _float_or_none(pick.get("pick_no"))
        if numeric_adp is None or pick_no is None:
            continue
        rows.append(
            {
                **pick,
                "adp": round(numeric_adp, 2),
                "value_delta": round(numeric_adp - pick_no, 2),
            }
        )
    if not rows:
        reason = adp_source.get("reason") or adp_source.get("error")
        if adp_source.get("status") not in {None, "available"}:
            return unavailable("draft_adp_value", reason or "Authoritative draft ADP unavailable")
        return unavailable("draft_adp_value", "Authoritative draft ADP unavailable for drafted players")
    return ready("draft_adp_value", rows)


def draft_value_board(snapshot: dict[str, Any]) -> FeatureResult:
    values = draft_adp_value(snapshot)
    if values.status == "unavailable":
        return unavailable("draft_value_board", values.reason or "Authoritative draft ADP unavailable")
    if values.status == "ready_no_items":
        return ready_no_items("draft_value_board", reason="No draft picks to compare with ADP")
    rows = sorted(
        (dict(row) for row in values.data),
        key=lambda row: (-float(row.get("value_delta") or 0), float(row.get("pick_no") or 10**9)),
    )
    return ready("draft_value_board", rows)


def draft_bargains(snapshot: dict[str, Any]) -> FeatureResult:
    values = draft_adp_value(snapshot)
    if values.status == "unavailable":
        return unavailable("draft_bargains", values.reason or "Authoritative draft ADP unavailable")
    if values.status == "ready_no_items":
        return ready_no_items("draft_bargains", reason="No draft picks to compare with ADP")
    rows = sorted(
        (dict(row) for row in values.data if float(row.get("value_delta") or 0) > 0),
        key=lambda row: (-float(row.get("value_delta") or 0), float(row.get("pick_no") or 10**9)),
    )
    if not rows:
        return ready_no_items("draft_bargains", reason="No drafted players beat authoritative ADP")
    return ready("draft_bargains", rows)


def draft_reach(snapshot: dict[str, Any]) -> FeatureResult:
    values = draft_adp_value(snapshot)
    if values.status == "unavailable":
        return unavailable("draft_reach", values.reason or "Authoritative draft ADP unavailable")
    if values.status == "ready_no_items":
        return ready_no_items("draft_reach", reason="No draft picks to compare with ADP")
    rows = sorted(
        (dict(row) for row in values.data if float(row.get("value_delta") or 0) < 0),
        key=lambda row: (float(row.get("value_delta") or 0), float(row.get("pick_no") or 10**9)),
    )
    if not rows:
        return ready_no_items("draft_reach", reason="No drafted players were taken ahead of authoritative ADP")
    return ready("draft_reach", rows)


def draft_market(snapshot: dict[str, Any]) -> FeatureResult:
    source = (snapshot.get("ranking_inputs") or {}).get("draft_adp")
    if not isinstance(source, dict) or source.get("status") != "available":
        reason = (source or {}).get("reason") or (source or {}).get("error") if isinstance(source, dict) else None
        return unavailable("draft_market", reason or "Authoritative draft ADP unavailable")
    players = source.get("players") or {}
    if not players:
        return ready_no_items("draft_market", reason="Authoritative draft ADP returned no player records")
    return ready("draft_market", dict(source))


def keeper_value(snapshot: dict[str, Any]) -> FeatureResult:
    source = snapshot.get("keeper_costs")
    if source is None:
        return ready_no_items("keeper_value", reason="No keeper-cost records supplied")
    players = snapshot.get("players") or {}
    rows = []
    for raw in source or []:
        player_id = str(raw.get("player_id") or "")
        rows.append(
            {
                **dict(raw),
                "player_id": player_id,
                "player": _player_name(player_id, players.get(player_id) or {}, {}),
            }
        )
    if not rows:
        return ready_no_items("keeper_value", reason="League has no keeper-cost records")
    return ready("keeper_value", rows)


def roster_age(snapshot: dict[str, Any]) -> FeatureResult:
    players = snapshot.get("players") or {}
    rows: list[dict[str, Any]] = []
    for roster in snapshot.get("rosters") or []:
        roster_id = int(roster.get("roster_id") or 0)
        experiences = []
        rookies = 0
        for player_id in roster.get("players") or []:
            value = (players.get(str(player_id)) or {}).get("years_exp")
            if isinstance(value, (int, float)):
                experiences.append(float(value))
                if float(value) == 0:
                    rookies += 1
        rows.append(
            {
                "roster_id": roster_id,
                "team": _team_name(snapshot, roster_id),
                "players_with_experience_data": len(experiences),
                "average_years_experience": round(sum(experiences) / len(experiences), 2)
                if experiences
                else None,
                "rookies": rookies,
            }
        )
    if not rows:
        return ready_no_items("roster_age", reason="No rosters available")
    return ready("roster_age", rows)


def positional_strength(snapshot: dict[str, Any]) -> FeatureResult:
    players = snapshot.get("players") or {}
    result: dict[int, dict[str, int]] = {}
    for roster in snapshot.get("rosters") or []:
        roster_id = int(roster.get("roster_id") or 0)
        counts: Counter[str] = Counter()
        for player_id in roster.get("players") or []:
            position = str((players.get(str(player_id)) or {}).get("position") or "")
            if position:
                counts[position] += 1
        result[roster_id] = dict(sorted(counts.items()))
    if not result:
        return ready_no_items("positional_strength", reason="No rosters available")
    return ready("positional_strength", result)


def future_pick_ledger(snapshot: dict[str, Any]) -> FeatureResult:
    rows = []
    for raw in snapshot.get("traded_picks") or []:
        rows.append(
            {
                "season": str(raw.get("season") or ""),
                "round": _int_or_none(raw.get("round")),
                "original_roster_id": _int_or_none(raw.get("roster_id")),
                "current_roster_id": _int_or_none(raw.get("owner_id")),
                "previous_roster_id": _int_or_none(raw.get("previous_owner_id")),
            }
        )
    rows.sort(key=lambda row: (row["season"], row["round"] or 99, row["original_roster_id"] or 0))
    if not rows:
        return ready_no_items("future_pick_ledger", reason="No traded future picks")
    return ready("future_pick_ledger", rows)


def rookie_draft(snapshot: dict[str, Any]) -> FeatureResult:
    drafts = draft_results(snapshot)
    if drafts.status == "unavailable":
        return unavailable("rookie_draft", drafts.reason or "Draft results unavailable")
    if drafts.status == "ready_no_items":
        return ready_no_items("rookie_draft", reason="No draft picks available")
    players = snapshot.get("players") or {}
    rows = []
    for pick in drafts.data:
        player = players.get(str(pick.get("player_id") or "")) or {}
        years_exp = player.get("years_exp")
        draft_name = str(pick.get("draft_name") or "").lower()
        if years_exp == 0 or "rookie" in draft_name:
            rows.append(dict(pick))
    if not rows:
        return ready_no_items("rookie_draft", reason="No rookie draft picks identified")
    return ready("rookie_draft", rows)


def recruiting_class(snapshot: dict[str, Any]) -> FeatureResult:
    rookies = rookie_draft(snapshot)
    if rookies.status == "unavailable":
        return unavailable("recruiting_class", rookies.reason or "Rookie draft unavailable")
    if rookies.status == "ready_no_items":
        return ready_no_items("recruiting_class", reason="No rookie picks to group")
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for pick in rookies.data:
        roster_id = int(pick.get("roster_id") or 0)
        grouped[roster_id].append(pick)
    rows = []
    for roster_id, picks in sorted(grouped.items()):
        positions = Counter(str(pick.get("position") or "") for pick in picks)
        rows.append(
            {
                "roster_id": roster_id,
                "team": _team_name(snapshot, roster_id),
                "rookies": len(picks),
                "offense_rookies": sum(positions[position] for position in OFFENSE_POSITIONS),
                "idp_rookies": sum(positions[position] for position in IDP_POSITIONS),
                "positions": dict(sorted((key, value) for key, value in positions.items() if key)),
                "picks": picks,
            }
        )
    return ready("recruiting_class", rows)


def dynasty_market(snapshot: dict[str, Any]) -> FeatureResult:
    source = (snapshot.get("ranking_inputs") or {}).get("dynasty_daddy") or {}
    if source.get("status") != "available":
        return unavailable(
            "dynasty_market",
            source.get("reason") or source.get("error") or "Authoritative dynasty market values unavailable",
        )
    players = source.get("players") or {}
    if not players:
        return ready_no_items("dynasty_market", reason="Dynasty market source returned no players")
    return ready("dynasty_market", players)


def offense_defense_splits(snapshot: dict[str, Any]) -> FeatureResult:
    players = snapshot.get("players") or {}
    rows = []
    for roster in snapshot.get("rosters") or []:
        roster_id = int(roster.get("roster_id") or 0)
        offense = idp = defense = other = 0
        for player_id in roster.get("players") or []:
            position = str((players.get(str(player_id)) or {}).get("position") or "")
            if position in OFFENSE_POSITIONS:
                offense += 1
            elif position in IDP_POSITIONS:
                idp += 1
            elif position in DEFENSE_POSITIONS:
                defense += 1
            else:
                other += 1
        rows.append(
            {
                "roster_id": roster_id,
                "team": _team_name(snapshot, roster_id),
                "offense_players": offense,
                "idp_players": idp,
                "team_defenses": defense,
                "other_players": other,
            }
        )
    if not rows:
        return ready_no_items("offense_defense_splits", reason="No rosters available")
    return ready("offense_defense_splits", rows)


def streaming_roster_state(snapshot: dict[str, Any]) -> FeatureResult:
    players = snapshot.get("players") or {}
    rows = []
    for roster in snapshot.get("rosters") or []:
        roster_id = int(roster.get("roster_id") or 0)
        for player_id in roster.get("players") or []:
            player_id = str(player_id)
            player = players.get(player_id) or {}
            position = str(player.get("position") or "").upper()
            if position not in DEFENSE_POSITIONS:
                continue
            rows.append(
                {
                    "roster_id": roster_id,
                    "team": _team_name(snapshot, roster_id),
                    "player_id": player_id,
                    "player": _player_name(player_id, player, {}),
                    "position": position,
                }
            )
    if not rows:
        return ready_no_items("streaming_roster_state", reason="No rostered team defenses")
    return ready("streaming_roster_state", rows)


def _draft_context(snapshot: dict[str, Any]) -> dict[str, Any]:
    direct = snapshot.get("draft_context")
    if isinstance(direct, dict):
        return direct
    flagship = snapshot.get("flagship_sleeper") or {}
    drafts = flagship.get("drafts")
    if isinstance(drafts, dict):
        return drafts
    return {"status": "unavailable", "records": [], "reason": "Draft context not collected"}


def _team_name(snapshot: dict[str, Any], roster_id: int) -> str:
    users = {str(row.get("user_id")): row for row in snapshot.get("users") or []}
    for roster in snapshot.get("rosters") or []:
        if int(roster.get("roster_id") or 0) != roster_id:
            continue
        owner = users.get(str(roster.get("owner_id"))) or {}
        metadata = owner.get("metadata") or {}
        return str(
            metadata.get("team_name")
            or owner.get("display_name")
            or owner.get("username")
            or f"Roster {roster_id}"
        )
    return f"Roster {roster_id}"


def _player_name(player_id: str, player: dict[str, Any], metadata: dict[str, Any]) -> str:
    metadata_name = " ".join(
        str(value)
        for value in (metadata.get("first_name"), metadata.get("last_name"))
        if value
    ).strip()
    return str(player.get("full_name") or metadata_name or player_id)


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
