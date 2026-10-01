# Ironbound Research Packet and 25-Page Template Alignment

## Purpose

Align the Ironbound flagship research packet with the approved 25-page editable magazine template so each recurring data-backed slot has a corresponding research field and readiness check. The packet remains a factual, pre-editorial dossier. It supplies verified facts, ranked candidates, source status, and editorial handoff guidance; it does not write publication prose, render the PowerPoint, or generate artwork.

## User-approved requirements

- Use the 25-page sequence in `output/templates/ironbound-weekly-template-readme.md`, including separate manager-honors, player-honors, and Rookie Watch pages.
- Each of the three results pages contains two game reports. The two featured games are reported in feature modules; the six remaining completed matchups occupy the three two-report pages.
- Mark a matchup as divisional only when the supplied league/division data verifies that both teams belong to the same division. Missing division data must remain explicit rather than inferred.
- Manager of the Week spans the page in the template. Research must supply its selected winner and supporting facts. Most Efficient Manager must exclude that winner.
- Bad Beat and Escape Artist must not use the same manager or matchup. Prefer a manager with a winning record for each: Bad Beat favors a high-scoring loss; Escape Artist favors a narrow win in a low-scoring game. Rank and explain candidates without inventing an unapproved hard cutoff. If record/history evidence is missing, mark the candidate for manual verification.
- Provide weekly overall Player of the Week plus one distinct starter-only QB, RB, WR, and TE positional award. A positional award cannot repeat the overall winner.
- The player-honors page needs cumulative Top 3 fantasy-scoring players at QB/RB/WR/TE, with player, cumulative points, and current fantasy team.
- Rookie Watch is its own page. Keep Rookie of the Week eligible for starters, bench, and taxi; separately supply Top Rookie Starter and Rookie Disappointment. Include a weekly Top 5 with stat line, fantasy points, fantasy team, and fantasy rookie-draft pick. Do not require NFL team in the magazine display. Also supply a cumulative rookie leader at each core position when applicable, with cumulative fantasy points and fantasy team.
- Include Benchwarmer of the Week and Free Agent of the Week. A free agent has `UNROSTERED` as fantasy-team display value.
- Cumulative manager efficiency Top 3 and cumulative manager points-scored Top 3 must be season totals through the reviewed week. They are not interchangeable with weekly leaderboards or highest single-week scores.
- Supply explicit division-level context and the hardest/easiest remaining schedule evidence used by the Division of Death page.
- The anvil/football and crown/throne artwork are fixed recurring template assets. Weekly stats, copy, callouts, and replaceable art stay as distinct editable/movable presentation elements; the research packet does not generate or flatten them.
- Preserve missing-input states. In particular, do not substitute current/postgame projections for a verified pregame projection capture.

## Canonical editorial spine

The packet's canonical spine is 25 pages, in this order:

1. Cover
2. Contents
3. Lead-player art opener
4. Lead-feature article
5–7. Week results, two reports per page
8. Secondary feature
9. Usage Desk
10. Roster Health
11. Transaction Desk
12. Manager Honors and cumulative team boards
13. Player Honors and cumulative positional player boards
14. Rookie Watch
15. Playoff Forecast
16. Power Rankings
17–20. Four Power Board pages, four teams per page
21. Pressure Points
22. Full Slate
23. Division of Death / Road Ahead
24. Week Ahead
25. Sources and Model Notes

The spine, report allocations, and displayed section names must be covered by tests so future packet changes cannot silently regress to the prior 22-page layout.

## Packet contract changes

### Game reports and division evidence

Each completed matchup record must carry the existing scoreboard/stat evidence plus a division classification state: verified divisional with a division label, verified non-divisional, or unavailable/manual verification. The same source of division identity should power division summaries; do not infer membership from team names.

### Manager honors

- Keep Manager of the Week as the existing five-component research result.
- Choose Most Efficient Manager from the lineup-efficiency order after excluding Manager of the Week.
- Keep top weekly score as a weekly honor and retain a separate cumulative points-scored board.
- Compute cumulative manager points by summing each franchise's finalized/current-week points through the packet week, de-duplicating franchise/week records.
- For Bad Beat and Escape Artist, create ranked candidate lists using entering records and completed matchup data. Apply the different-manager/different-matchup constraint when selecting candidates. Bad Beat prioritizes winning-record losses and higher losing scores. Escape Artist prioritizes winning-record wins, smaller winning margins, and lower-scoring games. If the constraints or history prevent a supported selection, return a manual-review/unavailable state instead of selecting overlapping or unsupported winners.
- Preserve one optional rotating-award slot as editor-selected. Projection-dependent awards require the existing verified same-week pregame capture and must remain unavailable when that provenance is absent.

### Player honors and rookie research

- Preserve five distinct weekly awards: overall and QB/RB/WR/TE starter-only leaders. For each positional slot, select the best eligible starter other than the overall winner.
- Add cumulative player fantasy-point Top 3 lists for QB/RB/WR/TE, grouped by player across completed weeks and associated with the current fantasy roster for display.
- Add Rookie of the Week, retaining roster status including `STARTED`, `BENCH`, and `TAXI`; add Top Rookie Starter as the highest-scoring started rookie.
- Add Top Rookie Disappointment as a ranked editorial candidate list. Use low fantasy output, starter status, fantasy rookie-draft cost, and underperformance against a verified pregame projection when one exists. Missing projection evidence must not be treated as zero or otherwise fabricated; availability should explain the limitation. No hard qualification threshold is added without editorial approval.
- Preserve the Top 5 rookie table with fantasy rookie-draft context and fantasy-team ownership. NFL-team metadata may remain in the raw source snapshot but is not required in the publication field/display.
- Add cumulative rookie scoring leaders, one per QB/RB/WR/TE when eligible, with cumulative points and current fantasy team.
- Pass through Free Agent of the Week using league scoring and identify the fantasy team display as `UNROSTERED`.

### Division outlook and readiness

The packet must expose division summary inputs needed for the Division of Death page and the full remaining-strength-of-schedule ordering needed to call out the hardest/easiest teams. Missing division or schedule inputs produce a specific readiness warning. Existing forecast/rankings inputs remain owned by the external Ironbound Power Rankings handoff, with matching season/week and asset provenance checked.

Validation must distinguish:

- required packet structure and source evidence that block research completeness;
- optional editorial candidates, such as a rotating award, that can be absent with an explicit availability reason;
- external Tuesday inputs/assets awaiting delivery; and
- editorial work that remains intentionally human-authored (headlines, article prose, callout wording, visual selection).

## Non-goals

- Do not edit or replace files under the project `sources/` directory.
- Do not change the official power-ranking engine, playoff simulation, ranking graphics, or schedule.
- Do not create or modify a PowerPoint/PDF issue in this change.
- Do not generate, redraw, or embed text into recurring or issue-specific artwork.
- Do not infer projections, historical results, divisions, or award cutoffs that the sources do not establish.
- Do not push, open a pull request, or otherwise publish the local work.

## Acceptance criteria

1. Packet spine is exactly the approved 25-page order, with pages 12, 13, and 14 separate.
2. Validation detects a missing/incorrect spine and a mismatch in the required game-report allocation.
3. Every completed matchup has an explicit divisional status; confirmed divisional labels agree with supplied league division data.
4. Most Efficient Manager differs from Manager of the Week.
5. Bad Beat and Escape Artist selections do not share a manager or matchup, respect the stated priority order, and become manual review when required history is absent.
6. Overall/positional weekly player awards are distinct and carry the team, fantasy points, and stat-line fields needed by the template.
7. Player-season and rookie-season positional tables use cumulative fantasy points through the packet week, correctly de-duplicate historical and current-week data, and include current fantasy team.
8. Rookie of the Week preserves bench/taxi eligibility; Top Rookie Starter is starter-only; Rookie Disappointment exposes ranked evidence and does not invent a projection comparison.
9. Rookie Top 5 carries the fantasy rookie-draft pick and fantasy team, without requiring NFL team in publication output.
10. Free Agent of the Week is exposed with the `UNROSTERED` display value.
11. Required division and schedule-strength evidence appears with explicit source/readiness status.
12. Projection-dependent awards stay unavailable without a verified pregame projection snapshot.
13. Focused tests and the full editorial-desk test suite pass. No synced source material or magazine render is changed.
