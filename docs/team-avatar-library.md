# Sleeper Team Avatar Library

This is an independent research-desk feature, not part of weekly scoring, ranking, Chronicle, or reporting.

## Collect
Run:
    python -m editorial_desk collect-team-avatars --config config/leagues.example.json --league-key ironbound_sixteen --asset-root output/team-avatars

It uses public Sleeper league/users/rosters endpoints and retrieves full-size images from the official CDN, requiring league-user metadata.avatar (a Sleeper team upload URL or legacy avatar identifier), with no fallback to user.avatar or individual account profiles. It preserves original image bytes, writes a presentation-ready PNG at its original dimensions, and records dimensions, checksum, source and failure diagnostics. It never upscales or fabricates a missing icon. Missing team metadata is reported as missing_team_upload instead of silently substituting the manager profile photo.

The stable mapping is league key + season + roster ID, never mutable team name.

Files live under output/team-avatars/<league-key>/<season>/ with manifest.json and roster-N.png.

## Attach to a magazine
Run:
    python -m editorial_desk attach-team-avatars --config config/leagues.example.json --league-key ironbound_sixteen --season 2026 --asset-root output/team-avatars --issue-dir output/primary/ironbound_sixteen

This copies each PNG into the publication-assets/team-avatars issue folder, emits team_avatars.json, and adds media_assets.team_avatars to an existing publication_packet.json. Every entry has a roster ID and image path for the designer. Matchup stats and other content are untouched.

## GitHub Actions
Run the separate "RUN THIS - Collect Sleeper Team Avatars" workflow. Choose a configured league, then download the resulting team-avatar-archive artifact. Keep a permanent copy of the downloaded folder because GitHub's workflow artifacts have finite retention.

The collection and attachment operations are intentionally independent. Nothing automatically writes binary image files to the application repository or replaces commissioner-selected logos.
