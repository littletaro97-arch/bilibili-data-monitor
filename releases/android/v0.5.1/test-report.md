# v0.5.1 Test Report

## Windows

- Command: python -m pytest
- Result: passed
- Summary: 47 passed

## Android

- Command: .\gradlew.bat test
- Result: passed
- Command: .\gradlew.bat assembleDebug
- Result: passed
- Command: powershell -ExecutionPolicy Bypass -File .\scripts\android-build-ascii.ps1
- Result: passed
- Build path: C:\Users\LittleTaro\codex-bilibili-monitor-ascii\android
- Used ASCII junction: yes

## User Feedback Regression Checks

- Settings page invisible in v0.5.0: fixed by scrollable top navigation and a home-screen auto refresh settings button.
- Auto refresh not observable in v0.5.0: improved by showing registered/waiting/running/finished/failed diagnostics in settings and DataStore.
- Real-device execution timing still depends on Android WorkManager scheduling and vendor background policy.

## APK

- File: releases/android/v0.5.1/bilibili-monitor-android-v0.5.1-debug.apk
- Size: 10443807 bytes
- SHA256: 69622A89C22863D2359A6294898963A0655AC955194610B35DA3DCE91CE89244
- Copied to release directory: yes

## Real Device Test

- Codex did not perform real-device installation testing. Waiting for user validation.
