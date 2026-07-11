# Bilibili History Exchange v1

ZIP entries are exactly `manifest.json`, `videos.json`, `snapshots.json`, and `checksums.json`.

- `formatName`: `bilibili-history-exchange`
- `formatVersion`: `1`
- Times: UTC RFC 3339 strings ending in `Z`.
- Video identity: normalized BV id.
- Snapshot identity: `bvId + collectedAt + collectionSource`.
- Snapshot duplicate: identity and `contentSha256` both match.
- Snapshot conflict: identity matches but digest differs; keep the local row and report the conflict.
- Sources: `MANUAL`, `AUTO`, `UNKNOWN`; old ambiguous rows become `UNKNOWN`.
- SHA-256 detects corruption or ordinary modification. It is not authenticity proof.

Import limits: 100 MB ZIP, 8 entries, 200 MB total uncompressed, 100 MB per JSON file, and compression ratio no greater than 100:1. Importers reject unknown entries, duplicate names, absolute paths, `..`, backslashes, symlinks, invalid JSON, checksum mismatches, and unsupported versions before opening a database transaction.

Version 1 exchanges only videos and statistic snapshots. Comments, danmaku, credentials, raw databases, absolute paths, device identifiers, logs, permissions, and authentication data are excluded.
