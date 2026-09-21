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
- Generated editorial output is ignored by Git. Complete and supplemental
  packets are uploaded only as temporary workflow artifacts.
- Durable Chronicle history lives on the dedicated `chronicle-data` branch.
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
division performance where the league actually has divisions. Every publication
also receives an NFL game-day timeline that identifies Thursday positive and
negative projection swings, Thursday scoring edges that ultimately supplied the
winning margin, Monday lead changes, the closest finishes involving Monday
starters, and noteworthy late NFL plays linked to fantasy starters. Every
dossier also separates official standings from a transparent data power
ranking.

Ranking inputs are fetched once per run and then trimmed to the players in each
league. Sleeper supplies weekly projections scored against that league's own
settings. Dynasty Daddy supplies current-season starter ranks and dynasty market
values. If either optional source is unavailable, collection continues and the
dossier clearly marks the missing input.

Ironbound Weekly and Unbound Weekly receive an additional flagship Sleeper
sourcebook. For those two magazines only, each run collects all 18 schedule
weeks and transaction rounds, every current-league draft and draft-pick record,
the winner and consolation brackets, the future-pick ledger, next-week
projections, and expanded player availability and depth-chart fields. The
human-readable email attachment turns those sources into:

- starter-by-starter **actual NFL box-score and usage evidence**, including completions/attempts, passing/rushing/receiving yards and touchdowns, catches/targets, offensive snap share, target share, carry share, and high-value opportunities when the relevant source is available;
- team and division strength-of-schedule comparisons;
- current-season team, player, and positional record watches;
- a decoded seven-day activity report plus the season trade file;
- draft first-round archives and playoff bracket history;
- next-week matchup projections; and
- a dedicated injury/roster-health section that merges Sleeper availability/IR state with nflverse official weekly injury-report fields, practice participation, injury designation, and report timestamp where available.

The flagship versions retain a larger candidate list and a calendar of all
Wednesday, Thursday, Friday, Saturday, and Monday starters. Newspaper packets
receive a shorter version of the same timing evidence. Sleeper remains
authoritative for fantasy points; nflverse supplies NFL weekday, game,
real-life stat line, snap/usage context, official weekly injury reports, and
late-play description. Flagship research packets use real NFL statistics as the
default language for player performance. Fantasy points remain available for
matchup totals, awards, lineup efficiency, and start/sit decisions where the
point swing matters to the fantasy result. A missing optional nflverse file does
not stop the rest of the weekly collection; the packet names the missing source
and identifies submitted starters whose stat line requires manual verification.

- Dynasty leagues use the Ironbound/Unbound editorial model: starter strength
  and projected scoring lead, with dynasty value, playoff and title
  probabilities, roster balance, schedule context, and future-pick value kept
  as distinct evidence.
- Redraft leagues use only submitted-lineup projection, optimal starting-lineup
  projection, and win-loss record. Their automated consensus is the equal
  average of those three league-relative ranks.

The source primers and publications have been audited into
`config/publications.json`; see `docs/source-audit.md` for the resulting brand
and editorial map. Chronicle supplies cross-season and all-time factual history.

## Chronicle data branch and live pulse collection

Editorial Desk v2 stores durable generated history on the dedicated
`chronicle-data` branch. Application code continues to run from `main`; the
data branch contains only Chronicle state such as event ledgers, registries,
coverage metadata, manifests, materialized history, backup receipts, and
short-lived diagnostic comparison state. Normal automation never force-pushes
`chronicle-data`.

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
All Chronicle writers share the `editorial-chronicle-writer` serialized
concurrency group. The workflow checks out application code and
`chronicle-data` separately, runs the test suite before mutation, commits only
when data changed, and refuses force pushes.

Manual collection is available with:

```bash
python -m editorial_desk chronicle-collect \
  --config config/leagues.json \
  --week 2 \
  --chronicle-root ../chronicle-data
```

`--finalize-matchups` is intentionally opt-in. Ordinary intraweek pulses never
write an in-progress score as `MATCHUP_FINAL`; the scheduled Tuesday workflow
performs the normal completed-week finalization before editorial generation.

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

## Magazine Story Desk

Ironbound Weekly and Unbound Weekly have an explicit Story Desk capability.
Newspapers do not. The Story Desk reads normalized weekly evidence plus the
pinned Chronicle revision and produces private `story_desk.json` and
`story_desk.md` planning artifacts. Candidates preserve evidence references,
historical coverage, objective signal components, cautions, headline concepts,
depth suggestions, and graphic ideas. A temporal sequence may be reported when
supported; unsupported motive or causation is not asserted.

Official Ironbound/Unbound Power Rankings and playoff odds remain owned by the
separate rankings workflow. Editorial Desk does not fetch, recreate, or
substitute for those outputs. The Tuesday handoff also carries Dynasty Daddy
usage, WAR, and cWAR context. These inputs may be supplied as publication-named
JSON files in a directory passed with
`--external-inputs-dir`, for example:

```bash
python -m editorial_desk collect \
  --config config/leagues.json \
  --week 7 \
  --chronicle-root ../chronicle-data \
  --chronicle-revision "$CHRONICLE_SHA" \
  --external-inputs-dir editorial-inputs
```

If no external input file is supplied, Story Desk still operates from Chronicle
and weekly evidence, but the flagship research contract marks Power Rankings,
playoff odds, Dynasty Daddy usage, WAR, and cWAR as
`AWAITING_TUESDAY_INPUT`. This is distinct from a collection failure. Story
Desk also does not collect images. Headline packages may include a text-only
suggested visual based on the supported story content, such as a rivalry image,
game-action photo concept, trade-chain graphic, workload chart, or record-card
overlay. No image URL, path, asset, or downloaded file is produced.

## Chronicle recovery, receipts, and retention

A Chronicle recovery ZIP contains permanent registries, ledgers, materialized
history, coverage, manifests, and backup receipts, while diagnostic/cache/temp
material is excluded. `BACKUP_MANIFEST.json` records the exact Chronicle
revision, schema versions, leagues, seasons, event counts, file sizes, and
SHA-256 checksums. The archive is validated before it is published or restored.

On the first Tuesday of each month in `America/New_York`, the normal Tuesday
email also carries one validated Chronicle ZIP unless a successful receipt for
that month already exists. After SMTP accepts the message, a permanent monthly
receipt records the Chronicle revision, archive checksum, and acceptance time.
If SMTP fails before acceptance, no receipt is written and the archive remains
eligible for retry. There is one unavoidable transport edge case: SMTP can
accept a message and the later receipt write can fail, which can cause a retry
to send a duplicate archive. The archive filename and checksum make that case
identifiable; the system does not claim stronger exactly-once semantics than
SMTP plus Git can provide.

Major Chronicle-affecting maintenance uses a pre-change backup gate. Protected
operations cannot reach their maintenance callback until a fresh backup is
created, validated against the exact revision, accepted by the delivery
callback, and receipted. Ordinary append collection is not treated as
destructive maintenance.

Diagnostic retention is separate from permanent history. The command below
removes only timestamped diagnostic files older than the selected window and
never prunes ledger/history/registry/coverage/manifests or backup receipts:

```bash
python -m editorial_desk chronicle-prune-diagnostics \
  --chronicle-root ../chronicle-data \
  --retention-days 30
```

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

## Flagship production research contract

Ironbound Weekly and Unbound Weekly now receive a deterministic
`flagship_research_packet.json` plus a matching Markdown reading packet. The
contract mirrors the approved production-manuscript requirements rather than
asking an LLM to discover the league story from scratch. It includes all eight
completed matchups, two editorial cover-feature slots plus six remaining game
writeups, actual NFL starter stat lines and usage signals, Injury & Roster
Health, Weekly Honors, Benchwarmer of the Week, Rookie Watch Top 5, running
season efficiency and team-score record boards, rotating-award candidates, and
Power Board evidence.

The contract deliberately separates three states:

- collected/deterministic facts;
- `AWAITING_TUESDAY_INPUT` for Power Rankings, playoff odds, Dynasty Daddy
  usage, WAR, and cWAR that arrive from the separate rankings/data workflow; and
- `MANUAL_VERIFY` when a required source or identity cannot be verified.

Cover selection, the rotating award choice, headlines, prose, context-box
wording, Power Board writeups, and art direction remain editorial/AI work after
the facts are validated. The emailed flagship Markdown is the exact validated
research artifact that will later feed the Word production manuscript.

Finalized Chronicle collection also stores one
`LINEUP_EFFICIENCY_FINAL` event per roster/week. This makes the running
season-to-date efficiency board durable instead of depending on temporary
GitHub Actions artifacts.

## Weekly reading packets

Each publication now has a `reading_packet.md` and one email attachment in this order:

1. **EDITOR'S BRIEF** — a plain-English account of the results and notable findings, targeted at 1–3 pages (capped at 1,200 words; sparse weeks are not padded).
2. **COMMISSIONER REQUESTS** — the existing Publication Readiness buckets for Ironbound/Unbound, including inputs already supplied. Newspapers show only explicitly identified, unresolved human requests; automated source failures remain coverage notes.
3. **STORY DESK** — for enabled magazines, candidates with resolved player/team/franchise names, readable facts, and historical coverage cautions. Unresolved identities are labeled for verification.
4. Newspaper named departments in contract order, summarized in prose, followed by an evidence-artifact guide.

The complete snapshot, detailed dossier, newspaper packet JSON, and Story Desk planning artifacts remain in the workflow artifacts for diagnostics. Email builds the reading packet from those structured artifacts and does not attach the raw dossier or a second raw Story Desk. `dossier.md` and `story_desk.md` remain detailed diagnostic views. This does not change Wednesday delta-only delivery.

Rocky Top Rumble / Volunteer Voice is explicitly non-divisional for publication purposes. `editorial_desk/publication_policy.py` suppresses division metadata and derived division features in publication payloads, including Official Table standings and nested evidence. Sleeper snapshots retain the original divisions. Re-enabling divisions requires an explicit change to that publication rule; Sleeper settings or a stale feature contract cannot enable them. Other publications retain their division coverage.

## GitHub weekly delivery

The scheduled workflow automatically identifies the most recently completed
regular-season NFL week. It does not assume that Sleeper's current week is the
week that just ended, and it will not send anything before every NFL game in
the reviewed week has a final score.

At 9:17 p.m. Eastern every Tuesday, the workflow serializes with the Chronicle
pulse collector, finalizes the completed fantasy week into Chronicle,
materializes derived history, commits any change, and captures that exact
Chronicle SHA. Full newspaper packets and Ironbound/Unbound Story Desk artifacts
are then built against that pinned revision. The editorial build does not mutate
Chronicle underneath itself.

After successful Tuesday delivery, the exact packet plus
`chronicle-baseline.json` is saved as the Wednesday comparison baseline. At
5:17 a.m. Eastern Wednesday, the workflow first records a lightweight Chronicle
pulse, then compares the fresh dossier with Tuesday and queries Event Ledger
entries observed after Tuesday's baseline time. The Wednesday email contains
only new evidence. If nothing new is found, no second email is sent. If the
Tuesday baseline cannot be restored, Wednesday still keeps Chronicle current
but refuses to send a duplicate full packet.

The slight offset from the top of the hour reduces the chance of a GitHub
Actions scheduling delay. Both schedules use the `America/New_York` timezone,
so they remain 9:17 p.m. and 5:17 a.m. across daylight-saving changes.

## Manual GitHub run

Open **Actions -> Editorial desk weekly delivery -> Run workflow**. Validation is
the default. Select **collect**, enter the week, and enable **send_email** to
deliver one email containing the seven publication Markdown dossiers. The
data-only league remains excluded from the email. Manual collection reads the
current Chronicle revision but does not perform the scheduled Tuesday
finalization transaction.

## Email secrets

In the GitHub repository, open **Settings -> Secrets and variables -> Actions**
and add these repository secrets:

- `IRONBOUND_GMAIL_ADDRESS`: the Gmail address that sends and receives the packet;
- `IRONBOUND_GMAIL_APP_PASSWORD`: the Google app password, not the normal account
  password. Spaces in Google's displayed app password are accepted.

For the current setup, `IRONBOUND_GMAIL_ADDRESS` should be
`the.ironbound.ffl@gmail.com`. Never place the app password in a configuration
file, commit, issue, or chat message.
