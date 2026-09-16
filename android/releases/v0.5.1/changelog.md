# v0.5.1 Android Changelog

## Added

- Exposes the auto refresh settings entry on the home screen and scrollable top navigation.
- Adds visible WorkManager registration and worker execution status fields.
- Records registration, cancellation, start, finish, result, and error diagnostics in DataStore.
- Generates versioned Debug APK under releases/v0.5.1/.
- Generates build info and test report with APK size and SHA256.

## Changed

- Android versionName/versionCode updated for v0.5.1.
- Auto refresh settings are now reachable on narrow phone screens.
- Logs and settings status distinguish not registered, registered, waiting for system scheduling, running, finished, and failed states.

## Known Issues

- Codex did not perform real-device installation testing for v0.5.1.
- Direct Android unit tests under the formal Chinese path may still fail because of JDK/Gradle worker argfile classpath handling.
- Auto refresh depends on Android WorkManager scheduling and can be delayed or merged by the system.
- Network requests remain low frequency and cover only already-added videos; no login, Cookie, captcha, proxy, or risk-control bypass is implemented.
