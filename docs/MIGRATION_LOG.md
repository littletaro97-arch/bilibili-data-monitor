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
