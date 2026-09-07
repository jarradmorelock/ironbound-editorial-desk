# Source audit and editorial map

This file records what the data pipeline may safely infer from the supplied
2026 primers and sample publications. The PDFs themselves remain in the
ChatGPT project source library and are not copied into this repository.

## Publication map

| League | Publication | Format | Supplied authority |
| --- | --- | --- | --- |
| Ironbound Sixteen | The Ironbound Weekly | Flagship magazine | `ironbound-weekly-2026.01-preseason-issue.pdf` |
| Free Ironbound Sixteen | Unbound Weekly | Flagship magazine | `unboundweekly-2026.01-preseason issue.pdf` |
| Ballad of Broken Hearts | The Ballad Crier | Newspaper | `BALLAD CRIER 26.01 - preseason edition.pdf` and `BrokenHearts_Primer.pdf` |
| 9-5 | The Stampede | Newspaper | `The Stampede 2026.01 -Preseason Edition.pdf` and `9-5 fantasy football league - 2026 primer.pdf` |
| Rocky Top Rumble | The Volunteer Voice | Newspaper | `The_Volunteer_Voice_2026_Preseason_Mockup.pdf` and `Rocky_Top_Rumble_2026_Primer_Rev3.pdf` |
| SEC Dynasty | The Saturday Standard | Newspaper | `The_Saturday_Standard_SEC_Dynasty_2026.pdf` |
| Best Characters Dynasty | To be established | Newspaper | No source supplied yet |
| Don't Tell My Wife I'm In This | To be established | Newspaper | No source supplied yet |

The Ironbound Weekly and Unbound Weekly are equal flagships. Both require
magazine-scale analysis, prominent lineup efficiency, deep division coverage,
schedule-disparity context, and cumulative franchise history.

## Common weekly research packet

Every publication should receive verified inputs for the scoreboard, standings,
power movement, lineup efficiency, Manager of the Week, Bench MVP, Bad Beat,
Escape Artist, a single legal start/sit change that would have reversed a
result, waiver impact, additions and drops, trades, weekly records, and the next
slate. All-play belongs as supporting evidence for Bad Beat, Escape Artist, and
schedule analysis rather than as a freestanding department.

The weekly dossier may carry a verified MVP Card Result. The separate MVP-card
automation remains responsible for selecting a template and producing the card.

## Historical cycle

Finalized editions should be retained as editorial memory. During the season,
each weekly issue builds on the prior issues. The same archive will later feed
a season wrap-up, one rookie-draft preview, and one preseason edition. It also
makes multi-year Trade Afterlife stories and season/all-time Record Watch
possible.

## Power-ranking models

The ranking desk must select its model from the league configuration.

- Every dynasty league uses the same editorial model as The Ironbound Weekly
  and Unbound Weekly. Starter strength and projected scoring lead the analysis;
  current dynasty value, playoff and title probability, roster balance,
  schedule context, and future-pick value remain visible supporting evidence.
  The final published order remains an editorial synthesis, not a hidden
  arithmetic replacement.
- Every redraft league uses only three inputs: the submitted-lineup projection,
  the best legal starting-lineup projection, and the current win-loss record.
  The research dossier provides an equal-rank consensus and exposes all three
  component ranks for review.

The collector uses a single daily Dynasty Daddy player-value pull and a single
weekly Sleeper projection pull for all leagues. It stores source status and the
trimmed inputs alongside each dossier so a missing or changed external source
cannot silently alter a published ranking.

## League-specific findings

- Unbound currently has four live Sleeper divisions: Hammer, Anvil, Crucible,
  and Forge. Division strength and schedule disparity are core flagship inputs.
- SEC currently has East and West divisions and an offense-plus-IDP lineup.
  Defensive performance must remain visible rather than being folded into a
  generic bench calculation.
- Ballad of Broken Hearts, 9-5, and Rocky Top currently enable a weekly league-
  median matchup in Sleeper.
- Rocky Top has six managers. Its playoff home-field advantage remains active:
  the higher seed receives one point per seed difference, capped at five points.
  The postseason dossier must show both the unadjusted score and the home-field-
  adjusted score so the published result can be verified.
- Ironbound Sixteen uses Sleeper league ID `1314016187998294016`, supplied by
  the commissioner after the source audit, and is enabled in the configuration.

## Data-versus-copy boundary

The automated desk organizes facts and candidates under the established
sections. It does not invent headlines, declare a final editorial angle, or
publish finished prose. Those decisions belong to the publication phase after
human review.
