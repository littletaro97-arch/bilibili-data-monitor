# Android 端

本目录是 Android 原生应用工程，和根目录 `app/` 的 Windows/Python 端隔离维护。

- 根目录 `app/`：Windows/Python 后端、页面、采集与测试。
- `android/app/`：Android 原生应用模块。
- `shared/`：仅放双端共享 schema 和说明，不放 Android 私有代码。

## v0.3.0 MVP 范围

v0.3.0 提供 Android MVP 原型：

- 输入 BV 号或 Bilibili 视频链接。
- 解析 BV 号。
- 手动刷新基础视频数据。
- 展示视频基础信息和最新快照。
- 使用 Room 保存视频、快照和本地日志。
- 展示历史快照列表。
- 支持 JSON/CSV 导出。
- 显示基础错误信息。
- 生成 Debug APK。

本版本不包含 WorkManager、前台服务、高频后台采集、登录、验证码处理、Cookie、代理池或任何风控绕过逻辑。

## 构建

本工程使用 Gradle Wrapper：

```powershell
cd android
.\gradlew.bat test
.\gradlew.bat assembleDebug
```

正式打包优先使用根目录脚本：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\android-build-ascii.ps1
```

该脚本会通过 `C:\Users\LittleTaro\codex-bilibili-monitor-ascii\android` 执行测试和构建，并把 Debug APK 复制到对应版本的 `releases/android/` 目录。

如果项目位于包含中文字符的 Windows 路径，JDK/Gradle 的测试 worker `@argfile` 可能无法正确加载 unit-test classpath，表现为 `ClassNotFoundException`。本机验证时使用临时 ASCII junction 指向同一仓库后执行 Android 测试和打包。

APK 输出位置：

```text
releases/android/v0.3.0/bilibili-monitor-android-v0.3.0-debug.apk
```

v0.4.0 输出位置：

```text
releases/android/v0.4.0/bilibili-monitor-android-v0.4.0-debug.apk
```
