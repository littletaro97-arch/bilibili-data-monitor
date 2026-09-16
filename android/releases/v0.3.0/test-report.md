# v0.3.0 Test Report

## Windows

- Command: `python -m pytest`
- Result: passed
- Summary: `47 passed`

## Android Unit Tests

- Command: `.\gradlew.bat test`
- Path used: `%TEMP%\bilibili-monitor-ascii\android`
- Result: passed
- Note: the path is a temporary ASCII junction pointing to `<formal-project-root>`.

## Android Build

- Command: `.\gradlew.bat assembleDebug`
- Path used: `%TEMP%\bilibili-monitor-ascii\android`
- Result: passed
- APK generated: yes
- APK copied to release directory: yes

## APK

- File: `releases/v0.3.0/bilibili-monitor-android-v0.3.0-debug.apk`
- Size: 9658118 bytes
- SHA256: `CC5B49C0FE09D04F2675466A24C0DE25E61C7A40270161C430C96E32F92EAE8A`

## Real Device Test

- Status: 未进行实机测试
- Reason: 本轮只进行本机 Windows 测试、Android 单元测试和 Debug APK 构建，未连接 Android 设备安装验证。

## Known Test Environment Issue

Direct Android unit-test execution under the formal Chinese path can fail with `ClassNotFoundException` from the Gradle/JDK worker `@argfile` classpath. The validated workaround is to run the same Gradle Wrapper through an ASCII junction that points to the same repository.
