from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def render_publication_packet(packet: dict[str, Any]) -> str:
    lines = [
        f"# {packet.get('publication') or 'Publication'}",
        "",
        f"Phase: {packet.get('phase') or 'unknown'}",
        f"Week: {packet.get('week') if packet.get('week') is not None else 'N/A'}",
        f"Packet status: {packet.get('status') or 'unknown'}",
        "",
    ]
    for department in packet.get("departments") or []:
        lines.extend(
            [
                f"## {department.get('display_name') or department.get('feature') or 'Department'}",
                "",
                f"Status: {department.get('status') or 'unknown'}",
            ]
        )
        if department.get("degraded"):
            lines.append("Degraded: yes")
        for warning in department.get("dependency_warnings") or []:
            lines.append(f"Dependency warning: {warning}")
        if department.get("reason"):
            lines.append(f"Reason: {department['reason']}")
        data = department.get("data")
        if data not in (None, [], {}, ()):
            lines.extend(
                [
                    "",
                    "```json",
                    json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False),
                    "```",
                ]
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_publication_packet(
    directory: Path, packet: dict[str, Any]
) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "publication_packet.json"
    markdown_path = directory / "publication_packet.md"
    json_path.write_text(
        json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_publication_packet(packet), encoding="utf-8")
    return json_path, markdown_path
