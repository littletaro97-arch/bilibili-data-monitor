# v0.12.2 Android test report

## Automated

- Debug JVM unit tests: 87 passed, 0 failed, 0 errors, 0 skipped.
- `TrendSamplingTest` pressure sampling: 100 raw to 100 displayed in 1.3151 ms; 500 raw to 180 displayed in 2.6015 ms; 5,000 raw to 180 displayed in 15.3707 ms. These are JVM sampling timings, not device rendering or frame-rate measurements.
- Added coverage for per-video chart preference codec fallback, dual-axis bounds, 5,000-record ratio shared sampling, zero/missing denominators, peak/endpoints, and existing cover URL policy.
- `lintDebug`: 0 errors and 24 pre-existing warnings; no warning is introduced by this version.
- Debug APK, unsigned Release APK and androidTest APK compilation: passed. The final clean build and package result are appended before tagging.

## Not executed

- No adb device, emulator executable or AVD is available. Compose UI runtime, rotation, dark mode, font scale, touch tooltip, Room migration runtime, image/cache runtime and emulator verification were not run.
- No physical-device testing was performed.
