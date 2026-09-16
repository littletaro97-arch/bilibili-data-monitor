# v0.5.0 Android Changelog

## Added

- Added opt-in low-frequency auto refresh with WorkManager.
- Added DataStore-backed auto refresh settings; default remains disabled.
- Added local trend calculation and chart/table display for views, likes, replies, coins, and favorites.
- Added Android Sharesheet export sharing through FileProvider.
- Generates versioned Debug APK under releases/v0.5.0/.
- Generates build info and test report with APK size and SHA256.

## Changed

- Android versionName/versionCode updated for v0.5.0.
- Export results now show file name, absolute path, size, and export time.
- Logs distinguish manual refresh, auto refresh registration/cancel, worker execution, and failures.

## Known Issues

- Codex did not perform real-device installation testing for v0.5.0.
- Direct Android unit tests under the formal Chinese path may still fail because of JDK/Gradle worker argfile classpath handling.
- Auto refresh depends on Android WorkManager scheduling and can be delayed or merged by the system.
- Network requests remain low frequency and cover only already-added videos; no login, Cookie, captcha, proxy, or risk-control bypass is implemented.
