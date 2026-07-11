# v0.11.0 Android Changelog

- Repairs external video opening by attempting the Bilibili package and then a fresh unrestricted HTTPS intent.
- Adds an explicit, default-off data-sync foreground service for 1/3/5/10-minute continuous monitoring, with persistent notification and stop action.
- Adds real WorkManager/foreground-service diagnostics and a visible `高级 · 后台受限` warning.
- Adds Room v2-to-v3 migration and cross-platform history ZIP import/export through SAF.
- Implements history format v1 validation, checksums, duplicate detection, conflict reporting and transactional import.

Known limits: Android and OPPO policies may delay or stop background work; data-sync foreground services have system time limits; comments and danmaku are not part of exchange format v1.
