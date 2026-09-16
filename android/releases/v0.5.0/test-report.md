# v0.5.0 Test Report

## Windows

- Command: python -m pytest
- Result: passed
- Summary: 47 passed

## Android

- Command: .\gradlew.bat test
- Result: passed
- Command: .\gradlew.bat assembleDebug
- Result: passed
- Command: powershell -ExecutionPolicy Bypass -File .\scripts\build-ascii.ps1
- Result: passed
- Build path: %TEMP%\bilibili-monitor-ascii\android
- Used ASCII junction: yes

## Build Notes

- Gradle printed no fatal build errors. assembleDebug completed successfully.

## APK

- File: releases/v0.5.0/bilibili-monitor-android-v0.5.0-debug.apk
- Size: 10433002 bytes
- SHA256: B98DCD7369D1AC69F4FE255A18926E5BD2AE85893ECF1A93F55C8AD83F6059E2
- Copied to release directory: yes

## Real Device Test

- Codex did not perform real-device installation testing. Waiting for user validation.
