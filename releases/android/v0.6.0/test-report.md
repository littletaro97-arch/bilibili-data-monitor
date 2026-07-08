# v0.6.0 Test Report

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

## Feature Checks

- Auto refresh diagnostics area: implemented in settings page.
- One-shot auto refresh test button: implemented, manual trigger only.
- Refresh all existing videos button: implemented, manual trigger only.
- Log filters: implemented for all/info/warning/error/manual/auto/export.

## APK

- File: releases/android/v0.6.0/bilibili-monitor-android-v0.6.0-debug.apk
- Size: 10443803 bytes
- SHA256: C2F181B3702694BC8767FF59C30072F358B6F9C0DD726CDACDECDF803D19BCCB
- Copied to release directory: yes

## Real Device Test

- Codex did not perform real-device installation testing. Waiting for user validation.
