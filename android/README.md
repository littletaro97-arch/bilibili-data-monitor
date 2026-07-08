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

v0.5.0 输出位置：

```text
releases/android/v0.5.0/bilibili-monitor-android-v0.5.0-debug.apk
```

v0.5.1 输出位置：

```text
releases/android/v0.5.1/bilibili-monitor-android-v0.5.1-debug.apk
```

v0.6.0 输出位置：

```text
releases/android/v0.6.0/bilibili-monitor-android-v0.6.0-debug.apk
```

## v0.5.0 范围

v0.5.0 增加低频后台刷新和趋势展示，但仍不扩大采集边界：

- 自动刷新默认关闭，必须在设置页手动开启。
- 使用 WorkManager，间隔限制为 15 分钟、30 分钟、1 小时、3 小时、6 小时。
- WorkManager 由 Android 系统调度，可能被省电策略延迟或合并，不保证准点执行。
- 自动刷新只刷新 Room 中已经添加的视频，不发现新视频，不采集评论/弹幕。
- 不实现登录、Cookie、验证码处理、代理池、风控绕过或高频保活。
- 设置项使用 DataStore；Room schema 未变化，数据库版本仍为 1。
- 历史页使用本地快照绘制简单 Compose Canvas 趋势图，支持最近 20/50 条。
- 导出页显示文件名、路径、大小、时间，并通过 FileProvider 调用 Android Sharesheet 分享文件。

## v0.5.1 热修复范围

v0.5.1 只修复自动刷新设置可达性和状态可观测性，不扩大采集范围：

- 顶部导航使用可横向滚动列表，避免“设置”按钮在窄屏被裁掉。
- 首页新增“自动刷新设置”入口。
- 设置页显示 WorkManager 是否已注册，以及最近注册、取消、开始、结束、结果、错误。
- DataStore 记录自动刷新诊断状态，便于实机判断是否注册、是否等待系统调度、是否执行失败。
- 不引入高频后台任务，不做隐藏保活，不采集评论/弹幕，不处理登录、Cookie、验证码或风控。

## v0.6.0 诊断增强范围

v0.6.0 只增强自动刷新可观测性和手动 debug 工具：

- 设置页诊断区显示 unique work name、约束、最近状态和累计成功/失败次数。
- “测试自动刷新一次”按钮手动执行一次自动刷新同范围逻辑。
- “刷新所有已添加视频”按钮手动批量刷新本地已有视频。
- 日志页提供基础筛选。
- 不新增循环任务，不降低 WorkManager 周期，不做隐藏保活。
