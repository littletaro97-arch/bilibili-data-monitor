# v0.8.0 Test Report

## Windows

- Command: python -m pytest
- Result: passed, 47 passed

## Android

- Command: .\gradlew.bat clean test lintDebug assembleDebug
- Result: passed
- Command: .\gradlew.bat test
- Result: passed
- Command: .\gradlew.bat lintDebug
- Result: passed
- Command: .\gradlew.bat assembleDebug
- Result: passed
- Build path: %TEMP%\bilibili-monitor-ascii\android
- Used ASCII junction: yes

## APK

- File: releases/android/v0.8.0/bilibili-monitor-android-v0.8.0-debug.apk
- Size: 10509528 bytes
- SHA256: 40F52FB62ED9B64AA49126F81BFA97ABE7266B4ECBA1B49543BFE0ED1AA0AD3B
- Copied to release directory: yes

## Real Device Test

- Result: not run
- Reason: `adb devices -l` did not detect a connected device in this environment.
- Follow-up: run the v0.8.0 checklist in docs/实机测试记录.md.

## Emulator Test

- Result: not run
- Reason: no available Android emulator was detected or started in this environment.
