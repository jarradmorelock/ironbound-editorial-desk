from __future__ import annotations

import json
from pathlib import Path

PACKETS = Path("editorial_desk/publication_packets.py")
CONFIG = Path("config/publications.json")


def patch_packets() -> None:
    text = PACKETS.read_text(encoding="utf-8")

    import_marker = "from .publication_contracts import evaluate_dependencies\n"
    imports = (
        "from .preseason_features import (\n"
        "    draft_bargains,\n"
        "    draft_market,\n"
        "    draft_reach,\n"
        "    draft_value_board,\n"
        ")\n"
        "from .preseason_support import preseason_support\n"
    )
    if "from .preseason_support import preseason_support" not in text:
        if import_marker not in text:
            raise RuntimeError("publication contract import marker not found")
        text = text.replace(import_marker, import_marker + imports, 1)

    adp_marker = '    if feature == "draft_adp_value":\n        return draft_adp_value(snapshot)\n'
    adp_block = (
        adp_marker
        + '    if feature == "draft_value_board":\n        return draft_value_board(snapshot)\n'
        + '    if feature == "draft_reach":\n        return draft_reach(snapshot)\n'
        + '    if feature == "draft_bargains":\n        return draft_bargains(snapshot)\n'
        + '    if feature == "draft_market":\n        return draft_market(snapshot)\n'
    )
    if 'if feature == "draft_value_board"' not in text:
        if adp_marker not in text:
            raise RuntimeError("draft ADP resolver marker not found")
        text = text.replace(adp_marker, adp_block, 1)

    support_marker = "    direct = _direct_feature_value(feature, snapshot, dossier)\n"
    support_block = (
        "    support = preseason_support(feature, snapshot, dossier)\n"
        "    if support is not None:\n"
        "        return support\n\n"
        + support_marker
    )
    if "support = preseason_support(feature, snapshot, dossier)" not in text:
        if support_marker not in text:
            raise RuntimeError("direct feature fallback marker not found")
        text = text.replace(support_marker, support_block, 1)

    PACKETS.write_text(text, encoding="utf-8")


def patch_config() -> None:
    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    targets = {
        "ballad_crier": {"draft_value_board", "draft_reach"},
        "the_stampede": {"draft_value_board", "draft_market", "draft_reach", "draft_bargains"},
    }
    for publication in data.get("publications", []):
        wanted = targets.get(publication.get("key"))
        if not wanted:
            continue
        preseason = (publication.get("feature_contracts") or {}).get("preseason") or []
        for contract in preseason:
            if contract.get("feature") not in wanted:
                continue
            dependencies = contract.setdefault("dependencies", [])
            if not any(row.get("source") == "draft_adp" for row in dependencies):
                dependencies.append({"source": "draft_adp", "strength": "preferred"})

    CONFIG.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    patch_packets()
    patch_config()


if __name__ == "__main__":
    main()
