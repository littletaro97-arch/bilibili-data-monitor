# v0.11.2 Android test report

## Automated

- `clean test lintDebug assembleDebug assembleDebugAndroidTest`: passed through the ASCII junction.
- JVM unit tests: 74 passed, 0 failed, 0 errors, 0 skipped.
- Lint, debug APK and androidTest APK compilation: passed.
- Runtime interval/mode/countdown policy tests: added.
- Foreground-service notification content tests: added.
- DataStore persistence and unique WorkManager instrumentation tests: compiled; runtime pending an AVD/device.
- History stable-key/default-collapse tests: added.

## Environment limitation

- Direct JUnit execution from the Chinese path failed with ClassNotFoundException for every suite; the established ASCII junction is required. This is an environment path issue, not counted as a product test failure.
- No AVD or connected device is available. Compose/instrumentation runtime and real notification behavior are not marked passed.
- No screenshots, screen recording, visual clicking, or physical-device exploration were used.
