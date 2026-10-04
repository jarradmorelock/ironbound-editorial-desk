# Locked Weekly Newspaper Feature Contracts

Date: 2026-09-16
Status: Approved design checkpoint companion
Parent design: `2026-09-16-editorial-chronicle-story-desk-design-checkpoint.md`

## Purpose

This document locks the recurring editorial/data contracts for the weekly newspaper publications. These requirements are derived from the actual preseason and Week 1 papers and from publication behavior already established in the Editorial Desk.

These contracts are not suggestions. Implementation must preserve the facts required to support these sections unless an upstream source is genuinely unavailable. The final paper may vary in layout and may elevate a different lead story each week, but the underlying feature packet must remain coherent and consistent.

The five newspaper publications covered here are:

- The Ballad Crier
- The Stampede
- The Volunteer Voice
- The Saturday Standard
- The Hollywood Beat

Ironbound Weekly and Unbound Weekly are governed by the separate Magazine Story Desk model and are not newspaper-contract publications.

## Shared newspaper rule

All weekly newspapers use the same normalized factual spine. The code computes facts once and publication profiles rename and organize those facts into each paper's theme.

The newspaper compiler must never calculate separate contradictory versions of the same metric simply because two papers use different names for it.

Examples:

- a matchup-flipping bench decision is one calculation that may render as `Weekly Rounds`, `Portal Film Room`, or `Cutting Room Floor`
- waiver impact is one calculation that may render as `Waiver Star`, `Portal Commitments`, or `Casting Call`
- roster health is one factual feed that may render as `Ward Report`, `Health Board`, `Depth Chart Wire`, or `Production Delays`

## Weekly newspaper factual baseline

Every newspaper packet should include the applicable form of these facts:

- completed matchup scores
- winner, loser, margin, and closest/largest-margin context
- league-median result when the league uses median scoring
- official standings and record
- points scored
- forward-looking projection/ranking inputs used by that publication
- ranking or poll movement from the prior issue when applicable
- lineup efficiency
- optimal legal lineup
- points left on the bench
- matchup-flipping start/sit decisions
- manager-decision evidence
- Manager of the Week candidate/result
- Bad Beat
- Escape Artist where applicable
- bench leader / Benchwarmer / Bench MVP
- Rookie of the Week
- Free Agent of the Week
- position leaders
- waiver/free-agent additions, drops, trades, and FAAB when available
- waiver-impact evidence
- general player health/status
- Sleeper IR/reserve state
- division metrics when the league has divisions
- Record Watch
- historical matchup context from the Chronicle when relevant
- next-week matchups
- NFL game-window/timeline context sufficient to explain Monday-night or late-window swings

Not every publication must print every baseline item every week, but the feature packet must expose the data required by that paper's contract.

## Readiness contract

Each newspaper packet must include a machine-readable and human-readable readiness result.

Required departments must report one of:

- `ready`
- `ready_no_items` when data was successfully collected but there is nothing to report
- `unavailable` only when an upstream dependency actually failed or data cannot be obtained

A healthy roster is `ready_no_items`, not `unavailable`.

A week with no result-flipping bench decisions is `ready_no_items`, not a missing feature.

The compiler must not silently omit a required department because no qualifying event occurred.

## Issue phases

Contracts are issue-phase aware.

### Weekly regular-season phase

Contains the recurring weekly feature packet described below for each paper.

### Preseason/draft phase

May additionally require:

- draft board
- ADP reach/value analysis
- keeper cost/value
- positional roster strength
- roster age
- preseason projection composites
- rookie/recruiting draft analysis
- future-pick capital
- season simulation where that publication uses it

### Offseason/postseason phase

May reuse Chronicle, draft, transaction, dynasty-market, and season-summary data without forcing regular-season departments into an offseason issue.

---

# The Ballad Crier

## Editorial identity

Medical / hospital-rounds framing. The paper "rounds on every team to report their vitals." Thematic language should organize factual output without changing the underlying calculations.

## Locked weekly departments

### Lead / weekly diagnosis

The packet must identify material suitable for a lead story, especially:

- closest finish
- largest comeback
- highest score
- largest margin
- late-game or Monday-night reversal
- important health-driven swing

This is deterministic lead material, not a magazine-style Story Candidate Engine.

### Week Cardiogram / scoreboard

Required inputs:

- every team's final score
- matchup pairings
- win/loss result
- weekly median line when applicable
- above/below median result
- final H2H plus median record impact

### Final Monitor

Required inputs:

- compact final matchup list
- winner and loser
- final score

### Weekly Rounds / lineup autopsy

Required inputs:

- all legal bench-to-starter substitutions that would have flipped a matchup result
- started player and bench player
- actual points for each
- hypothetical corrected final score
- whether the loss becomes a win

This calculation must not be reduced to generic lineup efficiency. It is specifically a result-flipping decision analysis.

### Official Standings

Required inputs:

- official record including median decisions where league rules use them
- points scored
- lineup efficiency
- current ordering/seeding rules

### Rankings Wire

Required inputs:

- the paper's forward-looking data-power projection
- submitted/projected lineup total
- optimal/projected lineup total as defined by the model
- rank movement from prior issue when available

This is distinct from the official standings.

### Rounds Report / weekly honors

Required outputs:

- Manager of the Week
- Bad Beat
- Escape Artist
- Benchwarmer
- Rookie of the Week
- Free Agent of the Week

### Position Leaders

Required outputs for the league's applicable positions, including at minimum:

- QB
- RB
- WR
- TE
- DEF/DST when used

The packet must identify whether the position leader was started or benched.

### Waiver Star

Required inputs:

- player/team
- transaction type
- FAAB cost if any
- weekly fantasy production
- relationship to final margin when meaningful

### Ward Report

Required inputs:

- IR/reserve players
- Out
- Doubtful
- Questionable
- other meaningful status labels
- per-team health counts
- team(s) carrying the largest ward
- status changes since prior collection when available

General health/status and reserve state are required. Deep practice/injury-history enrichment is not required for this newspaper tier.

### Record Watch

Required inputs:

- weekly high/low score
- largest/closest margin
- season records
- Chronicle-backed historical records when relevant

### Next Card

Required inputs:

- next week's matchups
- current record/standing context
- projection context where available

## Locked preseason/draft departments

- Draft Desk
- keeper value / Keeper Heist
- draft reach and value board
- full draft board context
- market event / news-driven ADP context
- Streamers' Pact for teams carrying no D/ST where relevant

The existing papers are not to be retroactively rebuilt. These requirements govern future output.

---

# The Stampede

## Editorial identity

9-to-5 / workweek / Dolly Parton framing. The paper should retain its colorful workday language while using the common factual spine.

## Locked weekly departments

### Scoreboard and median result

Required inputs:

- every matchup and final score
- median result where league settings use league-median scoring
- weekly standings consequences

### Standings and power movement

Required inputs:

- official record
- points
- prior rank/poll position
- current rank/poll position
- movement

### Lineup Efficiency and Manager of the Week

Required inputs:

- submitted points
- optimal legal points
- points left on bench
- efficiency percentage
- manager-decision evidence used by the Manager of the Week selection

### Bad Beat and Escape Artist

Required inputs:

- highest-scoring loss / strongest bad-beat candidate
- low-scoring or below-median win / Escape Artist candidate where rules make that meaningful

### Bench MVP and result-flipping decision

Required inputs:

- highest relevant bench performance
- all matchup flips caused by one legal bench substitution

### Waiver / transaction desk

Required inputs:

- additions
- drops
- trades
- FAAB
- subsequent weekly production
- result relevance where measurable

### The Week's Heavy Lifting

This is a locked Stampede-specific feature.

The collector must preserve real football stat lines, not only fantasy points, to identify standout work in categories such as:

- rushing attempts
- rushing yards
- rushing touchdowns
- receiving volume
- receiving yards
- receiving touchdowns
- passing volume / passing yards / passing touchdowns where editorially useful

The feature should be capable of highlighting the week's most substantial rushing and passing/receiving workloads rather than merely repeating the fantasy-points leaderboard.

### Health Board / Mystery Mine

Required inputs:

- current player health/status
- IR/reserve state
- per-team health uncertainty
- status changes where available

### Record Watch

Required inputs:

- weekly/season records
- Chronicle-backed historical context when useful

### Next Shift

Required inputs:

- next week's matchups
- current records
- projection context

## Locked preseason/draft departments

- Rankings Wire
- The First Shift
- The Value Board
- The Paper Favorite
- The Stampede Board
- Why'd You Come in Here Lookin' Like That? / reach watch
- I Will Always Love You / notable reaches
- The Bargain Store
- Coat of Many Colors / positional strength
- Old Flames / keeper value
- The Little Engine That Could / youth-development roster context
- Mystery Mine / Health Board
- season predictions when simulation inputs are available

A Week 1 Stampede PDF was not part of the September 16 audit set, so regular-season requirements are locked from the established publication config, league primer, and preseason identity. They may be refined when a regular-season Stampede issue is reviewed, but should not lose any requirement above.

---

# The Volunteer Voice

## Editorial identity

Tennessee / family rivalry / Rocky Top framing. It is a shallow family league, so the packet should emphasize clear weekly decisions and rivalry context without trying to manufacture magazine-scale narratives.

## Locked weekly departments

### Lead Story / weekly aftermath

Required material should surface:

- high score
- largest margin
- closest or most dramatic result
- meaningful late-game comeback
- family-rivalry context when supported by Chronicle history

### Official Table

Required inputs:

- record
- points
- seed/order
- league-median effects where used

### Median line

Required inputs:

- weekly median
- teams above/below
- second result for each team

### Rankings Wire

Required inputs:

- forward-looking data-power submitted projection
- prior/current rank
- movement

### Decision Desk / The Call That Won the Week

This is a locked Volunteer Voice-specific calculation.

Required inputs:

- manager who won
- started player
- plausible alternative bench player
- projection relationship
- actual scoring relationship
- point swing
- final victory margin
- evidence that the decision materially protected or caused the victory

This is distinct from overall lineup efficiency.

### Volunteer Voice Honors

Required outputs:

- divisional MVP nominees
- gold-foil MVP, defined as the highest-scoring STARTED player among divisional MVPs
- Manager of the Week
- Benchwarmer
- Rookie of the Week
- Free Agent of the Week

MVP identification is data/editorial packet work only. The actual trading-card images are produced separately.

### Efficiency Board

Required inputs:

- submitted points
- optimal legal points
- efficiency percentage
- points left on bench

Efficiency may include losing teams and must remain independent from Manager of the Week.

### Division Pulse

Required inputs:

- division average score
- division head-to-head record
- gap between divisions
- divisional standings/context where useful

### Week Notebook

Required candidate facts:

- Bad Beat
- Escape Artist
- Waiver Star
- Bench Blast

### Record Watch

Required inputs:

- weekly high score
- margins
- season record
- historical family rivalry / manager-vs-manager facts when relevant

### Next-week Scouting Report

Required inputs:

- upcoming matchup card
- current seed/record
- projection context
- Chronicle rivalry context as supporting color when available

## Special league rule awareness

The contract must remain aware of Rocky Top's league-specific structures, including league-median scoring and any established playoff/home-field rules that affect published standings or postseason previews.

---

# The Saturday Standard

## Editorial identity

SEC college-football framing. Offense, IDP defense, divisions, recruiting, and transfer-portal language are structural parts of the publication, not decorative renames.

## Locked weekly departments

### The Saturday Scoreboard

Required inputs:

- all matchup final scores
- margin
- high score
- low score
- largest margin
- closest finish
- Bad Beat
- Escape Artist
- division edge

### Opening Statement / game feature material

Required deterministic story material:

- strongest weekly team performance
- largest margin
- most efficient high-scoring performance
- Monday-night or late-window comeback
- projection overperformance that materially changed a matchup

### East and West Division Pulse

Required inputs:

- division average score
- head-to-head division record
- current standings/poll context

### East and West Power Polls

Required inputs:

- current rank in each division
- previous rank
- movement
- record
- points

### Lineup Efficiency

Required inputs:

- submitted points
- optimal legal points
- points left on bench
- efficiency percentage

### Portal Film Room

Required inputs:

- legal bench substitutions that would flip a matchup
- player points
- hypothetical final
- team/result affected

### Portal Commitments

Required inputs:

- waiver/free-agent player
- acquiring program
- fantasy points
- FAAB

### Saturday Honors

Required outputs:

- East MVP
- West MVP
- gold-foil designation for the higher-scoring divisional MVP
- Manager of the Week

MVP candidates must be the highest-scoring STARTED player in each division. Card art remains outside the Editorial Desk.

### Position Board

The collector must support offensive and IDP positional leaders as first-class data.

Expected positions should include, as league settings support them:

- QB
- RB
- WR
- TE
- LB
- DL
- DE
- DT
- DB
- CB
- NT

Each leader must retain team, status (started/bench), and points.

### Saturday Desk

Required outputs include:

- Benchwarmer
- Rookie of the Week
- Free Agent of the Week
- Bad Beat

### Dynasty Market Board

Required inputs:

- authoritative dynasty market values when source is available
- top rostered league assets
- team ownership

The packet must label the source and not fabricate values when unavailable.

### Transfer Portal Dispatch

Required inputs:

- trades
- waiver/free-agent adds
- players/picks sent and received
- completed timestamp

### Recruiting Desk

Required inputs:

- rookie draft board
- offensive and IDP rookie positions
- projected immediate scoring
- recruiting-class totals
- first IDP selection
- top class / immediate-impact class / other factual superlatives

### Recruiting / future-pick ledger

Required inputs:

- future picks owned
- traded future picks
- round/year
- original owner where available

### Next-week Slate

Required inputs:

- upcoming SEC-themed fantasy matchups
- divisional context
- standings/poll context

## IDP is non-negotiable

The Saturday Standard must never collapse the league into offense-only fantasy analysis. IDP production, IDP lineup decisions, IDP rookies, and defensive roster strength are first-class requirements.

---

# The Hollywood Beat

## Editorial identity

Film-industry / studio / box-office framing. The preseason and Week 1 papers establish a complete publication identity. The earlier "publication standard pending" state is obsolete and must be removed during implementation.

## Locked weekly departments

### The Box Office

Required inputs:

- all final scores
- winner/loser
- weekly median
- teams earning the median result

### The Marquee / Official Standings

Required inputs:

- official record including median result
- points
- current ordering

### Top Billing / First Cut / weekly lead material

Required deterministic inputs:

- biggest upset against preseason/current context
- largest margin
- highest score
- Monday-night or late-window comeback
- major collapse

Hollywood Beat does not get the flagship Story Candidate Engine. Its lead material is selected from deterministic weekly facts and publication context.

### Hollywood Board

Required factual slots should support at least:

- Top Billing
- Scene Stealer
- Plot Twist
- Bad Beat

The exact selected labels may evolve editorially, but the supporting facts must be present.

### Industry Page / Monday Night / Late Show

Required inputs:

- score entering final game window
- players remaining
- points scored in late game
- projection delta when available
- final result and margin

### For Your Consideration / weekly honors

Required outputs:

- Scene Stealer
- Best Supporting Act
- Manager of the Week
- Bench MVP
- Rookie of the Week
- Free Agent Watch
- position leaders

### Cutting Room Floor

Required inputs:

- result-flipping start/sit decisions
- started player
- bench alternative
- hypothetical final

### Studio Efficiency

Required inputs:

- submitted points
- optimal legal points
- efficiency percentage
- points left unused

### Casting Call

Required inputs:

- waiver/free-agent additions
- FAAB contract
- subsequent weekly scoring
- result relevance where measurable

### Production Delays

Required inputs:

- IR/reserve
- Out/Doubtful/Questionable where relevant
- team/player
- recent status change where available

### The Dailies / Backlot Reports

Required inputs may include concise notes on:

- significant trade volume
- unusual roster construction
- reserve problems
- notable league-wide changes

These are deterministic briefs, not magazine feature pitches.

### This Week's Bill

Required inputs:

- all next-week matchups
- one highlighted Double Feature when deterministic criteria support one
- standings/record context
- Chronicle history as supporting color where useful

## Locked dynasty/preseason departments

- Critics' Poll inputs
- Meet the Cast roster capsules
- top billing / supporting cast / production read / risk context
- rookie Casting Call
- Development Rights / future picks
- Studio Deals / major trades
- Production Delays
- future-capital context
- roster timeline / contender-rebuild framing

---

# Shared metric definitions that must remain stable

## Lineup efficiency

Lineup efficiency compares submitted points with the optimal legal active lineup. Taxi and IR/reserve players are excluded from the editorial optimal lineup when they are not legally startable.

## Result-flipping lineup decision

A result-flipping decision is a legal alternative lineup substitution that changes the matchup winner. It must show the actual starter, alternative player, point swing, and resulting hypothetical final.

## Manager of the Week

Manager of the Week is not simply highest score or highest efficiency. Each publication may frame the honor thematically, but the selection must be evidence-based and use the established manager-decision methodology. For Volunteer Voice, a documented result-changing decision is especially important.

## Bad Beat

Bad Beat identifies a strong losing performance based primarily on points and matchup context, with median context where applicable.

## Escape Artist

Escape Artist identifies a win achieved despite weak scoring context, especially a below-median victory in median leagues.

## Rookie of the Week

Rookie of the Week should identify the strongest rookie fantasy performance and explicitly record whether the rookie was started or benched.

## Free Agent of the Week

Free Agent of the Week should consider genuinely unrostered players, not merely rostered players absent from the current matchup.

## Waiver impact

Waiver impact should preserve transaction type, FAAB, player production, lineup status, and result relevance when measurable.

## Historical facts

All historical claims must be generated from Chronicle evidence. If historical coverage is incomplete, the output must say so rather than assume the available period equals all-time history.

# Newspaper consistency objective

The purpose of these contracts is not to make the papers look identical. It is to make them reliably themselves.

Each Tuesday packet should give the editors a complete, coherent set of facts already organized into the paper's established departments. The editors should not have to rediscover which sections exist, recalculate recurring features by hand, or notice after layout that a normal department disappeared.

The implementation goal is:

```text
raw collection
  -> normalized facts
  -> publication feature contract
  -> publication-ready weekly packet
  -> human editorial writing and design
```

# Locked decisions

The following newspaper decisions are approved and must not be weakened during implementation without explicit editorial approval:

- the five weekly newspapers are contract-driven
- each newspaper keeps its own established thematic department names and identity
- shared calculations are normalized and reused across papers
- weekly packets must be publication-ready rather than generic research dumps
- readiness must distinguish no qualifying items from genuinely unavailable data
- lineup-flip analysis is a first-class shared calculation
- game-window and Monday-night context is a first-class shared calculation
- health/status plus Sleeper IR/reserve is available to every newspaper
- Chronicle history is available to every newspaper as supporting context
- redraft history follows manager identity; dynasty history follows franchise identity
- The Ballad Crier keeps Cardiogram/Final Monitor, Weekly Rounds, Rankings Wire, Rounds Report, Ward Report, Waiver Star, Record Watch, and next-card support
- The Stampede keeps workweek-themed standings/power, lineup/awards, waiver/transaction, health, Record Watch, next-shift support, and The Week's Heavy Lifting using real football stat lines
- The Volunteer Voice keeps median scoring, Decision Desk, divisional/gold MVPs, efficiency, Division Pulse, Notebook awards, Record Watch, and next-week scouting support
- The Saturday Standard keeps offense and IDP as equal first-class data, divisional polls, Portal Film Room, Portal Commitments, Saturday Honors, offensive/IDP Position Board, Dynasty Market Board, Transfer Portal, Recruiting Desk, future picks, and next-week slate
- The Hollywood Beat keeps Box Office, Marquee, Hollywood Board, late-show context, weekly awards, Cutting Room Floor, Studio Efficiency, Casting Call, Production Delays, and next week's bill
- Hollywood Beat does not receive the Ironbound/Unbound Magazine Story Candidate Engine
- newspaper thematic framing must not change the underlying metric definitions
- existing published papers are not retroactively regenerated; these contracts govern future Editorial Desk output
