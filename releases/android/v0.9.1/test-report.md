# v0.9.1 Test Report

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
- Build path: %TEMP%\bilibili-monitor-ascii\android
- Used ASCII junction: yes

## APK

- File: releases/android/v0.9.1/bilibili-monitor-android-v0.9.1-debug.apk
- Size: 10558762 bytes
- SHA256: E0B97391988ED3E6069FDA503170C9135FBA4D1B8902E3BF19EA3781ADDDAF27
- Copied to release directory: yes

## Real Device Test

- Command: %LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe devices -l
- Result: no devices attached. Codex did not perform real-device installation testing.

## Emulator Test

- Command: %LOCALAPPDATA%\Android\Sdk\emulator\emulator.exe -list-avds
- Result: no AVDs returned. Codex did not perform emulator UI testing.
