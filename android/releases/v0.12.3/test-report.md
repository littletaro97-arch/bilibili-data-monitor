# v0.12.3 Android test report

## Automated

- Debug JVM tests: 87 passed, 0 failed, 0 errors.
- `compileDebugKotlin` and `assembleDebugAndroidTest`: passed.
- `test lintDebug assembleDebug assembleRelease assembleDebugAndroidTest` generated all requested APK outputs; the outer command exceeded the 64-second host limit, then test XML, lint report and outputs were verified.
- Lint: 0 errors, 9 warnings.
- Added instrumentation coverage for v4→v5 migration and the recycle / restore / permanent-delete DAO lifecycle.
- Packaging script for `v0.12.3`: completed through the ASCII junction. Debug APK size: 10,723,168 bytes; SHA-256: `9CFC01F844EEA92A51D238C60E31C0A8EE5678BE78D4482D29C8179DE27C96A1`.

## Device status

- ADB initially detected OPPO PKT110 on Android 16, but the device disconnected before installation and remained absent after restarting the ADB server. No v0.12.3 installation, migration runtime, UI flow or instrumentation test has been executed yet.
