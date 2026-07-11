# v0.8.0 Android Changelog

## Added

- Adds a wheel-style auto refresh interval picker for fixed allowed intervals.
- Adds collapsible long text, diagnostics, and log details.
- Adds advanced-page state and expandable-text policy unit coverage.
- Generates versioned Debug APK under releases/android/v0.8.0/.
- Generates build info and test report with APK size and SHA256.

## Changed

- Android versionName/versionCode updated for v0.8.0.
- Fixes Advanced page crash by removing nested vertical LazyColumn composition.
- Converts Home, Detail, History, Settings, and Advanced pages to bounded primary scroll containers.
- Moves auto refresh configuration out of Home and keeps it in Settings.
- Short interval selections are saved, while WorkManager background scheduling respects Android's minimum periodic interval.

## Known Issues

- Full SAF save-directory behavior still depends on user interaction in Android's system picker.
- Device and emulator UI validation may be unavailable when no adb device or emulator is connected.
- Direct Android unit tests under the formal Chinese path may still fail because of JDK/Gradle worker argfile classpath handling.
- Auto refresh depends on Android WorkManager scheduling; values below 15 minutes are not guaranteed as background periodic work.
- Network requests remain low frequency and cover only already-added videos; no login, Cookie, captcha, proxy, or risk-control bypass is implemented.
