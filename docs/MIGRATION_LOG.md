# Migration log

## v0.11.0

| Old path | New canonical path | Compatibility |
| --- | --- | --- |
| `app/` | `windows/app/` | Python package remains named `app` when launched from `windows/`. |
| `app/tests/` | `windows/tests/` | Run `python -m pytest` from `windows/`. |
| `requirements.txt` | `windows/requirements.txt` | Root no longer owns Python dependencies. |
| `config.example.toml` | `windows/config.example.toml` | Runtime config is ignored under `windows/runtime-data/`. |
| `run.bat` | `windows/run.bat` | Root `run.bat` is a forwarding compatibility shim. |
| `scripts/android-build-ascii.ps1` | `android/scripts/build-ascii.ps1` | Junction continues to point at the repository root. |
| root `config.toml`, `data/`, `logs/`, `reports/` | `windows/runtime-data/` | Copy only when the destination is absent; never overwrite or delete legacy data. |

Windows SQLite moves from PRAGMA user_version 0 to 1 and adds `collection_source` plus `exchange_digest`. Existing source labels are ambiguous and migrate to `UNKNOWN`. Android Room moves from v2 to v3 and adds nullable `exchangeDigest` without deleting snapshots.

## v0.11.1

No database schema migration. New Android timestamps are stored as canonical UTC `Z` strings. Existing UTC and offset-bearing timestamps remain unchanged and are parsed as absolute instants for history/trend sorting and import deduplication. Legacy timestamps without an offset remain preserved; Windows interprets them using the current system zone because their original zone cannot be recovered with certainty.

## v0.12.0

Android Room moves from v3 to v4 without destructive migration. `videos` gains nullable `coverUrl`; `video_snapshots` gains non-null `collectedAtEpochMillis` (default `0`) and an index on `(bvId, collectedAtEpochMillis, id)`. Migration backfills parseable RFC3339 timestamps with SQLite `strftime`; application writes use `DeviceTime` absolute epoch values. Existing unparsable legacy timestamps remain stored and use the existing absolute-time parser/fallback for presentation ordering. History exchange stays at formatVersion 1; `coverUrl` is optional so old packages remain importable.
