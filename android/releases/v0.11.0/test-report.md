# v0.11.0 Android Test Report

## Automated

- `clean test lintDebug assembleDebug`: passed.
- JVM unit tests: 64 passed, 0 failed.
- Connected instrumentation: 2 passed, 0 failed (Compose launch/navigation and Room v2-to-v3 migration).
- Lint: passed.
- APK build: passed.

## OPPO PKT110 / Android 16

- Bilibili installed: standard HTTPS URI opened `tv.danmaku.bili` successfully.
- Bilibili disabled: unrestricted fallback reached Microsoft Edge through the OPPO confirmation dialog; Bilibili was re-enabled immediately.
- Foreground continuous monitoring: `dataSync` service and persistent notification were observed with `dumpsys`; WorkManager cancellation was implemented with awaited completion.
- Screen-off run: display reached `DOZE_SUSPEND`; after more than one 1-minute interval the service remained foreground and logged `continuous monitoring cycle finished`, total=4, success=4, failed=0.
- Windows ZIP to Android SAF import: previewed 3 videos/2147 snapshots and imported +3/+2147 with 0 conflicts.
- Android SAF export to Windows: exported 4 videos/2217 snapshots; Windows imported 4 videos/2216 snapshots with 1 in-package duplicate, and a second import added zero records.
- User app data was backed up before instrumentation. Connected tests uninstalled the test package as a side effect; the v0.10.0 data backup was restored, then Room migrated it to v3. Final verified data: 1 video, 55 snapshots.

## Not fully executed

- Phone reboot, long-duration Android 15/16 foreground-service timeout, multiple-day battery comparison, manufacturer auto-start UI, no-network/mobile-network matrix and real process reclaim.
- These remain in the real-device checklist; no permanent-background guarantee is claimed.
