# v0.11.0 Windows Changelog

- Moves the Python/FastAPI application into the isolated `windows/` project.
- Moves runtime configuration, SQLite, logs, reports and exports under ignored `windows/runtime-data/` with copy-only legacy migration.
- Adds Windows import/export of history exchange format v1 with preview, SHA-256 validation, transactional merge, duplicate detection and conflict reporting.
- Updates SQLite to PRAGMA user_version 1 and records future snapshot sources as MANUAL/AUTO/UNKNOWN.
- Preserves existing CSV export and per-video CSV history import.
