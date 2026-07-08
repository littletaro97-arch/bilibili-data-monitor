# v0.6.0 Android Changelog

## Added

- Adds an auto refresh diagnostics area with cumulative success and failure counts.
- Adds a one-shot auto refresh test button for real-device debugging.
- Adds a manual refresh-all-existing-videos button.
- Adds log filters for level, manual refresh, auto refresh, and export logs.
- Generates versioned Debug APK under releases/android/v0.6.0/.
- Generates build info and test report with APK size and SHA256.

## Changed

- Android versionName/versionCode updated for v0.6.0.
- Settings diagnostics now show unique work name, constraints, counters, and last result details.

## Known Issues

- Codex did not perform real-device installation testing for v0.6.0.
- Direct Android unit tests under the formal Chinese path may still fail because of JDK/Gradle worker argfile classpath handling.
- Auto refresh depends on Android WorkManager scheduling and can be delayed or merged by the system.
- Network requests remain low frequency and cover only already-added videos; no login, Cookie, captcha, proxy, or risk-control bypass is implemented.
