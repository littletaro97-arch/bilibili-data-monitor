# v0.9.0 Test Report

## Windows

- Command: python -m pytest
- Result: passed, 47 passed

## Android

- Command: .\gradlew.bat test
- Result: passed
- Command: .\gradlew.bat lintDebug
- Result: passed
- Command: .\gradlew.bat assembleDebug
- Result: passed
- Notification policy tests: covered by Gradle unit tests.
- Notification interval tests: covered by Gradle unit tests.
- Build path: C:\Users\LittleTaro\codex-bilibili-monitor-ascii\android
- Used ASCII junction: yes

## APK

- File: releases/android/v0.9.0/bilibili-monitor-android-v0.9.0-debug.apk
- Size: 10542382 bytes
- SHA256: 45B6C07697A12A8B2893D0B65C5DAAEE799A603C5B016A13F64D1C2D7D86FABC
- Copied to release directory: yes

## Real Device Test

- Command: C:\Users\LittleTaro\AppData\Local\Android\Sdk\platform-tools\adb.exe devices -l
- Result: no devices attached. Codex did not perform real-device installation testing.

## Emulator Test

- Command: C:\Users\LittleTaro\AppData\Local\Android\Sdk\emulator\emulator.exe -list-avds
- Result: no AVDs returned. Codex did not perform emulator UI testing.
