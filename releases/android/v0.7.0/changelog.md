# v0.7.0 Android Changelog

## Added

- Adds a combined Advanced area for selected-video export tools and logs.
- Adds dynamic top navigation that hides detail/history until a video is selected.
- Adds Android system save flow for first export, with optional persisted default directory.
- Adds export naming and export location policy unit coverage.
- Generates versioned Debug APK under releases/android/v0.7.0/.
- Generates build info and test report with APK size and SHA256.

## Changed

- Android versionName/versionCode updated for v0.7.0.
- Applies safe drawing insets around the app shell for status bars and display cutouts.
- Reorganizes Settings into auto refresh, network constraints, export settings, storage, background, and diagnostics sections.
- Keeps share export available while changing direct export to Storage Access Framework.

## Known Issues

- Full SAF save-directory behavior still depends on user interaction in Android's system picker.
- Direct Android unit tests under the formal Chinese path may still fail because of JDK/Gradle worker argfile classpath handling.
- Auto refresh depends on Android WorkManager scheduling and can be delayed or merged by the system.
- Network requests remain low frequency and cover only already-added videos; no login, Cookie, captcha, proxy, or risk-control bypass is implemented.
