from pathlib import Path

path = Path("editorial_desk/story_desk.py")
text = path.read_text(encoding="utf-8")

import_line = "from .story_models import StoryCandidate, StoryEvidenceRef\n"
new_import = import_line + "from .story_presentation import present_story_candidate\n"
if "from .story_presentation import present_story_candidate" not in text:
    if import_line not in text:
        raise SystemExit("story model import anchor missing")
    text = text.replace(import_line, new_import, 1)

old = '''    unique = {candidate.candidate_id: candidate for candidate in candidates}\n    ordered = sorted(\n        unique.values(),\n        key=lambda row: (-row.signal_score, row.candidate_type, row.candidate_id),\n    )[: max(0, min(int(max_candidates), 20))]\n'''
new = '''    unique = {candidate.candidate_id: candidate for candidate in candidates}\n    presented = [\n        present_story_candidate(candidate, publication_key)\n        for candidate in unique.values()\n    ]\n    ordered = sorted(\n        presented,\n        key=lambda row: (-row.signal_score, row.candidate_type, row.candidate_id),\n    )[: max(0, min(int(max_candidates), 20))]\n'''
if old in text:
    text = text.replace(old, new, 1)
elif "present_story_candidate(candidate, publication_key)" not in text:
    raise SystemExit("candidate ordering anchor missing")

path.write_text(text, encoding="utf-8")
