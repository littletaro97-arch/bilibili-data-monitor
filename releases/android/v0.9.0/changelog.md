# v0.9.0 Android Changelog

## Added

- Adds notification reminder settings, Android 13 notification permission flow, and notification channel delivery.
- Adds each-refresh and timed-summary notification modes with interval validation.
- Adds optional background-running guidance and system settings entry points.
- Adds redesigned reusable wheel picker for detection and notification intervals.
- Adds notification interval and notification policy unit coverage.
- Generates versioned Debug APK under releases/android/v0.9.0/.
- Generates build info and test report with APK size and SHA256.

## Changed

- Android versionName/versionCode updated for v0.9.0.
- Notification summary intervals are automatically kept no shorter than the effective WorkManager detection interval.
- Worker completion can emit a single merged notification for one detection batch.
- Wheel selections are saved only after a stable value is selected.

## Known Issues

- Full SAF save-directory behavior still depends on user interaction in Android's system picker.
- Real notification behavior still requires Android 13+ permission and device/emulator validation.
- Device and emulator UI validation may be unavailable when no adb device or emulator is connected.
- Direct Android unit tests under the formal Chinese path may still fail because of JDK/Gradle worker argfile classpath handling.
- Auto refresh depends on Android WorkManager scheduling; values below 15 minutes are not guaranteed as background periodic work.
- Network requests remain low frequency and cover only already-added videos; no login, Cookie, captcha, proxy, or risk-control bypass is implemented.
