# v0.13.1 Test Report

## Windows

- Command: python -m pytest
- Result: run separately before release; record final result in the delivery report.

## Android

- Command: .\gradlew.bat test
- Result: passed
- Command: .\gradlew.bat lintDebug
- Result: passed
- Command: .\gradlew.bat assembleDebug
- Result: passed
- Notification policy tests: covered by Gradle unit tests.
- Notification interval tests: covered by Gradle unit tests.
- Build path: C:\jtmp\bilibili-monitor-ascii\android
- Used ASCII junction: yes

## APK

- File: android/releases/v0.13.1/bilibili-monitor-android-v0.13.1-debug.apk
- Size: 10739552 bytes
- SHA256: 9DA9666480BEC87F81081E9A6A991BAF7F5F20702EA330E4A7BF54AF3ACE54F5
- Copied to release directory: yes

## Real Device Test

- Device: PKT110, Android 17, connected through ADB.
- Existing v0.13.0 installation was upgraded in place with `adb install -r`; application data was retained.
- Result: v0.13.1 (versionCode 25) installed successfully, `MainActivity` became top-resumed, and the application process remained alive after launch.
- Logcat: no new `FATAL EXCEPTION` or Room migration validation failure after the v0.13.1 launch.
