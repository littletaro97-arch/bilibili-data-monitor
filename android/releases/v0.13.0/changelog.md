# v0.13.0 Android Changelog

## Added

- Creates and persists a non-secret installation UUID used as the origin identity for future LAN data merging.
- Each newly collected Android snapshot now records an origin device ID and a unique origin snapshot ID.
- Room v6 adds origin fields and an origin lookup index; existing local snapshots are safely backfilled once after startup.

## Changed

- The shared history ZIP can carry optional origin fields while remaining compatible with existing v1 readers and its original content digest.
- Android versionName/versionCode updated to v0.13.0 / 24.

## Known Issues

- Full SAF save-directory behavior still depends on user interaction in Android's system picker.
- Nested scroll edge handoff for wheels still requires real device validation.
- Real notification behavior still requires Android 13+ permission and device/emulator validation.
- Device and emulator UI validation may be unavailable when no adb device or emulator is connected.
- Direct Android unit tests under the formal Chinese path may still fail because of JDK/Gradle worker argfile classpath handling.
- HTTPS pairing and automatic LAN transport are deliberately not implemented in this build; the existing HTTP LAN page must not receive long-lived sync credentials.
- Auto refresh depends on Android WorkManager scheduling; values below 15 minutes are not guaranteed as background periodic work.
- Network requests remain low frequency and cover only already-added videos; no login, Cookie, captcha, proxy, or risk-control bypass is implemented.
