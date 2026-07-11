# v0.11.1 Android test report

## Automated

- `clean test lintDebug assembleDebug assembleDebugAndroidTest`: passed.
- JVM unit tests: 69 passed, 0 failed, 0 errors, 0 skipped.
- Lint: passed.
- Debug APK and androidTest APK compilation: passed.
- Import feedback/state tests: added.
- Navigation back-policy tests: added.
- Notification channel and clearability policy tests: added.
- Cross-time-zone and trend ordering tests: added.

## Not executed

- Compose instrumentation runtime: no AVD or connected device available.
- Real notification display, swipe-to-dismiss, clear-all and notification click.
- Predictive-back gesture on a physical device.
- Small-screen, large-font and dark-mode visual inspection.
- No screenshot recognition or visual automation was used.
