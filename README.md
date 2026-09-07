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

Each enabled league receives:

- a raw, timestamped weekly snapshot;
- a machine-readable weekly dossier;
- a human-readable Markdown dossier; and
- a shared MVP result that a separate card workflow can consume later.

The first metric layer covers matchup results, supporting all-play context,
league-median results where enabled, lineup efficiency, points left on the
bench, Manager of the Week, Bench MVP, Bad Beat, Escape Artist, result-flipping
start/sit decisions, waiver-impact candidates, weekly records, and named
division performance.

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

The Ironbound Sixteen entry remains disabled until its current Sleeper league
ID is confirmed. The seven other league IDs are carried forward from the
existing companion transaction reporter. No credential is required to read
public Sleeper league data.

## GitHub dry run

Open **Actions -> Editorial desk dry run -> Run workflow**. Validation is the
default. Live collection must be selected explicitly and still only creates a
downloadable research artifact.
