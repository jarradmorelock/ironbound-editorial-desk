from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .publication_policy import publication_view
from .reading_packet import render_reading_packet


def render_publication_packet(packet: dict[str, Any]) -> str:
    return render_reading_packet({}, packet=packet)


def write_publication_packet(
    directory: Path, packet: dict[str, Any]
) -> tuple[Path, Path]:
    packet = publication_view(packet, packet)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "publication_packet.json"
    markdown_path = directory / "publication_packet.md"
    json_path.write_text(
        json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_publication_packet(packet), encoding="utf-8")
    return json_path, markdown_path
