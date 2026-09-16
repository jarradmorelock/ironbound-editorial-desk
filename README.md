# Ironbound Editorial Desk

An isolated, read-only Sleeper data pipeline for the Ironbound family of
weekly fantasy-football publications.

The project turns verified league data into editorial research dossiers. It
does not publish magazines, create MVP cards, or post to Discord. Email delivery
is opt-in and uses repository secrets.

## Safety boundaries

- Sleeper is accessed through its public read-only API.
- NFL game dates, weekly box scores, and late-play context come from the public
  read-only [nflverse data releases](https://github.com/nflverse/nflverse-data).
- The existing transaction and Discord reporters are not imported or changed.
- GitHub runs the complete collection Tuesday at 9:17 p.m. Eastern and a
  delta-only safety check Wednesday at 5:17 a.m. Eastern.
- Generated output is ignored by Git. Complete and supplemental packets are
  uploaded only as temporary workflow artifacts.
- Gmail credentials are read only from GitHub Actions secrets and are never
  committed to the repository.

## Phase 1 output

Each publication-enabled league receives:

- a raw, timestamped weekly snapshot;
- a machine-readable weekly dossier;
- a human-readable Markdown dossier; and
- a shared MVP result that a separate card workflow can consume later.

Leagues marked as data-only still receive a raw snapshot and machine-readable
analysis, including ranking inputs, but no publication dossier or Markdown
draft. Don't Tell My Wife I'm In This is intentionally configured this way.

The first metric layer covers matchup results, supporting all-play context,
league-median results where enabled, lineup efficiency, points left on the
bench, Manager of the Week, Bench MVP, Bad Beat, Escape Artist, result-flipping
start/sit decisions, waiver-impact candidates, weekly records, and named
division performance. Every publication also receives an NFL game-day timeline
that identifies Thursday positive and negative projection swings, Thursday
scoring edges that ultimately supplied the winning margin, Monday lead changes,
the closest finishes involving Monday starters, and noteworthy late NFL plays
linked to fantasy starters. Every dossier also separates official standings
from a transparent data power ranking. The eventual publication archive will
add the prior issue's editorial ranking and week-to-week movement without
treating the formula as the final editorial opinion.

Ranking inputs are fetched once per run and then trimmed to the players in each
league. Sleeper supplies weekly projections scored against that league's own
settings. Dynasty Daddy supplies current-season starter ranks and dynasty
market values. If either optional source is unavailable, collection continues
and the dossier clearly marks the missing input.

Ironbound Weekly and Unbound Weekly receive an additional flagship Sleeper
sourcebook. For those two magazines only, each run collects all 18 schedule
weeks and transaction rounds, every current-league draft and draft-pick record,
the winner and consolation brackets, the future-pick ledger, next-week
projections, and expanded player availability and depth-chart fields. The
human-readable email attachment turns those sources into:

- starter-by-starter box-score and projection evidence;
- team and division strength-of-schedule comparisons;
- current-season team, player, and positional record watches;
- a decoded seven-day activity report plus the season trade file;
- draft first-round archives and playoff bracket history;
- next-week matchup projections; and
- injury, practice, and roster-availability flags.

The flagship versions retain a larger candidate list and a calendar of all
Wednesday, Thursday, Friday, Saturday, and Monday starters. Newspaper packets
receive a shorter version of the same timing evidence. Sleeper remains
authoritative for the fantasy points; nflverse supplies the NFL weekday, game,
real-life stat line, and late-play description. A missing optional nflverse
file does not stop the rest of the weekly collection.

- Dynasty leagues use the Ironbound/Unbound editorial model: starter strength
  and projected scoring lead, with dynasty value, playoff and title
  probabilities, roster balance, schedule context, and future-pick value kept
  as distinct evidence.
- Redraft leagues use only submitted-lineup projection, optimal starting-lineup
  projection, and win-loss record. Their automated consensus is the equal
  average of those three league-relative ranks.

The source primers and publications have been audited into
`config/publications.json`; see `docs/source-audit.md` for the resulting brand
and editorial map. Cross-season and all-time records, Giant Killer based on
prior published expectations, trade-afterlife trees, and persistent editorial
memory still require a finalized-publication archive and are the next data
layer.

## Chronicle data branch and live pulse collection

Editorial Desk v2 stores durable generated history on the dedicated
`chronicle-data` branch. Application code continues to run from `main`; the
data branch contains only Chronicle state such as event ledgers, registries,
coverage metadata, manifests, and short-lived diagnostic comparison state.
Normal automation never force-pushes `chronicle-data`.

The lightweight Chronicle collector is intentionally separate from the full
editorial collector. It does not fetch Dynasty Daddy, nflverse play-by-play,
full-season flagship schedules, drafts, brackets, or other expensive magazine
enrichment. A pulse fetches the Sleeper player directory once globally, then
only the current league/roster/matchup/transaction state needed to observe
transactions, lineup changes, reserve changes, and relevant player-status
transitions. A player-status transition is stored once in the cross-league NFL
player stream even when that player appears in multiple fantasy leagues.
League-specific reactions remain league events.

During the season, `.github/workflows/editorial-desk-chronicle.yml` runs one
baseline collection at 6:17 a.m. Eastern every day and three additional pulses
at 12:17 p.m., 5:17 p.m., and 9:17 p.m. Eastern from Wednesday through Sunday.
All Chronicle writers share a serialized concurrency group. The workflow
checks out application code and `chronicle-data` separately, runs the test suite
before mutation, commits only when data changed, and refuses force pushes.

Manual collection is available with:

```bash
python -m editorial_desk chronicle-collect \
  --config config/leagues.json \
  --week 2 \
  --chronicle-root ../chronicle-data
```

`--finalize-matchups` is intentionally opt-in. Ordinary intraweek pulses never
write an in-progress score as `MATCHUP_FINAL`; the Tuesday completed-period
workflow will become the normal finalization path in the later integration
phase.

## Historical Chronicle bootstrap and identity repair

Historical backfill walks each configured Sleeper league through its
`previous_league_id` renewal chain and writes durable matchup, transaction,
draft, traded-pick, and playoff evidence into the same Chronicle that live
collection continues to update. Backfill is therefore a seed operation, not a
static historical snapshot. New matchup events automatically change rebuilt
all-time records, streaks, and head-to-head totals.

Run a bootstrap with:

```bash
python -m editorial_desk chronicle-backfill \
  --config config/leagues.json \
  --chronicle-root ../chronicle-data
```

The newest/current season is handled conservatively. Backfill may preserve
completed transactions from the active week, but it only emits
`MATCHUP_FINAL` events through the most recently completed NFL week. Historical
health, practice, projection, or intraweek lineup transitions are never
invented when Sleeper does not preserve them.

Dynasty history follows a stable franchise identity. A team-name change is an
alias, not a new franchise. If ownership changes and roster-slot/owner evidence
cannot prove continuity, the backfill records an ambiguity and returns nonzero
instead of guessing. Redraft history follows stable Sleeper manager identity;
ownerless/orphan slots remain separate and are not treated as one fictional
manager.

The canonical registry is `registry/identity.json`. For easier review, every
registry write also produces deterministic projections in
`registry/franchises.json`, `registry/managers.json`, and
`registry/ambiguities.json`. Manual dynasty continuity corrections are entered
as an `overrides` row in the canonical registry with `league_key`, `season`,
`roster_id`, `franchise_key`, and a human-readable `reason`. After editing the
registry, rerun `chronicle-backfill` so the previously ambiguous season gets a
stable mapping, then rebuild derived history if necessary.

Use these commands to inspect/rebuild without refetching source history:

```bash
python -m editorial_desk chronicle-identity-report \
  --chronicle-root ../chronicle-data

python -m editorial_desk chronicle-materialize \
  --chronicle-root ../chronicle-data
```

Materialization reads only the Event Ledger plus the identity registry. It does
not increment yesterday's cached all-time totals. Derived history can therefore
be regenerated after an identity correction while leaving the original source
events intact. Source corrections use explicit superseding events rather than
silently deleting the old audit record.

## Local dry run

Create a real configuration from the example, then run:

```bash
python -m pip install -r requirements.txt
cp config/leagues.example.json config/leagues.json
python -m editorial_desk validate-config --config config/leagues.json
python -m editorial_desk collect --config config/leagues.json --week 1
```

All eight current league IDs are enabled for collection in the example
configuration. Seven feed publications; Don't Tell My Wife I'm In This remains
data-only. No credential is required to read public Sleeper league data.

## GitHub weekly delivery

The scheduled workflow automatically identifies the most recently completed
regular-season NFL week. It does not assume that Sleeper's current week is the
week that just ended, and it will not send anything before every NFL game in
the reviewed week has a final score.

At 9:17 p.m. Eastern every Tuesday, GitHub collects and emails the full set of
publication dossiers. It saves that exact collection as the comparison
baseline. At 5:17 a.m. Eastern every Wednesday, GitHub collects again and
compares the result with the saved Tuesday packet. The Wednesday email contains
only newly available source data, score corrections, newly calculable features,
and new NFL game-day evidence. If nothing new is found, no second email is sent.
If the Tuesday baseline cannot be restored, the backup refuses to send a full
duplicate packet.

The slight offset from the top of the hour reduces the chance of a GitHub
Actions scheduling delay. Both schedules use the `America/New_York` timezone,
so they remain 9:17 p.m. and 5:17 a.m. across daylight-saving changes.

## Manual GitHub run

Open **Actions -> Editorial desk weekly delivery -> Run workflow**. Validation is the
default. Select **collect**, enter the week, and enable **send_email** to deliver
one email containing the seven publication Markdown dossiers. The data-only
league remains excluded from the email.

## Email secrets

In the GitHub repository, open **Settings -> Secrets and variables -> Actions**
and add these repository secrets:

- `IRONBOUND_GMAIL_ADDRESS`: the Gmail address that sends and receives the packet;
- `IRONBOUND_GMAIL_APP_PASSWORD`: the Google app password, not the normal account
  password. Spaces in Google's displayed app password are accepted.

For the current setup, `IRONBOUND_GMAIL_ADDRESS` should be
`the.ironbound.ffl@gmail.com`. Never place the app password in a configuration
file, commit, issue, or chat message.
