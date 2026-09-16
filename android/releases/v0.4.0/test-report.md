# v0.4.0 Test Report

## Windows

- Command: `python -m pytest`
- Result: passed
- Summary: `47 passed`

## Android Unit Tests

- Command: `.\gradlew.bat test`
- Path used: `%TEMP%\bilibili-monitor-ascii\android`
- Used ASCII junction: yes
- Result: passed

## Android Build

- Command: `.\gradlew.bat assembleDebug`
- Path used: `%TEMP%\bilibili-monitor-ascii\android`
- Used ASCII junction: yes
- Result: passed

## Build Script

- Command: `powershell -ExecutionPolicy Bypass -File .\scripts\build-ascii.ps1`
- Result: passed
- APK copied to release directory: yes

## APK

- File: `releases/v0.4.0/bilibili-monitor-android-v0.4.0-debug.apk`
- Size: `9663158 bytes`
- SHA256: `B12B87C210CC454486F804189E0936C69008024333E88D9A964671E64194D28E`

## Real Device Test

- Codex 未进行实机测试，等待用户安装验证。
- v0.3.0 的用户手动安装反馈已记录到 `根目录实机测试记录.md`。
