# v0.11.0 Windows Test Report

- Full pytest: 54 passed, 0 failed.
- FastAPI startup: `/settings` returned HTTP 200 and displayed history ZIP controls.
- Legacy runtime migration: root data copied without deletion; old/new counts both remain videos=3, snapshots=2147, comments=5, danmaku=7.
- SQLite migration: new database uses PRAGMA user_version 1 with `collection_source` and `exchange_digest`.
- Cross-platform: Android export was parsed and transactionally merged; immediate repeated import added zero records.
- Security tests cover checksum corruption, unsupported future version, Zip Slip, size/version validation, duplicate import and conflict-without-overwrite.
- No Windows executable was built; the supported artifact is source plus `windows/run.bat` and `windows/requirements.txt`.
