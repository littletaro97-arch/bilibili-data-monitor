# v0.13.0 Test Report

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

- File: android/releases/v0.13.0/bilibili-monitor-android-v0.13.0-debug.apk
- Size: 10739556 bytes
- SHA256: 7B855956EA9475BB8D8B7B060515296271DF486610184E99688D3DB8B46C76E1
- Copied to release directory: yes

## Real Device Test

- Codex did not perform real-device installation testing. Waiting for user validation.
