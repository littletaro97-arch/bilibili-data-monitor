# v0.12.1 Android test report

## Automated

- `clean test lintDebug assembleDebug assembleRelease assembleDebugAndroidTest --no-daemon --stacktrace`: passed through the temporary ASCII junction.
- Packaging script with the new portable default: `powershell -ExecutionPolicy Bypass -File .\android\scripts\build-ascii.ps1 -Version v0.12.1`: passed.
- Debug JVM unit tests: 82 passed, 0 failed, 0 errors, 0 skipped.
- Debug lint, Debug APK, unsigned Release APK and androidTest APK compilation: passed.
- Existing 5,000-record sampling, ratio, zero/absent denominator, snapshot delta, cover URL and exchange tests all remain part of the passing JVM suite.

## Scope confirmation

- This hotfix verifies that selected-video snapshot sorting is upstream of `flowOn(Dispatchers.Default)`; sampling itself remains in the existing `Dispatchers.Default` producer.
- Room remains v4 and history exchange remains formatVersion 1. No WorkManager, foreground service, notification, battery or screen-off scheduling file was changed.

## Not executed

- No `adb`, emulator executable or AVD is installed in this environment. Compose UI runtime, Room migration runtime, image/cache runtime and simulator tests were not run.
- No physical device was connected or tested. Follow `real-device-checklist.md` after installation.
