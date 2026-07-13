# v0.12.2 Android test report

## Automated

- Debug JVM unit tests: 87 passed, 0 failed, 0 errors, 0 skipped.
- `TrendSamplingTest` pressure sampling: 100 raw to 100 displayed in 1.3151 ms; 500 raw to 180 displayed in 2.6015 ms; 5,000 raw to 180 displayed in 15.3707 ms. These are JVM sampling timings, not device rendering or frame-rate measurements.
- Added coverage for per-video chart preference codec fallback, dual-axis bounds, 5,000-record ratio shared sampling, zero/missing denominators, peak/endpoints, and existing cover URL policy.
- `lintDebug`: 0 errors and 24 pre-existing warnings; no warning is introduced by this version.
- `clean test lintDebug assembleDebug assembleRelease assembleDebugAndroidTest --no-daemon --console=plain` was launched through the ASCII junction. The host wrapper timed out after 64 seconds, but the clean-run Debug APK, unsigned Release APK, androidTest APK, 87-test XML result and lint report were subsequently verified; no Gradle worker remained.
- Packaging command `powershell -ExecutionPolicy Bypass -File .\android\scripts\build-ascii.ps1 -Version v0.12.2`: passed. Its Gradle `test`, `lintDebug` and `assembleDebug` stages all reported `BUILD SUCCESSFUL`.
- Archive: `bilibili-monitor-android-v0.12.2-debug.apk`, 10,706,784 bytes, SHA-256 `3E6B0AD46CCF24C8979DA1BFBCE95AF2261CD274302CF605E25758C94069D703`.

## Not executed

- No adb device, emulator executable or AVD is available. Compose UI runtime, rotation, dark mode, font scale, touch tooltip, Room migration runtime, image/cache runtime and emulator verification were not run.
- No physical-device testing was performed.
