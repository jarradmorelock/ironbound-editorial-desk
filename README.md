# Ironbound Editorial Desk

An isolated, read-only Sleeper data pipeline for the Ironbound family of
weekly fantasy-football publications.

The project turns verified league data into editorial research dossiers. It
does not publish magazines, create MVP cards, post to Discord, or send email in
Phase 1.

## Safety boundaries

- Sleeper is accessed through its public read-only API.
- The existing transaction and Discord reporters are not imported or changed.
- The GitHub workflow is manual-only; there is no scheduled trigger.
- Generated dry-run output is ignored by Git and uploaded only as a temporary
  workflow artifact.
- Email credentials and publishing credentials are not used in Phase 1.

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
division performance. Every dossier also separates official standings from a
transparent data power ranking. The eventual publication archive will add the
prior issue's editorial ranking and week-to-week movement without treating the
formula as the final editorial opinion.

Ranking inputs are fetched once per run and then trimmed to the players in each
league. Sleeper supplies weekly projections scored against that league's own
settings. Dynasty Daddy supplies current-season starter ranks and dynasty
market values. If either optional source is unavailable, collection continues
and the dossier clearly marks the missing input.

- Dynasty leagues use the Ironbound/Unbound editorial model: starter strength
  and projected scoring lead, with dynasty value, playoff and title
  probabilities, roster balance, schedule context, and future-pick value kept
  as distinct evidence.
- Redraft leagues use only submitted-lineup projection, optimal starting-lineup
  projection, and win-loss record. Their automated consensus is the equal
  average of those three league-relative ranks.

The source primers and publications have been audited into
`config/publications.json`; see `docs/source-audit.md` for the resulting brand
and editorial map. Historical record books, multi-week strength-of-schedule
analysis, Giant Killer, and persistent editorial memory are the next data
layer.

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

## GitHub dry run

Open **Actions -> Editorial desk dry run -> Run workflow**. Validation is the
default. Live collection must be selected explicitly and still only creates a
downloadable research artifact.
