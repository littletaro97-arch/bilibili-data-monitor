# v0.13.1 Android Changelog

## Added

- Fixes parsing for mobile Bilibili share text, standard mobile links, wrapped text, and short-link redirects.
- Adds compact expand/edit wheel rows to reduce accidental setting changes while scrolling Settings.
- Stores new collection, log, export, and worker times with device local offset time.
- Adds parser, short-link resolver, wheel editor, device-time, and notification-time unit coverage.
- Generates versioned Debug APK under android/releases/v0.13.1/.
- Generates build info and test report with APK size and SHA256.

## Changed

- Android versionName/versionCode updated for v0.13.1.
- Aligns the Room entity declaration with the existing 5-to-6 database migration: origin identity columns now declare their empty-string defaults and composite index, preventing the startup crash when an existing database is upgraded.
- Short-link resolution is performed off the UI path through the existing OkHttp layer.
- Settings time wheels are collapsed by default and expose an explicit completion action.
- User-visible snapshot and worker times are formatted in the current device time zone.

## Known Issues

- Full SAF save-directory behavior still depends on user interaction in Android's system picker.
- Nested scroll edge handoff for wheels still requires real device validation.
- Real notification behavior still requires Android 13+ permission and device/emulator validation.
- Device and emulator UI validation may be unavailable when no adb device or emulator is connected.
- Direct Android unit tests under the formal Chinese path may still fail because of JDK/Gradle worker argfile classpath handling.
- Auto refresh depends on Android WorkManager scheduling; values below 15 minutes are not guaranteed as background periodic work.
- Network requests remain low frequency and cover only already-added videos; no login, Cookie, captcha, proxy, or risk-control bypass is implemented.
