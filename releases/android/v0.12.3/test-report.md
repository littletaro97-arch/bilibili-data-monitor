# v0.12.3 Android test report

## Automated

- Debug JVM tests: 87 passed, 0 failed, 0 errors.
- `compileDebugKotlin` and `assembleDebugAndroidTest`: passed.
- `test lintDebug assembleDebug assembleRelease assembleDebugAndroidTest` generated all requested APK outputs; the outer command exceeded the 64-second host limit, then test XML, lint report and outputs were verified.
- Lint: 0 errors, 9 warnings.
- Added instrumentation coverage for v4→v5 migration and the recycle / restore / permanent-delete DAO lifecycle.

## Device status

- ADB initially detected OPPO PKT110 on Android 16, but the device disconnected before installation. No v0.12.3 installation, migration runtime, UI flow or instrumentation test has been executed yet.
