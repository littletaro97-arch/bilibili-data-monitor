# v0.7.0 Test Report

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
- Build path: %TEMP%\bilibili-monitor-ascii\android
- Used ASCII junction: yes

## APK

- File: releases/android/v0.7.0/bilibili-monitor-android-v0.7.0-debug.apk
- Size: 10605035 bytes
- SHA256: 75C807AB1729D3C756FD3C425262982807376CB573F75FF6D915D3B9B0ABBB23
- Copied to release directory: yes

## Real Device Test

- Device: XCU47H455LJJUODQ, model PKT110
- Command: adb install -r releases/android/v0.7.0/bilibili-monitor-android-v0.7.0-debug.apk
- Result: passed
- Launch: `adb shell monkey -p com.littletaro.bilibilimonitor 1`
- Result: passed
- Screenshot: reports/android-v0.7.0-launch.png
- Observed: final APK launched, top content was not hidden by the display cutout, and no-selection navigation showed only Home, Settings, Advanced.
- Earlier interaction check: after opening a video, Detail and History appeared and Detail was the only selected top navigation item.
- Not fully automated: SAF save dialog and default directory authorization require user interaction with Android system UI.
